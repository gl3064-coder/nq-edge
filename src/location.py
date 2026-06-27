"""
location.py — condition #2 of the entry trigger: pullback to a HIGHER LOW.

Within up-context (condition #1), this finds the spots you actually enter: a pullback
that made a higher low than the prior swing low, confirmed as price turns back up.
It's what separates a real up-leg (higher lows) from a chop bounce (no higher low) —
the residual noise the moving-average filter couldn't remove.

Mechanics:
- A "pivot low" = a bar that is the lowest in a +/-k window (k bars each side).
- A "higher low" = a pivot low above the *previous* pivot low (uptrend structure intact).
- The signal fires k bars later — the moment the higher low is actually confirmable —
  but only IF up-context still holds there.

k is the single knob: bigger k = stronger/slower swings, fewer signals. Default 3
(~1 min on 20s bars, ~3 min on 1-min bars). Calibrate on real 20s data later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PIVOT_K = 3


def pivot_lows(close: pd.Series, k: int = PIVOT_K) -> np.ndarray:
    """Boolean array: True where close[i] is the lowest in [i-k, i+k]."""
    c = close.to_numpy()
    n = len(c)
    piv = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        if c[i] == c[i - k:i + k + 1].min():
            piv[i] = True
    return piv


def higher_low_signal(
    close: pd.Series,
    up_context: pd.Series | np.ndarray,
    k: int = PIVOT_K,
) -> pd.Series:
    """
    Fire True where a higher-low pullback is confirmed AND up-context holds.

    This is the complete free-data entry signal (condition #1 AND #2): the moments
    the co-pilot would actually alert "your setup is forming."
    """
    c = close.to_numpy()
    up = np.asarray(up_context, dtype=bool)
    piv_positions = np.where(pivot_lows(close, k))[0]
    sig = np.zeros(len(c), dtype=bool)

    prev = None
    for pos in piv_positions:
        if prev is not None and c[pos] > c[prev]:        # higher low than the last one
            confirm = pos + k                            # only knowable k bars later
            if confirm < len(c) and up[confirm]:         # ...and context still up
                sig[confirm] = True
        prev = pos
    return pd.Series(sig, index=close.index)


if __name__ == "__main__":
    # Synthetic rising staircase with pullbacks -> should fire on the higher low(s).
    base = np.concatenate([
        np.linspace(100, 110, 30), np.linspace(110, 105, 10),   # up then pullback
        np.linspace(105, 120, 30), np.linspace(120, 115, 10),   # up then higher pullback
        np.linspace(115, 130, 30),                               # up
    ])
    close = pd.Series(base)
    up = pd.Series(True, index=close.index)
    sig = higher_low_signal(close, up)
    print(f"bars: {len(close)} | higher-low signals: {int(sig.sum())} "
          f"at bars {list(np.where(sig.to_numpy())[0])}")
