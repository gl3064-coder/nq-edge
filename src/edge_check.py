"""
edge_check.py - the gate. "Is my NQ edge real?"

Run this:  python src/edge_check.py

It prints a report and saves two equity-curve charts to output/. Everything is
computed THREE WAYS - all trades / exploration era / edge era - because mixing
the throwing-shit-at-the-wall trades with the real-strategy trades averages two
different traders into mush. The edge-era column is the one that answers the
question.

Numbers are in NQ points (P/L is in points; $20/point for full NQ, $2 for MNQ).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # save charts to files, no GUI window
import matplotlib.pyplot as plt

# load.py sits next to this file; running the script puts this dir on sys.path.
from load import load_trades

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# Core stat block - the numbers that decide whether an edge exists.
# --------------------------------------------------------------------------- #
def stats_block(df: pd.DataFrame) -> dict:
    """Edge metrics for one slice of trades. P/L assumed in points."""
    pl = df["pl"].dropna()
    n = len(pl)
    if n == 0:
        return {"n": 0}

    wins = pl[pl > 0]
    losses = pl[pl < 0]
    win_rate = len(wins) / n
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0  # negative
    # Expectancy = what you make per trade on average, in points.
    expectancy = pl.mean()
    # Profit factor = gross won / gross lost. > 1 means the wins outweigh losses.
    profit_factor = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf

    # Daily Sharpe: collapse trades to a per-day P/L stream, then mean/std.
    daily = df.dropna(subset=["pl", "date"]).groupby("date")["pl"].sum()
    if len(daily) >= 2 and daily.std(ddof=1) > 0:
        daily_sharpe = daily.mean() / daily.std(ddof=1) * np.sqrt(TRADING_DAYS)
    else:
        daily_sharpe = np.nan

    return {
        "n": n,
        "total_pl": pl.sum(),
        "expectancy": expectancy,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "trading_days": len(daily),
        "daily_sharpe": daily_sharpe,
    }


def print_phase_table(df: pd.DataFrame) -> None:
    slices = {
        "ALL": df,
        "exploration": df[df["phase"] == "exploration"],
        "edge": df[df["phase"] == "edge"],
    }
    rows = {name: stats_block(sub) for name, sub in slices.items()}

    print("\n" + "=" * 66)
    print("EDGE CHECK - computed three ways (points)")
    print("=" * 66)
    label = f"{'metric':<16}" + "".join(f"{k:>16}" for k in rows)
    print(label)
    print("-" * 66)

    def line(metric, key, fmt):
        cells = ""
        for name in rows:
            v = rows[name].get(key)
            cells += f"{(fmt(v) if v is not None and not (isinstance(v,float) and np.isnan(v)) else '-'):>16}"
        print(f"{metric:<16}{cells}")

    line("trades", "n", lambda v: f"{int(v)}")
    line("total P/L (pts)", "total_pl", lambda v: f"{v:,.1f}")
    line("expectancy/trd", "expectancy", lambda v: f"{v:,.3f}")
    line("win rate", "win_rate", lambda v: f"{v:.1%}")
    line("avg win", "avg_win", lambda v: f"{v:,.2f}")
    line("avg loss", "avg_loss", lambda v: f"{v:,.2f}")
    line("profit factor", "profit_factor", lambda v: f"{v:,.2f}")
    line("trading days", "trading_days", lambda v: f"{int(v)}")
    line("daily Sharpe*", "daily_sharpe", lambda v: f"{v:,.2f}")
    print("-" * 66)
    print("* daily Sharpe annualized x sqrt(252). For edge-era Replay trades the")
    print("  calendar dates are practice dates, so read Sharpe as a within-sample")
    print("  consistency measure, not a live track record.")


# --------------------------------------------------------------------------- #
# Equity curves - the visual gut check.
# --------------------------------------------------------------------------- #
def plot_equity(df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    d = df.dropna(subset=["pl"]).reset_index(drop=True)
    edge_start = df.attrs.get("edge_start")

    # All-trades equity with the phase boundary marked.
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(d["Name"], d["pl"].cumsum(), lw=1.3)
    ax.axhline(0, color="0.6", lw=0.8)
    if edge_start is not None:
        ax.axvline(edge_start, color="crimson", ls="--", lw=1,
                   label=f"edge era starts (trade #{edge_start})")
        ax.legend()
    ax.set_title("Cumulative P/L - all trades (points)")
    ax.set_xlabel("trade number")
    ax.set_ylabel("cumulative points")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "equity_all.png", dpi=120)
    plt.close(fig)

    # Edge-era only, re-based to zero - the curve that actually matters.
    edge = d[d["phase"] == "edge"].reset_index(drop=True)
    if len(edge):
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(range(len(edge)), edge["pl"].cumsum(), lw=1.3, color="seagreen")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_title("Cumulative P/L - edge era only (points)")
        ax.set_xlabel("edge-era trade #")
        ax.set_ylabel("cumulative points")
        fig.tight_layout()
        fig.savefig(OUTPUT_DIR / "equity_edge.png", dpi=120)
        plt.close(fig)
    print(f"\nSaved charts -> {OUTPUT_DIR}")


# --------------------------------------------------------------------------- #
# Per-setup expectancy - which of your setups actually pay (edge era only,
# since Setups is only logged there).
# --------------------------------------------------------------------------- #
def per_setup(df: pd.DataFrame) -> None:
    edge = df[(df["phase"] == "edge") & df["Setups"].notna() & df["pl"].notna()]
    if edge.empty:
        return
    g = edge.groupby("Setups")["pl"].agg(
        trades="count", total_pts="sum", expectancy="mean",
        win_rate=lambda s: (s > 0).mean(),
    ).sort_values("expectancy", ascending=False)
    print("\n" + "=" * 66)
    print("PER-SETUP EXPECTANCY (edge era) - ranked by points/trade")
    print("=" * 66)
    with pd.option_context("display.float_format", lambda v: f"{v:,.2f}"):
        print(g.to_string())


# --------------------------------------------------------------------------- #
# What to avoid - the buckets that bleed points. This is the "early junk is
# still valuable because it tells me what NOT to do" angle.
# --------------------------------------------------------------------------- #
def what_to_avoid(df: pd.DataFrame) -> None:
    print("\n" + "=" * 66)
    print("WHAT TO AVOID - mean points by context (edge era where labeled)")
    print("=" * 66)
    edge = df[(df["phase"] == "edge") & df["pl"].notna()]
    factors = [
        "Emotional State", "Process", "Continuation Or Reversal trade",
        "Market Condition", "Position", "DOM agreement?", "Tape Agreement?",
    ]
    for col in factors:
        if col not in edge.columns:
            continue
        sub = edge[edge[col].notna()]
        if sub.empty:
            continue
        g = sub.groupby(col)["pl"].agg(
            trades="count", mean_pts="mean",
            win_rate=lambda s: (s > 0).mean(),
        ).sort_values("mean_pts")
        if g.empty:
            continue
        print(f"\n-- {col} --")
        with pd.option_context("display.float_format", lambda v: f"{v:,.2f}"):
            print(g.to_string())


# --------------------------------------------------------------------------- #
# Information Ratio - best effort. Honest caveats apply for this dataset.
# --------------------------------------------------------------------------- #
def information_ratio(df: pd.DataFrame) -> None:
    print("\n" + "=" * 66)
    print("INFORMATION RATIO (alpha vs NQ) - best effort")
    print("=" * 66)
    edge = df[(df["phase"] == "edge")].dropna(subset=["pl", "date"])
    if edge.empty:
        print("No edge-era trades with dates - skipping.")
        return
    daily = edge.groupby("date")["pl"].sum()

    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed - skipping the NQ regression.")
        print("To enable later:  pip install yfinance  (then re-run).")
        return

    try:
        start, end = daily.index.min(), daily.index.max() + pd.Timedelta(days=1)
        nq = yf.download("NQ=F", start=start, end=end, progress=False,
                         auto_adjust=True)
        if nq is None or nq.empty:
            print("No NQ=F data returned (offline or symbol issue) - skipping.")
            return
        nq_ret = nq["Close"].pct_change()
        if isinstance(nq_ret, pd.DataFrame):
            nq_ret = nq_ret.iloc[:, 0]
        joined = pd.DataFrame({"pl": daily}).join(nq_ret.rename("nq")).dropna()
        if len(joined) < 10:
            print(f"Only {len(joined)} overlapping days - too few for a regression.")
            return
        import statsmodels.api as sm
        X = sm.add_constant(joined["nq"])
        res = sm.OLS(joined["pl"], X).fit()
        alpha = res.params["const"]
        resid = res.resid + alpha
        ir = resid.mean() / resid.std(ddof=1) * np.sqrt(TRADING_DAYS)
        print(f"overlapping days : {len(joined)}")
        print(f"alpha (pts/day)  : {alpha:,.3f}   t = {res.tvalues['const']:.2f}")
        print(f"beta to NQ       : {res.params['nq']:,.3f}")
        print(f"Information Ratio: {ir:,.2f}")
        print("\nCAVEAT: edge-era trades are NinjaTrader Replay (historical sim).")
        print("Their dates are when you PRACTICED, not necessarily the live NQ")
        print("session, so this regression is indicative, not a verdict. IR becomes")
        print("trustworthy once there are live (date-accurate) trades to feed it.")
    except Exception as e:  # network/parse issues shouldn't crash the report
        print(f"IR step skipped ({type(e).__name__}: {e}).")


def main() -> None:
    edge_start = int(sys.argv[1]) if len(sys.argv) > 1 else None
    df = load_trades(edge_start=edge_start)

    print(f"\nLoaded {len(df)} trades  |  "
          f"{df['trade_date'].min():%Y-%m-%d} -> {df['trade_date'].max():%Y-%m-%d}")
    print(f"Accounts: {df['Account'].value_counts(dropna=False).to_dict()}")
    print(f"Phase boundary: edge era = trade #{df.attrs['edge_start']} onward "
          f"({(df['phase']=='edge').sum()} trades)")

    print_phase_table(df)
    plot_equity(df)
    per_setup(df)
    what_to_avoid(df)
    information_ratio(df)


if __name__ == "__main__":
    main()
