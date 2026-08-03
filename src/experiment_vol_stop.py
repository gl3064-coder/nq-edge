"""
experiment_vol_stop.py — a stop that changes with the ATR at entry: does any
piecewise rule beat the flat 20?

The rule: look at avg ATR (15-bar) at entry, pick the stop for that bucket
(low / mid / high). Trail structure stays his real ATM (arm +30, trail 20);
only the stop size varies. Rules tested:

  flat 20            — baseline (his current ATM)
  vol-matched 10/20/40, 15/20/50, 15/20/30 — HIS hypothesis: size the stop to the tape
  inverse 20/20/10   — what the bucket table hinted (tight stop in hot tape).
                       ⚠ MINED from the same data — shown for comparison, not for trading.
  skip-low           — no trades below the low boundary, flat 20 elsewhere

Boundary perturbation: the low/high cutoffs (10/20) are re-run at (8,18) and
(12,22). A real effect survives moved boundaries; an artifact doesn't.

All in-sample, pre-cost, close-only fills. Compare rows to each other.

Run:  python src/experiment_vol_stop.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_atr_exits import build_sessions, stats


def sim_atm(c, d, idx, stops, activate=30.0, trail=20.0):
    """His ATM structure with a per-entry stop: fixed stop until +activate,
    then trail `trail` behind the peak."""
    pls = []
    for i, init_stop in zip(idx, stops):
        entry, peak = c[i], c[i]
        stop, on, pl = entry - init_stop, False, None
        for j in range(i + 1, len(c)):
            if d[j] != d[i]:
                pl = c[j - 1] - entry
                break
            px = c[j]
            peak = max(peak, px)
            if not on and px - entry >= activate:
                on = True
            if on:
                stop = max(stop, peak - trail)
            if px <= stop:
                pl = stop - entry
                break
        if pl is None:
            pl = c[-1] - entry
        pls.append(pl)
    return np.array(pls)


def main():
    close, sig, day, atr_avg, _ = build_sessions()
    c = close.to_numpy(); d = day.to_numpy(); aa = atr_avg.to_numpy()
    entries = np.where(sig.to_numpy())[0]

    # (name, (stop_low, stop_mid, stop_high)); None = skip trades in that bucket
    rules = [
        ("flat 20 (baseline)",        (20, 20, 20)),
        ("vol-matched 10/20/40",      (10, 20, 40)),
        ("vol-matched 15/20/50",      (15, 20, 50)),
        ("vol-matched 15/20/30",      (15, 20, 30)),
        ("inverse 20/20/10 (MINED)",  (20, 20, 10)),
        ("skip-low, 20 elsewhere",    (None, 20, 20)),
    ]

    for lo, hi in [(10, 20), (8, 18), (12, 22)]:
        bucket = np.where(aa[entries] < lo, 0, np.where(aa[entries] < hi, 1, 2))
        print(f"\n=== boundaries: low < {lo} | mid | high >= {hi} ===")
        print(f"{'rule':<28}{'n':>6}{'win%':>7}{'avg':>8}{'total':>9}{'tSharpe':>9}{'dSharpe':>9}")
        print("-" * 76)
        for name, (s0, s1, s2) in rules:
            per_bucket = [s0, s1, s2]
            keep = np.array([per_bucket[b] is not None for b in bucket])
            idx = entries[keep]
            stops = np.array([float(per_bucket[b]) for b in bucket[keep]])
            pls = sim_atm(c, d, idx, stops)
            st = stats(pls, d[idx])
            print(f"{name:<28}{st['n']:>6}{st['win']*100:>6.0f}%{st['avg']:>8.2f}"
                  f"{st['total']:>9.0f}{st['sharpe']:>9.3f}{st['dsharpe']:>9.3f}")

    print("\nSame entries throughout; only the stop rule (and skips) change.")
    print("In-sample, pre-cost, close-only. The inverse rule is data-mined — a")
    print("candidate for the forward test, not a change to make today.")


if __name__ == "__main__":
    main()
