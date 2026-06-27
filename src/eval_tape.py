"""
eval_tape.py — does condition #4 (tape green) sharpen the entries?

Reconstructs the tape read from the tick files (Last vs Bid/Ask → per-bar buy_delta) and
tests whether requiring "tape was buying" at the signal improves the −EV automated entries.
Proof run on the June file (small/fast); if it helps, reprocess all and add #4 for real.

Run:  python src/eval_tape.py
"""
from __future__ import annotations

from datetime import time

import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars, REPLAY_DIR
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter
from scorer import score

SESSION = (time(9, 30), time(12, 0))


def main():
    bars = load_bars(REPLAY_DIR / "NQ 09-26.Last.txt")  # June, now with buy_delta
    t = bars.index
    m = bars[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]

    close, day, sig, tape = [], [], [], []
    for d, grp in m.groupby(m.index.date):
        c = grp["close"].reset_index(drop=True)
        out = up_context(c, fast=20, slow=50, slope_lookback=10)
        s = drawdown_filter(out["close"], higher_low_signal(out["close"], out["up_context"]))
        bd = grp["buy_delta"].reset_index(drop=True).fillna(0).rolling(3, min_periods=1).mean()
        close.append(out["close"]); sig.append(s); tape.append(bd)
        day.append(pd.Series(f"jun_{d}", index=out.index))
    close = pd.concat(close, ignore_index=True); day = pd.concat(day, ignore_index=True)
    sig = pd.concat(sig, ignore_index=True); tape = pd.concat(tape, ignore_index=True)

    print(f"June sessions | exit 30/20\n")
    print(f"{'entry filter':<26}{'trades':>7}{'win%':>7}{'avg':>8}{'total':>9}")
    print("-" * 57)
    _, b0 = score(close, sig, day, target=30, stop=20)
    print(f"{'B: no tape':<26}{b0['n']:>7}{b0['win_rate']*100:>6.0f}%{b0['avg_pts']:>8.1f}{b0['total_pts']:>9.0f}")
    for thr in [0.0, 0.2, 0.4]:
        c4 = sig & (tape > thr)
        _, s = score(close, c4, day, target=30, stop=20)
        print(f"{f'B + tape buy_delta>{thr}':<26}{s['n']:>7}{s['win_rate']*100:>6.0f}%"
              f"{s['avg_pts']:>8.1f}{s['total_pts']:>9.0f}")


if __name__ == "__main__":
    main()
