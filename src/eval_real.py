"""
eval_real.py — first REAL win-rate verdict on the codified signal.

Runs context (#1) + higher-low (#2) + drawdown (#3) on real 20-second NQ bars across
every NY-morning session in all three tick files, then scores +30/-30. Compares the
signal with vs without the drawdown filter. 20s periods (fast 20 / slow 50) per the
user's calibration. Close-only scoring is fine here — 20s bars have tiny intrabar range.

Run:  python src/eval_real.py
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
from scorer import score

DATA = Path(__file__).resolve().parent.parent / "data"
SESSION = (time(9, 30), time(12, 0))
# (pickle, min_date) — 06-26 starts after 03-26 ends to avoid double-counting the roll.
FILES = [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]


def main() -> None:
    close, day, sigA, sigB = [], [], [], []
    mornings = 0
    for name, mindate in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if mindate:
            m = m[m.index.date >= pd.Timestamp(mindate).date()]
        for d, grp in m.groupby(m.index.date):
            c = grp["close"].reset_index(drop=True)
            out = up_context(c, fast=20, slow=50, slope_lookback=10)
            a = higher_low_signal(out["close"], out["up_context"])
            bb = drawdown_filter(out["close"], a)
            close.append(out["close"]); sigA.append(a); sigB.append(bb)
            day.append(pd.Series(f"{name}_{d}", index=out.index))
            mornings += 1

    close = pd.concat(close, ignore_index=True)
    day = pd.concat(day, ignore_index=True)
    sigA = pd.concat(sigA, ignore_index=True)
    sigB = pd.concat(sigB, ignore_index=True)

    _, sa = score(close, sigA, day)
    _, sb = score(close, sigB, day)

    def line(nm, s):
        return (f"{nm:<22}{s['n']:>7}{s['win_rate']*100:>7.0f}%"
                f"{s['avg_pts']:>9.1f}{s['total_pts']:>8.0f}"
                f"   ({s['wins']}W/{s['losses']}L/{s['unresolved']}U)")

    print(f"\nmornings: {mornings} | 20s bars | target/stop 30/30")
    print(f"{'signal':<22}{'trades':>7}{'win%':>8}{'avg':>9}{'total':>8}")
    print("-" * 64)
    print(line("A: cond #1+#2", sa))
    print(line("B: +#3 drawdown", sb))


if __name__ == "__main__":
    main()
