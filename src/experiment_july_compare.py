"""
experiment_july_compare.py — run the bot on the REAL July 8-9 sessions the user traded,
to fill the Me-vs-Bot tracker with actual Bot numbers.

Bot = codified signal (up-context + higher-low + drawdown) + strong-tape gate (buy_delta
>= 0.10, the global top-tercile threshold from the 591 historical arrows — a PRE-SET rule,
not fit to July). Reports per day and per hour, under both exits (Trail30 = his live ATM,
and fixed 30/20). Also shows the un-gated control for reference.

Run:  python src/experiment_july_compare.py
"""
from __future__ import annotations

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from context import up_context
from location import higher_low_signal, PIVOT_K
from drawdown import drawdown_filter
from experiment_entry_fill import exit_first_touch, SESSION
from experiment_tape_gate_trail import exit_trail30

_DEFAULT = Path(__file__).resolve().parent.parent / "Replay Data" / "NQ July 8-July 9th.txt"
FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT
TAPE_THR = 0.10
HOURS = {9: "9-10", 10: "10-11", 11: "11-12"}


def main() -> None:
    bars = load_bars(FILE)
    t = bars.index
    m = bars[(t.time >= SESSION[0]) & (t.time <= SESSION[1])]

    rows = []
    for d, grp in m.groupby(m.index.date):
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        a = higher_low_signal(out["close"], out["up_context"])
        sig = drawdown_filter(out["close"], a)
        g = grp.loc[out.index]
        close = out["close"].to_numpy()
        high, low = g["high"].to_numpy(), g["low"].to_numpy()
        bd = g["buy_delta"].to_numpy()
        hrs = g.index.hour.to_numpy()
        n = len(close)
        for i in np.where(sig.to_numpy())[0]:
            if i - PIVOT_K < 0 or i + 1 >= n or i < 3:
                continue
            e = float(close[i])
            _, fx = exit_first_touch(e, high, low, close, i + 1)
            tr = exit_trail30(e, high, low, close, i + 1)
            rows.append({"day": str(d), "hour": int(hrs[i]),
                         "tape": float(np.nanmean(bd[i - 2:i + 1])),
                         "fixed": fx, "trail": tr})

    df = pd.DataFrame(rows)
    print(f"\nBot on {FILE.name} | tape gate >= {TAPE_THR} | session 9:30-12:00\n")
    for d in sorted(df["day"].unique()):
        dd = df[df["day"] == d]
        gg = dd[dd["tape"] >= TAPE_THR]
        print(f"=== {d} ===")
        print(f"  ALL arrows (control):   n={len(dd):>2}  "
              f"trail={dd['trail'].sum():>7.1f}  fixed={dd['fixed'].sum():>7.1f}")
        print(f"  GATED (strong tape):    n={len(gg):>2}  "
              f"trail={gg['trail'].sum():>7.1f}  fixed={gg['fixed'].sum():>7.1f}")
        for h, lab in HOURS.items():
            hh = gg[gg["hour"] == h]
            if len(hh):
                print(f"     gated {lab:<6} n={len(hh)}  "
                      f"trail={hh['trail'].sum():>6.1f}  fixed={hh['fixed'].sum():>6.1f}")
        print()


if __name__ == "__main__":
    main()
