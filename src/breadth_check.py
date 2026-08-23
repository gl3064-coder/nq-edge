"""breadth_check.py — does gold actually diversify NQ, and does it survive costs?

Two questions, in order, because the second only matters if the first passes:

1. CORRELATION. Breadth (the sqrt-N law) needs UNCORRELATED bets. Gold's edge
   showed up only in the 09:30-12:00 NY window and inverted in London, which is
   what it would look like if gold were simply tracking equities during equity
   hours. If the daily P/L streams correlate, gold is not a second bet, it is
   NQ wearing a different ticker, and adding it buys nothing.

2. COSTS. Gross of costs gold was +0.165R at t=2.42. Crude was +0.165R and died
   after costs. Gold's cost ratio is better (9.3 vs 5.7) so it should survive
   further, but "further" is not "enough".

Descriptive measurement only. No new configuration is searched, nothing is
tuned, so this sits inside the pre-registration gate's exemption.

Costs, round trip, in price units:
    NQ    0.75 pt   (1 tick 0.25 + commission)  over a 20 pt stop  = 0.0375R
    GC    0.14      (1 tick 0.10 + ~$4/rt over 100oz) over its ATR stop
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from databento_bars import load_bars_databento
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

NY = ("09:30", "12:00")
LEG_THR = 30
NQ_COST_R = 0.75 / 20.0          # 0.0375R
GC_COST_PRICE = 0.14             # 1 tick + commission, per oz


def exit_fixed(entry, high, low, close, start, stop, target):
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def daily_R(bars, stop, target, min_dd, label):
    """Run frozen V2 on NY-session bars, return a per-day R series."""
    m = bars.between_time(*NY)
    thr = float(np.nanpercentile(m["buy_delta"].to_numpy(), 66.67))
    rows = []
    for d, grp in m.groupby(m.index.date):
        if len(grp) < 60:
            continue
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        upc = out["up_context"].to_numpy().astype(bool)
        a = higher_low_signal(out["close"], out["up_context"], k=3)
        sig = drawdown_filter(out["close"], a, k=3, min_dd=min_dd)
        close = out["close"].to_numpy()
        g = grp.loc[out.index]
        high, low = g["high"].to_numpy(), g["low"].to_numpy()
        bd = g["buy_delta"].to_numpy()
        n = len(close)
        run = np.zeros(n, dtype=int)
        for j in range(n):
            run[j] = run[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            if np.nanmean(bd[i - 2:i + 1]) < thr or run[i] > LEG_THR:
                continue
            pl = exit_fixed(float(close[i]), high, low, close, i + 1, stop, target)
            rows.append({"day": pd.Timestamp(d), "R": pl / stop})
    df = pd.DataFrame(rows)
    print(f"{label}: {len(df)} trades over {df['day'].nunique()} days "
          f"(tape gate {thr:.4f})")
    return df


def stats(daily: pd.Series, label: str):
    mu, sd = daily.mean(), daily.std(ddof=1)
    sharpe = mu / sd * np.sqrt(252) if sd > 0 else float("nan")
    t = mu / (sd / np.sqrt(len(daily))) if sd > 0 else float("nan")
    print(f"  {label:26} days={len(daily):>4}  {mu:+.4f}R/day  "
          f"t={t:>5.2f}  ann.Sharpe={sharpe:>6.2f}")
    return sharpe


def main():
    # ---- gold ----
    gfiles = sorted(glob.glob("Replay Data/databento/GC_n0_tbbo_2026-*.csv"))
    gb = pd.concat([load_bars_databento(f) for f in gfiles]).sort_index()
    gb = gb[~gb.index.duplicated(keep="first")]
    g_atr = float(pd.concat([gb["high"] - gb["low"],
                             (gb["high"] - gb["close"].shift()).abs(),
                             (gb["low"] - gb["close"].shift()).abs()],
                            axis=1).max(axis=1).median())
    g_stop = 20.0 / 17.0 * g_atr
    gold = daily_R(gb, g_stop, 1.5 * g_stop, 10.0 / 17.0 * g_atr, "GOLD")
    gc_cost_R = GC_COST_PRICE / g_stop

    # ---- NQ, non-overlapping front-month windows ----
    p = {k: pd.read_pickle(f"data/bars_NQ_{k}.pkl") for k in ("03-26", "06-26", "09-26")}
    nq = pd.concat([
        p["03-26"][p["03-26"].index < "2026-03-12"],
        p["06-26"][(p["06-26"].index >= "2026-03-12") & (p["06-26"].index < "2026-06-08")],
        p["09-26"][p["09-26"].index >= "2026-06-08"],
    ]).sort_index()
    nq = nq[~nq.index.duplicated(keep="first")]
    nqd = daily_R(nq, 20.0, 30.0, 10.0, "NQ  ")

    # ---- align on shared days ----
    G = gold.groupby("day")["R"].sum()
    N = nqd.groupby("day")["R"].sum()
    gn = gold.groupby("day")["R"].size()
    nn = nqd.groupby("day")["R"].size()
    days = G.index.intersection(N.index)
    print(f"\noverlapping trading days: {len(days)}")

    Gg, Nn = G.loc[days], N.loc[days]
    print("\n--- GROSS of costs ---")
    sg = stats(Gg, "gold  (daily R)")
    sn = stats(Nn, "NQ    (daily R)")
    sc = stats((Gg + Nn) / 2, "combined (equal weight)")

    rho = float(np.corrcoef(Gg, Nn)[0, 1])
    print(f"\n  daily P/L correlation gold vs NQ:  rho = {rho:+.3f}")
    print(f"  breadth only pays if rho is low. combined/best-single = "
          f"{sc / max(sg, sn):.2f}x")

    # ---- net of costs ----
    Gn = Gg - gn.loc[days] * gc_cost_R
    Nc = Nn - nn.loc[days] * NQ_COST_R
    print(f"\n--- NET of costs (gold {gc_cost_R:.4f}R/trade, "
          f"NQ {NQ_COST_R:.4f}R/trade) ---")
    sgn = stats(Gn, "gold  net")
    snn = stats(Nc, "NQ    net")
    scn = stats((Gn + Nc) / 2, "combined net")
    rho_n = float(np.corrcoef(Gn, Nc)[0, 1])
    print(f"\n  net correlation: rho = {rho_n:+.3f}")
    print(f"  combined/best-single = {scn / max(sgn, snn):.2f}x"
          if max(sgn, snn) > 0 else "\n  best single is negative net")


if __name__ == "__main__":
    main()
