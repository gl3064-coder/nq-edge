"""
experiment_tape_gate_trail.py — the tape-gate vs control test, under TRAIL30 (his real exit).

Same as experiment_tape_gate.py but the exit is his Trail30 (init stop -20, arm trailing once
+30 is touched, then trail 20 below the peak) evaluated on real OHLC instead of fixed +30/-20.
Trail30 lets winners run past +30, so if the tape gate's edge survives / grows here, it's real
under the way he actually trades.

Run:  python src/experiment_tape_gate_trail.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal, PIVOT_K
from drawdown import drawdown_filter
from experiment_entry_fill import DATA, FILES, SESSION
from experiment_tape_gate import daily_sharpe, TERCILE

INIT_STOP, ACTIVATE, TRAIL = 20.0, 30.0, 20.0


def exit_trail30(entry: float, high: np.ndarray, low: np.ndarray,
                 close: np.ndarray, start: int) -> float:
    """His Trail30 on OHLC: -20 stop until +30 touched, then trail 20 below the peak.
    Stop checked on the bar low (pre-trail) for a conservative fill; unresolved -> last close."""
    stop, peak, armed = entry - INIT_STOP, entry, False
    for j in range(start, len(close)):
        if low[j] <= stop:                       # stop hit (checked before trailing up)
            return stop - entry
        if high[j] > peak:
            peak = high[j]
        if not armed and (high[j] - entry) >= ACTIVATE:
            armed = True
        if armed:
            stop = max(stop, peak - TRAIL)
    return float(close[-1] - entry)


def collect() -> pd.DataFrame:
    rows = []
    for name, mindate in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if mindate:
            m = m[m.index.date >= pd.Timestamp(mindate).date()]
        for d, grp in m.groupby(m.index.date):
            out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
            a = higher_low_signal(out["close"], out["up_context"])
            sig = drawdown_filter(out["close"], a)
            g = grp.loc[out.index]
            close = out["close"].to_numpy()
            high, low = g["high"].to_numpy(), g["low"].to_numpy()
            bd = g["buy_delta"].to_numpy()
            n = len(close)
            for i in np.where(sig.to_numpy())[0]:
                if i - PIVOT_K < 0 or i + 1 >= n or i < 3:
                    continue
                pl = exit_trail30(float(close[i]), high, low, close, i + 1)
                rows.append({"file": name, "day": f"{name}_{d}",
                             "tape": float(np.nanmean(bd[i - 2:i + 1])), "pl": pl})
    return pd.DataFrame(rows)


def stats(pl: pd.Series) -> dict:
    pl = pl.dropna()
    return {"n": len(pl), "win": (pl > 0).mean() * 100, "avg": pl.mean(),
            "net": pl.sum(), "sharpe": pl.mean() / pl.std() if pl.std() else float("nan")}


def line(tag: str, s: dict) -> str:
    return (f"{tag:<22}{s['n']:>5}{s['win']:>8.0f}%{s['avg']:>8.2f}"
            f"{s['net']:>9.0f}{s['sharpe']:>9.3f}")


def main() -> None:
    df = collect().dropna(subset=["tape"])
    thr = df["tape"].quantile(TERCILE)
    all_days = df["day"].unique()
    ctrl, gated = df, df[df["tape"] >= thr]

    print(f"\nEXIT = Trail30 (stop -20, arm +30, trail 20) | arrows: {len(df)} "
          f"| strong-tape thr: {thr:.2f}\n")
    print(f"{'strategy':<22}{'n':>5}{'win':>9}{'avg':>8}{'net':>9}{'shrp/trd':>9}")
    print("-" * 62)
    print(line("CONTROL (all arrows)", stats(ctrl["pl"])))
    print(line("GATED (strong tape)", stats(gated["pl"])))
    print(f"\ndaily Sharpe   control {daily_sharpe(ctrl, all_days):.3f}"
          f"   gated {daily_sharpe(gated, all_days):.3f}")

    print("\n[2] PER-FILE, single fixed global threshold")
    print(f"{'file':<12}{'ctrl net':>10}{'gated net':>11}{'ctrl avg':>10}{'gated avg':>11}{'gated n':>9}")
    print("-" * 63)
    for name, _ in FILES:
        c = df[df["file"] == name]
        gg = c[c["tape"] >= thr]
        sc, sg = stats(c["pl"]), stats(gg["pl"])
        print(f"{name:<12}{sc['net']:>10.0f}{sg['net']:>11.0f}"
              f"{sc['avg']:>10.2f}{sg['avg']:>11.2f}{sg['n']:>9}")

    print("\n[3] LEAVE-ONE-FILE-OUT (true OOS, threshold from the other two)")
    print(f"{'held-out file':<14}{'thr':>7}{'ctrl net':>10}{'gated net':>11}{'gated avg':>11}{'gated n':>9}")
    print("-" * 62)
    for name, _ in FILES:
        train = df[df["file"] != name]
        test = df[df["file"] == name]
        tt = train["tape"].quantile(TERCILE)
        g = test[test["tape"] >= tt]
        sc, sg = stats(test["pl"]), stats(g["pl"])
        print(f"{name:<14}{tt:>7.1f}{sc['net']:>10.0f}{sg['net']:>11.0f}"
              f"{sg['avg']:>11.2f}{sg['n']:>9}")


if __name__ == "__main__":
    main()
