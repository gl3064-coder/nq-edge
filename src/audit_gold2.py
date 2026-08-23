"""audit_gold2.py — inspect the 2026-01-29 intra-session jump, and put honest
error bars on the gold Sharpe.

PART 1. A 78.6-point move in one 20-second bar at 10:27:40 ET, inside the traded
window. Real news spike or bad print? Print the surrounding bars and the raw
trades so it can be judged by eye rather than by summary statistic.

PART 2. The 4.25 annualized Sharpe is arithmetically correct and practically
meaningless without a standard error. For a Sharpe estimated from n periods:

    SE(SR_period) ~= sqrt( (1 + SR_period^2 / 2) / n )

annualized by sqrt(252). With ~104 days that error bar is enormous. Also apply
the 50% winner's-curse shrink the significance audit already uses for NQ.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from databento_bars import load_bars_databento

TARGET_DAY = "2026-01-29"
ANN = np.sqrt(252)


def part1():
    print("=" * 62)
    print(f"PART 1 — {TARGET_DAY} 10:27:40 ET, the 78.6 point bar")
    print("=" * 62)
    bars = load_bars_databento("Replay Data/databento/GC_n0_tbbo_2026-01.csv")
    day = bars[bars.index.date == pd.Timestamp(TARGET_DAY).date()]
    win = day.between_time("10:24", "10:32")
    print("\n20-second bars around the jump:")
    print(win[["open", "high", "low", "close", "volume", "buy_delta"]].to_string())

    print("\nraw trades 10:27:20 - 10:28:20:")
    df = pd.read_csv("Replay Data/databento/GC_n0_tbbo_2026-01.csv",
                     usecols=["ts_event", "price", "size", "bid_px_00", "ask_px_00"])
    ts = pd.to_datetime(df["ts_event"], format="mixed", utc=True)
    df = df.assign(ts=ts.dt.tz_convert("America/New_York"))
    w = df[(df["ts"] >= f"{TARGET_DAY} 10:27:20-05:00") &
           (df["ts"] <= f"{TARGET_DAY} 10:28:20-05:00")]
    print(f"  {len(w)} trades in that minute")
    if len(w):
        print(f"  price range {w['price'].min():.1f} - {w['price'].max():.1f}")
        print(w.head(25)[["ts", "price", "size", "bid_px_00", "ask_px_00"]].to_string(index=False))

    # Is a 78-point 20s move plausible for gold? Compare to the day's own range.
    print(f"\n  that day's full range: {day['low'].min():.1f} - {day['high'].max():.1f}"
          f"  ({day['high'].max() - day['low'].min():.1f} pts)")


def sharpe_with_error(daily: np.ndarray, label: str):
    mu, sd = daily.mean(), daily.std(ddof=1)
    n = len(daily)
    sr_d = mu / sd
    sr_a = sr_d * ANN
    se_a = np.sqrt((1 + sr_d ** 2 / 2) / n) * ANN
    print(f"  {label:22} {sr_a:>6.2f}  +/- {se_a:.2f}   "
          f"95% CI [{sr_a - 1.96*se_a:>6.2f}, {sr_a + 1.96*se_a:>5.2f}]")
    return sr_a, se_a


def part2():
    print("\n" + "=" * 62)
    print("PART 2 — Sharpe with error bars")
    print("=" * 62)
    # daily R series regenerated cheaply from the audit's own numbers
    from audit_gold import main as _  # noqa: F401  (import guard only)
    print("\n(using the daily R series from breadth_check: gross mean 0.5135,"
          "\n sd 1.918 over 104 shared days; net mean 0.2265)")
    rng = np.random.default_rng(0)
    # Reconstruct plausible daily series is NOT ok — use the reported moments.
    for label, mu, sd in [("gross", 0.5135, 1.918), ("net of costs", 0.2265, 1.883)]:
        sr_d = mu / sd
        sr_a = sr_d * ANN
        se_a = np.sqrt((1 + sr_d ** 2 / 2) / 104) * ANN
        lo, hi = sr_a - 1.96 * se_a, sr_a + 1.96 * se_a
        print(f"  {label:14} Sharpe {sr_a:>5.2f}  +/- {se_a:.2f}   "
              f"95% CI [{lo:>6.2f}, {hi:>5.2f}]")
    print("\n  after 50% winner's-curse shrink (the same haircut the NQ")
    print("  significance audit applies to a first-look result):")
    for label, mu, sd in [("gross", 0.5135, 1.918), ("net of costs", 0.2265, 1.883)]:
        sr_a = (mu * 0.5) / sd * ANN
        print(f"    {label:14} {sr_a:>5.2f}")
    print("\n  reference: SPY buy-and-hold is about 0.45")


if __name__ == "__main__":
    part1()
    part2()
