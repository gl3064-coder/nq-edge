"""
experiment_trail_after.py — "trail only AFTER +30" vs continuous trail vs fixed 30/20.

The user's mental model: keep the fixed -20 stop until the trade reaches +30, THEN start
trailing. Difference vs continuous trail: more room early (won't get shaken out by a small
dip on the way up), but you give back everything if it reverses before +30. Test it.

Run:  python src/experiment_trail_after.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_rr import build_signal
from experiment_trail import score_trailing
from scorer import score


def score_trail_after(close, signal, day, init_stop=20.0, activate=30.0, trail=20.0):
    c = close.to_numpy(); sig = np.asarray(signal, bool); d = np.asarray(day)
    pls = []
    for i in np.where(sig)[0]:
        entry, peak, stop, on, pl = c[i], c[i], c[i] - init_stop, False, None
        for j in range(i + 1, len(c)):
            if d[j] != d[i]:
                pl = c[j - 1] - entry; break
            px = c[j]
            if px > peak:
                peak = px
            if not on and px - entry >= activate:   # arm trailing once +30 is touched
                on = True
            if on:
                stop = max(stop, peak - trail)       # ...then trail behind the peak
            if px <= stop:
                pl = stop - entry; break
        if pl is None:
            pl = c[-1] - entry
        pls.append(pl)
    a = np.array(pls)
    return {"win": (a > 0).mean(), "avg": a.mean(), "total": a.sum()}


def main():
    close, sig, day = build_signal()
    _, base = score(close, sig, day, target=30, stop=20)
    ct = score_trailing(close, sig, day, init_stop=20, trail=20, target=None)

    print(f"signal: {int(sig.sum())} trades\n")
    print(f"{'exit rule':<30}{'win%':>7}{'avg':>8}{'total':>9}")
    print("-" * 54)
    print(f"{'fixed 30/20':<30}{base['win_rate']*100:>6.0f}%"
          f"{base['avg_pts']:>8.1f}{base['total_pts']:>9.0f}")
    print(f"{'continuous trail 20':<30}{ct['win']*100:>6.0f}%{ct['avg']:>8.1f}{ct['total']:>9.0f}")
    for tr in [15, 20, 25]:
        s = score_trail_after(close, sig, day, init_stop=20, activate=30, trail=tr)
        print(f"{f'trail AFTER +30 (trail {tr})':<30}{s['win']*100:>6.0f}%"
              f"{s['avg']:>8.1f}{s['total']:>9.0f}")


if __name__ == "__main__":
    main()
