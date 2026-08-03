"""
experiment_reverse_short.py — his hypothesis (trade #550): after the morning uptrend, NQ
often fades for a long midday stretch. Does REVERSING his long setup into a short setup make
money there, and does adding it raise his OVERALL Sharpe (diversification)?

Every condition mirrored (a real short setup, not just "sell when long says buy"):
  up-context      -> down-context  (fast MA < slow MA, slow MA FALLING)
  higher-low      -> lower-high    (pivot highs, each below the prior)
  drawdown-into-low -> runup-into-high (require a real rally into the pivot high first)

Down-context IS the midday-fade regime filter (only fires when actually trending down), so no
hard-coded time window. Reported by hour anyway to check the midday-concentration claim.

Exit: fixed +30/-20 first-touch on OHLC (mirrored for shorts). Same session 9:30-12:00 as the
long tests, for apples-to-apples on the combined-Sharpe question.

Run:  python src/experiment_reverse_short.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import up_context
from location import higher_low_signal, PIVOT_K
from drawdown import drawdown_filter, LOOKBACK, MIN_DD
from experiment_entry_fill import exit_first_touch, STOP, TARGET, DATA, FILES, SESSION


# ---- mirrored short-side signal ----
def down_context(close: pd.Series, fast=20, slow=50, slope=10) -> np.ndarray:
    fma = close.rolling(fast, min_periods=fast).mean()
    sma = close.rolling(slow, min_periods=slow).mean()
    flag = (fma < sma) & (sma.diff(slope) < 0)
    return flag.fillna(False).to_numpy()


def pivot_highs(c: np.ndarray, k=PIVOT_K) -> np.ndarray:
    n = len(c); piv = np.zeros(n, bool)
    for i in range(k, n - k):
        if c[i] == c[i - k:i + k + 1].max():
            piv[i] = True
    return piv


def short_signal(c: np.ndarray, down: np.ndarray, k=PIVOT_K) -> np.ndarray:
    sig = np.zeros(len(c), bool)
    prev = None
    for pos in np.where(pivot_highs(c, k))[0]:
        if prev is not None and c[pos] < c[prev]:      # lower high (downtrend structure)
            conf = pos + k
            if conf < len(c) and down[conf]:
                sig[conf] = True
        prev = pos
    return sig


def runup_filter(c: np.ndarray, sig: np.ndarray, k=PIVOT_K,
                 lookback=LOOKBACK, min_ru=MIN_DD) -> np.ndarray:
    sig = sig.copy()
    for i in np.where(sig)[0]:
        pivot = i - k
        if pivot <= 0:
            sig[i] = False; continue
        window = c[max(0, pivot - lookback):pivot + 1]
        sig[i] = bool(c[pivot] - window.min() >= min_ru)   # real rally into the high
    return sig


def exit_short(entry, high, low, close, start):
    tp, sl = entry + (-TARGET), entry + STOP     # target below, stop above
    for j in range(start, len(close)):
        if high[j] >= sl:
            return "loss", -STOP
        if low[j] <= tp:
            return "win", TARGET
    return "unresolved", float(entry - close[-1])


HOURS = {9: "9-10", 10: "10-11", 11: "11-12"}


def main() -> None:
    rows = []
    for name, mindate in FILES:
        b = pd.read_pickle(DATA / f"bars_{name}.pkl")
        t = b.index
        m = b[(t.dayofweek < 5) & (t.time >= SESSION[0]) & (t.time <= SESSION[1])]
        if mindate:
            m = m[m.index.date >= pd.Timestamp(mindate).date()]
        for d, grp in m.groupby(m.index.date):
            out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
            g = grp.loc[out.index]
            close = out["close"].to_numpy()
            high, low = g["high"].to_numpy(), g["low"].to_numpy()
            bd = g["buy_delta"].to_numpy()
            hrs = g.index.hour.to_numpy()
            n = len(close)
            day = f"{name}_{d}"
            # LONG (existing)
            la = higher_low_signal(out["close"], out["up_context"])
            lsig = drawdown_filter(out["close"], la).to_numpy()
            for i in np.where(lsig)[0]:
                if i - PIVOT_K < 0 or i + 1 >= n:
                    continue
                _, pl = exit_first_touch(float(close[i]), high, low, close, i + 1)
                rows.append({"day": day, "side": "long", "pl": pl, "hour": hrs[i]})
            # SHORT (mirrored)
            down = down_context(out["close"])
            ss = runup_filter(close, short_signal(close, down))
            for i in np.where(ss)[0]:
                if i - PIVOT_K < 0 or i + 1 >= n or i < 3:
                    continue
                _, pl = exit_short(float(close[i]), high, low, close, i + 1)
                rows.append({"day": day, "side": "short", "pl": pl, "hour": hrs[i],
                             "tape": float(np.nanmean(bd[i - 2:i + 1]))})

    df = pd.DataFrame(rows)
    all_days = df["day"].unique()

    def stat(x):
        x = x.dropna()
        return (len(x), (x == TARGET).mean() * 100, x.mean(), x.sum())

    def dsharpe(sub):
        daily = sub.groupby("day")["pl"].sum().reindex(all_days, fill_value=0.0)
        return daily.mean() / daily.std() if daily.std() else float("nan"), daily

    L, S = df[df.side == "long"], df[df.side == "short"]
    print(f"\nsessions: {len(all_days)} | fixed {TARGET:.0f}/{STOP:.0f} exit\n")
    print(f"{'book':<10}{'n':>5}{'win%':>7}{'avg':>8}{'net':>8}{'dSharpe':>9}")
    print("-" * 47)
    for tag, sub in [("LONG", L), ("SHORT", S)]:
        n, w, a, net = stat(sub["pl"])
        sh, _ = dsharpe(sub)
        print(f"{tag:<10}{n:>5}{w:>6.0f}%{a:>8.2f}{net:>8.0f}{sh:>9.3f}")

    # does adding shorts raise overall Sharpe?
    shL, dL = dsharpe(L)
    shS, dS = dsharpe(S)
    comb = dL + dS
    shC = comb.mean() / comb.std()
    print(f"\nDIVERSIFICATION (the hypothesis):")
    print(f"  long only        net {dL.sum():>6.0f}   daily Sharpe {shL:>6.3f}")
    print(f"  long + short     net {comb.sum():>6.0f}   daily Sharpe {shC:>6.3f}")
    print(f"  daily long/short corr: {dL.corr(dS):+.2f}")

    print(f"\nSHORT book by hour (midday-concentration check):")
    for h, lab in HOURS.items():
        sub = S[S.hour == h]
        if len(sub):
            n, w, a, net = stat(sub["pl"])
            print(f"  {lab:<7} n={n:>4}  win%={w:>3.0f}  avg={a:>6.2f}  net={net:>6.0f}")

    # bonus: strong SELL tape gate on shorts (bottom third of buy_delta)
    if "tape" in S and S["tape"].notna().any():
        thr = S["tape"].quantile(1 / 3)
        g = S[S["tape"] <= thr]
        n, w, a, net = stat(g["pl"])
        print(f"\nSHORT + strong sell-tape (bottom third): n={n} win%={w:.0f} "
              f"avg={a:.2f} net={net:.0f}")


if __name__ == "__main__":
    main()
