"""ho_test.py — the frozen bot on heating oil, corrected anchor, one run.

WHY HO. Of everything measured on 2026-08-04, heating oil had the second-best
movement-per-cost ratio (19.5 vs NQ's 22.2, gold 9.3, crude 5.7). My idea:
if the energy signal is real but crude cannot pay its toll, route it through the
cheapest door in the same complex. Twelve months of tick data came free from
NinjaTrader in the native ticks.py format.

PRE-REGISTERED, and this is the only run.
  anchor      A_NQ = NQ's SESSION median 20s true range (11.75), not the old
              hardcoded 17.0 which failed its own self-consistency test
  stop        20/A_NQ * HO session ATR;  target 1.5x;  min_dd 0.5x stop
  leg gate    <= 30 bars, unscaled
  tape gate   HO's own top tercile, per contract
  session     09:30-12:00 ET, unchanged
  windows     each contract clipped so no day is counted twice

CAVEAT KNOWN IN ADVANCE. HO trades ~10 contracts per 20s bar against NQ's 297.
buy_delta is therefore coarse, roughly quantized in steps of 0.2. Coarse
measurement ATTENUATES a real signal rather than manufacturing a fake one, so a
positive here would be credible, but a null cannot distinguish "no edge" from
"too noisy to see."

Twelve contracts also means a 12-fold per-contract robustness view, four times
what NQ's three contracts allow. Per-contract stability is what killed dd=25.
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
A_NQ = 11.750          # NQ session ATR, measured 2026-08-04
ROOT = Path(__file__).resolve().parent.parent / "Replay Data" / "HO"

ORDER = ["HO 10-25", "HO 11-25", "HO 12-25", "HO 01-26", "HO 02-26", "HO 03-26",
         "HO 04-26", "HO 05-26", "HO 06-26", "HO 07-26", "HO 08-26", "HO 09-26"]


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
        print(f"  {label:20} n={len(rs):>4}  (too few) {extra}")
        return None
    a = np.array(rs)
    t = a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))
    print(f"  {label:20} n={len(a):>4}   {a.mean():+.3f}R   t={t:>5.2f}   "
          f"tot {a.sum():+7.1f}R {extra}")
    return a


def main():
    print(f"anchor A_NQ = {A_NQ} (NQ session ATR)\n")
    prev_end = None
    allR, per = [], {}
    for name in ORDER:
        p = ROOT / f"{name}.Last.txt"
        if not p.exists():
            continue
        b = load_bars(p)
        if prev_end is not None:                 # clip so no day is double counted
            b = b[b.index > prev_end]
        if b.empty:
            continue
        prev_end = b.index.max()
        atr = float(tr(b.between_time(*NY)).median())
        if not np.isfinite(atr) or atr <= 0:
            continue
        stop = NQ_STOP / A_NQ * atr
        thr = float(np.nanpercentile(
            b.between_time(*NY)["buy_delta"].to_numpy(), 66.67))
        rs = run_contract(b, stop, thr)
        per[name] = rs
        allR += rs
        print(f"  {name}  bars={len(b):>7,}  ATR={atr:.5f}  stop={stop:.5f}  "
              f"tape>={thr:.4f}  trades={len(rs)}", flush=True)
        del b
        _gc.collect()

    print("\n=== per contract (12-fold robustness) ===")
    pos = 0
    for name, rs in per.items():
        a = report(name, rs)
        if a is not None and a.mean() > 0:
            pos += 1
    print(f"\n  contracts with positive mean: {pos}/{len(per)}")

    print("\n=== pooled ===")
    report("HEATING OIL v2", allR)
    print("\nGross of costs. HO round trip is ~1 tick (0.0001) + commission.")
    print("Reference: NQ frozen +0.154R t=1.92 | crude corrected +0.204R t=1.42")


if __name__ == "__main__":
    main()
