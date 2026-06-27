"""
compare_drawdown.py — is the drawdown condition (#3) actually better?

Builds two signals on NY-morning 1-min Nasdaq data and scores both:
  A = conditions #1 + #2        (up-context + higher-low)
  B = conditions #1 + #2 + #3   (+ the "real pullback before entry" filter)
Then prints the win-rate / points comparison and plots which signals survived.

Run:  python src/compare_drawdown.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_context import fetch, SESSION_START, SESSION_END
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter
from scorer import score

OUTPUT = Path(__file__).resolve().parent.parent / "output"


def main() -> None:
    ticker, close = fetch()
    t = close.index
    mask = (t.dayofweek < 5) & (t.time >= SESSION_START) & (t.time <= SESSION_END)
    morning = close[mask]

    parts = []
    for day, grp in morning.groupby(morning.index.date):
        out = up_context(grp.reset_index(drop=True), fast=7, slow=17, slope_lookback=5)
        a = higher_low_signal(out["close"], out["up_context"])
        b = drawdown_filter(out["close"], a)
        out["sigA"] = a.to_numpy()
        out["sigB"] = b.to_numpy()
        out["day"] = str(day)
        parts.append(out)
    df = pd.concat(parts, ignore_index=True)

    _, sa = score(df["close"], df["sigA"], df["day"])
    _, sb = score(df["close"], df["sigB"], df["day"])

    def row(name, s):
        if s["n"] == 0:
            return f"{name:<26}{0:>9}{'-':>8}{'-':>10}{'-':>9}"
        return (f"{name:<26}{s['n']:>9}{s['win_rate']*100:>7.0f}%"
                f"{s['avg_pts']:>10.1f}{s['total_pts']:>9.0f}")

    print(f"\nsource: {ticker} 1-min | {len(parts)} mornings | target/stop = 30/30 pts")
    print("=" * 62)
    print(f"{'signal':<26}{'trades':>9}{'win%':>8}{'avg pts':>10}{'total':>9}")
    print("-" * 62)
    print(row("A: cond #1+#2", sa))
    print(row("B: +#3 drawdown (your rule)", sb))
    print("=" * 62)
    for name, s in [("A", sa), ("B", sb)]:
        if s["n"]:
            print(f"{name}: {s['wins']}W / {s['losses']}L / {s['unresolved']}unresolved")

    # Plot: which signals survived the drawdown filter.
    x = np.arange(len(df))
    lo, hi = df["close"].min(), df["close"].max()
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(x, df["close"], color="0.4", lw=0.8, label="price")
    ax.fill_between(x, lo, hi, where=df["up_context"].values,
                    color="seagreen", alpha=0.12, label="up-context")
    cut = df["sigA"].values & ~df["sigB"].values
    ax.scatter(x[cut], df["close"].values[cut], marker="x", s=70, color="0.5",
               zorder=5, label="cut by drawdown filter")
    ax.scatter(x[df["sigB"].values], df["close"].values[df["sigB"].values],
               marker="^", s=95, color="crimson", edgecolor="white", zorder=6,
               label="survives (cond #1+#2+#3)")
    for b in df.index[df["day"].ne(df["day"].shift())][1:]:
        ax.axvline(b, color="0.7", lw=0.8, ls=":")
    ax.set_title(f"Drawdown filter on {ticker} 1-min — X = cut, triangle = kept")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_xlabel("1-minute bar (dotted = new morning)"); ax.set_ylabel("price")
    fig.tight_layout()
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / "drawdown_compare.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"saved: {path}")


if __name__ == "__main__":
    main()
