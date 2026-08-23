"""cl_test.py - the frozen bot on crude oil, full year, one run.

WHY THIS EXISTS. The 2026-08-04 audit had crude at n=74 with only ~3 months of
data (bars_CL_c_0.pkl). Point estimate was +0.204R t=1.42 gross, net +0.082R
t=0.57 after 1-tick spread + $4.50 commission. Too small to matter.

I pulled 13 monthly contracts from NinjaTrader (Sep 2025 - Sep 2026). Full
year, ~250 sessions, target n~200+. Same pipeline as ho_test.py, no other
changes.

PRE-REGISTERED.
  anchor      A_NQ = NQ session median 20s true range (11.75)
  stop        20/A_NQ * CL session ATR, per contract; target 1.5x; min_dd 0.5x
  leg gate    <= 30 bars, unscaled
  tape gate   per-contract, computed two ways:
                (as coded) pctile(single-bar buy_delta, 66.67)
                (NQ-matched) pctile(3-bar mean, 100 - 16.9) matches NQ selectivity
              primary reported result is as-coded to keep apples-to-apples with
              the other ports; NQ-matched shown alongside for the audit finding
  session     09:30 - 12:00 ET
  windows     each contract clipped so no day is counted twice
  costs       round-turn = 1 tick (0.01) + $4.50 commission / $1000 per point
              = 0.0145 in price, quoted as fraction of R per contract at the end
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
NQ_TAPE_SEL = 0.169     # NQ's 0.10 gate keeps top 16.9% of 3-bar means
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "CL"

CL_TICK = 0.01
CL_MULT = 1000.0
COMMISSION = 4.50
COST_PRICE = 1.0 * CL_TICK + COMMISSION / CL_MULT

ORDER = ["CL 09-25", "CL 10-25", "CL 11-25", "CL 12-25", "CL 01-26", "CL 02-26",
         "CL 03-26", "CL 04-26", "CL 05-26", "CL 06-26", "CL 07-26", "CL 08-26",
         "CL 09-26"]


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
    print(f"cost/round-turn = {COST_PRICE:.5f} in price "
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

        print(f"  {name}  bars={len(b):>7,}  ATR={atr:.5f}  stop={stop:.5f}  "
              f"tape[as]>={thr_as:+.4f} n={len(rs_as):>3}  "
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
    a_as = report("CRUDE OIL [as coded]", R_as)
    a_nq = report("CRUDE OIL [NQ match]", R_nq)

    print("\n=== pooled, net of costs ===")
    print(f"  cost is fixed in price ({COST_PRICE:.5f}); cost-in-R varies by "
          f"contract stop.\n  Applied per-trade using each contract's own stop.")
    for label, per, R in [("as coded", per_as, R_as),
                          ("NQ match", per_nq, R_nq)]:
        net = []
        for name, rs in per.items():
            c = COST_PRICE / stops[name]
            net += [r - c for r in rs]
        if len(net) >= 2:
            a = np.array(net)
            t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
            print(f"  net [{label:8}]         n={len(a):>4}   {a.mean():+.3f}R   "
                  f"t={t:>5.2f}   tot {a.sum():+7.1f}R")

    print("\nReference: NQ frozen +0.154R t=1.92 (n=235)")
    print("Prior CL (~3 months, n=74): +0.204R t=1.42 gross, +0.082R t=0.57 net")


if __name__ == "__main__":
    main()
