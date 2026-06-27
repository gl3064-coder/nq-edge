"""
scorer.py — does a signal actually win?

For each signal bar: enter long at that bar's close, then walk forward (same morning
only) until price hits entry + target (win) or entry - stop (loss), whichever first.
Unresolved by session end is scored at the final close. Tallies win rate and points.

CLOSE-ONLY APPROXIMATION: we don't have intrabar highs/lows here, so target/stop are
checked on closes. That under-counts intrabar touches — treat the numbers as a rough
read, not a fill-accurate backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def score(
    close: pd.Series,
    signal: pd.Series | np.ndarray,
    day: pd.Series | np.ndarray,
    target: float = 30.0,
    stop: float = 30.0,
) -> tuple[pd.DataFrame, dict]:
    c = close.to_numpy()
    sig = np.asarray(signal, dtype=bool)
    d = np.asarray(day)
    rows = []
    for i in np.where(sig)[0]:
        entry = c[i]
        outcome, pl = "unresolved", c[-1] - entry
        for j in range(i + 1, len(c)):
            if d[j] != d[i]:                       # don't carry a trade overnight
                outcome, pl = "unresolved", c[j - 1] - entry
                break
            move = c[j] - entry
            if move >= target:
                outcome, pl = "win", target
                break
            if move <= -stop:
                outcome, pl = "loss", -stop
                break
        rows.append({"bar": int(i), "entry": entry, "pl": pl, "outcome": outcome})

    res = pd.DataFrame(rows)
    if res.empty:
        return res, {"n": 0, "win_rate": float("nan"), "avg_pts": float("nan"),
                     "total_pts": 0.0, "wins": 0, "losses": 0, "unresolved": 0}
    summ = {
        "n": len(res),
        "wins": int((res["outcome"] == "win").sum()),
        "losses": int((res["outcome"] == "loss").sum()),
        "unresolved": int((res["outcome"] == "unresolved").sum()),
        "win_rate": (res["outcome"] == "win").mean(),
        "avg_pts": res["pl"].mean(),
        "total_pts": res["pl"].sum(),
    }
    return res, summ
