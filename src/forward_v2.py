"""
forward_v2.py — the Bot v2 FORWARD TEST. Run this per trading day alongside the journal.

v2 is the FROZEN candidate that beat the tape-only bot out-of-sample (2026-07-14 study):
  arrow = up_context + higher_low + drawdown (the standard signal, k=3, min_dd=10)
  gate  = strong tape (buy_delta >= 0.10, pre-set) AND young leg (leg_age <= 30 bars)
  exit  = Trail30 (matches the live ATM)

"leg_age" = consecutive up_context bars ending at the arrow. The <=30 cutoff (~10 min of
up-leg on 20s bars) is FROZEN — do NOT refit it per day. It was calibrated ONCE (2026-07-14
frozen-threshold scan): <=30 beat <=20/25/40 on total net AND was positive on all 3
independent contracts (per-contract stable, broad 25-30 plateau, not a mined value). An
outcome-triggered switch (tape-only-until-losses) was tested and REJECTED as knob-fitting
(result swung 2x on arbitrary switch logic); the clean frozen cutoff beat it outright. Prints v1 (all arrows) and the
tape-only bot for reference, plus v2, by day and hour. Feed the v2 number into the
"Bot v2 pts / trades" columns of the Me vs Bot (Daily) tracker.

Needs a Last-tick export WITH Bid/Ask (so buy_delta / the tape gate can be computed).
Run:  python src/forward_v2.py "Replay Data/<day>.txt"
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter
from experiment_entry_fill import SESSION
from experiment_tape_gate_trail import exit_trail30

TAPE_THR = 0.10   # frozen: pre-set top-tercile buy_delta
LEG_THR = 30      # frozen: skip legs older than ~30 bars (~10 min). Calibrated 2026-07-14.
HOURS = {9: "9-10", 10: "10-11", 11: "11-12", 12: "12-1"}

# --- TWO EXITS, BOTH REPORTED (added 2026-08-03) ---------------------------
# This file originally printed Trail30 only, labelled "matches the live ATM".
# That was wrong for the BOT. The frozen bot spec is FIXED +30/-20; Trail30 is
# the live DISCRETIONARY exit, a different population. It matters because the
# mechanical edge was ~zero under Trail30 - the fixed target was the lever -
# and the significance budget (t~1.9 on ~235 trades, ~1,000 needed for t>3.0)
# is denominated in fixed-exit points.
#
# FIXED is the bot's official number. TRAIL is kept because his own trades use
# the trailing ATM, so it is the right basis for the Me-vs-Bot comparison.
# Neither was chosen after seeing forward results; fixed was the spec first.
TARGET, STOP = 30.0, 20.0


def exit_fixed(entry: float, high, low, close, start: int) -> float:
    """Fixed +30 / -20. Stop checked before target on the same bar, matching
    exit_trail30's conservative same-bar convention. Unresolved -> last close."""
    for j in range(start, len(close)):
        if low[j] <= entry - STOP:
            return -STOP
        if high[j] >= entry + TARGET:
            return TARGET
    return float(close[-1] - entry)

_DEFAULT = Path(__file__).resolve().parent.parent / "Replay Data" / "July 14.txt"
FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT


def main() -> None:
    bars = load_bars(FILE)
    t = bars.index
    m = bars[(t.time >= SESSION[0]) & (t.time <= SESSION[1])]

    rows = []
    for d, grp in m.groupby(m.index.date):
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        upc = out["up_context"].to_numpy().astype(bool)
        a = higher_low_signal(out["close"], out["up_context"], k=3)
        sig = drawdown_filter(out["close"], a, k=3, min_dd=10)
        close = out["close"].to_numpy()
        g = grp.loc[out.index]
        high, low = g["high"].to_numpy(), g["low"].to_numpy()
        bd = g["buy_delta"].to_numpy()
        hrs = g.index.hour.to_numpy()
        n = len(close)
        run = np.zeros(n, dtype=int)
        for j in range(n):
            run[j] = run[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            e = float(close[i])
            rows.append({"day": str(d), "hour": int(hrs[i]),
                         "tape": float(np.nanmean(bd[i - 2:i + 1])),
                         "leg_age": int(run[i]),
                         "trail": exit_trail30(e, high, low, close, i + 1),
                         "fixed": exit_fixed(e, high, low, close, i + 1)})

    df = pd.DataFrame(rows)
    print(f"\nBot v2 forward test | {FILE.name} | tape>={TAPE_THR} & leg_age<={LEG_THR}")
    print("FIXED = the bot's official number (frozen spec). TRAIL = his live ATM basis.\n")
    for d in sorted(df["day"].unique()):
        dd = df[df["day"] == d]
        tape = dd[dd.tape >= TAPE_THR]
        v2 = dd[(dd.tape >= TAPE_THR) & (dd.leg_age <= LEG_THR)]
        print(f"=== {d} ===                     FIXED     trail")
        print(f"  v1 (all arrows):   n={len(dd):>2}     {dd['fixed'].sum():>7.1f}  {dd['trail'].sum():>8.1f}")
        print(f"  bot (tape only):   n={len(tape):>2}     {tape['fixed'].sum():>7.1f}  {tape['trail'].sum():>8.1f}")
        print(f"  BOT v2 (tape+leg): n={len(v2):>2}     {v2['fixed'].sum():>7.1f}  {v2['trail'].sum():>8.1f}   <-- log both")
        for h, lab in HOURS.items():
            vv = v2[v2.hour == h]
            if len(vv):
                print(f"     v2 {lab:<6} n={len(vv)}     {vv['fixed'].sum():>7.1f}  {vv['trail'].sum():>8.1f}")
        print()


if __name__ == "__main__":
    main()
