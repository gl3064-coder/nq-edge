"""
experiment_rr.py — the pipeline AS a research engine.

Same drawdown-filtered signal as eval_real, but sweeps risk:reward (target/stop) against
the baseline to answer a real question: does a tighter stop (the user's "if it draws down
past 20 it hits 30, so I cut at 20" rule) actually help? Change ONE thing, compare.

Run:  python src/experiment_rr.py
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
FILES = [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]


def build_signal():
    """The baseline drawdown-filtered signal across all real sessions."""
    close, day, sig = [], [], []
    for name, md in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if md:
            m = m[m.index.date >= pd.Timestamp(md).date()]
        for d, grp in m.groupby(m.index.date):
            c = grp["close"].reset_index(drop=True)
            out = up_context(c, fast=20, slow=50, slope_lookback=10)
            s = drawdown_filter(out["close"],
                                higher_low_signal(out["close"], out["up_context"]))
            close.append(out["close"]); sig.append(s)
            day.append(pd.Series(f"{name}_{d}", index=out.index))
    return (pd.concat(close, ignore_index=True),
            pd.concat(sig, ignore_index=True),
            pd.concat(day, ignore_index=True))


def main():
    close, sig, day = build_signal()
    print(f"baseline signal: {int(sig.sum())} trades over the real sessions\n")
    print(f"{'target/stop':<16}{'R:R':>6}{'win%':>7}{'avg':>8}{'total':>9}")
    print("-" * 46)
    combos = [(30, 30), (30, 20), (30, 15), (45, 30), (20, 20), (15, 15)]
    for tgt, stp in combos:
        _, s = score(close, sig, day, target=tgt, stop=stp)
        tag = "  <- baseline" if (tgt, stp) == (30, 30) else ""
        tag = "  <- your DD-20 rule" if (tgt, stp) == (30, 20) else tag
        print(f"{f'{tgt}/{stp}':<16}{tgt/stp:>6.1f}{s['win_rate']*100:>6.0f}%"
              f"{s['avg_pts']:>8.1f}{s['total_pts']:>9.0f}{tag}")
    print("\nNote: R:R only redistributes win-rate vs win-size on a fixed set of entries.")
    print("It can't create edge a -EV entry lacks — real lift comes from better entries.")


if __name__ == "__main__":
    main()
