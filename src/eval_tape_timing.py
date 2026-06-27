"""
eval_tape_timing.py — does entering at the tape turn beat the late structural signal?

Head-to-head on the same sessions, same exit (30/20):
  structural  = drawdown-filtered higher-low (fires after confirmation, ~late)
  tape-timing = fire when tape flips green in a pullback (fires at the turn, earlier)

Needs bars with `buy_delta` — reprocess ticks.py first so the pkls carry it.

Run:  python src/eval_tape_timing.py
"""
from __future__ import annotations

from datetime import time
from pathlib import Path

import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter
from tape_timing import tape_timing_signal
from scorer import score

DATA = Path(__file__).resolve().parent.parent / "data"
SESSION = (time(9, 30), time(12, 0))
FILES = [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]


def main():
    close, day, sB, sT = [], [], [], []
    for name, md in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if md:
            m = m[m.index.date >= pd.Timestamp(md).date()]
        for d, grp in m.groupby(m.index.date):
            c = grp["close"].reset_index(drop=True)
            out = up_context(c, fast=20, slow=50, slope_lookback=10)
            B = drawdown_filter(out["close"], higher_low_signal(out["close"], out["up_context"]))
            T = tape_timing_signal(out["close"], out["up_context"],
                                   grp["buy_delta"].reset_index(drop=True))
            close.append(out["close"]); sB.append(B); sT.append(T)
            day.append(pd.Series(f"{name}_{d}", index=out.index))
    close = pd.concat(close, ignore_index=True); day = pd.concat(day, ignore_index=True)
    sB = pd.concat(sB, ignore_index=True); sT = pd.concat(sT, ignore_index=True)

    print(f"same sessions | exit 30/20\n")
    print(f"{'entry method':<34}{'trades':>7}{'win%':>7}{'avg':>8}{'total':>9}")
    print("-" * 65)
    for nm, s in [("structural higher-low (late)", sB),
                  ("tape-timing (enter at the turn)", sT)]:
        _, r = score(close, s, day, target=30, stop=20)
        print(f"{nm:<34}{r['n']:>7}{r['win_rate']*100:>6.0f}%"
              f"{r['avg_pts']:>8.1f}{r['total_pts']:>9.0f}")


if __name__ == "__main__":
    main()
