"""cross_asset_v2.py — run the FROZEN v2 bot on a non-NQ instrument.

Reconstructs the 2026-07-14 breadth test (CL +0.165R t=2.0 n=228; ZN +0.409R
t=4.0 n=145 — both gross-positive, both dead after costs). The original script
was never saved; this is it, written back from the spec.

PRE-REGISTERED, DO NOT TUNE. Everything below was fixed before gold data
existed. The whole value of a cross-asset test is that it is evidence from
OUTSIDE the searched NQ sample, and that evaporates the moment a knob gets
turned to make the new market look better.

  signal    up_context(20/50, slope 10) + higher_low(k=3) + drawdown   [unchanged]
  leg gate  leg_age <= 30 bars                                          [unchanged,
            it is a count of bars, so it ports without scaling]
  tape gate market's OWN top tercile of buy_delta                       [ported as a
            RANK, not as 0.10 — 0.10 is just where NQ's top third sits]
  session   TWO pre-registered windows, both reported, neither chosen after
            seeing a result:
              NY      09:30-12:00 ET  (the frozen NQ window, unchanged)
              LONDON  03:00-09:30 ET  (08:00-14:30 BST, disjoint from NY)
            Gold's liquidity is London-led, so the NY window may simply be the
            wrong place to look. Testing two windows is two trials: the
            significance bar rises to t ~ 2.24 (Bonferroni at 5%) instead of
            1.96. Adding a THIRD window later, after seeing these, would be
            fishing and would invalidate both.
  stop      20 pts on NQ, ATR-scaled elsewhere: 20/17 * market_atr
  target    1.5 x stop  (NQ's +30/-20 is 1.5:1)
  units     R = P/L / stop, so markets are comparable

A_NQ = 17.0 is NQ's median 20-second true range, the scaling reference.

Usage:
    python src/cross_asset_v2.py "Replay Data/databento/GC_n0_tbbo_2026-*.csv"
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from databento_bars import load_bars_databento
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

A_NQ = 17.0          # NQ median 20s true range, the scaling anchor
NQ_STOP = 20.0       # NQ stop in points
RR = 1.5             # target/stop, i.e. NQ's 30/20
NQ_MIN_DD = 10.0     # NQ entry-drawdown filter in points
LEG_THR = 30         # bars, unscaled
SESSIONS = {                      # pre-registered, disjoint, both reported
    "NY     09:30-12:00": ("09:30", "12:00"),
    "LONDON 03:00-09:30": ("03:00", "09:30"),
}
BONFERRONI_T = 2.24  # 2 windows tested -> the bar for either one to count


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"],
                      (df["high"] - prev).abs(),
                      (df["low"] - prev).abs()], axis=1).max(axis=1)


def exit_fixed(entry: float, high, low, close, start: int,
               stop: float, target: float) -> float:
    """Stop checked before target on the same bar (conservative, matches forward_v2)."""
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def main() -> None:
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no files match: {pattern!r}")

    bars = pd.concat([load_bars_databento(f) for f in files]).sort_index()
    bars = bars[~bars.index.duplicated(keep="first")]

    atr = float(true_range(bars).median())
    stop = NQ_STOP / A_NQ * atr
    target = RR * stop
    min_dd = NQ_MIN_DD / A_NQ * atr

    print(f"files      : {len(files)}   bars: {len(bars):,}")
    print(f"median 20s TR : {atr:.4f}   -> stop {stop:.4f}  target {target:.4f}"
          f"  min_dd {min_dd:.4f}")
    print(f"two pre-registered windows; bar for either is t >= {BONFERRONI_T}\n")

    for label, window in SESSIONS.items():
        run_window(bars, label, window, atr, stop, target, min_dd)


def run_window(bars, label, window, atr, stop, target, min_dd) -> None:
    m = bars.between_time(*window)
    if m.empty:
        print(f"=== {label} ===  no bars\n")
        return

    # Tape threshold = this market's own top tercile, within THIS window.
    tape_thr = float(np.nanpercentile(m["buy_delta"].to_numpy(), 66.67))
    print(f"=== {label} ===   session bars {len(m):,}   "
          f"tape gate buy_delta >= {tape_thr:.4f}")

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
        high, low = g["high"].to_numpy(), g["low"].to_numpy()
        bd = g["buy_delta"].to_numpy()
        n = len(close)
        run = np.zeros(n, dtype=int)
        for j in range(n):
            run[j] = run[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            e = float(close[i])
            pl = exit_fixed(e, high, low, close, i + 1, stop, target)
            rows.append({"day": str(d),
                         "tape": float(np.nanmean(bd[i - 2:i + 1])),
                         "leg_age": int(run[i]),
                         "R": pl / stop})

    df = pd.DataFrame(rows)
    if df.empty:
        print("  no signals fired\n")
        return

    def report(name: str, sub: pd.DataFrame) -> None:
        if len(sub) < 2:
            print(f"  {name:22} n={len(sub):>4}   (too few)")
            return
        mean, sd = sub["R"].mean(), sub["R"].std(ddof=1)
        t_stat = mean / (sd / np.sqrt(len(sub)))
        flag = "  <-- clears bar" if t_stat >= BONFERRONI_T else ""
        print(f"  {name:22} n={len(sub):>4}   {mean:+.3f}R/trade   "
              f"t={t_stat:>5.2f}   total {sub['R'].sum():+.1f}R{flag}")

    report("v1 (all arrows)", df)
    report("tape only", df[df.tape >= tape_thr])
    report("V2 (tape + leg<=30)", df[(df.tape >= tape_thr) & (df.leg_age <= LEG_THR)])
    print()


if __name__ == "__main__":
    main()
