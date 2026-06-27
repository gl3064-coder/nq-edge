"""
ticks.py — turn NinjaTrader tick exports into 20-second bars.

NinjaTrader "Last" export rows look like:
    20260312 040001 3640000;24939;24939;24946.75;5
    = <YYYYMMDD HHMMSS fffffff>;Last;Bid;Ask;Volume

We keep Last + Volume, drop sub-second precision (irrelevant for 20s bars), and resample
to 20-second OHLCV. The export timestamps are in UTC (confirmed: files start at 04:00 UTC
= midnight ET, and volume peaks at UTC 13-16 = ET 09:00-12:00, the RTH morning). We
localize as UTC then convert to America/New_York so the NY-morning filter is correct.

Parses once and caches the bars to data/ as pickle so the pipeline never re-reads the
hundreds of MB of ticks.

Run:  python src/ticks.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPLAY_DIR = ROOT / "Replay Data"
DATA_DIR = ROOT / "data"
TZ = "America/New_York"


def load_bars(path: str | Path, seconds: int = 20,
              chunksize: int = 4_000_000) -> pd.DataFrame:
    """Read a NinjaTrader Last-tick file and return 20-second OHLCV bars (tz=ET).

    Reads in chunks and resamples each, so multi-GB files (the 1.3 GB NQ 03-26)
    don't blow up memory. A 20s bucket split across a chunk boundary is merged in
    the final re-aggregation (open=first, high=max, low=min, close=last, vol=sum).
    """
    rule = f"{seconds}s"
    parts = []
    reader = pd.read_csv(path, sep=";", header=None, usecols=[0, 1, 2, 3, 4],
                         names=["ts", "last", "bid", "ask", "vol"], chunksize=chunksize)
    for chunk in reader:
        dt = pd.to_datetime(chunk["ts"].str.slice(0, 15), format="%Y%m%d %H%M%S")
        last = chunk["last"].to_numpy()
        bid, ask, vol = chunk["bid"].to_numpy(), chunk["ask"].to_numpy(), chunk["vol"].to_numpy()
        # Aggressor: +vol if the trade hit the ask (buy/green), -vol if hit the bid (sell/red).
        sign = np.where(last >= ask, 1.0, np.where(last <= bid, -1.0, 0.0))
        b = pd.Series(last, index=dt).resample(rule).ohlc()
        b["volume"] = pd.Series(vol, index=dt).resample(rule).sum()
        b["svol"] = pd.Series(vol * sign, index=dt).resample(rule).sum()
        parts.append(b.dropna(subset=["close"]))

    allb = pd.concat(parts)
    bars = allb.groupby(level=0).agg(open=("open", "first"), high=("high", "max"),
                                     low=("low", "min"), close=("close", "last"),
                                     volume=("volume", "sum"), svol=("svol", "sum"))
    # buy_delta in [-1, +1]: signed aggressive volume / total volume per bar (the "tape").
    bars["buy_delta"] = bars["svol"] / bars["volume"].replace(0, np.nan)
    bars = bars.drop(columns="svol")
    bars.index = bars.index.tz_localize("UTC").tz_convert(TZ)
    return bars


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for path in sorted(REPLAY_DIR.glob("*.Last.txt")):
        contract = path.stem.replace(".Last", "")
        bars = load_bars(path)
        out = DATA_DIR / f"bars_{contract.replace(' ', '_')}.pkl"
        bars.to_pickle(out)

        print(f"\n=== {contract} ===")
        print(f"bars: {len(bars):,} | {bars.index.min()} -> {bars.index.max()}")
        # Volume-by-hour profile — confirms the timezone (RTH should dominate).
        prof = bars.groupby(bars.index.hour)["volume"].sum()
        peak = prof.sort_values(ascending=False).head(5)
        print("top volume hours (ET):", {int(h): int(v) for h, v in peak.items()})
        print(f"saved: {out}")


if __name__ == "__main__":
    main()
