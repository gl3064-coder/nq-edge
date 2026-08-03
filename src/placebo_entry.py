r"""
PLACEBO ENTRY TEST for the frozen bot. Measurement only — does not touch the
strategy, and cannot improve its number.

The question
------------
The frozen bot is LONG ONLY (`longs only in up-context; downtrends = stand
down`). Its t-stat of 1.92 gross / 1.45 net compares the strategy against
ZERO. It has never been compared against the obvious alternative: buying at a
random moment in the same window and applying the same exit.

If a coin-flip entry with the same +30/-20 bracket earns the same points per
trade, then the signal (tape >= 0.10, leg_age <= 30) contributes nothing and
the edge is intraday drift in a rising market. This is the same control that
was run on the News Corpus study on 2026-07-28, where always-long turned out
to explain most of an apparent Sharpe of 3.08.

Design
------
- Same session window as the frozen bot: 09:30-12:00 ET, weekdays.
- Same bracket: +30 target / -20 stop, evaluated on subsequent bars.
- Same trade rate: 235 trades over ~135 sessions = 1.74 entries per session.
- Entries drawn uniformly at random from eligible bars in the window.
- 2,000 simulated runs, each a full 235-trade sample, giving the null
  distribution of "mean points per trade with no signal at all".

Conservative on ambiguity: if a bar's range spans both the target and the
stop, the STOP is assumed to fill first. That biases the placebo DOWN, which
is the safe direction — it makes the strategy look better by comparison, so
any conclusion against the strategy is not an artefact of this choice.

Trades still open at the 12:00 cutoff are closed at that bar's close, matching
the bot's session boundary.

Usage:
    python src/placebo_entry.py
    python src/placebo_entry.py --runs 5000 --seed 7
"""

from __future__ import annotations

import argparse
import glob
import os
from datetime import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# ---- frozen bot constants, copied from significance_audit.py --------------
TARGET_PTS = 30.0
STOP_PTS = 20.0
SESSION_START = time(9, 30)
SESSION_END = time(12, 0)
N_TRADES = 235            # frozen bot's historical trade count
MEAN_GROSS = 3.08         # frozen bot, pts/trade, gross
MEAN_NETCOST = 2.33       # frozen bot, pts/trade, after ~0.75pt round trip
COST_PTS = 0.75


def load_bars() -> pd.DataFrame:
    """Concatenate the NQ contract files, dropping overlapping duplicates."""
    frames = []
    for f in sorted(glob.glob(os.path.join(DATA, "bars_NQ_*.pkl"))):
        frames.append(pd.read_pickle(f))
    bars = pd.concat(frames).sort_index()
    bars = bars[~bars.index.duplicated(keep="first")]
    return bars


def session_slices(bars: pd.DataFrame) -> list[np.ndarray]:
    """One array of (open, high, low, close) rows per eligible session."""
    t = bars.index.time
    mask = (t >= SESSION_START) & (t <= SESSION_END) & (bars.index.dayofweek < 5)
    win = bars.loc[mask, ["open", "high", "low", "close"]]
    out = []
    for _, day in win.groupby(win.index.normalize()):
        if len(day) >= 30:          # skip holidays / stub sessions
            out.append(day.to_numpy(dtype=float))
    return out


def run_bracket(sess: np.ndarray, i: int) -> float:
    """Enter long at bar i's open; return points from a +30/-20 bracket.

    Stop is checked before target within the same bar (conservative)."""
    entry = sess[i, 0]
    tgt, stp = entry + TARGET_PTS, entry - STOP_PTS
    for j in range(i, len(sess)):
        if sess[j, 2] <= stp:       # low breached the stop
            return -STOP_PTS
        if sess[j, 1] >= tgt:       # high reached the target
            return TARGET_PTS
    return sess[-1, 3] - entry      # session cutoff, close it out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    bars = load_bars()
    sessions = session_slices(bars)
    if not sessions:
        raise SystemExit("no eligible sessions found")

    # Precompute every possible entry once; sampling then costs nothing.
    print(f"loading  {len(bars):,} bars, {len(sessions)} sessions "
          f"({bars.index[0].date()} -> {bars.index[-1].date()})")
    print("precomputing every possible entry in the window...")
    pool = np.concatenate([
        np.array([run_bracket(s, i) for i in range(len(s) - 1)])
        for s in sessions
    ])
    print(f"  {len(pool):,} candidate entries\n")

    rng = np.random.default_rng(args.seed)
    means = np.array([
        rng.choice(pool, size=N_TRADES, replace=False).mean()
        for _ in range(args.runs)
    ])

    lo, hi = np.percentile(means, [2.5, 97.5])
    pct = (means < MEAN_GROSS).mean() * 100
    pool_net = pool.mean() - COST_PTS

    w = "=" * 66
    print(w)
    print("PLACEBO ENTRY TEST — frozen bot vs. random entry, same bracket")
    print(w)
    print(f"  window               09:30-12:00 ET, +{TARGET_PTS:.0f}/-{STOP_PTS:.0f}")
    print(f"  simulated runs       {args.runs:,} x {N_TRADES} trades")
    print()
    print(f"  RANDOM entry, gross  {pool.mean():+.2f} pts/trade")
    print(f"    95% range of runs  [{lo:+.2f}, {hi:+.2f}]")
    print(f"  FROZEN BOT, gross    {MEAN_GROSS:+.2f} pts/trade")
    print(f"  edge over random     {MEAN_GROSS - pool.mean():+.2f} pts/trade")
    print(f"  bot's percentile     {pct:.1f}%")
    print()
    print(f"  RANDOM entry, net    {pool_net:+.2f} pts/trade")
    print(f"  FROZEN BOT, net      {MEAN_NETCOST:+.2f} pts/trade")
    print(f"  edge over random     {MEAN_NETCOST - pool_net:+.2f} pts/trade")
    print()
    print(w)
    print("HOW TO READ THIS")
    print(w)
    if pct >= 95:
        print("  The signal beats random entry. The edge is not just drift.")
    elif pct >= 80:
        print("  The signal is ahead of random entry but not decisively so at")
        print("  this sample size. Suggestive, not settled.")
    else:
        print("  The signal does NOT clearly beat buying at a random moment in")
        print("  the same window with the same bracket. Most of the reported")
        print("  points per trade is available without the signal at all.")
    print()
    print("  This is a placebo test, not a re-optimisation. It can only lower")
    print("  the strategy's standing, never raise it, so it is safe to run on")
    print("  a spent sample. It does not touch the pre-registration gate.")


if __name__ == "__main__":
    main()
