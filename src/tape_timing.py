"""
tape_timing.py — condition #4 as TIMING, not filtering.

Fire the entry the moment the tape flips green (buy_delta crosses <=0 -> >0) while in
up-context and still inside a pullback (price >= min_dd below a recent high). That triggers
at the *turn* — earlier than the confirmed higher-low — which is how the user actually
enters (Jan 15: his tape read got him in ~5 min ahead of the structural signal).

Real-time-able: uses only the current and past bars (no pivot confirmation, no lookahead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 30      # bars to look back for the recent high (the pullback reference)
MIN_DD = 10.0    # must be at least this far below the recent high (a real pullback)


def tape_timing_signal(close, up_context, buy_delta,
                       window: int = WINDOW, min_dd: float = MIN_DD) -> pd.Series:
    c = close.to_numpy()
    up = np.asarray(up_context, dtype=bool)
    bd = pd.Series(buy_delta).fillna(0).to_numpy()
    sig = np.zeros(len(c), dtype=bool)
    for i in range(1, len(c)):
        if not up[i]:
            continue
        recent_high = c[max(0, i - window):i + 1].max()
        pulled_back = (recent_high - c[i]) >= min_dd       # still down in the dip
        tape_flips_green = bd[i] > 0 and bd[i - 1] <= 0     # buyers just took over
        sig[i] = pulled_back and tape_flips_green
    return pd.Series(sig, index=close.index)
