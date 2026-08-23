"""
pull_databento.py — pull CME futures TRADES from Databento for the breadth test.

Trades schema = smallest/cheapest data, and it carries the exchange aggressor `side`
flag, which is exactly what buy_delta needs (cleaner than our Last-vs-bid/ask method).

SETUP (keeps your key out of files/chat):
  Windows cmd:         set DATABENTO_API_KEY=db-xxxxxxxx
  PowerShell:          $env:DATABENTO_API_KEY = "db-xxxxxxxx"
Then run this in YOUR terminal (it needs the key + an interactive y/n):
  C:\Users\lgavi\anaconda3\python.exe src\pull_databento.py

It PREVIEWS the cost first and only downloads if you type y. Start with ES; if it's
cheap, widen the dates or add CL/GC/ZN. Edit the four knobs below.
"""
from pathlib import Path
import databento as db

DATASET = "GLBX.MDP3"                 # CME Globex
SCHEMA  = "trades"                    # cheapest; has aggressor side
STYPE   = "continuous"               # front-month continuous (auto-roll)
SYMBOLS = ["ES.c.0"]                  # start here; later: ["CL.c.0","GC.c.0","ZN.c.0"]
START   = "2026-01-01"               # match your NQ window first (cheap, clean replication)
END     = "2026-07-01"
OUTDIR  = Path(__file__).resolve().parent.parent / "Replay Data" / "databento"

client = db.Historical()             # reads DATABENTO_API_KEY from env

cost = client.metadata.get_cost(dataset=DATASET, symbols=SYMBOLS, stype_in=STYPE,
                                schema=SCHEMA, start=START, end=END)
size = client.metadata.get_billable_size(dataset=DATASET, symbols=SYMBOLS, stype_in=STYPE,
                                         schema=SCHEMA, start=START, end=END)
print(f"\n{SYMBOLS}  {START} -> {END}  schema={SCHEMA}")
print(f"ESTIMATED COST = ${cost:,.2f}    (billable size {size/1e6:,.1f} MB)")
print("your $125 credit should cover a lot of this at trades resolution.\n")

if input("download now? type y to confirm: ").strip().lower() != "y":
    raise SystemExit("aborted — no charge.")

OUTDIR.mkdir(parents=True, exist_ok=True)
data = client.timeseries.get_range(dataset=DATASET, symbols=SYMBOLS, stype_in=STYPE,
                                   schema=SCHEMA, start=START, end=END)
tag = "_".join(s.replace(".", "") for s in SYMBOLS)
out = OUTDIR / f"{tag}_{START}_{END}.csv"
data.to_csv(out, pretty_px=True, pretty_ts=True, map_symbols=True)
print(f"\nsaved -> {out}\ndrop me a note and I'll wire the loader (buy_delta from `side`).")
