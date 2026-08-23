# NQ Edge — Quantitative Trading Research Pipeline

A Python research pipeline that takes my own journaled NQ futures trades, turns
discretionary intuition into quantified, testable rules, and grades every setup with the
same discipline used to evaluate a real strategy: expectancy, Sharpe, information ratio,
and out-of-sample plus multiple-testing controls.

The headline is deliberately modest, and that is the point. The entry edge is real but
small (t ≈ 1.9 gross / 1.45 net over ~235 trades), and it was found only after trying
~75 configurations. So rather than overclaim it, the strategy is **frozen and running a
pre-registered forward test** before any further historical work. What this repo
demonstrates is the research process, not a turnkey money printer.

## The signal pipeline

Each long setup passes through:

1. **context** — trend / regime filter (moving-average based); longs only in up-context.
2. **location** — higher-low pullback detection.
3. **drawdown** — requires a genuine pullback before entry.
4. **tape gate** — order-flow confirmation (buy-delta) and a young-leg age cap.
5. **scoring** — grades the setup by expectancy, Sharpe, and information ratio.

The bot's exit is a fixed +30 / −20 bracket, and the t-stat is denominated in that. Trail30,
my live discretionary exit, is logged alongside for a me-vs-bot comparison only.

## The part that matters: how hard I tried to kill it

- **Multiple-testing audit** — `src/significance_audit.py`. Deflated Sharpe, minimum
  backtest length, and the Harvey-Liu-Zhu t > 3.0 hurdle: how much of the t-stat survives
  the ~75 trials actually run, and how much forward data is needed to settle it (~1,000
  trades for t > 3.0).
- **Placebo entry test** — `src/placebo_entry.py`. A random entry in the same window with
  the same bracket earns +0.00 pts/trade; the bot sits at the 97.5th percentile. This rules
  out intraday drift as the explanation, since the bot is long-only.
- **Pre-registered forward test** — `FORWARD_RECORD.md` + `src/forward_v2.py`. A frozen
  spec, gates set in advance (no new historical test until forward n > 400), appended to and
  never edited. This is the live, honest tally.
- **Cross-asset validation** — the frozen NQ rule re-run on other futures (crude, gold,
  heating oil, gasoline, Bitcoin). Mostly nulls or net-flat after costs, which is the honest
  and useful result: the edge is largely NQ-specific and was not p-hacked into working
  elsewhere. Suspicious results were audited for bugs, and two porting-spec errors were
  found and corrected in the open.

## Repo map (what to read first)

The pipeline is ~30 small scripts. Start here:

- **Core signal** — `context.py` · `location.py` · `drawdown.py` · `scorer.py` ·
  `step2_filter.py` · `edge_check.py`
- **Data** — `load.py` · `ticks.py` · `databento_bars.py` · `pull_databento.py`
- **Rigor / validation** — `significance_audit.py` · `placebo_entry.py` · `forward_v2.py` ·
  `eval_real.py`
- **Live alerting** — `copilot_alerts.py` · `ninjascript/NQEdgeCoPilot.cs` ·
  `ninjascript/NQTapeLogger.cs`
- **Cross-asset validation** — `cross_asset_v2.py` · `breadth_check.py` · `btc_test.py` ·
  `cl_test.py` · `ho_test.py` · `rb_test.py` · the `audit_gold*` / `gold_*` source-reconciliation
  set · `atr_sensitivity.py` · `vol_regime.py`: the NQ rule ported to other futures, with the
  suspicious results audited and the porting-spec errors corrected out loud.
- **Research trail** — the `experiment_*.py` and `eval_*.py` / `compare_*.py` files: every
  rule change tested against the baseline, dead ends included.

## Methodology

- Built from ~530 personally journaled NQ trades plus real tick data resampled to
  20-second bars.
- Attribution per setup: expectancy, daily Sharpe, information ratio, drawdown.
- Overfitting-aware: out-of-sample testing, pre-registered forward gates, and no
  knob-tuning on small samples.
- Headline finding (kept general): trade *management* and *volatility regime* drove the
  results far more than entry selection. The raw entry signal is a watchlist, not an
  auto-trader.

## Stack

Python · pandas · NumPy · statsmodels · matplotlib · Databento (tick data) · NinjaScript
(C#) for the live indicator.

## Data note

Raw trade data, licensed feeds, and exact tuned parameters are withheld (personal /
proprietary; see `.gitignore`). This repo shows the methodology and architecture, not a
turnkey strategy.
