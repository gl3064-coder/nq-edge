# Cross-asset / breadth tests — full record

The frozen NQ rule, ported to other futures. This file exists because the first version of
this test was **wrong, published, and retracted**, and the honest thing is to show the
whole sequence rather than only the final number.

**Verdict: the edge is NQ-specific.** The frozen rule was ported to **six other
instruments** (crude, gold, bonds, heating oil, gasoline, Bitcoin). None of them survives
costs, at sample sizes large enough to say so.

---

## 1. What was originally claimed, and retired

A July 2026 breadth test reported the frozen rule as gross-positive on crude and bonds,
and that result was used as evidence the signal was not curve-fit to NQ.

**Retired 2026-08-04.** It was computed with a mis-specified scaling anchor.

### The bug

The port scaled every instrument's stop as `20 / A_NQ * that market's ATR`, with `A_NQ`
hardcoded to **17.0**.

NQ's measured median 20-second true range is **4.75 all-hours** and **11.75 in the
09:30-12:00 session the bot actually trades**. 17.0 matches neither. So "the same risk NQ
takes, expressed in this market's units" was never preserved.

A second error rode along: each instrument's ATR was measured **all-hours**, while the
strategy only trades the NY session. Two different windows inside one formula.

### The self-consistency test that catches it

If the anchor is NQ's own session ATR, then running the scaled port *on NQ* must reproduce
the frozen spec exactly.

| anchor | result on NQ |
|---|---|
| `A_NQ = 11.75` | stop 20.00, n=235, +0.154R, t=1.92 — **identical to frozen** |
| `A_NQ = 17.0` | a **5.6-point stop** on the very instrument it was anchored to |

**Any future rescaling must pass this test before its output means anything.**

### Corrected results, 2026-08-04 (gross, session-measured ATR, anchor 11.75)

| instrument | corrected | July claim (retired) |
|---|---|---|
| NQ frozen | +0.154R t=1.92 n=235 | unchanged |
| Crude CL | +0.204R t=1.42 **n=74** | +0.165R t=2.00 n=228 |
| Bonds ZN | **−0.166R t=−1.17** | +0.409R t=4.00 n=145 |
| Gold GC | −0.004R t=−0.06 | never claimed |
| Heating oil HO | +0.028R t=0.51, 6/12 contracts positive | never claimed |

Trade counts collapsed because the corrected stops are ~2.5x larger, which scales `min_dd`
up and filters most signals out.

At n=64-74 this was **not a disproof**. It retired the July figures, because they came from
a formula that provably breaks on its own anchor, and left the question open.

---

## 2. The full-year re-test, 2026-08-05 — this is the one with power

The 8/04 correction left the question open at n=64-74. Re-running on full-year data closed
it at **n=294-532 per instrument**.

Net column is 1 tick + $4.50 commission.

| instrument | n | gross | net | verdict |
|---|---|---|---|---|
| CL as-coded | 532 | +0.101R t=1.90 | **−0.140R t=−2.61** | cost eats the edge, decisively |
| CL NQ-matched gate | 413 | +0.174R t=2.86 | −0.069R t=−1.12 | same story, marginal net |
| RB as-coded | 479 | +0.106R t=1.88 | −0.019R t=−0.34 | flat null; cheaper costs saved it from CL's fate |
| BTC as-coded | 351 | +0.022R t=0.33 | −0.058R t=−0.89 | null gross, despite a good cost structure |
| HO | 474 | +0.028R t=0.51 | ~flat | still null |

Two tape-gate variants are reported for CL because 8/04's NQ-matched fix helped CL and hurt
RB. It is not a clean win, so it stays as an alternative, not a replacement.

**This is what makes the conclusion sayable.** Instruments spanning different asset classes,
cost structures and sessions. No pattern of confirmation anywhere.

---

## 3. The rescue hypothesis, tested and killed

Jun-Jul 2026 fired positive across CL, RB and HO simultaneously. The obvious hypothesis:
"trade only in high-vol contracts."

Split at median ATR per instrument, pooled: **HIGH-vol −0.051R vs LOW-vol −0.114R, Welch
t = 0.97.** Not significant even in-sample. HO actively reverses direction, with low-vol
beating high-vol.

One in favour, one against, one slight. That is pattern-recognition, not a regime effect.

> **The rule worth keeping:** cross-asset simultaneity is not independence. Three energy
> contracts moving together in Jun-Jul is **one event scored three times.**

---

## 4. Gold: closed, with all five looks on the record

Six months of `GC.n.0` tbbo bought from Databento for **$27.63** (Jan-Jul 2026).

Under five different ATR conventions gold ranged from **+0.165R (t=2.42) to −0.004R
(t=−0.06)**, and three of four contracts were negative in the NinjaTrader replication.

All five looks are recorded here so no future session can cherry-pick one:

| look | result |
|---|---|
| Databento pooled | +0.165 |
| NinjaTrader pooled | +0.140 |
| per-contract | +0.024 |
| per-day causal | +0.078 |
| corrected anchor | −0.004 |

**A result that exists under one arbitrary convention was never a result.** Gold is closed.
Do not forward-test it and do not buy the COMEX subscription for it.

---

## 5. Two bugs found along the way, both worth more than the result

**The `.c.0` vs `.n.0` roll bug.** The July gold pull returned ~150 trades/day against a
market doing ~270,000. `GC.c.0` rolls by *calendar*, and gold's liquidity skips months.
`GC.n.0` rolls by *open interest*: **649x more data, 81,894 trades/day.** Crude and bonds
were unaffected because their calendar-front months are liquid. See `src/pull_gold.py`.

**`ticks.py` is independently validated.** NinjaTrader vs Databento bars on 2026-04-15:
451 bars each on identical timestamps, median close difference **0.000**, buy_delta
correlation **0.9987**, **100%** agreement on the 0.10 tape gate. The loader the entire
forward record runs through has been checked against a commercial vendor.

Also worth recording: **NinjaTrader exports other-exchange tick history for free.** The
$27.63 bought data that was already available.

---

## 6. What this does and does not support

**Supported.** The frozen bot's signal is **NQ-specific**, most likely a microstructure
feature (tick size, participant mix, futures-index basis dynamics) rather than a universal
buyers-pressing-into-drawdown pattern. This is a scope statement and a limitation.

**Also supported, and it is the point.** The search was not continued until something
worked. Six instruments were tested and every one reported as a null, including one that
cost money to test.

**NOT supported, and previously claimed in error:** that these results are evidence the
mechanism is *real*. Null results elsewhere cannot validate a result here. That claim
appeared in `src/significance_audit.py`, in `FORWARD_RECORD.md`, and in a README bullet
written 2026-08-23, nineteen days after the pillar had already been retired. All three were
retracted 2026-09-07.

Evidence from outside the searched sample is **two** items, not three: the placebo entry
test and the live-delta validation.

---

## 7. Caveats

- **This code was written in one session and has not been independently reviewed.**
  `cross_asset_v2.py`, `gold_nt_check.py`, `gold_reconcile.py`, `atr_sensitivity.py`,
  `rescale_corrected.py`, `ho_test.py`, `breadth_check.py`, `audit_gold.py`, `pull_gold.py`.
  The 8/05 re-tests (`cl_test.py`, `rb_test.py`, `btc_test.py`, `vol_regime.py`) follow the
  same template. Treat the numbers as provisional in that sense.
- The 8/05 runs were pre-registered, one run each, `A_NQ = 11.750`.
- Ported to **six** instruments beyond NQ: GC, ZN, CL, HO, RB, BTC. None survives costs.
  ZN was tested on Databento data (`Replay Data/databento/CLGCZN_6mo_2026-01_2026-07.dbn`)
  rather than a NinjaTrader replay folder, which is why it has no `zn_test.py`.
