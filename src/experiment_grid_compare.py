"""
experiment_grid_compare.py — bot vs me on 7/13, from the NinjaTrader "Grid" CSV exports.

The Grid format is Last price + Volume only (no Bid/Ask), so buy_delta / the tape gate
CANNOT be computed. But 7/13 was a DEAD-TAPE day, so the operative live-bot filter is the
ATR dead-tape gate (avg ATR < MinAtr -> stand down), which IS computable here. This runs:
  - CONTROL: every co-pilot arrow (no gate)
  - DEAD-GATED: arrows suppressed when SMA(TR,15) < 10 (the live co-pilot's dead-tape gate)
under both Trail30 (his exit) and fixed 30/20, per day and per hour.

Run:  python src/experiment_grid_compare.py
"""
from __future__ import annotations

import glob
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal, PIVOT_K
from drawdown import drawdown_filter
from experiment_entry_fill import exit_first_touch
from experiment_tape_gate_trail import exit_trail30

REPLAY = Path(__file__).resolve().parent.parent / "Replay Data"
SESSION = (time(9, 30), time(12, 0))
MIN_ATR = 10.0
HOURS = {9: "9-10", 10: "10-11", 11: "11-12", 12: "12-1"}


def load_grid_bars() -> pd.DataFrame:
    frames = []
    for f in glob.glob(str(REPLAY / "NinjaTrader Grid 2026-07-13*.csv")):
        d = pd.read_csv(f)
        d["ts"] = pd.to_datetime(d["Time"], format="%m/%d/%Y %I:%M:%S %p")
        frames.append(d[["ts", "Price", "Volume"]])
    t = pd.concat(frames).sort_values("ts").set_index("ts")
    bars = t["Price"].resample("20s").ohlc()
    bars["volume"] = t["Volume"].resample("20s").sum()
    bars = bars.dropna(subset=["close"])
    bars.index = bars.index.tz_localize("America/New_York")  # grid times are already ET
    return bars


def avg_atr(h, l, c, n=15):
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def main() -> None:
    bars = load_grid_bars()
    print(f"grid bars: {len(bars)} | ET {bars.index.min()} -> {bars.index.max()}")
    t = bars.index
    m = bars[(t.time >= SESSION[0]) & (t.time <= SESSION[1])]

    rows = []
    for d, grp in m.groupby(m.index.date):
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        a = higher_low_signal(out["close"], out["up_context"])
        sig = drawdown_filter(out["close"], a)
        g = grp.loc[out.index]
        close = out["close"].to_numpy()
        high, low = g["high"].to_numpy(), g["low"].to_numpy()
        aatr = avg_atr(g["high"], g["low"], g["close"]).to_numpy()
        hrs = g.index.hour.to_numpy()
        n = len(close)
        for i in np.where(sig.to_numpy())[0]:
            if i - PIVOT_K < 0 or i + 1 >= n:
                continue
            e = float(close[i])
            _, fx = exit_first_touch(e, high, low, close, i + 1)
            tr = exit_trail30(e, high, low, close, i + 1)
            rows.append({"hour": int(hrs[i]), "avgatr": float(aatr[i]) if not np.isnan(aatr[i]) else 0.0,
                         "fixed": fx, "trail": tr})

    df = pd.DataFrame(rows)
    dead_ok = df[df["avgatr"] >= MIN_ATR]     # arrows the dead-tape gate would ALLOW
    print(f"\n7/13 bot (co-pilot signal, 9:30-12:00) | dead-tape gate = SMA(TR,15) >= {MIN_ATR:.0f}\n")
    print(f"{'variant':<26}{'arrows':>7}{'trail':>9}{'fixed':>9}")
    print("-" * 51)
    print(f"{'CONTROL (all arrows)':<26}{len(df):>7}{df['trail'].sum():>9.1f}{df['fixed'].sum():>9.1f}")
    print(f"{'DEAD-GATED (avgATR>=10)':<26}{len(dead_ok):>7}{dead_ok['trail'].sum():>9.1f}{dead_ok['fixed'].sum():>9.1f}")
    print(f"\n(gate suppressed {len(df) - len(dead_ok)} of {len(df)} arrows as dead tape)")

    print("\nby hour (avg ATR at each arrow):")
    for h, lab in HOURS.items():
        hh = df[df["hour"] == h]
        if len(hh):
            allowed = hh[hh["avgatr"] >= MIN_ATR]
            print(f"  {lab:<6} arrows={len(hh)}  avgATR~{hh['avgatr'].mean():.1f}  "
                  f"control trail={hh['trail'].sum():>6.1f}  gated trail={allowed['trail'].sum():>6.1f} "
                  f"(kept {len(allowed)})")


if __name__ == "__main__":
    main()
