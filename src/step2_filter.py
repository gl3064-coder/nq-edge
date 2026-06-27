"""
step2_filter.py — "does discipline beat what I actually did?"

Two questions, one computation:
  * FILTER test    — what does the edge look like keeping only the right-context
                     trades (the "clean edge")?
  * DISCRETION test — would a disciplined robot following my rules have beaten my
                     actual edge-era trading (which includes the tilted/forced ones)?

They're the same numbers seen two ways: "actual" = every edge-era trade;
"rules" = only the trades that met the conditions. If rules >> actual, the
trades you took OUTSIDE your rules are the leak.

Run:  python src/step2_filter.py

HONEST CAVEAT (printed below too): these filters were found in THIS same 180
trades, so the improvement is in-sample and optimistic. The real proof is
whether it holds on NEW trades. Treat this as "where to look," not a verdict.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from load import load_trades

TRADING_DAYS = 252
# A filter is only useful to a BOT if the bot can know it at entry time.
#   market-observable -> a bot can check it live
#   self-state        -> only YOU know it live (a bot can't read your mood)


def _conf_score(s):
    """Pull the confluence numerator out of '3/7', 'Setup B (6/7)', etc."""
    if pd.isna(s):
        return np.nan
    m = re.search(r"(\d+)\s*/\s*\d+", str(s))
    return int(m.group(1)) if m else np.nan


def stats(sub: pd.DataFrame) -> dict:
    pl = sub["pl"].dropna()
    n = len(pl)
    if n == 0:
        return {"n": 0, "exp": np.nan, "win": np.nan, "total": 0.0, "sharpe": np.nan}
    daily = sub.dropna(subset=["pl", "date"]).groupby("date")["pl"].sum()
    sharpe = (daily.mean() / daily.std(ddof=1) * np.sqrt(TRADING_DAYS)
              if len(daily) >= 2 and daily.std(ddof=1) > 0 else np.nan)
    return {"n": n, "exp": pl.mean(), "win": (pl > 0).mean(),
            "total": pl.sum(), "sharpe": sharpe}


def main() -> None:
    df = load_trades()
    edge = df[(df["phase"] == "edge") & df["pl"].notna()].copy()

    # --- build each condition as a boolean column (True = "rule satisfied") ---
    tape = edge["Tape Agreement?"].astype("string").str.strip()
    cond_tape = tape.eq("Yes")

    cont = edge["Continuation Or Reversal trade"].astype("string").str.strip()
    cond_cont = cont.eq("Continuation")

    pos = edge["Position"].astype("string").str.strip()
    cond_long = pos.eq("Long")

    edge["conf"] = edge["Setups"].map(_conf_score)
    cond_conf = edge["conf"] >= 3

    mc = edge["Market Condition"].astype("string").fillna("")
    cond_trend = mc.str.contains("Trending Upwards") & ~mc.str.contains("Trending Downwards")

    state = edge["Emotional State"].astype("string").str.strip()
    cond_state = state.notna() & state.ne("Rough")  # self-state: only you know this live

    market_rules = cond_tape & cond_cont & cond_long & cond_conf & cond_trend
    full_rules = market_rules & cond_state

    scenarios = {
        "ACTUAL (all edge trades)": pd.Series(True, index=edge.index),
        "  tape agrees": cond_tape,
        "  continuation only": cond_cont,
        "  long only": cond_long,
        "  confluence >= 3/7": cond_conf,
        "  uptrend only": cond_trend,
        "  not 'Rough' state": cond_state,
        "RULES (market-observable)": market_rules,
        "RULES + good state": full_rules,
    }

    print("\n" + "=" * 86)
    print("STEP 2 - actual vs rule-following (edge era, 180 trades, points)")
    print("=" * 86)
    hdr = f"{'scenario':<28}{'trades':>7}{'exp':>8}{'win%':>7}{'total':>9}{'Sharpe':>8}{'net@0.5':>9}{'net@1.0':>9}"
    print(hdr)
    print("-" * 86)
    for name, mask in scenarios.items():
        s = stats(edge[mask.reindex(edge.index, fill_value=False)])
        if s["n"] == 0:
            print(f"{name:<28}{0:>7}{'—':>8}")
            continue
        print(f"{name:<28}{s['n']:>7}{s['exp']:>8.2f}{s['win']*100:>6.0f}%"
              f"{s['total']:>9.0f}{(s['sharpe'] if not np.isnan(s['sharpe']) else float('nan')):>8.2f}"
              f"{s['exp']-0.5:>9.2f}{s['exp']-1.0:>9.2f}")
    print("-" * 86)
    print("exp = points/trade. net@X = expectancy minus an X-point round-trip cost.")
    print("'self-state' rows (Rough) need YOUR input live; the others a bot can read.")
    print("\nIN-SAMPLE CAVEAT: filters were found in these same trades, so these")
    print("numbers are optimistic. The verdict is whether they hold on NEW trades.")


if __name__ == "__main__":
    main()
