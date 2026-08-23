"""gold_nt_check.py — reproduce the Databento gold result on NinjaTrader data.

WHY. On 2026-08-04 the frozen v2 bot run on Databento GC.n.0 (tbbo, Jan-Jul
2026, NY 09:30-12:00) gave +0.165R/trade, t=2.42, n=334. Then the same gold
turned up as NinjaTrader Last exports, a second independent source in the
native ticks.py format. Two sources over an overlapping window is the same
check that validated the 2026-08-03 NQ gap buy-back (7/30 reproduced exactly,
0/540 bars disagreed on the tape gate).

PER-CONTRACT, NOT SPLICED. Gold contract months differ in price by cost of
carry, so concatenating GC 04-26 onto GC 02-26 would inject a fake gap at every
roll. Each file is processed on its own and trades are pooled afterwards.
That also yields the leave-one-contract-out view that caught the dd=25 mirage.

Parameters are the frozen ones from cross_asset_v2.py. Nothing is refit here.
"""
from __future__ import annotations

import gc as _gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

A_NQ, NQ_STOP, RR, NQ_MIN_DD = 17.0, 20.0, 1.5, 10.0
LEG_THR = 30
NY = ("09:30", "12:00")
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "GC"

# Front-month window per contract, so the same day is never counted twice.
CONTRACTS = [
    ("GC 02-26.Last.txt", None,         "2026-01-22"),
    ("GC 04-26.Last.txt", "2026-01-22", "2026-03-26"),
    ("GC 06-26.Last.txt", "2026-03-26", "2026-05-28"),
    ("GC 08-26.Last.txt", "2026-05-28", "2026-07-25"),
]


def exit_fixed(entry, high, low, close, start, stop, target):
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def run_one(path: Path, lo, hi):
    bars = load_bars(path)
    if lo:
        bars = bars[bars.index >= lo]
    if hi:
        bars = bars[bars.index < hi]
    if bars.empty:
        return pd.DataFrame()

    tr = pd.concat([bars["high"] - bars["low"],
                    (bars["high"] - bars["close"].shift()).abs(),
                    (bars["low"] - bars["close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.median())
    stop, target = NQ_STOP / A_NQ * atr, RR * NQ_STOP / A_NQ * atr
    min_dd = NQ_MIN_DD / A_NQ * atr

    m = bars.between_time(*NY)
    if m.empty:
        return pd.DataFrame()
    thr = float(np.nanpercentile(m["buy_delta"].to_numpy(), 66.67))

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
            if np.nanmean(bd[i - 2:i + 1]) < thr or run[i] > LEG_THR:
                continue
            pl = exit_fixed(float(close[i]), high, low, close, i + 1, stop, target)
            rows.append({"day": str(d), "R": pl / stop})

    print(f"  {path.name:26} bars={len(bars):>7,}  ATR={atr:.3f}  "
          f"stop={stop:.3f}  tape>={thr:.4f}  trades={len(rows)}", flush=True)
    del bars, m
    _gc.collect()
    return pd.DataFrame(rows)


def stat(name, sub):
    if len(sub) < 2:
        print(f"  {name:28} n={len(sub):>4}  (too few)")
        return
    mu, sd = sub["R"].mean(), sub["R"].std(ddof=1)
    t = mu / (sd / np.sqrt(len(sub)))
    print(f"  {name:28} n={len(sub):>4}   {mu:+.3f}R   t={t:>5.2f}   "
          f"total {sub['R'].sum():+7.1f}R")


def main():
    print("loading per contract (front-month windows, no splicing):\n")
    parts = {}
    for fn, lo, hi in CONTRACTS:
        p = ROOT / fn
        if not p.exists():
            print(f"  {fn}: MISSING")
            continue
        parts[fn] = run_one(p, lo, hi)

    df = pd.concat(parts.values(), ignore_index=True)
    print("\n=== per contract ===")
    for fn, sub in parts.items():
        stat(fn.replace(".Last.txt", ""), sub)

    print("\n=== pooled (NinjaTrader) ===")
    stat("GOLD v2, Jan-Jul 2026", df)
    print("\n=== Databento result for the same window ===")
    print("  GOLD v2, Jan-Jul 2026        n= 334   +0.165R   t= 2.42   total   +55.0R")


if __name__ == "__main__":
    main()
