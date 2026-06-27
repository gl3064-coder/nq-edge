"""
copilot_alerts.py — the co-pilot's actual output: a clean watchlist of "go look" zones.

The raw signal fires 8-20x/morning (too noisy to ping). This collapses clustered fires
into distinct alerts with a cooldown, so each ping is a real, separate opportunity — what
the live co-pilot would actually surface. Prints the noise reduction across all sessions,
then one recent morning in detail (time, price, why), the way a ping would read.

Run:  python src/copilot_alerts.py
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
COOLDOWN = 15   # bars (=5 min): suppress repeat pings within this window


def session_alerts(grp: pd.DataFrame):
    c = grp["close"].reset_index(drop=True)
    out = up_context(c, fast=20, slow=50, slope_lookback=10)
    sig = drawdown_filter(out["close"], higher_low_signal(out["close"], out["up_context"]))
    bd = grp["buy_delta"].reset_index(drop=True).fillna(0).rolling(3, min_periods=1).mean()

    raw = np.where(sig.to_numpy())[0]
    alerts, last = [], -COOLDOWN - 1
    for i in raw:
        if i - last > COOLDOWN:
            alerts.append(i); last = i
    return out, bd, len(raw), alerts


def main():
    raw_total, alert_total, n_sessions = 0, 0, 0
    for name, md in [("NQ_03-26", None), ("NQ_06-26", "2026-03-16"), ("NQ_09-26", None)]:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if md:
            m = m[m.index.date >= pd.Timestamp(md).date()]
        for _, grp in m.groupby(m.index.date):
            _, _, n_raw, alerts = session_alerts(grp)
            raw_total += n_raw; alert_total += len(alerts); n_sessions += 1

    print(f"across {n_sessions} sessions:")
    print(f"  raw signals/morning : {raw_total/n_sessions:.1f}")
    print(f"  de-duped alerts/morning : {alert_total/n_sessions:.1f}  (cooldown 5 min)")

    # One recent morning in detail — what the co-pilot would have pinged.
    b = pd.read_pickle(DATA / "bars_NQ_09-26.pkl")
    t = b.index
    m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
    last_day = sorted(set(m.index.date))[-1]
    grp = m[m.index.date == last_day]
    out, bd, _, alerts = session_alerts(grp)
    idx = grp.index
    print(f"\nsample morning {last_day} — co-pilot pings:")
    for i in alerts:
        ctx_bars = int(out["up_context"].iloc[max(0, i-30):i+1].sum())
        tape = bd.iloc[i]
        flag = "green" if tape > 0.1 else ("red" if tape < -0.1 else "flat")
        print(f"  {idx[i]:%H:%M:%S}  {out['close'].iloc[i]:.0f}  "
              f"| up-context | tape {tape:+.2f} ({flag})")


if __name__ == "__main__":
    main()
