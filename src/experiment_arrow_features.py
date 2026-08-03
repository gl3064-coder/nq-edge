"""
experiment_arrow_features.py — can a signal AT THE ARROW separate runners from returners?

Follow-up to experiment_entry_fill.py, which found: the money is in the arrows that RUN
(price never returns to the pullback low) — market-at-arrow makes ~+15/trade on those.
The arrows that RETURN (price comes back to the low) are ~breakeven at best even with a
perfect fill. So the automatable edge is a FILTER: take market only on arrows likely to
run / win, skip the rest.

This tests each feature available AT the arrow bar (no lookahead) against outcome:
  - tape        : mean buy_delta over the last 3 bars (aggressor pressure)
  - ctx_spread  : fast_ma - slow_ma (trend strength)
  - slope       : slow_ma - slow_ma[-10] (trend steepness)
  - dd_depth    : drop from prior high into the pullback low (pullback size)
  - gap         : arrow_price - pivot_low (how far above the low the arrow fills)
  - volume      : arrow-bar volume

For each feature we tercile the 591 arrows and report, per bucket: market win%,
market avg pts, and runner% (share that did NOT return to the low). A useful feature
shows a monotonic split — and, ideally, a top bucket whose market net flips positive.

Run:  python src/experiment_arrow_features.py
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
from drawdown import drawdown_filter, LOOKBACK
from experiment_entry_fill import exit_first_touch, TARGET, FILL_WINDOW, DATA, FILES, SESSION


def main() -> None:
    rows = []
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
            fast_ma = out["fast_ma"].to_numpy()
            slow_ma = out["slow_ma"].to_numpy()
            high = g["high"].to_numpy()
            low = g["low"].to_numpy()
            vol = g["volume"].to_numpy()
            bd = g["buy_delta"].to_numpy()
            n = len(close)
            for i in np.where(sig.to_numpy())[0]:
                pivot = i - PIVOT_K
                if pivot < 0 or i + 1 >= n or i < 10:
                    continue
                pivot_low = float(close[pivot])
                arrow_price = float(close[i])
                # outcome: market-at-arrow
                _, m_pl = exit_first_touch(arrow_price, high, low, close, i + 1)
                # runner = limit-at-low did NOT fill within window
                filled = any(low[j] <= pivot_low
                             for j in range(i + 1, min(i + 1 + FILL_WINDOW, n)))
                # features at the arrow (no lookahead)
                win_lo = close[max(0, pivot - LOOKBACK):pivot + 1]
                dd_depth = float(win_lo.max() - pivot_low)
                rows.append({
                    "tape": float(np.nanmean(bd[i - 2:i + 1])),
                    "ctx_spread": float(fast_ma[i] - slow_ma[i]),
                    "slope": float(slow_ma[i] - slow_ma[i - 10]),
                    "dd_depth": dd_depth,
                    "gap": arrow_price - pivot_low,
                    "volume": float(vol[i]),
                    "market_pl": m_pl,
                    "market_win": int(m_pl == TARGET),
                    "runner": int(not filled),
                })

    df = pd.DataFrame(rows)
    print(f"\narrows: {len(df)} | baseline market net: {df['market_pl'].sum():.0f} pts "
          f"| win% {df['market_win'].mean()*100:.0f} | runner% {df['runner'].mean()*100:.0f}\n")

    feats = ["tape", "ctx_spread", "slope", "dd_depth", "gap", "volume"]
    print(f"{'feature / tercile':<20}{'n':>5}{'mkt win%':>10}{'mkt avg':>9}"
          f"{'mkt net':>9}{'runner%':>9}")
    print("-" * 62)
    for f in feats:
        try:
            df["_b"] = pd.qcut(df[f], 3, labels=["low", "mid", "high"], duplicates="drop")
        except ValueError:
            continue
        for lab in ["low", "mid", "high"]:
            s = df[df["_b"] == lab]
            if len(s) == 0:
                continue
            print(f"{f + ' [' + lab + ']':<20}{len(s):>5}"
                  f"{s['market_win'].mean()*100:>9.0f}%"
                  f"{s['market_pl'].mean():>9.2f}{s['market_pl'].sum():>9.0f}"
                  f"{s['runner'].mean()*100:>8.0f}%")
        print()


if __name__ == "__main__":
    main()
