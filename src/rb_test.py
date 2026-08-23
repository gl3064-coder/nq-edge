"""rb_test.py - the frozen bot on RBOB gasoline, full year, one run.

WHY THIS EXISTS. CL had gross edge (+0.174R t=2.86 at NQ-matched gate, n=413)
but cost ate it (net -0.069R t=-1.12). HO was measured null at n=474. RB is the
last untested cheap-cost cousin in the energy complex - same 42,000-gallon
refined-product contract as HO, so same tick/multiplier and same ~2.5x cost
advantage over CL. If RB shows CL-strength gross edge at HO-level cost, we get
a net-positive energy port. If it null, the frozen bot is NQ-specific.

PRE-REGISTERED, one run.
  anchor      A_NQ = 11.75 (NQ session median 20s TR)
  stop        20/A_NQ * RB session ATR, per contract
  target/dd   1.5x / 0.5x stop
  leg gate    <= 30 bars
  tape gate   two variants:
                (as coded)  pctile(single-bar buy_delta, 66.67), per contract
                (NQ match)  pctile(3-bar mean, 100 - 16.9), per contract
  session     09:30 - 12:00 ET
  windows     each contract clipped so no day counted twice
  costs       1 tick (0.0001) + $4.50 commission at $42,000/point
              = 0.000207 in price
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
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "RB"

RB_TICK = 0.0001
RB_MULT = 42000.0
COMMISSION = 4.50
COST_PRICE = 1.0 * RB_TICK + COMMISSION / RB_MULT

ORDER = ["RB 09-25", "RB 10-25", "RB 11-25", "RB 12-25", "RB 01-26", "RB 02-26",
         "RB 03-26", "RB 04-26", "RB 05-26", "RB 06-26", "RB 07-26", "RB 08-26",
         "RB 09-26"]


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
    print(f"cost/round-turn = {COST_PRICE:.6f} in price "
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
    report("RBOB [as coded]", R_as)
    report("RBOB [NQ match]", R_nq)

    print("\n=== pooled, net of costs ===")
    print(f"  cost is fixed in price ({COST_PRICE:.6f}); cost-in-R varies by "
          f"contract stop.\n  Applied per-trade using each contract's own stop.")
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
    print("  CL NQ-match +0.174R t=2.86 (n=413) gross | -0.069R t=-1.12 net")
    print("  HO as-coded +0.028R t=0.51 (n=474) gross")


if __name__ == "__main__":
    main()
