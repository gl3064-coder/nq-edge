"""rescale_corrected.py — the cross-asset port with the scaling anchor fixed.

TWO SPECIFICATION ERRORS ARE BEING CORRECTED (both found 2026-08-04):

1. A_NQ was hardcoded 17.0. NQ's measured median 20-second true range is 4.75
   all-hours and 11.75 in the 09:30-12:00 session the bot actually trades.
   17 matches neither, so "the same risk NQ takes, expressed in this market's
   units" was never actually preserved by the port.

2. Each instrument's ATR was measured over ALL HOURS while the strategy only
   trades the NY session. Two different windows inside one formula.

THE SELF-CONSISTENCY TEST. With A_NQ defined as NQ's own session ATR, running
the scaled port ON NQ must return the frozen spec exactly: stop 20, target 30,
min_dd 10. If it does not, the scaling is still wrong. The old A_NQ=17 failed
this badly, producing a 5.6 point stop.

PRE-COMMITTED. This is being run once, on terms agreed before seeing output:
the anchor is fixed because 17 is wrong, not because a corrected number is
hoped to help. Gold is the FIFTH look at the same six months, so a positive
gold result is discounted on arrival. CL and ZN are the point of the exercise,
since the breadth claim rests on them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

NQ_STOP, RR, NQ_MIN_DD, LEG_THR = 20.0, 1.5, 10.0, 30
NY = ("09:30", "12:00")
DATA = Path(__file__).resolve().parent.parent / "data"


def tr(b):
    p = b["close"].shift(1)
    return pd.concat([b["high"] - b["low"], (b["high"] - p).abs(),
                      (b["low"] - p).abs()], axis=1).max(axis=1)


def session_atr(bars):
    """Median 20s true range measured ON THE TRADED SESSION ONLY."""
    s = bars.between_time(*NY)
    return float(tr(s).median())


def exit_fixed(entry, high, low, close, start, stop, target):
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def run(bars, stop, thr):
    target, min_dd = RR * stop, NQ_MIN_DD / NQ_STOP * stop
    m = bars.between_time(*NY)
    rows = []
    for d, grp in m.groupby(m.index.date):
        if len(grp) < 60:
            continue
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        upc = out["up_context"].to_numpy().astype(bool)
        a = higher_low_signal(out["close"], out["up_context"], k=3)
        sig = drawdown_filter(out["close"], a, k=3, min_dd=min_dd)
        close = out["close"].to_numpy()
        g = grp.loc[out.index]
        high, low, bd = g["high"].to_numpy(), g["low"].to_numpy(), g["buy_delta"].to_numpy()
        n = len(close)
        runlen = np.zeros(n, dtype=int)
        for j in range(n):
            runlen[j] = runlen[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            if np.nanmean(bd[i - 2:i + 1]) < thr or runlen[i] > LEG_THR:
                continue
            rows.append(exit_fixed(float(close[i]), high, low, close,
                                   i + 1, stop, target) / stop)
    return rows


def report(label, rs, extra=""):
    if len(rs) < 2:
        print(f"  {label:26} n={len(rs):>4}  (too few) {extra}")
        return
    a = np.array(rs)
    t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
    print(f"  {label:26} n={len(a):>4}   {a.mean():+.3f}R   t={t:>5.2f}  {extra}")


def main():
    # ---- anchor: NQ's own session ATR ----
    p = {k: pd.read_pickle(DATA / f"bars_NQ_{k}.pkl")
         for k in ("03-26", "06-26", "09-26")}
    nq = pd.concat([
        p["03-26"][p["03-26"].index < "2026-03-12"],
        p["06-26"][(p["06-26"].index >= "2026-03-12") & (p["06-26"].index < "2026-06-08")],
        p["09-26"][p["09-26"].index >= "2026-06-08"],
    ]).sort_index()
    A_NQ = session_atr(nq)
    print(f"anchor: NQ session ATR = {A_NQ:.3f}   (was hardcoded 17.0)\n")

    def scaled_stop(bars):
        return NQ_STOP / A_NQ * session_atr(bars)

    def tercile(bars):
        return float(np.nanpercentile(
            bars.between_time(*NY)["buy_delta"].to_numpy(), 66.67))

    # ---- self-consistency: NQ must return the frozen spec ----
    print("SELF-CONSISTENCY CHECK (scaled NQ must equal frozen NQ)")
    print("=" * 60)
    s_nq = scaled_stop(nq)
    print(f"  scaled NQ stop = {s_nq:.2f}   (frozen is 20.00)")
    report("NQ frozen 20/30/10", run(nq, NQ_STOP, 0.10))
    report("NQ scaled (corrected)", run(nq, s_nq, 0.10))

    # ---- the ports ----
    print("\nCROSS-ASSET, corrected anchor + session-measured ATR")
    print("=" * 60)
    targets = []
    gcache = DATA / "bars_GC_nt_jan_jul.pkl"
    if gcache.exists():
        gc = pd.read_pickle(gcache)
        targets.append(("GOLD (5th look)", pd.concat(gc.values()).sort_index()))
    for name, fn in [("CRUDE CL", "bars_CL_c_0.pkl"), ("BONDS ZN", "bars_ZN_c_0.pkl")]:
        f = DATA / fn
        if f.exists():
            targets.append((name, pd.read_pickle(f)))

    for name, bars in targets:
        atr = session_atr(bars)
        stop = NQ_STOP / A_NQ * atr
        report(name, run(bars, stop, tercile(bars)),
               extra=f"| ATR {atr:.4f} stop {stop:.4f}")

    print("\nJuly numbers under the OLD anchor, for contrast:")
    print("  CRUDE CL                   n= 228   +0.165R   t= 2.00")
    print("  BONDS ZN                   n= 145   +0.409R   t= 4.00")
    print("\nGross of costs. Cost is what killed CL and ZN before.")


if __name__ == "__main__":
    main()
