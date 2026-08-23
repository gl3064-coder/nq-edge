"""audit_gold.py — interrogate the suspiciously good gold result.

Gross Sharpe came out 4.25. That is the shape of a bug, not a discovery.
This checks the specific ways it could be fake, in order of suspicion:

1. UNRESOLVED TRADES. exit_fixed returns (last_close - entry) when a trade
   never touches target or stop. Every RESOLVED trade is bounded to exactly
   +1.5R or -1.0R, so any |R| outside that came from this branch. On a
   continuous contract a roll-day residual could be enormous.

2. ROLL GAPS. GC.n.0 switches contract months; price jumps at the seam.
   Look for bar-to-bar moves far outside the normal distribution.

3. CONCENTRATION. If a handful of days carry the whole result, it is not an
   edge, it is a few lucky prints.

Prints, does not fix. Read the numbers before changing anything.
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

NY = ("09:30", "12:00")
LEG_THR = 30


def exit_fixed_tagged(entry, high, low, close, start, stop, target):
    """Same logic as the backtest, but reports HOW the trade ended."""
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop, "stop"
        if high[j] >= entry + target:
            return target, "target"
    return float(close[-1] - entry), "UNRESOLVED"


def main():
    files = sorted(glob.glob("Replay Data/databento/GC_n0_tbbo_2026-*.csv"))
    bars = pd.concat([load_bars_databento(f) for f in files]).sort_index()
    bars = bars[~bars.index.duplicated(keep="first")]

    tr = pd.concat([bars["high"] - bars["low"],
                    (bars["high"] - bars["close"].shift()).abs(),
                    (bars["low"] - bars["close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.median())
    stop = 20.0 / 17.0 * atr
    target = 1.5 * stop
    min_dd = 10.0 / 17.0 * atr

    # ---------- 2. roll gaps ----------
    print("=== bar-to-bar jumps (roll-gap check) ===")
    d = bars["close"].diff().abs()
    print(f"  median 20s |move| : {d.median():.3f}")
    print(f"  99.9th pct        : {d.quantile(0.999):.3f}")
    print(f"  max               : {d.max():.3f}")
    big = d[d > 20 * atr]
    print(f"  bars moving >20x ATR ({20*atr:.1f}): {len(big)}")
    for ts, v in big.sort_values(ascending=False).head(8).items():
        print(f"     {ts}   {v:.1f}")

    # ---------- 1 & 3. trade-level audit ----------
    m = bars.between_time(*NY)
    thr = float(np.nanpercentile(m["buy_delta"].to_numpy(), 66.67))
    rows = []
    for day, grp in m.groupby(m.index.date):
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
            if np.nanmean(bd[i - 2:i + 1]) < thr or run[i] > LEG_THR:
                continue
            pl, how = exit_fixed_tagged(float(close[i]), high, low, close,
                                        i + 1, stop, target)
            rows.append({"day": str(day), "R": pl / stop, "how": how,
                         "entry": float(close[i])})

    df = pd.DataFrame(rows)
    print(f"\n=== trade outcomes (n={len(df)}) ===")
    print(df.groupby("how")["R"].agg(["count", "mean", "min", "max"]).to_string())

    print(f"\n  total R           : {df['R'].sum():+.1f}")
    for how, sub in df.groupby("how"):
        print(f"  contributed by {how:<11}: {sub['R'].sum():+8.1f}R "
              f"({100*sub['R'].sum()/df['R'].sum():.0f}%)")

    print("\n=== biggest single trades ===")
    for _, r in df.reindex(df["R"].abs().sort_values(ascending=False).index).head(10).iterrows():
        print(f"  {r['day']}  {r['R']:+9.2f}R  {r['how']:<11} entry {r['entry']:.1f}")

    print("\n=== day concentration ===")
    byday = df.groupby("day")["R"].sum().sort_values()
    print(f"  total {byday.sum():+.1f}R over {len(byday)} days")
    print(f"  best 5 days  : {byday.tail(5).sum():+.1f}R")
    print(f"  worst 5 days : {byday.head(5).sum():+.1f}R")
    print(f"  median day   : {byday.median():+.3f}R")
    print(f"  total WITHOUT the best 5 days: {byday.sum() - byday.tail(5).sum():+.1f}R")


if __name__ == "__main__":
    main()
