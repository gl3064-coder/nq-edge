"""
experiment_tape_gate.py — is "signal + strong-tape gate" truly better than the control?

Control  = every green arrow, market entry (the current bot).
Gated    = only arrows whose tape (mean buy_delta, last 3 bars) is in the STRONG bucket.

Three honesty checks, hardest last:
  1. Overall control vs gated: net, win%, avg, per-trade + daily Sharpe.
  2. Per-file with a SINGLE fixed threshold (global top-tercile cutoff) — does the edge
     survive in each of the three regimes, or is one file carrying it?
  3. LEAVE-ONE-FILE-OUT (true OOS): set the threshold on two files, test on the held-out
     third. The gate never sees the data it's scored on. This is the "truly better" test.

Exit: fixed +TARGET / -STOP first-touch on real OHLC (same as the other experiments).

Run:  python src/experiment_tape_gate.py
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
from experiment_entry_fill import exit_first_touch, TARGET, STOP, DATA, FILES, SESSION

TERCILE = 2 / 3   # "strong tape" = top third


def collect_arrows() -> pd.DataFrame:
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
                _, pl = exit_first_touch(float(close[i]), high, low, close, i + 1)
                rows.append({"file": name, "day": f"{name}_{d}",
                             "tape": float(np.nanmean(bd[i - 2:i + 1])), "pl": pl})
    return pd.DataFrame(rows)


def stats(pl: pd.Series) -> dict:
    pl = pl.dropna()
    return {"n": len(pl), "win": (pl == TARGET).mean() * 100,
            "avg": pl.mean(), "net": pl.sum(),
            "sharpe": pl.mean() / pl.std() if pl.std() else float("nan")}


def daily_sharpe(df: pd.DataFrame, all_days: pd.Index) -> float:
    daily = df.groupby("day")["pl"].sum().reindex(all_days, fill_value=0.0)
    return daily.mean() / daily.std() if daily.std() else float("nan")


def line(tag: str, s: dict) -> str:
    return (f"{tag:<22}{s['n']:>5}{s['win']:>8.0f}%{s['avg']:>8.2f}"
            f"{s['net']:>9.0f}{s['sharpe']:>9.3f}")


def main() -> None:
    df = collect_arrows().dropna(subset=["tape"])
    thr = df["tape"].quantile(TERCILE)
    all_days = df["day"].unique()
    ctrl, gated = df, df[df["tape"] >= thr]

    print(f"\narrows: {len(df)} | strong-tape threshold (global top third): {thr:.2f}\n")
    print(f"{'strategy':<22}{'n':>5}{'win':>9}{'avg':>8}{'net':>9}{'shrp/trd':>9}")
    print("-" * 62)
    print(line("CONTROL (all arrows)", stats(ctrl["pl"])))
    print(line("GATED (strong tape)", stats(gated["pl"])))
    print(f"\ndaily Sharpe   control {daily_sharpe(ctrl, all_days):.3f}"
          f"   gated {daily_sharpe(gated, all_days):.3f}")

    print("\n[2] PER-FILE, single fixed global threshold (regime consistency)")
    print(f"{'file':<12}{'ctrl net':>10}{'gated net':>11}{'ctrl win':>10}{'gated win':>11}{'gated n':>9}")
    print("-" * 63)
    for name, _ in FILES:
        c = df[df["file"] == name]
        gg = c[c["tape"] >= thr]
        sc, sg = stats(c["pl"]), stats(gg["pl"])
        print(f"{name:<12}{sc['net']:>10.0f}{sg['net']:>11.0f}"
              f"{sc['win']:>9.0f}%{sg['win']:>10.0f}%{sg['n']:>9}")

    print("\n[3] LEAVE-ONE-FILE-OUT (threshold from the OTHER two, tested on held-out)")
    print(f"{'held-out file':<14}{'thr':>7}{'ctrl net':>10}{'gated net':>11}{'gated avg':>11}{'gated n':>9}")
    print("-" * 62)
    for name, _ in FILES:
        train = df[df["file"] != name]
        test = df[df["file"] == name]
        t = train["tape"].quantile(TERCILE)
        g = test[test["tape"] >= t]
        sc, sg = stats(test["pl"]), stats(g["pl"])
        print(f"{name:<14}{t:>7.1f}{sc['net']:>10.0f}{sg['net']:>11.0f}"
              f"{sg['avg']:>11.2f}{sg['n']:>9}")


if __name__ == "__main__":
    main()
