"""
experiment_atr_exits.py — do ATR-scaled exits and/or the regime gates beat Trail30?

Two pre-registered questions (NOT an open exit sweep — the 6/25 lesson stands):

1. EXITS: scale the whole Trail30 structure by volatility at entry.
   stop = k * avgATR(15) at entry, arm trailing at 1.5*stop, trail = stop —
   the exact 20/30/20 proportions, just sized to the tape. k in {1.5, 2.0, 2.5};
   k=2.0 reproduces the 20-pt stop at the typical ~10-pt avg ATR, so it's the
   "same rule, vol-aware" anchor. Mechanism (user's 6/29 insight): a flat 20 is
   a noise stop in high ATR and oversized in dead tape.

2. GATES: apply the indicator's regime suppression to entries — a candle is hot
   (TR > 18) or dead (TR < 5); >= 5 of the last 15 bars in either class blocks
   the entry. Does gating change the per-trade Sharpe, i.e. is the combined
   strategy better than the raw signal?

Scoring is close-only on 20s bars, same as every prior experiment, so numbers
are directly comparable to the Trail30 baseline (+2,088 total).

Run:  python src/experiment_atr_exits.py
"""
from __future__ import annotations

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

DATA = Path(__file__).resolve().parent.parent / "data"
SESSION = (time(9, 30), time(12, 0))
FILES = [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]

# Indicator gate params (mirror NQEdgeCoPilot.cs defaults exactly).
HOT_ATR, DEAD_ATR = 18.0, 5.0
REGIME_WINDOW, REGIME_COUNT = 15, 5


def build_sessions():
    """Signal + true-range series per session, concatenated with day labels."""
    close, day, sig, atr_avg, blocked = [], [], [], [], []
    for name, md in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if md:
            m = m[m.index.date >= pd.Timestamp(md).date()]
        for d, grp in m.groupby(m.index.date):
            g = grp.reset_index(drop=True)
            c = g["close"]
            out = up_context(c, fast=20, slow=50, slope_lookback=10)
            s = drawdown_filter(out["close"],
                                higher_low_signal(out["close"], out["up_context"]))

            # ATR(1) equivalent: per-bar true range.
            prev_c = g["close"].shift(1)
            tr = pd.concat([g["high"] - g["low"],
                            (g["high"] - prev_c).abs(),
                            (g["low"] - prev_c).abs()], axis=1).max(axis=1)
            avg = tr.rolling(REGIME_WINDOW, min_periods=1).mean()

            hot_n = (tr > HOT_ATR).rolling(REGIME_WINDOW, min_periods=1).sum()
            dead_n = (tr < DEAD_ATR).rolling(REGIME_WINDOW, min_periods=1).sum()
            blk = (hot_n >= REGIME_COUNT) | (dead_n >= REGIME_COUNT)

            close.append(out["close"]); sig.append(s.reindex(out.index, fill_value=False))
            atr_avg.append(avg.reindex(out.index)); blocked.append(blk.reindex(out.index, fill_value=False))
            day.append(pd.Series(f"{name}_{d}", index=out.index))
    cat = lambda xs: pd.concat(xs, ignore_index=True)
    return cat(close), cat(sig), cat(day), cat(atr_avg), cat(blocked)


def sim_trail_after(close, entries, day, stops, arm_mult=1.5):
    """Trail30 structure with a per-entry stop size: fixed stop until +arm_mult*stop,
    then trail stop-distance behind the peak. Returns per-trade P/L array."""
    c = close.to_numpy(); d = np.asarray(day)
    pls, sizes = [], []
    for i, init_stop in zip(entries, stops):
        entry, peak = c[i], c[i]
        stop, on, pl = entry - init_stop, False, None
        for j in range(i + 1, len(c)):
            if d[j] != d[i]:
                pl = c[j - 1] - entry; break
            px = c[j]
            peak = max(peak, px)
            if not on and px - entry >= arm_mult * init_stop:
                on = True
            if on:
                stop = max(stop, peak - init_stop)
            if px <= stop:
                pl = stop - entry; break
        if pl is None:
            pl = c[-1] - entry
        pls.append(pl); sizes.append(init_stop)
    return np.array(pls), np.array(sizes)


def stats(pls, days_of_trades):
    if len(pls) == 0:
        return dict(n=0, win=np.nan, avg=np.nan, total=0.0, sharpe=np.nan, dsharpe=np.nan)
    daily = pd.Series(pls).groupby(pd.Series(days_of_trades)).sum()
    return dict(
        n=len(pls), win=(pls > 0).mean(), avg=pls.mean(), total=pls.sum(),
        sharpe=pls.mean() / pls.std(ddof=1) if len(pls) > 1 else np.nan,
        dsharpe=daily.mean() / daily.std(ddof=1) if len(daily) > 1 else np.nan,
    )


def main():
    close, sig, day, atr_avg, blocked = build_sessions()
    all_idx = np.where(sig.to_numpy())[0]
    gated_idx = np.where((sig & ~blocked).to_numpy())[0]
    d = day.to_numpy(); aa = atr_avg.to_numpy()
    print(f"signal entries: {len(all_idx)} raw | {len(gated_idx)} after regime gates "
          f"({len(all_idx) - len(gated_idx)} blocked)\n")

    header = f"{'exit rule':<26}{'gate':>6}{'n':>6}{'win%':>7}{'avg':>8}{'total':>9}{'tSharpe':>9}{'dSharpe':>9}{'~stop':>7}"
    print(header); print("-" * len(header))

    for gate, idx in [("off", all_idx), ("ON", gated_idx)]:
        # baseline: the real Trail30 (flat 20-pt stop, arm +30, trail 20)
        pls, sz = sim_trail_after(close, idx, day, np.full(len(idx), 20.0))
        s = stats(pls, d[idx])
        print(f"{'Trail30 flat 20':<26}{gate:>6}{s['n']:>6}{s['win']*100:>6.0f}%"
              f"{s['avg']:>8.2f}{s['total']:>9.0f}{s['sharpe']:>9.3f}{s['dsharpe']:>9.3f}{sz.mean():>7.1f}")
        for k in (1.5, 2.0, 2.5):
            stops = k * aa[idx]
            pls, sz = sim_trail_after(close, idx, day, stops)
            s = stats(pls, d[idx])
            print(f"{f'ATR-scaled k={k}':<26}{gate:>6}{s['n']:>6}{s['win']*100:>6.0f}%"
                  f"{s['avg']:>8.2f}{s['total']:>9.0f}{s['sharpe']:>9.3f}{s['dsharpe']:>9.3f}{sz.mean():>7.1f}")
        print()

    print("tSharpe = per-trade mean/std; dSharpe = per-day mean/std (days with trades).")
    print("All in-sample, pre-cost, close-only fills. Compare rows, not to live P/L.")


if __name__ == "__main__":
    main()
