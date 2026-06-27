"""
experiment_trail.py — does trailing the stop beat the fixed 30/20?

User: "I sometimes trail the 30/20 and get more, but sometimes it bites me." So test it.
Trailing = stop rides `trail` points below the high-water mark (only moves up); no hard
target means winners can run past +30, the cost being you give back `trail` from the peak
on a reversal. Compared against the fixed 30/20 baseline on the same signal + sessions.

Run:  python src/experiment_trail.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_rr import build_signal
from scorer import score


def score_trailing(close, signal, day, init_stop=20.0, trail=20.0, target=None):
    c = close.to_numpy(); sig = np.asarray(signal, bool); d = np.asarray(day)
    pls = []
    for i in np.where(sig)[0]:
        entry, peak, stop, pl = c[i], c[i], c[i] - init_stop, None
        for j in range(i + 1, len(c)):
            if d[j] != d[i]:
                pl = c[j - 1] - entry; break
            px = c[j]
            if px > peak:
                peak = px
            stop = max(stop, peak - trail)              # trail only moves up
            if target is not None and px - entry >= target:
                pl = target; break
            if px <= stop:
                pl = stop - entry; break
        if pl is None:
            pl = c[-1] - entry
        pls.append(pl)
    a = np.array(pls)
    return {"n": len(a), "win": (a > 0).mean(), "avg": a.mean(), "total": a.sum()}


def main():
    close, sig, day = build_signal()
    _, base = score(close, sig, day, target=30, stop=20)

    print(f"signal: {int(sig.sum())} trades\n")
    print(f"{'exit rule':<26}{'win%':>7}{'avg':>8}{'total':>9}")
    print("-" * 50)
    print(f"{'fixed 30/20 (your rule)':<26}{base['win_rate']*100:>6.0f}%"
          f"{base['avg_pts']:>8.1f}{base['total_pts']:>9.0f}")
    for name, kw in [
        ("trail 20, no target", dict(trail=20, target=None)),
        ("trail 15, no target", dict(trail=15, target=None)),
        ("trail 25, no target", dict(trail=25, target=None)),
        ("30 target + trail 20", dict(trail=20, target=30)),
    ]:
        s = score_trailing(close, sig, day, init_stop=20, **kw)
        print(f"{name:<26}{s['win']*100:>6.0f}%{s['avg']:>8.1f}{s['total']:>9.0f}")


if __name__ == "__main__":
    main()
