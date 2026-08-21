# NQ Edge — forward record

The frozen bot's out-of-sample tally. Started 2026-07-28.

**Why this file exists.** The historical sample is spent — roughly 75 configurations
were tried on it, so its t-stat of 1.92 gross / 1.45 net sits at or below its own
multiple-testing bar. Only forward data can move the belief now. This file is the
running total, appended to and never edited.

**Frozen spec** (do not change; changing it restarts the count at zero):

```
signal   up_context + higher_low(k=3) + drawdown_filter(k=3, min_dd=10)
gate     buy_delta >= 0.10  AND  leg_age <= 30 bars
exit     FIXED +30/-20   <- the bot's official exit, and what the t-stat is denominated in
         Trail30 logged alongside  <- his live ATM, the basis for Me-vs-Bot only
window   09:30-12:00 ET, weekdays
bars     NQ, 20 second
```

**Gates, set in advance:** no new historical test until forward n > 400. Clearing
Harvey-Liu-Zhu's t > 3.0 net of cost needs roughly **1,000 trades, about two years**
of recording. A softer t > 2.0 needs about 6 months.

**Run:** `python src/forward_v2.py "Replay Data/<export>.txt"`

---

## ⚠️ Exit correction, 2026-08-03 — read before using any number above or below

This file previously recorded **Trail30 only**, on the line "matches the live ATM". That
was wrong for the bot and it mattered.

The frozen bot's exit is **fixed +30/-20**. The project notes are explicit: *"exit = FIXED
+30/-20 target (NOT Trail30 for the BOT; Trail30 stays his live DISCRETIONARY exit,
different population)."* And the reason is not cosmetic: **the mechanical edge was ~zero
under Trail30 — the fixed target was the lever.** The whole significance budget (t≈1.9 on
~235 trades, ~1,000 needed for t>3.0) is denominated in fixed-exit points, so accumulating
Trail30 points toward that threshold was measuring one strategy against another's finish
line.

Every forward session has been rescored both ways. **Fixed is the official number.** Trail30
stays logged because his own trades use the trailing ATM, which makes it the right basis
for the Me-vs-Bot comparison and nothing else.

**On the obvious objection:** fixed also happens to score better forward (+250.5 vs +188.8),
and switching to the better-looking variant is exactly what this project exists to prevent.
The only thing making it legitimate is that **fixed was the spec first** — designated
2026-07-14, before any of these sessions existed. If the ordering had been the other way
round, the right move would have been to keep Trail30 and eat the worse number.

## Tally

| | fixed +30/-20 (official) | Trail30 (his ATM) |
|---|---|---|
| **Trades** | **52** | 52 |
| **Points** | **+31.7** | −5.2 |
| **Per trade** | **+0.61** | −0.10 |
| **Win rate** | 44% | 44% |
| **Approx. $ on 1 contract** | **+$634** | −$104 |
| Progress to 1,000 | **5.2%** | — |

*Last updated 2026-08-21, after the 8/2-8/21 export. The prior tally (34 trades,
+220.5, +6.49/trade, 56%) is superseded, not deleted. Trail30 has crossed into
negative for the first time.*

## Sessions

**The record of truth is the Notion database "Me vs Bot (Daily)"** (Trading Notebook →
Me vs Bot (Daily)). This file is the project-side mirror. Log every session there.

| date | trades | **fixed** | trail | note |
|---|---|---|---|---|
| 2026-07-15 | 0 | **0.0** | 0.0 | stood down — v1 fired 6 arrows and the gate rejected all of them |
| 2026-07-16 | 5 | **0.0** | −35.0 | ⧉ recovered. Official at last; replaces the provisional −67.25 |
| 2026-07-17 | 1 | **−20.0** | −20.0 | ⧉ recovered. v1 was strongly positive while both gated versions lost. Do not tune on it. |
| 2026-07-20 | 1 | **+30.0** | +10.8 | ⧉ recovered. Tape gate flipped a losing day |
| 2026-07-21 | 2 | **+10.0** | +32.2 | ⧉ recovered. Both gates helped |
| 2026-07-22 | 2 | **+37.0** | +33.8 | ⧉ recovered. Leg gate neutral |
| 2026-07-23 | 0 | **0.0** | 0.0 | ⧉ recovered. Stood down — gate rejected all 3 arrows, worth +11.8. Gate cost a small gain. |
| 2026-07-24 | 4 | **+70.0** | +36.5 | ⧉ recovered. Leg gate added value by dropping one old leg |
| 2026-07-26 | — | — | — | Sunday, not a session |
| 2026-07-27 | 3 | **+25.0** | +5.8 | both gates helped |
| 2026-07-28 | 3 | **−10.0** | +59.0 | the two exits disagree in sign here. v1 beat v2 on a trending day. Do not tune on it. |
| 2026-07-29 | 0 | **0.0** | 0.0 | ⧉ recovered. Stood down — gate rejected all 4 arrows, worth −34.8. Gate saved 34.8. |
| 2026-07-30 | 1 | **+30.0** | +18.8 | tape gate cut 13 arrows to 1; leg gate neutral |
| 2026-07-31 | 1 | **+30.0** | +11.5 | same shape as 7/30; leg gate neutral again |
| 2026-08-03 | 2 | **+48.5** | +35.5 | v1 beat v2 on a green day, same as 7/28. Expected. Do not tune on it. |
| 2026-08-04 | 2 | **+10.0** | −6.8 | one each way; leg gate neutral. The two exits disagree in sign. |
| 2026-08-05 | 3 | **−60.0** | −60.0 | worst session so far. All 3 on the same failing leg — see note below. |
| 2026-08-06 | 1 | **−20.0** | −20.0 | both gates cut the loss (v1 −100 → tape −40 → v2 −20), every survivor still lost |
| 2026-08-07 | 3 | **+40.0** | +36.8 | v1 beat v2 on a green day again. Do not tune on it. |
| 2026-08-10 | 3 | **−10.0** | −7.0 | two stops then a +30; leg gate neutral |
| 2026-08-11 | 3 | **−60.0** | −60.0 | three stops in 48 min on the same failing structure. See cluster note. |
| 2026-08-12 | 0 | **0.0** | 0.0 | stood down — tape gate rejected all 4 arrows, worth −62.5. Gate saved 62.5. |
| 2026-08-13 | 0 | **0.0** | 0.0 | stood down — leg gate cut the one tape survivor (+30). v1 was +180. Gate cost 30, or 180 against ungated. |
| 2026-08-14 | 2 | **−40.0** | −40.0 | both stopped; leg gate neutral |
| 2026-08-17 | 1 | **−20.0** | −20.0 | stopped |
| 2026-08-18 | 3 | **−10.0** | −1.5 | leg gate turned a positive tape-only day (+20.0) negative by cutting a +30 |
| 2026-08-19 | 5 | **−50.0** | −16.8 | most trades in one session so far. Four of the five clustered 10:56-11:22 and all four stopped. |
| 2026-08-20 | 1 | **+1.2** | +1.2 | unresolved at 12:00; exits at last close, the only such trade in the record |

⧉ = recovered from Databento rather than NinjaTrader. See § Recovering lost sessions.

**Fifty-two trades still means nothing.** One different fill swings the sign of the whole
tally, because the tally is now +31.7 points. Do not read a result into this number, and do
not adjust anything because of it.

## 2026-08-21 — the worst stretch of the forward test, and it settles nothing

**18 new trades, −188.8 fixed points, 4 winners of 18. Per-trade goes +6.49 → +0.61.**

Scored `Replay Data/NQ/August 2-21.txt` (NinjaTrader, 9 new sessions 8/10-8/20, full RTH).
8/21 is in the file but has no RTH bars: the export was taken 07:44 ET, before the open.

| | before | now |
|---|---|---|
| trades | 34 | **52** |
| points (fixed) | +220.5 | **+31.7** |
| per trade | +6.49 | **+0.61** |
| win rate | 56% | **44%** |
| Trail30 points | +138.8 | **−5.2** |
| progress to ~1,000 | 3.4% | **5.2%** |

**The forward mean is now +0.61/trade against a historical +3.08 and a placebo of +0.00.**
It sits between them and is statistically indistinguishable from either. Forward t ≈ 0.2
(mean +0.61, sd ≈ 22, n = 52).

**The arithmetic that matters, and it cuts both ways.** If the true edge is the historical
+3.08 with sd 22, then over 52 trades you expect **+160 ± 159 points at one standard
deviation**. The observed +31.7 is 0.8 sd below that. So this stretch does *not* reject the
historical edge — it is an ordinary draw from it. It is equally an ordinary draw from zero.
**52 trades cannot tell +3.08 from +0.00.** That is not a disappointment, it is the reason
the pre-registered gate is n > 400 and not n > 50. Both the +10.02 high on 8/03 and this
low are the same object: noise at small n. Reacting to either would be the error.

**Consistency check passed again, and wider.** 8/3-8/7 appear in this export and in the
8/2-8/9 one. All five sessions re-score **identically** — same trade counts, same entries,
same fixed and trail totals. 8/3 now agrees across **three** independent NinjaTrader
exports. The loader is not the source of variance.

**Correlated clusters, third occurrence — and now it is a pattern.** 8/5 was three re-entries
on one failing leg. This export has two more:

- **8/11**, three stops at 10:06:20 / 10:37:00 / 10:54:40, entries 29778.50 / 29775.25 /
  29794.50, all within 20 points, all −20.
- **8/19**, four stops at 10:56:40 / 10:59:00 / 11:04:20 / 11:22:40, entries 29609.25 /
  29619.25 / 29601.50 / 29624.50, all within 23 points, all −20. The day's one winner was
  earlier and unrelated (10:31:00, +30).

**7 of the 18 new trades sit in two clusters.** The spec counts them as 7 because the spec
does not move, but the independent information here is closer to 2 bets than 7, and the
same was true on 8/5. Across the whole forward record the clusters are consistently
*losses*, which is what a re-entry rule would be expected to catch. **Still not actionable:**
the gate is n > 400 and noticing a candidate fix while losing is exactly the condition under
which fixes get invented. Logged, dated, and deliberately not tested.

**The v1-beats-v2 pattern weakened.** v2 beat v1 on **8 of the 9** new sessions, several
decisively (8/20: v1 −98.8 → v2 +1.2; 8/17: −80 → −20; 8/11: −140 → −60). The count of
v1-beating-v2 sessions goes 5 → **6**, adding only 8/13, where the leg gate cut the single
tape survivor and stood the bot down on a day v1 made +180. On the 8/09 read this looked
like a live doubt about the gates; on this sample the gates earned their keep. Keep counting,
keep not acting.

**New: the leg gate cost money twice in one week** (8/13 stood down a +30 tape trade on a
+180 v1 day; 8/18 turned a +20.0 tape-only day into −10.0). Two sessions. This is the same
class of observation as the 7/30-7/31 note below and gets the same treatment: watch, do not
act.

**Cadence note.** Ad-hoc pull again, not the annual one. The annual-pull plan is unchanged.

---

## 2026-08-09 — first losing week, and it is the regression that was pre-registered

The 8/3-8/7 export (`Replay Data/NQ/8-2 to 8-9.txt`, NinjaTrader, full RTH coverage) added
four new sessions for **9 trades and −30.0 fixed points**, 3 winners of 9. Per-trade went
**+10.02 → +6.49**.

**This was predicted in writing.** The 8/03 entry said the forward +10.02 was running well
above the historical +3.08, that at n=25 it was noise, and to expect regression. It regressed
on the first new week. Nothing about the frozen spec changes.

**8/5 is one event, not three.** The three losing entries were 11:35:40, 11:37:00 and
11:39:40 at 29833.75 / 29841.25 / 29843.25 — the same up-leg failing, re-entered twice as it
went. All three stopped. The tally counts 3 trades because the spec says so and the spec does
not move, but the *independent* information in that session is closer to one bet than three.
Same shape as the cross-asset simultaneity error caught 2026-08-04: **correlated observations
inflate n without adding evidence.** Worth a re-entry-cooldown test one day; not now, the
pre-registration gate is forward n > 400 and we are at 34.

**Consistency check passed.** 8/3 was already in this record at +48.5 fixed / +35.5 trail from
a different export (`7.27 to 8.03.txt`). Re-scored from the new file it returns +48.5 / +35.5,
n=2, same two entries. Two NinjaTrader exports of the same session agree exactly.

**The v1-beats-v2 count is now five** (7/22, 7/28, 8/3, 8/6, 8/7). Still logged, still not
acted on, but it is no longer a two-session curiosity. If it is still there at n > 400 it is
the first thing to look at.

**Watch, do not act on:** on 7/30 and 7/31 the ungated v1 was heavily negative and the
tape gate alone flipped both positive, while the leg gate contributed nothing. Two
sessions. Logged so it can be checked later against a real sample, not acted on now.

## Recovering lost sessions — the gaps are no longer permanent

**All eight lost sessions were recovered on 2026-08-03 for $2.83.** This section used to
say the ticks were gone forever. That was wrong, and the error is worth keeping visible:
the ticks were gone *from NinjaTrader*, which is not the same thing as gone.

| was missing | trading days | status |
|---|---|---|
| 2026-07-16 (RTH) | 1 | ⧉ recovered — 5 trades, −35.0 |
| 2026-07-17 → 2026-07-24 | 6 | ⧉ recovered — 10 trades, +93.3 |
| 2026-07-29 | 1 | ⧉ recovered — 0 trades, gate stood down |

**The route.** Databento `GLBX.MDP3`, schema `tbbo`, symbol `NQU6`, RTH window only
(13:00–16:00 UTC, which covers the SMA50 warmup before 09:30 ET). Loader is
`src/databento_bars.py`; it feeds the unchanged `forward_v2` chain.

**Why `tbbo` and not `trades`.** `trades` carries the exchange's own aggressor flag, which
is a genuinely better estimator of buy_delta than inferring it from Last-vs-bid/ask. It was
rejected anyway. The record already contains sessions measured the NinjaTrader way, and a
tally mixing two estimators is not one tally. `tbbo` ships the bid/ask alongside each
trade, so `ticks.py`'s exact rule is reapplied unchanged and the `side` column is ignored.
Same discipline as rejecting the yield proxies on News Corpus: verify the substitute
reproduces the original before adopting it, and prefer consistency over a better number.

**The validation, which was run before any of this was trusted.** 2026-07-30 exists in both
sources. Scored from Databento it returns the identical result: v1 13 arrows → −74.0,
tape-only 1 → +18.8, v2 1 trade at 09:59:20 with tape 0.11532, leg_age 30, +18.75. Across
540 overlapping bars, buy_delta correlation was 0.9997 and **zero bars disagreed on the
0.10 gate decision**. OHLC is not byte-identical (502/540 opens match, max divergence 3.25
pts) — the sources filter some trade types differently — so this is "reproduces", not "is
the same file". The single v2 trade also sat exactly at leg_age = 30, the gate boundary,
so the 540-bar evidence is the load-bearing part, not the one-trade match.

**7/16 is settled, and the old note called it.** Official v2 = 5 trades, −35.0, replacing
the provisional −67.25 computed from the live tape log with close-only, wick-blind exits.
The Notion note had predicted those exits understated the day because the 10:35/10:37 spike
arrows likely filled on the ~29515 wick, and guessed a swing of +50 to +110. Actual swing
was +32.25 on v2 and +34.5 on tape-only. Right reasoning, slightly conservative. 7/16 now
has a real Me-vs-Bot comparison for the first time: him +81.75 over 6 trades against the
bot's −35.0 over 5.

**What this changes going forward.** A recording gap now costs about **$0.35 and an hour**,
not a permanent hole. That is worth far more than the 15 trades it just recovered.

Keeping NT recording still matters — it is free, it is same-day, and it avoids a purchase
and a loader run per gap. But it is now a convenience, not the thing the project's survival
rests on. **Check the recorder weekly; when it has failed, buy the gap rather than
mourning it.**

---

## Related finding — the placebo entry test (2026-07-28)

`src/placebo_entry.py`. Buying at a **random** moment in the same 09:30-12:00 window
with the same +30/-20 bracket returns **+0.00 pts/trade** (95% range −3.07 to +3.08)
against the frozen bot's **+3.08**, putting the bot at the **97.5th percentile**.

**What it settles:** the edge is not intraday drift. The bot is long-only, so drift was
a live alternative explanation, and it is now ruled out — everything it earned came from
*when* it chose to be long. This is the third piece of evidence from outside the searched
sample, alongside the Databento cross-asset result and the live-delta validation.

**What it does not settle:** the search problem, which remains the main doubt. Drift and
selection bias are different failure modes and this test speaks only to the first. The
margin is also thin — +3.08 against a random range topping out at +3.08.
