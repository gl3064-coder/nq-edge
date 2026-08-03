"""
databento_bars.py — turn a Databento `tbbo` CSV into the SAME 20-second bars
that ticks.py produces from a NinjaTrader Last export.

WHY tbbo AND NOT trades.
`trades` carries the exchange's own aggressor flag (`side`), which is a cleaner
measurement than inferring the aggressor from Last-vs-bid/ask. Cleaner is the
wrong goal here. The forward record already contains sessions measured the
NinjaTrader way, and a tally that mixes two estimators of buy_delta is not one
tally. `tbbo` gives trades WITH the bid/ask at trade time, so the exact rule in
ticks.py can be reapplied unchanged:

    sign = +1 if last >= ask, -1 if last <= bid, else 0
    buy_delta = sum(vol * sign) / sum(vol)      per 20s bar

The `side` column is deliberately ignored. It is the better number and it is
not the number the rest of the record is made of.

Timestamps: Databento ts_event is UTC nanoseconds. ticks.py builds bars in UTC
then converts to America/New_York, and pandas resample is start-labelled. Both
are matched here so bar boundaries line up.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/New_York"


def load_bars_databento(path: str | Path, seconds: int = 20) -> pd.DataFrame:
    """Read a Databento tbbo CSV and return 20-second OHLCV+buy_delta bars (tz=ET)."""
    df = pd.read_csv(
        path,
        usecols=["ts_event", "price", "size", "bid_px_00", "ask_px_00"],
    )

    dt = pd.to_datetime(df["ts_event"], format="ISO8601", utc=True).dt.tz_localize(None)
    last = df["price"].to_numpy(dtype=float)
    bid = df["bid_px_00"].to_numpy(dtype=float)
    ask = df["ask_px_00"].to_numpy(dtype=float)
    vol = df["size"].to_numpy(dtype=float)

    # Identical rule to ticks.py:49. A quote missing on one side leaves sign 0,
    # matching how a NaN comparison falls through there.
    sign = np.where(last >= ask, 1.0, np.where(last <= bid, -1.0, 0.0))

    rule = f"{seconds}s"
    bars = pd.Series(last, index=dt).resample(rule).ohlc()
    bars["volume"] = pd.Series(vol, index=dt).resample(rule).sum()
    svol = pd.Series(vol * sign, index=dt).resample(rule).sum()
    bars = bars.dropna(subset=["close"])
    bars["buy_delta"] = svol.reindex(bars.index) / bars["volume"].replace(0, np.nan)
    bars.index = bars.index.tz_localize("UTC").tz_convert(TZ)
    return bars


if __name__ == "__main__":
    import sys

    b = load_bars_databento(sys.argv[1])
    print(f"bars: {len(b):,} | {b.index.min()} -> {b.index.max()}")
    print(b.head(3).to_string())
