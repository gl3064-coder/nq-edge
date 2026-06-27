# NQ Edge: Quantitative Trading Research Pipeline

A Python pipeline that analyzes my own journaled NQ futures trades, turns discretionary
intuition into quantified, testable rules, and grades trade setups using the same rigor
(Sharpe, information ratio, expectancy, out-of-sample validation) used to evaluate real
strategies.

![pipeline](docs/pipeline.png)

## What it does
A modular signal pipeline that grades long setups:
- **context**: trend / regime filter (moving-average based)
- **location**: higher-low pullback detection
- **drawdown**: requires a genuine pullback before entry
- **scoring**: grades each setup by expectancy, Sharpe, and information ratio

A research layer (`eval_*.py`, `experiment_*.py`) back-tests any rule change against the baseline.

## Methodology
- Built from ~530 personally journaled NQ trades plus real tick data resampled to 20-second bars.
- Performance attribution: per-setup expectancy, daily Sharpe, information ratio, drawdown.
- Overfitting-aware: out-of-sample testing, and no knob-tuning on small samples.
- Headline finding (kept general): trade *management* and *volatility regime* drove the
  results far more than entry selection. The raw entry signal is a watchlist, not an auto-trader.

## Stack
Python · pandas · NumPy · matplotlib · statsmodels · yfinance · NinjaScript (C#) for the
live alerting indicator.

## Note
Raw trade data and exact tuned parameters are withheld (personal / proprietary). This repo
demonstrates the methodology and architecture, not a turnkey strategy.
