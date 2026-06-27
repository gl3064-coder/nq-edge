"""
load.py — the single source of truth for reading your trade journal.

Everything else in this project imports `load_trades()`. The cleaning rules
live here ONCE so they're written correctly in one place: date parsing, the
N/A -> blank conversion, P/L as a real number, a clean win flag, and the
exploration-vs-edge phase split.

Run nothing here directly — this is a library. See edge_check.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# The journal records "N/A" (and a few cousins) as text. Those are not data —
# they're "I didn't log this." We turn them into real missing values so pandas
# math (mean, groupby) skips them instead of choking on strings.
_NA_TOKENS = {"N/A", "n/a", "NA", "na", "None", "none", "nan", "NaN", "", "-"}

# Trade Date looks like:  "January 28, 2025 11:43 AM (EST)"
# pandas can't parse the trailing "(EST)"/"(EDT)" timezone tag, so we strip it.
_TZ_SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*$")
_DATE_FMT = "%B %d, %Y %I:%M %p"


def _strip_na(value):
    """Convert the journal's textual N/A markers into real NaN."""
    if isinstance(value, str) and value.strip() in _NA_TOKENS:
        return np.nan
    return value


def _parse_trade_date(series: pd.Series) -> pd.Series:
    """'January 28, 2025 11:43 AM (EST)' -> a real datetime (tz tag dropped)."""
    cleaned = series.astype("string").str.replace(_TZ_SUFFIX, "", regex=True)
    return pd.to_datetime(cleaned, format=_DATE_FMT, errors="coerce")


def load_trades(
    path: str | Path = None,
    edge_start: int | None = None,
) -> pd.DataFrame:
    """
    Read the trade journal CSV and return a cleaned DataFrame.

    Parameters
    ----------
    path : path to the CSV. Defaults to ../data/trades.csv relative to this file.
    edge_start : the trade `Name` (number) where the "edge era" begins. If None,
        we detect it automatically as the first trade where you started logging
        a `Setups` value — i.e. when you began trading an actual strategy instead
        of throwing things at the wall. Pass an int to override and slide the
        boundary yourself.

    Returns
    -------
    DataFrame with the original columns plus:
        trade_date : parsed datetime
        date       : calendar date (for daily aggregation)
        pl         : P/L as a float (NQ points)
        is_win     : True when pl > 0
        phase      : "exploration" or "edge"
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "trades.csv"
    path = Path(path)

    df = pd.read_csv(path)

    # 1. Kill the textual N/A markers everywhere.
    df = df.map(_strip_na)

    # 2. Trade number as a clean integer (the journal calls it "Name").
    df["Name"] = pd.to_numeric(df["Name"], errors="coerce").astype("Int64")

    # 3. Real datetime + a calendar-date column for daily grouping.
    df["trade_date"] = _parse_trade_date(df["Trade Date"])
    df["date"] = df["trade_date"].dt.normalize()

    # 4. P/L as a number (NQ points). Non-numeric rows -> NaN.
    df["pl"] = pd.to_numeric(df["P/L"], errors="coerce")

    # 5. Outcome: P/L is ground truth, so a win is simply a positive result.
    #    (The text `win` column is messy — "Win"/"Large Win"/"Small Win"/blank —
    #    so we trust the number, not the label.)
    df["is_win"] = df["pl"] > 0

    # 6. Sort by trade number so "phase by trade #" is meaningful, then split.
    df = df.sort_values("Name").reset_index(drop=True)

    if edge_start is None:
        edge_start = _detect_edge_start(df)
    # `Name` is a nullable Int64, so the comparison can yield <NA>; fill those
    # (trades with no number) into the exploration side before the string split.
    is_edge = (df["Name"] >= edge_start).fillna(False).astype(bool)
    df["phase"] = np.where(is_edge, "edge", "exploration")

    # Stash the boundary so callers can report it without re-deriving.
    df.attrs["edge_start"] = int(edge_start)
    return df


def _detect_edge_start(df: pd.DataFrame) -> int:
    """
    First trade number where a `Setups` value was logged. That's the data's
    fingerprint of "I now have a strategy I'm tracking" — which is exactly the
    moment the user described as the end of the throwing-shit-at-the-wall era.
    Falls back to the first Replay-account trade, then to 1.
    """
    has_setup = df["Setups"].notna()
    if has_setup.any():
        return int(df.loc[has_setup, "Name"].iloc[0])

    acct = df["Account"].astype("string").str.contains("Replay", case=False, na=False)
    if acct.any():
        return int(df.loc[acct, "Name"].iloc[0])

    return 1


if __name__ == "__main__":
    # Tiny smoke test so you can sanity-check the loader on its own.
    d = load_trades()
    print(f"loaded {len(d)} trades | edge era starts at trade #{d.attrs['edge_start']}")
    print(d["phase"].value_counts().to_dict())
