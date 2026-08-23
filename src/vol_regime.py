"""vol_regime.py - IN-SAMPLE test: does the observed vol-regime split hold up?

CAVEAT AT THE TOP. The rule (only trade in high-vol contracts) was noticed by
staring at cl_test.py + rb_test.py + ho_test.py outputs on 2026-08-04. Running
it on the same data is an in-sample test. If it shows a large effect, that is
the CEILING on what the rule could deliver, not evidence it will work forward.
The pre-registered version has to be tested on future data.

WHAT THIS DOES. For each of CL, RB, HO:
  1. Run the frozen bot on every monthly contract (as coded, single-bar 66.67).
  2. Rank contracts by their own session-median ATR.
  3. Split at the median ATR into HIGH-VOL half and LOW-VOL half.
  4. Report pooled gross and net for each half. Test the difference in net.

Cost is fixed in price, so a bigger stop makes cost-in-R smaller. That means
both the gross edge and the cost picture should improve in the high-vol half
simultaneously, if the story is real.
"""
from __future__ import annotations

import gc as _gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ticks import load_bars
from context import up_context
from location import higher_low_signal
from drawdown import drawdown_filter

NQ_STOP, RR, NQ_MIN_DD, LEG_THR = 20.0, 1.5, 10.0, 30
NY = ("09:30", "12:00")
A_NQ = 11.750
ROOT = Path(__file__).resolve().parent.parent / "Replay Data"

INSTRUMENTS = {
    "CL": {"tick": 0.01,   "mult": 1000.0,  "comm": 4.50,
           "order": [f"CL {m}" for m in ["09-25","10-25","11-25","12-25",
                                          "01-26","02-26","03-26","04-26",
                                          "05-26","06-26","07-26","08-26","09-26"]]},
    "RB": {"tick": 0.0001, "mult": 42000.0, "comm": 4.50,
           "order": [f"RB {m}" for m in ["09-25","10-25","11-25","12-25",
                                          "01-26","02-26","03-26","04-26",
                                          "05-26","06-26","07-26","08-26","09-26"]]},
    "HO": {"tick": 0.0001, "mult": 42000.0, "comm": 4.50,
           "order": [f"HO {m}" for m in ["10-25","11-25","12-25","01-26","02-26",
                                          "03-26","04-26","05-26","06-26",
                                          "07-26","08-26","09-26"]]},
}


def tr(b):
    p = b["close"].shift(1)
    return pd.concat([b["high"] - b["low"], (b["high"] - p).abs(),
                      (b["low"] - p).abs()], axis=1).max(axis=1)


def exit_fixed(entry, high, low, close, start, stop, target):
    for j in range(start, len(close)):
        if low[j] <= entry - stop:
            return -stop
        if high[j] >= entry + target:
            return target
    return float(close[-1] - entry)


def run_contract(bars, stop, thr):
    target, min_dd = RR * stop, NQ_MIN_DD / NQ_STOP * stop
    m = bars.between_time(*NY)
    rows = []
    for d, grp in m.groupby(m.index.date):
        if len(grp) < 60:
            continue
        out = up_context(grp["close"], fast=20, slow=50, slope_lookback=10)
        upc = out["up_context"].to_numpy().astype(bool)
        a = higher_low_signal(out["close"], out["up_context"], k=3)
        sig = drawdown_filter(out["close"], a, k=3, min_dd=min_dd)
        close = out["close"].to_numpy()
        g = grp.loc[out.index]
        high, low, bd = g["high"].to_numpy(), g["low"].to_numpy(), g["buy_delta"].to_numpy()
        n = len(close)
        rl = np.zeros(n, dtype=int)
        for j in range(n):
            rl[j] = rl[j - 1] + 1 if upc[j] else 0
        for i in np.where(sig.to_numpy())[0]:
            if i - 3 < 0 or i + 1 >= n:
                continue
            if np.nanmean(bd[i - 2:i + 1]) < thr or rl[i] > LEG_THR:
                continue
            rows.append(exit_fixed(float(close[i]), high, low, close,
                                   i + 1, stop, target) / stop)
    return rows


def scan_instrument(sym):
    cfg = INSTRUMENTS[sym]
    cost_price = cfg["tick"] + cfg["comm"] / cfg["mult"]
    folder = ROOT / sym
    prev_end = None
    entries = []
    for name in cfg["order"]:
        p = folder / f"{name}.Last.txt"
        if not p.exists():
            continue
        b = load_bars(p)
        if prev_end is not None:
            b = b[b.index > prev_end]
        if b.empty:
            continue
        prev_end = b.index.max()
        sess = b.between_time(*NY)
        atr = float(tr(sess).median())
        if not np.isfinite(atr) or atr <= 0:
            continue
        stop = NQ_STOP / A_NQ * atr
        thr = float(np.nanpercentile(sess["buy_delta"].to_numpy(), 66.67))
        rs = np.array(run_contract(b, stop, thr))
        cost_R = cost_price / stop
        entries.append({"name": name, "atr": atr, "stop": stop,
                        "cost_R": cost_R, "R": rs})
        del b
        _gc.collect()
    return entries, cost_price


def pool(entries, indices):
    R = np.concatenate([entries[i]["R"] for i in indices]) if indices else np.array([])
    net = np.concatenate([entries[i]["R"] - entries[i]["cost_R"] for i in indices]) \
        if indices else np.array([])
    return R, net


def stats(a):
    if len(a) < 2:
        return len(a), np.nan, np.nan
    return len(a), a.mean(), a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))


def welch(a, b):
    """Two-sample Welch t for mean(a) - mean(b)."""
    if len(a) < 2 or len(b) < 2:
        return np.nan
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se = np.sqrt(va / len(a) + vb / len(b))
    if se == 0:
        return np.nan
    return (a.mean() - b.mean()) / se


def main():
    print("=" * 84)
    print("VOL-REGIME SPLIT (IN-SAMPLE, exploratory)")
    print("=" * 84)
    print("Rule: split contracts at median ATR. High-vol half vs low-vol half.")
    print("This rule was chosen after seeing the data. Results are a CEILING.\n")

    all_results = {}
    for sym in ["CL", "RB", "HO"]:
        entries, _ = scan_instrument(sym)
        atrs = np.array([e["atr"] for e in entries])
        med = float(np.median(atrs))
        hi_idx = [i for i, e in enumerate(entries) if e["atr"] >= med]
        lo_idx = [i for i, e in enumerate(entries) if e["atr"] < med]

        print(f"--- {sym} ---   {len(entries)} contracts, median ATR = {med:.5f}")
        print(f"  HIGH-vol: {[entries[i]['name'] for i in hi_idx]}")
        print(f"  LOW-vol : {[entries[i]['name'] for i in lo_idx]}")

        R_hi, net_hi = pool(entries, hi_idx)
        R_lo, net_lo = pool(entries, lo_idx)

        for label, R, net in [("HIGH-vol half", R_hi, net_hi),
                              ("LOW-vol  half", R_lo, net_lo)]:
            n, mR, tR = stats(R)
            _, mN, tN = stats(net)
            print(f"  {label}   n={n:>4}   "
                  f"gross {mR:+.3f}R t={tR:+.2f}   "
                  f"net {mN:+.3f}R t={tN:+.2f}")

        # difference test on NET
        t_diff = welch(net_hi, net_lo)
        print(f"  net(hi) - net(lo) = {net_hi.mean() - net_lo.mean():+.3f}R   "
              f"Welch t = {t_diff:+.2f}\n")

        all_results[sym] = {"hi": (R_hi, net_hi), "lo": (R_lo, net_lo)}

    print("=" * 84)
    print("POOLED ACROSS ALL THREE ENERGY INSTRUMENTS")
    print("=" * 84)
    R_hi = np.concatenate([all_results[s]["hi"][0] for s in all_results])
    net_hi = np.concatenate([all_results[s]["hi"][1] for s in all_results])
    R_lo = np.concatenate([all_results[s]["lo"][0] for s in all_results])
    net_lo = np.concatenate([all_results[s]["lo"][1] for s in all_results])

    for label, R, net in [("HIGH-vol pooled", R_hi, net_hi),
                          ("LOW-vol  pooled", R_lo, net_lo)]:
        n, mR, tR = stats(R)
        _, mN, tN = stats(net)
        print(f"  {label}   n={n:>4}   "
              f"gross {mR:+.3f}R t={tR:+.2f}   "
              f"net {mN:+.3f}R t={tN:+.2f}")

    t_diff = welch(net_hi, net_lo)
    print(f"\n  net(hi) - net(lo) = {net_hi.mean() - net_lo.mean():+.3f}R   "
          f"Welch t = {t_diff:+.2f}")
    print("\nReminder: this rule was chosen after seeing the results.")
    print("A pre-registered forward test is what would count.")


if __name__ == "__main__":
    main()
