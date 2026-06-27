"""
drawdown.py — condition #3 (free-data): require a real pullback BEFORE entry.

The user's rule, in his words: "I look for drawdowns before going in so I don't get
stopped out even though it's trending up." Translation: don't enter a stretched move
that hasn't pulled back — wait until a genuine dip has happened, so you're entering
near support with room to run instead of at an extension that's due to revert (and stop
you out). This is the fix for the "bought the top" failure (bar ~200 / journal loss #488).

Mechanics: a higher-low signal fires `k` bars after the pivot low it confirmed, so the
pullback low sits at bar (i - k). We measure the DIP INTO that low — the drop from the
prior local high down to the pivot low — and keep the signal only if that dip is at
least `min_dd` points. Deep pullbacks (real drawdowns) pass; tiny grinds and vertical
tops, which barely dipped, fail.

Three knobs (k, min_dd, lookback); all calibrate on real 20s data later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PIVOT_K = 3        # must match location.higher_low_signal's k
MIN_DD = 10.0      # minimum pullback depth, in NQ points
LOOKBACK = 30      # bars before the pivot low to search for the prior high


def drawdown_filter(
    close: pd.Series,
    signal: pd.Series | np.ndarray,
    k: int = PIVOT_K,
    lookback: int = LOOKBACK,
    min_dd: float = MIN_DD,
) -> pd.Series:
    """Keep only signals preceded by a genuine drawdown into the higher-low."""
    c = close.to_numpy()
    sig = np.asarray(signal, dtype=bool).copy()
    for i in np.where(sig)[0]:
        pivot = i - k  # the pullback low this signal confirmed
        if pivot <= 0:
            sig[i] = False
            continue
        window = c[max(0, pivot - lookback):pivot + 1]  # ends AT the pullback low
        depth = float(window.max() - c[pivot])          # drop from prior high into low
        sig[i] = bool(depth >= min_dd)
    return pd.Series(sig, index=close.index)
