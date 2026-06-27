"""
context.py — the co-pilot's free-data brain: is the 20-second chart in "up-context"?

This is condition #1 of the codified entry trigger — the highest-value, free-data
filter (the one worth +14.5 pts/trade in the journal analysis). Everything else
(pullback location, DOM, tape) sits on top of this.

CALIBRATED FROM 5 WINNING-ENTRY CHARTS (2026-06-25):
The user's "up context" is a SHORT-HORIZON read — the local up-leg over roughly the
last 10-20 minutes — NOT the whole session. Two of the five wins (NQ DEC25, NQ JUN26)
were RECOVERIES: the broader trend was DOWN, but the recent up-leg off the bottom was
intact, and that's what he traded. So the context MA must be SHORT. On 20-second bars:
10 min ~= 30 bars, 20 min ~= 60 bars.

up_context = fast MA > slow MA  AND  slow MA rising.

The periods below are STARTING POINTS, not settled values. They must be calibrated
against real 20s NQ data — and the two recovery wins are the stress test: the chosen
periods MUST flag "up-context" by the entry on those, or they're too slow. Keeping the
knob count low on purpose (overfitting discipline).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Defaults in 20-second bars: fast ~= 7 min, slow ~= 17 min, slope window ~= 3 min.
FAST = 20
SLOW = 50
SLOPE_LOOKBACK = 10


def moving_average(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=period).mean()


def up_context(
    close: pd.Series,
    fast: int = FAST,
    slow: int = SLOW,
    slope_lookback: int = SLOPE_LOOKBACK,
) -> pd.DataFrame:
    """
    Flag each bar as "up-context" or not.

    up_context = fast MA above slow MA (a local up-leg is in force)
                 AND slow MA rising over the last `slope_lookback` bars
                 (the leg has real upward drift, not a one-bar blip).

    Returns a DataFrame: close, fast_ma, slow_ma, slow_rising, up_context (bool).
    """
    fast_ma = moving_average(close, fast)
    slow_ma = moving_average(close, slow)
    slow_rising = slow_ma.diff(slope_lookback) > 0
    flag = (fast_ma > slow_ma) & slow_rising
    return pd.DataFrame(
        {
            "close": close,
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "slow_rising": slow_rising.fillna(False),
            "up_context": flag.fillna(False),
        }
    )


if __name__ == "__main__":
    # Smoke test on synthetic data: a down-leg, a bottom, then a recovery up-leg
    # (mimics the two recovery wins). The detector should be FALSE through the
    # decline and flip TRUE once the recovery has enough upward drift.
    n = 200
    down = np.linspace(100, 60, n // 2)
    up = np.linspace(60, 95, n // 2)
    close = pd.Series(np.concatenate([down, up]))
    out = up_context(close)
    flip = out["up_context"].idxmax() if out["up_context"].any() else None
    print(f"bars: {len(out)} | up-context bars: {int(out['up_context'].sum())}")
    print(f"first up-context bar: {flip} (bottom is at bar {n // 2})")
    print("OK — flips TRUE during the recovery, as intended"
          if flip and flip > n // 2 else "check: did not flip during recovery")
