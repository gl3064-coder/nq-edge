"""btc_test.py - the frozen bot on Bitcoin futures, full year, one run.

WHY THIS EXISTS. Five instruments tested so far: NQ works, GC/HO nulls, ZN
broken, CL/RB net-flat. Every failure has been in the same conceptual family
(equity index or crude complex). BTC is the only genuinely different asset
class left that has 20s tick data and enough per-bar flow for a tape gate.
Not shopping for confirmation - looking for a real independent test of whether
the signal generalizes at all.

KNOWN CAVEATS.
  1. BTC trades 24-hour. Keeping NY 09:30-12:00 window for spec consistency
     but it is not the "opening" of BTC in any meaningful sense.
  2. Cost per turn = 1 tick ($5) + $4.50 commission at $5/point = 5.90 in price.
     Very cheap in absolute R terms because BTC ATRs are large.
  3. BTC futures had a documented risk-off regime in early 2026. Contracts will
     span both bull-trend and chop, useful for regime robustness.

PRE-REGISTERED, one run.
  anchor      A_NQ = 11.75
  stop        20/A_NQ * BTC session ATR, per contract
  target/dd   1.5x / 0.5x stop
  leg gate    <= 30 bars
  tape gate   two variants:
                (as coded)  pctile(single-bar buy_delta, 66.67)
                (NQ match)  pctile(3-bar mean, 100 - 16.9)
  session     09:30 - 12:00 ET
  windows     each contract clipped so no day is counted twice
  costs       1 tick (5.00) + $4.50 commission / $5 per point
              = 5.90 in price
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

NQ_STOP, RR, NQ_MIN_DD, LEG_THR = 20.0, 1.5, 10.0, 30
NY = ("09:30", "12:00")
A_NQ = 11.750
NQ_TAPE_SEL = 0.169
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "BTC"

BTC_TICK = 5.00
BTC_MULT = 5.00
COMMISSION = 4.50
COST_PRICE = 1.0 * BTC_TICK + COMMISSION / BTC_MULT

ORDER = ["BTC 08-25", "BTC 10-25", "BTC 11-25", "BTC 12-25", "BTC 01-26",
         "BTC 02-26", "BTC 03-26", "BTC 04-26", "BTC 05-26", "BTC 06-26",
         "BTC 07-26", "BTC 08-26"]


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


def run_contract(bars, stop, thr):
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
        rl = np.zeros(n, dtype=int)
        for j in range(n):
            rl[j] = rl[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            if np.nanmean(bd[i - 2:i + 1]) < thr or rl[i] > LEG_THR:
                continue
            rows.append(exit_fixed(float(close[i]), high, low, close,
                                   i + 1, stop, target) / stop)
    return rows


def report(label, rs, extra=""):
    if len(rs) < 2:
        print(f"  {label:22} n={len(rs):>4}  (too few) {extra}")
        return None
    a = np.array(rs)
    t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
    print(f"  {label:22} n={len(a):>4}   {a.mean():+.3f}R   t={t:>5.2f}   "
          f"tot {a.sum():+7.1f}R {extra}")
    return a


def main():
    print(f"anchor A_NQ = {A_NQ} (NQ session ATR)")
    print(f"cost/round-turn = {COST_PRICE:.4f} in price "
          f"(1 tick + ${COMMISSION:.2f})\n")

    prev_end = None
    R_as, R_nq, per_as, per_nq, stops = [], [], {}, {}, {}
    for name in ORDER:
        p = ROOT / f"{name}.Last.txt"
        if not p.exists():
            print(f"  {name}: MISSING")
            continue
        b = load_bars(p)
        if prev_end is not None:
            b = b[b.index > prev_end]
        if b.empty:
            continue
        prev_end = b.index.max()

        sess = b.between_time(*NY)
        atr = float(tr(sess).median())
        if not np.isfinite(atr) or atr <= 0:
            continue
        stop = NQ_STOP / A_NQ * atr

        bd = sess["buy_delta"].to_numpy()
        thr_as = float(np.nanpercentile(bd, 66.67))
        m3 = sess["buy_delta"].rolling(3).mean().to_numpy()
        m3 = m3[np.isfinite(m3)]
        thr_nq = float(np.nanpercentile(m3, 100.0 * (1 - NQ_TAPE_SEL)))

        rs_as = run_contract(b, stop, thr_as)
        rs_nq = run_contract(b, stop, thr_nq)
        per_as[name], per_nq[name] = rs_as, rs_nq
        stops[name] = stop
        R_as += rs_as
        R_nq += rs_nq

        print(f"  {name}  bars={len(b):>7,}  ATR={atr:.2f}  stop={stop:.2f}  "
              f"cost={COST_PRICE/stop:.3f}R  tape[as]>={thr_as:+.4f} n={len(rs_as):>3}  "
              f"tape[nq]>={thr_nq:+.4f} n={len(rs_nq):>3}", flush=True)
        del b
        _gc.collect()

    print("\n=== per contract, as coded (pctile single-bar, 66.67) ===")
    pos_as = 0
    for name, rs in per_as.items():
        a = report(name, rs)
        if a is not None and a.mean() > 0:
            pos_as += 1
    print(f"\n  contracts with positive mean: {pos_as}/{len(per_as)}")

    print("\n=== per contract, NQ-matched selectivity (top 16.9% of 3-bar mean) ===")
    pos_nq = 0
    for name, rs in per_nq.items():
        a = report(name, rs)
        if a is not None and a.mean() > 0:
            pos_nq += 1
    print(f"\n  contracts with positive mean: {pos_nq}/{len(per_nq)}")

    print("\n=== pooled, gross ===")
    report("BTC [as coded]", R_as)
    report("BTC [NQ match]", R_nq)

    print("\n=== pooled, net of costs ===")
    print(f"  cost = {COST_PRICE:.4f} in price; cost-in-R varies by contract stop.")
    for label, per in [("as coded", per_as), ("NQ match", per_nq)]:
        net = []
        for name, rs in per.items():
            c = COST_PRICE / stops[name]
            net += [r - c for r in rs]
        if len(net) >= 2:
            a = np.array(net)
            t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
            print(f"  net [{label:8}]         n={len(a):>4}   {a.mean():+.3f}R   "
                  f"t={t:>5.2f}   tot {a.sum():+7.1f}R")

    print("\nReference:")
    print("  NQ frozen  +0.154R t=1.92 (n=235)")
    print("  CL as-coded +0.101R t=1.90 (n=532) gross | -0.140R t=-2.61 net")
    print("  RB as-coded +0.106R t=1.88 (n=479) gross | -0.019R t=-0.34 net")
    print("  HO as-coded +0.028R t=0.51 (n=474) gross")


if __name__ == "__main__":
    main()
