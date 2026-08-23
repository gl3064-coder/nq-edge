"""atr_sensitivity.py — how load-bearing is the ATR convention?

The frozen NQ bot is FLAT: stop 20, target 30, min_dd 10. No ATR anywhere.
ATR scaling was invented purely to port the bot to other instruments, and then
"which ATR" (one pooled number vs one per contract) is a second free choice on
top. On gold those two choices gave +0.165R and +0.034R, a 5x swing.

THIS IS A SENSITIVITY TEST, NOT A SEARCH. Every convention is reported. None is
selected. If a result only survives under one arbitrary convention it was never
a result. Read the SPREAD across rows, not the best row.

Conventions:
  pooled      one ATR over the whole sample -> one stop everywhere
  per-contract  ATR recomputed per contract file
  per-day     ATR from the prior day's bars (the only causal one; the others
              peek at the whole sample to set today's stop)

NQ is included precisely because it is the instrument that matters. If NQ's
number is stable across conventions and gold's is not, that asymmetry is itself
the finding.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

A_NQ, NQ_STOP, RR, NQ_MIN_DD, LEG_THR = 17.0, 20.0, 1.5, 10.0, 30
NY = ("09:30", "12:00")
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "GC"
CACHE = Path(__file__).resolve().parent.parent / "data"

GC_WINDOWS = [
    ("GC 02-26.Last.txt", "2026-01-01", "2026-01-22"),
    ("GC 04-26.Last.txt", "2026-01-22", "2026-03-26"),
    ("GC 06-26.Last.txt", "2026-03-26", "2026-05-28"),
    ("GC 08-26.Last.txt", "2026-05-28", "2026-07-01"),
]


def tr(b):
    p = b["close"].shift(1)
    return pd.concat([b["high"] - b["low"], (b["high"] - p).abs(),
                      (b["low"] - p).abs()], axis=1).max(axis=1)


def exit_fixed(entry, high, low, close, start, stop, target):
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def trades_for(bars, stop_map, min_dd_map, thr):
    """stop_map/min_dd_map: date -> value, so per-day conventions work."""
    m = bars.between_time(*NY)
    rows = []
    for d, grp in m.groupby(m.index.date):
        if len(grp) < 60:
            continue
        stop = stop_map(d, grp)
        if stop is None or not np.isfinite(stop) or stop <= 0:
            continue
        target, min_dd = RR * stop, min_dd_map(stop)
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        upc = out["up_context"].to_numpy().astype(bool)
        a = higher_low_signal(out["close"], out["up_context"], k=3)
        sig = drawdown_filter(out["close"], a, k=3, min_dd=min_dd)
        close = out["close"].to_numpy()
        g = grp.loc[out.index]
        high, low, bd = g["high"].to_numpy(), g["low"].to_numpy(), g["buy_delta"].to_numpy()
        n = len(close)
        run = np.zeros(n, dtype=int)
        for j in range(n):
            run[j] = run[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            if np.nanmean(bd[i - 2:i + 1]) < thr or run[i] > LEG_THR:
                continue
            pl = exit_fixed(float(close[i]), high, low, close, i + 1, stop, target)
            rows.append(pl / stop)
    return rows


def report(label, rs):
    if len(rs) < 2:
        print(f"  {label:26} n={len(rs):>4}  (too few)")
        return
    a = np.array(rs)
    t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
    print(f"  {label:26} n={len(a):>4}   {a.mean():+.3f}R   t={t:>5.2f}")


def load_gc():
    cache = CACHE / "bars_GC_nt_jan_jul.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    out = {}
    for fn, lo, hi in GC_WINDOWS:
        b = load_bars(ROOT / fn)
        b = b[(b.index >= lo) & (b.index < hi)]
        out[fn] = b
        print(f"  loaded {fn}: {len(b):,} bars", flush=True)
    pd.to_pickle(out, cache)
    return out


def main():
    print("loading gold (cached after first run)...", flush=True)
    gc = load_gc()
    all_bars = pd.concat(gc.values()).sort_index()
    pooled_atr = float(tr(all_bars).median())
    thr_pooled = float(np.nanpercentile(
        all_bars.between_time(*NY)["buy_delta"].to_numpy(), 66.67))

    print(f"\nGOLD  pooled ATR={pooled_atr:.3f}  tape thr={thr_pooled:.4f}")
    print("=" * 56)

    # 1. pooled ATR
    s = NQ_STOP / A_NQ * pooled_atr
    rs = []
    for b in gc.values():
        rs += trades_for(b, lambda d, g, s=s: s,
                         lambda st: NQ_MIN_DD / NQ_STOP * st, thr_pooled)
    report("pooled ATR", rs)

    # 2. per-contract ATR
    rs = []
    for b in gc.values():
        s = NQ_STOP / A_NQ * float(tr(b).median())
        rs += trades_for(b, lambda d, g, s=s: s,
                         lambda st: NQ_MIN_DD / NQ_STOP * st, thr_pooled)
    report("per-contract ATR", rs)

    # 3. per-day ATR from the PRIOR day (causal)
    rs = []
    for b in gc.values():
        daily = tr(b).groupby(b.index.date).median()
        prev = {d: daily.iloc[i - 1] for i, d in enumerate(daily.index) if i > 0}
        rs += trades_for(
            b, lambda d, g, p=prev: (NQ_STOP / A_NQ * p[d]) if d in p else None,
            lambda st: NQ_MIN_DD / NQ_STOP * st, thr_pooled)
    report("per-day ATR (causal)", rs)

    # ---- NQ, the instrument that matters ----
    print("\nNQ  (frozen spec is FLAT stop 20 / target 30 / min_dd 10)")
    print("=" * 56)
    p = {k: pd.read_pickle(CACHE / f"bars_NQ_{k}.pkl")
         for k in ("03-26", "06-26", "09-26")}
    nq = {
        "03-26": p["03-26"][p["03-26"].index < "2026-03-12"],
        "06-26": p["06-26"][(p["06-26"].index >= "2026-03-12") &
                            (p["06-26"].index < "2026-06-08")],
        "09-26": p["09-26"][p["09-26"].index >= "2026-06-08"],
    }
    thr_nq = 0.10  # the frozen, pre-set gate

    rs = []
    for b in nq.values():
        rs += trades_for(b, lambda d, g: NQ_STOP, lambda st: NQ_MIN_DD, thr_nq)
    report("FLAT 20/30/10 (frozen)", rs)

    nq_all = pd.concat(nq.values()).sort_index()
    s = NQ_STOP / A_NQ * float(tr(nq_all).median())
    rs = []
    for b in nq.values():
        rs += trades_for(b, lambda d, g, s=s: s,
                         lambda st: NQ_MIN_DD / NQ_STOP * st, thr_nq)
    report("pooled ATR", rs)

    rs = []
    for b in nq.values():
        s = NQ_STOP / A_NQ * float(tr(b).median())
        rs += trades_for(b, lambda d, g, s=s: s,
                         lambda st: NQ_MIN_DD / NQ_STOP * st, thr_nq)
    report("per-contract ATR", rs)

    print("\nRead the SPREAD, not the best row. A result that only exists")
    print("under one arbitrary convention was never a result.")


if __name__ == "__main__":
    main()
