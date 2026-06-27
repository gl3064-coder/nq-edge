"""
plot_context.py — SEE the free-data signal run on real Nasdaq price, NY morning only.

Plots context.up_context() as green shading (condition #1: "allowed to look") AND
location.higher_low_signal() as markers (conditions #1+#2 together: "your setup is
forming — look now"). Free 1-minute data (NQ=F, else QQQ), NY morning (09:30-12:00 ET),
context computed fresh each morning. Periods/k get re-tuned on real 20s NQ bars later.

Run:  python src/plot_context.py
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from context import up_context
from location import higher_low_signal

OUTPUT = Path(__file__).resolve().parent.parent / "output"
SESSION_START, SESSION_END = time(9, 30), time(12, 0)  # NY morning


def fetch() -> tuple[str, pd.Series]:
    """Recent 1-minute Nasdaq closes, index normalized to America/New_York."""
    import yfinance as yf
    for ticker in ["NQ=F", "QQQ"]:
        df = yf.download(ticker, period="5d", interval="1m",
                         progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = close.dropna()
            idx = pd.DatetimeIndex(close.index)
            idx = (idx.tz_localize("America/New_York") if idx.tz is None
                   else idx.tz_convert("America/New_York"))
            close.index = idx
            return ticker, close
    raise RuntimeError("no intraday data returned from yfinance")


def main() -> None:
    ticker, close = fetch()

    t = close.index
    mask = (t.dayofweek < 5) & (t.time >= SESSION_START) & (t.time <= SESSION_END)
    morning = close[mask]

    parts = []
    for day, grp in morning.groupby(morning.index.date):
        out = up_context(grp.reset_index(drop=True), fast=7, slow=17, slope_lookback=5)
        out["signal"] = higher_low_signal(out["close"], out["up_context"]).to_numpy()
        out["day"] = str(day)
        parts.append(out)
    allout = pd.concat(parts, ignore_index=True)

    n_sig = int(allout["signal"].sum())
    print(f"source: {ticker} 1-min | mornings: {len(parts)} | morning bars: {len(allout)} | "
          f"up-context: {allout['up_context'].mean()*100:.0f}% | higher-low signals: {n_sig}")

    x = np.arange(len(allout))
    lo, hi = allout["close"].min(), allout["close"].max()
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(x, allout["close"], color="0.35", lw=0.8, label="price")
    ax.plot(x, allout["fast_ma"], color="tab:blue", lw=1.0, label="fast MA (~7m)")
    ax.plot(x, allout["slow_ma"], color="tab:orange", lw=1.0, label="slow MA (~17m)")
    ax.fill_between(x, lo, hi, where=allout["up_context"].values,
                    color="seagreen", alpha=0.15, label="up-context (cond #1: look here)")
    sig_x = x[allout["signal"].values]
    ax.scatter(sig_x, allout["close"].values[allout["signal"].values],
               marker="^", s=90, color="crimson", zorder=5, edgecolor="white",
               label="higher-low entry (cond #1+#2: go)")
    for b in allout.index[allout["day"].ne(allout["day"].shift())][1:]:
        ax.axvline(b, color="0.7", lw=0.8, ls=":")
    ax.set_title(f"Free-data signal on {ticker} 1-min — NY morning (9:30-12:00 ET)")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_xlabel("1-minute bar (dotted = new morning)"); ax.set_ylabel("price")
    fig.tight_layout()

    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / "signal_demo.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"saved: {path}")


if __name__ == "__main__":
    main()
