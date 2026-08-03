"""
experiment_entry_fill.py — does a LIMIT entry back at the pullback low beat
MARKET-at-arrow?

The green arrow fires k bars AFTER the pivot low it confirms, so its price is
structurally above the actual pullback low. The user's discretionary edge (and his
Note-1) is buying back down toward that low instead of filling at the arrow. This tests
whether that better fill is a measurable edge — and the honest cost of it: the limit
misses the signals that never come back down.

Two entries per historical green arrow, same signal, same exit:
  - MARKET   : fill at the arrow bar's close (what the live bot does today).
  - LIMIT(buf): resting buy at (pivot_low + buf); fills if any of the next FILL_WINDOW
                bars trades its low <= the limit, else the trade is SKIPPED.

Exit for both: fixed +TARGET / -STOP first-touch on real OHLC, same session only.
This is conservative vs the live Trail30 (which lets winners run past +30) — so a limit
edge here would only widen under Trail30. Flagged, not hidden.

Reports, per buffer:
  - PAIRED (filled signals only): limit vs market on the SAME trades -> pure fill quality.
  - FULL STRATEGY (all arrows): market takes every arrow; limit takes only fills, misses
    earn 0 -> the practical net, after paying for missed runners.

Run:  python src/experiment_entry_fill.py
"""
from __future__ import annotations

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal, PIVOT_K
from drawdown import drawdown_filter

DATA = Path(__file__).resolve().parent.parent / "data"
SESSION = (time(9, 30), time(12, 0))
FILES = [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]

STOP = 20.0          # his live stop
TARGET = 30.0        # fixed target (conservative vs Trail30)
FILL_WINDOW = 12     # bars (~4 min on 20s) for the limit to fill
BUFFERS = [0.0, 2.0, 3.0, 5.0]   # limit = pivot_low + buffer


def exit_first_touch(entry: float, high: np.ndarray, low: np.ndarray,
                     close: np.ndarray, start: int) -> tuple[str, float]:
    """Fixed +TARGET / -STOP, first touch on OHLC from bar `start` to end of day.
    Same-bar target+stop -> assume stop first (conservative). Unresolved -> last close."""
    tp, sl = entry + TARGET, entry - STOP
    for j in range(start, len(close)):
        if low[j] <= sl:
            return "loss", -STOP
        if high[j] >= tp:
            return "win", TARGET
    return "unresolved", float(close[-1] - entry)


def main() -> None:
    # accumulate per-arrow rows
    rows = []
    arrows = 0
    for name, mindate in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if mindate:
            m = m[m.index.date >= pd.Timestamp(mindate).date()]
        for d, grp in m.groupby(m.index.date):
            out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
            a = higher_low_signal(out["close"], out["up_context"])
            sig = drawdown_filter(out["close"], a)
            g = grp.loc[out.index]
            close = out["close"].to_numpy()
            high = g["high"].to_numpy()
            low = g["low"].to_numpy()
            sig_arr = sig.to_numpy()
            n = len(close)
            for i in np.where(sig_arr)[0]:
                pivot = i - PIVOT_K
                if pivot < 0 or i + 1 >= n:
                    continue
                arrows += 1
                pivot_low = float(close[pivot])
                arrow_price = float(close[i])
                _, m_pl = exit_first_touch(arrow_price, high, low, close, i + 1)
                row = {"day": f"{name}_{d}", "gap": arrow_price - pivot_low,
                       "market_pl": m_pl}
                for buf in BUFFERS:
                    limit = pivot_low + buf
                    fill_j = None
                    for j in range(i + 1, min(i + 1 + FILL_WINDOW, n)):
                        if low[j] <= limit:
                            fill_j = j
                            break
                    if fill_j is None:
                        row[f"lim{buf:g}_filled"] = False
                        row[f"lim{buf:g}_pl"] = np.nan
                    else:
                        _, l_pl = exit_first_touch(limit, high, low, close, fill_j + 1)
                        row[f"lim{buf:g}_filled"] = True
                        row[f"lim{buf:g}_pl"] = l_pl
                rows.append(row)

    df = pd.DataFrame(rows)
    print(f"\ngreen arrows: {arrows} | fixed {TARGET:.0f}/{STOP:.0f} exit | "
          f"fill window {FILL_WINDOW} bars")
    print(f"median arrow-above-pivot gap: {df['gap'].median():.1f} pts "
          f"(how far above the pullback low the arrow fills)\n")

    def stats(pl: pd.Series) -> str:
        pl = pl.dropna()
        if len(pl) == 0:
            return "no trades"
        wins = (pl == TARGET).sum()
        losses = (pl == -STOP).sum()
        wr = wins / len(pl) * 100
        return (f"n={len(pl):>4}  win%={wr:>4.0f}  avg={pl.mean():>6.2f}  "
                f"total={pl.sum():>8.0f}  ({wins}W/{losses}L)")

    print("MARKET-at-arrow (all arrows):")
    print("  " + stats(df["market_pl"]))
    print()
    print(f"{'strategy':<16}{'fill%':>7}  paired-vs-market (same fills)      full-net")
    print("-" * 88)
    for buf in BUFFERS:
        f = df[f"lim{buf:g}_filled"]
        pl = df[f"lim{buf:g}_pl"]
        fill_rate = f.mean() * 100
        # paired: same signals the limit filled
        paired = df[f]
        lim_total_paired = paired[f"lim{buf:g}_pl"].sum()
        mkt_total_paired = paired["market_pl"].sum()
        lim_avg = paired[f"lim{buf:g}_pl"].mean()
        mkt_avg = paired["market_pl"].mean()
        # full strategy: limit total over ALL arrows (misses = 0)
        full_limit = pl.dropna().sum()
        full_market = df["market_pl"].sum()
        print(f"limit +{buf:<4g}    {fill_rate:>5.0f}%   "
              f"lim {lim_avg:>6.2f} vs mkt {mkt_avg:>6.2f}/trade "
              f"(d{lim_avg - mkt_avg:>+5.2f})   "
              f"lim {full_limit:>7.0f} vs mkt {full_market:>6.0f}")


if __name__ == "__main__":
    main()
