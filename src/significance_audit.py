"""
Significance audit for the frozen bot: how much of the observed t-stat survives
the multiple testing we actually did, and how much forward sample is required
to settle it.

Sources:
  Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio" -- source for the
      E[max SR] benchmark used in PART 1: the highest t you expect from N
      independent zero-skill trials.
      NOTE: this script implements that BENCHMARK ONLY. It is not a Deflated
      Sharpe Ratio. A real DSR also needs the variance of the Sharpe ratios
      across the trials and the skew and kurtosis of the return series. This
      script takes a trial COUNT and assumes the trials are independent. Mine
      are not: they are variations on one idea. Read PART 1 as a
      multiple-testing sanity check, and read the effective N as well below
      the raw count of ~75.
  Bailey, Borwein, Lopez de Prado & Zhu (2014), "Pseudo-Mathematics and
      Financial Charlatanism" -- Minimum Backtest Length.
  Harvey, Liu & Zhu (2016) -- the argument for a t > 3.0 hurdle after
      accounting for the literature's (and your own) search.

This script does NOT touch the strategy. It is measurement only.
Run: C:\\Users\\lgavi\\anaconda3\\python.exe src/significance_audit.py
"""

import numpy as np
from scipy.stats import norm

GAMMA = 0.5772156649015329  # Euler-Mascheroni

# ---------------------------------------------------------------- frozen bot
# tape >= 0.10 AND leg_age <= 30, FIXED +30/-20, NQ 20s, 9:30-12:00 ET.
# Enlarged-data run, 2026-07-14.
N_TRADES = 235
MEAN_GROSS = 3.08       # pts/trade
T_OBSERVED = 1.92
MEAN_NETCOST = 2.33     # pts/trade after ~0.75pt round-trip cost
TRADES_PER_DAY = 235 / 135.0   # 235 trades over ~135 trading days of tick data


def expected_max_t(n_trials):
    """E[max t] across n_trials independent zero-skill trials (Bailey/LdP Eq.1
    with E[SR]=0, V[SR]=1, i.e. each trial's t ~ N(0,1) under the null)."""
    if n_trials < 2:
        return 0.0
    a = norm.ppf(1.0 - 1.0 / n_trials)
    b = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return (1.0 - GAMMA) * a + GAMMA * b


def required_n(mean_per_trade, sd_per_trade, t_target):
    """Trades needed for the t-stat to reach t_target at a given true edge."""
    return (t_target * sd_per_trade / mean_per_trade) ** 2


def main():
    sd = MEAN_GROSS * np.sqrt(N_TRADES) / T_OBSERVED
    print("=" * 68)
    print("FROZEN BOT, OBSERVED")
    print("=" * 68)
    print(f"  trades                 n = {N_TRADES}")
    print(f"  mean gross               = {MEAN_GROSS:+.2f} pts/trade")
    print(f"  implied per-trade sd     = {sd:.2f} pts")
    print(f"  observed t               = {T_OBSERVED:.2f}")
    print(f"  mean net of cost         = {MEAN_NETCOST:+.2f} pts/trade")
    print(f"  implied net-of-cost t    = {MEAN_NETCOST / (sd / np.sqrt(N_TRADES)):.2f}")

    print()
    print("=" * 68)
    print("PART 1 -- WHAT NOISE ALONE WOULD HAVE PRODUCED")
    print("  E[max t] from N INDEPENDENT zero-skill configurations.")
    print("  Compare each to our observed t = 1.92.")
    print("  CAVEAT: this is a multiple-testing sanity check, NOT a Deflated")
    print("  Sharpe Ratio. My ~75 trials were variations on one idea, so they")
    print("  are heavily correlated and the effective N is well below 75.")
    print("=" * 68)
    print(f"  {'N trials':>10} {'E[max t]':>10}   verdict vs observed")
    for n in (2, 5, 10, 15, 25, 50, 80):
        emax = expected_max_t(n)
        flag = "CLEARS" if T_OBSERVED > emax else "does NOT clear"
        print(f"  {n:>10} {emax:>10.2f}   {flag}")

    print()
    print("=" * 68)
    print("PART 2 -- FORWARD SAMPLE REQUIRED TO SETTLE IT")
    print("  Assumes the sd above and that the TRUE edge equals the")
    print("  scenario mean. Days assume the bot's historical rate of")
    print(f"  {TRADES_PER_DAY:.2f} trades/session.")
    print("=" * 68)
    scenarios = [
        ("point estimate, gross", MEAN_GROSS),
        ("point estimate, net of cost", MEAN_NETCOST),
        ("shrunk 50% (winner's curse)", MEAN_GROSS * 0.5),
    ]
    for label, mu in scenarios:
        print(f"\n  true edge = {mu:+.2f} pts/trade  ({label})")
        print(f"    {'target t':>9} {'total n':>9} {'more n':>9} {'sessions':>10} {'months':>8}")
        for t_target in (2.0, 2.5, 3.0):
            need = required_n(mu, sd, t_target)
            more = max(0.0, need - N_TRADES)
            days = more / TRADES_PER_DAY
            print(f"    {t_target:>9.1f} {need:>9.0f} {more:>9.0f} "
                  f"{days:>10.0f} {days / 21.0:>8.1f}")

    print()
    print("=" * 68)
    print("PART 3 -- MINIMUM BACKTEST LENGTH (Bailey et al. 2014)")
    print("  MinBTL (years) ~ 2*ln(N) / E[max SR]^2, the sample length below")
    print("  which an IS Sharpe of E[max SR] is expected from noise alone.")
    print("=" * 68)
    for n in (10, 25, 50, 80):
        emax = expected_max_t(n)
        minbtl = 2.0 * np.log(n) / (emax ** 2)
        print(f"  N = {n:>3}   E[max SR] = {emax:.2f}   MinBTL = {minbtl:.1f} years")

    print()
    print("=" * 68)
    print("READ THIS")
    print("=" * 68)
    print("""  The observed t of 1.92 is BELOW the t that noise alone is expected
  to produce once you have tried even ~10 independent configurations,
  and we tried far more than 10 (though heavily correlated, so the
  effective N is smaller than the raw count).

  This does not say the edge is fake. Two things are evidence the
  historical t-stat cannot supply: the placebo entry test
  (src/placebo_entry.py -- random entries in the same window with the same
  bracket earn +0.00 pts/trade, putting the bot at the 97.5th percentile)
  and the live-delta validation.

  RETRACTED 2026-08-04. An earlier version of this note also cited the
  cross-asset result as evidence the mechanism is real. That claim is
  WITHDRAWN. Auditing the port found two scaling errors: it hardcoded
  A_NQ = 17.0 when NQ's measured session median 20s true range is 11.75,
  and it measured instrument ATRs all-hours while the bot trades the NY
  session only.

  The full-year re-test (2026-08-05, n=294-532 per instrument) then
  settled it with real power: null or negative after costs on every
  instrument except NQ. So the cross-asset tests are NOT uninformative,
  they are a properly powered NULL. What that supports is that the edge
  is NQ-SPECIFIC, which is a limitation on scope. It is not, and never
  was, evidence that the mechanism here is real -- nulls elsewhere
  cannot validate a result here. Full record and every number:
  docs/CROSS_ASSET_RESULTS.md

  It does say the HISTORICAL sample can no longer settle the question,
  because we have searched it. Only out-of-sample forward data carries
  clean information now. That is already the plan; this quantifies how
  long the plan has to run.""")


if __name__ == "__main__":
    main()
