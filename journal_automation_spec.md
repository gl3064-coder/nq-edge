# NQ Edge — Journal Automation Spec (2026-06-29)

Source of truth for auto-filling the Notion "Every Single Trade" DB (37 columns).
Goal: machine fills the **objective** fields, the user fills only the **subjective read/state**.
Same division of labor as the co-pilot: bot holds objective context, human owns the read.

## Inputs per session
1. **NinjaTrader trade-history CSV export** → the exact numbers (fills, P/L, MAE/MFE, time, duration).
2. **One chart screenshot per trade** → the visual/structural fields (trend, pullback, ATR panel).
3. **(optional) bars pkl** → objective pullback count via `src/location.py`.

## The 37 columns by source

### A. CONSTANTS — auto, zero input (fixed for current trading)
| Column | Value | Note |
|---|---|---|
| Pair | NQ | |
| Entry Time Frame | 20s | |
| Account | Demo | ⚠️ FLIP to live account name when live (REPLAY/LIVE tag matters) |
| Entry Type | Market | |
| Entry aggression | Passive/Calculated | default; override if Aggressive |
| Position | Long | long-only currently |
| Used DOM? | No | dropped DOM 2026-06-29 |
| DOM agreement? | No | dropped |
| Tape Agreement? | No | dropped |
| Setups | Setup A (11/11) | single setup |
| Used Copilot | Yes | |
| Other Notes | Followed Setup | default; override on exception |

### B. DERIVED — pure functions
| Column | Function |
|---|---|
| Name | last row + 1 |
| Day | weekday(Trade Date) |
| Month | month(Trade Date) |
| Session | NY (time in 09:30–12:00 ET) |
| win | "Win" if P/L > 0 else blank |
| Loss | "Loss" if P/L < 0 else blank |

### C. FROM NINJATRADER EXPORT — exact, no eyeballing
| Column | Source |
|---|---|
| Trade Date | exact fill timestamp |
| P/L | points (journal unit; see flag #5) |
| Max Drawdown | MAE |
| Max Run-up | MFE |
| Trade length | duration ÷ 20s = candle count; bucket Shorter/Medium/Longer |
| Position | direction (confirms) |

### D. FROM CHART IMAGE — I read visually
| Column | What I read |
|---|---|
| Market Bias | overall trend direction (Bullish/Bearish/Neutral) |
| Past Price Action Alignment | context direction = the bot's up/down context |
| Market Condition | Trending Up/Down / Consolidating / Slow |
| Pullback? | Yes/No |
| Pullback Candle Color | Red (Ideal) / Green (Chasing), if visible |
| ATR Range | read off the ATR panel (standardize format — flag #3) |
| Continuation or Reversal | infer: with-trend-after-pullback = Continuation |

### E. OBJECTIFY VIA CODE — better than image or memory
| Column | Source |
|---|---|
| Previous Pullbacks In Trend | `location.py` counts higher-lows from price (kills the circular hand-label) |

### F. USER-ONLY — I will NOT auto-fill (measurement-integrity line)
Filling these with my guess makes the journal measure *my* read, not his, and pollutes the discretion-vs-mechanical signal.
- **Learnings** (the high-value reflection)
- **Emotional State**
- **Process**
- **Present Price Action Alignment** (his read of present PA)
- **Mid-trade intuition**
- **Mid-Trade Intuition Timing**

→ ~31 of 37 fields auto/assisted; **6 are his**, and they're the 6 that matter.

## Data-quality flags found in the current export
1. **Typo:** trade 528 logged `11:58 PM` — should be AM. Automation prevents these.
2. **Learnings = "n/a" for all 7 of today's trades** — the reflection got skipped (friction + tilt). Automating the mechanical fields exists to save energy FOR this field.
3. **ATR Range format drifted:** early = discrete list ("10, 11, 7, 9"); now = ranges ("0-20", "10-30+"). Inconsistent → breaks analysis. Pick one format going forward.
4. **DOM / DOM agreement / Tape columns now always "No"** — dead weight matching the drop-DOM decision. Archive/hide (keep history), stop typing them.
5. **P/L is in POINTS in the journal; the account shows DOLLARS net of fees.** Keep them distinct; export gives both. Consider a separate $ column for net-of-fee truth.
6. **Position / Setups / aggression all constant now** — confirms the simplification (long-only, Setup A, Passive).

## Proposed workflow
1. End of session: export NT trade history CSV + screenshot each trade.
2. Hand both to Claude. Claude builds each row: constants + derived + export numbers + image reads + code-counted pullbacks; leaves the 6 user fields marked `[YOU]`.
3. Claude writes rows to the Notion DB via the connector.
4. User fills the 6 subjective fields. ~5 min, not ~30.
