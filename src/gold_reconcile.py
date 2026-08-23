"""gold_reconcile.py — why did NinjaTrader give n=446 and Databento n=334?

PART 1. Suspected cause: my own window bug. In gold_nt_check.py the GC 02-26
window had no lower bound, so it reached back to 2025-11-23, and GC 08-26 ran to
2026-07-25. That is ~8 months against Databento's 6. Re-run clamped to exactly
2026-01-01 .. 2026-07-01 and see whether n converges.

PART 2. The definitive check, the same one that validated the NQ gap buy-back on
2026-08-03: take one day present in BOTH sources, build 20s bars from each, and
diff them. Bars, closes, buy_delta, and agreement on the 0.10 tape gate. If the
two pipelines disagree at bar level, that is a real problem. If they agree, the
trade-count gap is purely windowing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from databento_bars import load_bars_databento
from gold_nt_check import run_one, stat, ROOT

DBENTO = Path(__file__).resolve().parent.parent / "Replay Data" / "databento"
LO, HI = "2026-01-01", "2026-07-01"
TEST_DAY = "2026-04-15"


def part1():
    print("=" * 66)
    print("PART 1 - same window, clamped to 2026-01-01 .. 2026-07-01")
    print("=" * 66)
    windows = [
        ("GC 02-26.Last.txt", LO,           "2026-01-22"),
        ("GC 04-26.Last.txt", "2026-01-22", "2026-03-26"),
        ("GC 06-26.Last.txt", "2026-03-26", "2026-05-28"),
        ("GC 08-26.Last.txt", "2026-05-28", HI),
    ]
    parts = {}
    for fn, lo, hi in windows:
        p = ROOT / fn
        if p.exists():
            parts[fn] = run_one(p, lo, hi)
    df = pd.concat(parts.values(), ignore_index=True)
    print("\nper contract:")
    for fn, sub in parts.items():
        stat(fn.replace(".Last.txt", ""), sub)
    print("\npooled:")
    stat("NinjaTrader, Jan-Jul only", df)
    print("  Databento, same window       n= 334   +0.165R   t= 2.42")
    return df


def part2():
    print("\n" + "=" * 66)
    print(f"PART 2 - bar-level diff on {TEST_DAY} (in both sources)")
    print("=" * 66)
    nt = load_bars(ROOT / "GC 06-26.Last.txt")
    nt = nt[nt.index.date == pd.Timestamp(TEST_DAY).date()].between_time("09:30", "12:00")
    db = load_bars_databento(DBENTO / "GC_n0_tbbo_2026-04.csv")
    db = db[db.index.date == pd.Timestamp(TEST_DAY).date()].between_time("09:30", "12:00")

    print(f"  NinjaTrader bars : {len(nt):>5}   close {nt['close'].iloc[0]:.1f} -> {nt['close'].iloc[-1]:.1f}")
    print(f"  Databento   bars : {len(db):>5}   close {db['close'].iloc[0]:.1f} -> {db['close'].iloc[-1]:.1f}")

    j = nt.join(db, how="inner", lsuffix="_nt", rsuffix="_db")
    print(f"  bars on identical timestamps: {len(j)}")
    if j.empty:
        print("  NO OVERLAP - different contracts or timezone handling")
        return

    dc = (j["close_nt"] - j["close_db"]).abs()
    print(f"\n  |close difference|  median {dc.median():.3f}   max {dc.max():.3f}")
    print(f"  volume  NT median {j['volume_nt'].median():.0f}"
          f"   DB median {j['volume_db'].median():.0f}")
    r = j[["buy_delta_nt", "buy_delta_db"]].corr().iloc[0, 1]
    print(f"  buy_delta correlation : {r:.4f}")
    agree = ((j["buy_delta_nt"] >= 0.10) == (j["buy_delta_db"] >= 0.10)).mean()
    print(f"  agree on the 0.10 tape gate : {100*agree:.1f}%")
    print("\n  (the NQ buy-back validation hit corr 0.9997 and 0/540 gate disagreements)")


if __name__ == "__main__":
    part1()
    part2()
