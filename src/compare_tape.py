"""
compare_tape.py — validate that the LIVE buy_delta (from NQTapeLogger in Market Replay)
matches the Python backtest buy_delta (ticks.py) for the same day.

Usage:
  python src/compare_tape.py "Replay Data/July 14.txt"
  (optional 2nd arg: path to the live log CSV; defaults to Replay Data/live_tape_log.csv)

The gate is a top-tercile RANK threshold, so the number that matters most is the SPEARMAN
(rank) correlation and the "strong-tape" set agreement, not exact value equality.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars

ROOT = Path(__file__).resolve().parent.parent
TICKFILE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Replay Data" / "July 14.txt"
LIVECSV = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "Replay Data" / "live_tape_log.csv"
TAPE_THR = 0.10

# --- live log (NT bar-close timestamps, ET local) ---
live = pd.read_csv(LIVECSV)
live["time"] = pd.to_datetime(live["time"])
live = live[live["volume"] > 0].copy()
print(f"live log: {len(live)} bars  {live['time'].min()} -> {live['time'].max()}")

# --- python backtest delta for the same day ---
pb = load_bars(TICKFILE)
pb.index = pb.index.tz_localize(None)          # ET naive, bar-START labels
pb = pb[pb["volume"] > 0][["buy_delta"]].rename(columns={"buy_delta": "py_delta"})

# NT labels bars at CLOSE, pandas at START. Try candidate offsets, keep the best match.
best = None
for off in (-20, 0, 20):
    key = live["time"] + pd.Timedelta(seconds=off)
    m = pd.DataFrame({"live": live["buy_delta"].to_numpy(),
                      "key": key.to_numpy()}).merge(
                      pb, left_on="key", right_index=True, how="inner")
    if best is None or len(m) > len(best[1]):
        best = (off, m)
off, m = best
print(f"\nmatched {len(m)} bars (alignment offset {off:+d}s)\n")

if len(m) < 10:
    print("Too few matched bars to judge. Check that the tick file and the replayed day "
          "are the SAME date, and that the log has realtime bars.")
    raise SystemExit

pear = m["live"].corr(m["py_delta"])
spear = m["live"].corr(m["py_delta"], method="spearman")
mad = (m["live"] - m["py_delta"]).abs().mean()

live_strong = m["live"] >= TAPE_THR
py_strong = m["py_delta"] >= TAPE_THR
agree = (live_strong == py_strong).mean() * 100
both = (live_strong & py_strong).sum()

print(f"Pearson corr (values):   {pear:.3f}")
print(f"Spearman corr (RANK):    {spear:.3f}   <- the one that matters for the gate")
print(f"mean abs difference:     {mad:.4f}")
print(f"strong-tape (>= {TAPE_THR}) agreement: {agree:.0f}%   "
      f"(py flagged {py_strong.sum()}, live flagged {live_strong.sum()}, both {both})")

print("\nVERDICT:")
if spear >= 0.9 and agree >= 85:
    print("  STRONG MATCH. The live tape ranks like the backtest. The gate transfers. "
          "The bot could exist live -> worth integrating + forward/auto testing.")
elif spear >= 0.75:
    print("  DECENT MATCH but not airtight. Live tracks the backtest directionally; a "
          "small live-vs-export bias exists. Re-derive the live top-tercile threshold on "
          "live-style deltas rather than reusing 0.10 literally, then it likely holds.")
else:
    print("  WEAK MATCH. The live delta does NOT rank like the backtest. The tape gate "
          "does not transfer as-is, which means the bot's measured edge was a backtest "
          "artifact. Better to learn this here than with a funded account.")
