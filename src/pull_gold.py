"""pull_gold.py — buy GC (gold) tbbo from Databento, the way that actually works.

WHY THIS EXISTS
The 2026-07-14 CL/GC/ZN pull used `GC.c.0` and the gold came back useless:
20,428 trades over six months, about 150/day, against a real market doing
roughly 270,000 contracts/day. Crude and bonds were fine from the same pull.

THE BUG WAS THE ROLL RULE, NOT THE MONTH.
    GC.c.0  (calendar roll)          980,544 bytes    $0.03
    GC.n.0  (open-interest roll)   635,734,944 bytes  $16.58   <- 649x
Gold's liquidity skips months (Feb/Apr/Jun/Aug/Oct/Dec carry the volume), so a
calendar-front roll lands on dead contracts. Crude is liquid every month and ZN
is quarterly, which is why `.c.0` worked for them and not for gold.

SCHEMA: tbbo, NOT trades.
`trades` carries the exchange aggressor flag, which is a *better* buy_delta
estimator and therefore the wrong one — the record is made of NinjaTrader-style
inference and a tally mixing two estimators is not one tally. `tbbo` ships
bid/ask per trade so ticks.py's rule reapplies unchanged. Same argument as the
header of databento_bars.py. Output CSV columns match what that loader reads.

COST (measured 2026-08-04 via the free get_cost endpoint, month by month):
    Jan 6.80 | Feb 4.48 | Mar 4.66 | Apr 4.09 | May 3.42 | Jun 4.19  = $27.63

KNOWN ISSUE: on 2026-08-04 every timeseries call returned 504 at exactly 60s.
Databento's status page had an open incident, "Consistent 504 timeout on the
Historical API". Metadata calls worked; data calls did not. Retry when green:
https://status.databento.com/

Run:  $env:DATABENTO_API_KEY = [Environment]::GetEnvironmentVariable("DATABENTO_API_KEY","User")
      C:\Users\lgavi\anaconda3\python.exe src\pull_gold.py
"""
from __future__ import annotations

import os
from pathlib import Path

import databento as db

OUT = Path(__file__).resolve().parent.parent / "Replay Data" / "databento"
SYMBOL = "GC.n.0"          # open-interest roll. NOT .c.0 — see docstring.
SCHEMA = "tbbo"            # NOT trades — see docstring.

MONTHS = [
    ("2026-01-01", "2026-02-01"), ("2026-02-01", "2026-03-01"),
    ("2026-03-01", "2026-04-01"), ("2026-04-01", "2026-05-01"),
    ("2026-05-01", "2026-06-01"), ("2026-06-01", "2026-07-01"),
]


def main() -> None:
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise SystemExit("DATABENTO_API_KEY not set in this shell")

    OUT.mkdir(parents=True, exist_ok=True)
    client = db.Historical(key)

    for start, end in MONTHS:
        tag = start[:7]
        dest = OUT / f"GC_n0_tbbo_{tag}.csv"

        # Skip anything already downloaded so a rerun never double-charges.
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"{tag}  SKIP  ({dest.stat().st_size:,} bytes already on disk)")
            continue

        try:
            store = client.timeseries.get_range(
                dataset="GLBX.MDP3", symbols=[SYMBOL], stype_in="continuous",
                schema=SCHEMA, start=start, end=end,
            )
            store.to_csv(dest)
            print(f"{tag}  OK    {dest.stat().st_size:,} bytes -> {dest.name}")
        except Exception as exc:  # noqa: BLE001
            # Deliberately no retry: a retried partial delivery can bill twice.
            print(f"{tag}  FAIL  {type(exc).__name__}: {str(exc)[:110]}")

    print(f"\nfiles in {OUT}")
    print("next: load with src/databento_bars.py, then check trades/day is "
          "in the hundreds of thousands, not the hundreds.")


if __name__ == "__main__":
    main()
