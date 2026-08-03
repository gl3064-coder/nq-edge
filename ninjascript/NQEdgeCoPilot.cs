// NQEdgeCoPilot.cs — desktop NinjaTrader 8 indicator.
//
// Pings when a long-setup zone forms, using the exact signal validated in the Python
// research (NQ Edge): up-context (fast MA > slow MA, slow rising) + a higher-low pullback
// + a real drawdown into it. Load on your 20-second NQ chart. It draws a green arrow and
// fires an Alert (sound + Alerts-window row) on each fresh zone, with a cooldown so it
// doesn't spam. It does NOT place orders — it just tells you where to look.
//
// Parameters default to the Python values (fast 20 / slow 50 / slope 10 / pivot 3 /
// drawdown window 30 / min drawdown 10 pts / cooldown 15 bars = 5 min on 20s).
//
// Volatility handling (reworked again 2026-07-03 pm, after the vol-stop backtest):
//  - DEAD-TAPE GATE (the only suppressor): when the rolling AVERAGE of ATR over
//    RegimeWindowBars (15 = 5 min on 20s) is below MinAtr (10), the tape is dead --
//    slate background over the whole stretch, green arrow + sound suppressed.
//    Backtest basis (experiment_vol_stop.py, 593 mechanical entries, 3 boundary
//    perturbations): entries at avg ATR < 10 are net NEGATIVE at every stop size;
//    skipping them lifted total +1,596 -> +2,154 and daily Sharpe 0.157 -> 0.258.
//  - HOT SIDE IS INFORMATIONAL up to MaxAvgAtr: candles with ATR > MaxAtr (18) tint
//    amber, nothing suppressed. Three independent tests (journal buckets 6/29, regime
//    decomposition + stop table 7/3) all found the signal's best trades live in hot
//    tape (hot-regime entries: +9.3/trade, Sharpe 0.211 vs 0.004 for the remainder).
//  - EXTREME GATE: avg ATR > MaxAvgAtr (30) = circuit breaker -- dense amber bg +
//    arrows/sound dark. NOT backtest-validated: a judgment call on probation.
//    Evidence is thin (mechanical n=4 all losses, ~13% by chance at a 40% win rate;
//    journal 25-30 = 0/5 but 30+ = 2/6; found by bucket-scanning). Kept because it
//    costs ~2.6% of bars and matches the chaos-open prior. Forward test decides;
//    remove freely if it blocks winners.
//  - Stops/trail: vol-matched stop scaling FAILED the backtest (every variant, every
//    boundary). The ATM stays flat 20 / Trail30. Don't rebuild ATR-scaled stops.
//  - v2 FORWARD-TEST LAYER (leg age, added 2026-07-14): arrows on an OLD up-leg
//    (consecutive up-context bars > MaxLegAge = 30) DIM to gray with a "leg N" label;
//    fresh-leg arrows stay lime. NON-DESTRUCTIVE — every arrow still draws + alerts; this
//    is the visible half of Bot v2 (the tape half needs live buy_delta, still to come).
//    Backtest: leg<=30 gated on tape beat tape-only OOS (+392 vs +130 net), positive on
//    all 3 contracts. Leg age = consecutive up-context bars; up-context here == context.py.
// All backtest numbers are in-sample, pre-cost, close-only; the forward-test journal
// ("regime at entry" column) is the final judge of the dead gate.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class NQEdgeCoPilot : Indicator
    {
        private SMA fast;
        private SMA slow;
        private MAX recentHigh;
        private ATR atr;
        private SMA atrAvg;
        private int    lastAlertBar = -100000;
        private double prevPivotLow = double.MinValue;
        private double activeZoneLow = 0;
        private int    activeZoneBar = -1;   // -1 = no zone currently being watched
        private Brush  upBrush;
        private Brush  downBrush;
        private Brush  hotBrush;
        private Brush  deadBrush;
        private Brush  extremeBrush;
        private Brush  staleBrush;
        private int    legAge = 0;   // consecutive up-context bars (the v2 leg-age counter)
        private Dictionary<DateTime, string> thinDates;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name        = "NQEdgeCoPilot";
                Description = "Pings when a long-setup zone forms (up-context + higher-low + drawdown). Surfaces zones; does not trade.";
                Calculate   = Calculate.OnBarClose;   // act on closed 20s bars (matches the backtest)
                IsOverlay   = true;
                DrawOnPricePanel = true;

                FastPeriod      = 20;
                SlowPeriod      = 50;
                SlopeLookback   = 10;
                PivotK          = 3;
                DrawdownWindow  = 30;
                MinDrawdownPts  = 10;
                CooldownBars    = 15;
                SessionStart    = 93000;    // 09:30:00 — only ping during your NY morning
                SessionEnd      = 120000;   // 12:00:00
                ZoneLifeBars    = 30;       // how long a flagged zone stays "watched" for invalidation
                AtrPeriod       = 1;        // matches your chart's ATR(...,1) + journal ATR scale
                MaxAtr          = 18;       // amber tint above this (informational only, no suppression)
                MinAtr          = 10;       // dead tape: avg ATR below this = arrows dark (backtested)
                MaxAvgAtr       = 30;       // extreme: avg ATR above this = arrows dark (0 winners ever)
                RegimeWindowBars = 15;      // averaging window: 15 bars = 5 min on the 20s chart
                MaxLegAge       = 30;       // v2 leg-age gate: arrows on legs older than this dim (frozen)
                // Known holiday / holiday-adjacent thin-tape dates. Format per entry:
                // yyyyMMdd=Name (the name shows in the banner; "=Name" is optional).
                // Comma-separated, editable in the indicator settings, no recompile.
                // Refresh each January.
                ThinDates = "20260703=July 4th (observed),20260907=Labor Day,"
                          + "20261125=Thanksgiving eve,20261126=Thanksgiving,"
                          + "20261127=Day after Thanksgiving,20261224=Christmas Eve,"
                          + "20261225=Christmas,20261231=New Year's Eve,20270101=New Year's Day";
            }
            else if (State == State.DataLoaded)
            {
                fast       = SMA(Close, FastPeriod);
                slow       = SMA(Close, SlowPeriod);
                recentHigh = MAX(High, DrawdownWindow);
                atr        = ATR(AtrPeriod);
                atrAvg     = SMA(atr, RegimeWindowBars);

                // Faint background tints: green = up-context (longs on), red = downtrend (stand down),
                // amber = ATR too hot, slate-gray = dead tape (both override the trend tints).
                upBrush   = new SolidColorBrush(Color.FromArgb(22, 0, 180, 0));     upBrush.Freeze();
                downBrush = new SolidColorBrush(Color.FromArgb(22, 200, 0, 0));     downBrush.Freeze();
                hotBrush  = new SolidColorBrush(Color.FromArgb(30, 230, 140, 0));   hotBrush.Freeze();
                deadBrush = new SolidColorBrush(Color.FromArgb(30, 130, 135, 150)); deadBrush.Freeze();
                extremeBrush = new SolidColorBrush(Color.FromArgb(55, 230, 120, 0)); extremeBrush.Freeze();
                staleBrush   = new SolidColorBrush(Color.FromArgb(150, 130, 135, 150)); staleBrush.Freeze();  // dimmed gray = old-leg arrow

                // Parse the thin-tape date list once. Bad entries are skipped silently
                // rather than killing the indicator load.
                thinDates = new Dictionary<DateTime, string>();
                foreach (string s in (ThinDates ?? "").Split(','))
                {
                    string[] parts = s.Split(new[] { '=' }, 2);
                    DateTime dt;
                    if (DateTime.TryParseExact(parts[0].Trim(), "yyyyMMdd",
                        CultureInfo.InvariantCulture, DateTimeStyles.None, out dt))
                        thinDates[dt.Date] = parts.Length > 1 && parts[1].Trim().Length > 0
                            ? parts[1].Trim() : "Holiday";
                }
            }
        }

        protected override void OnBarUpdate()
        {
            // Need enough history for the MAs, the slope lookback, a full pivot window,
            // and a full regime-count window.
            int warmup = Math.Max(Math.Max(SlowPeriod + SlopeLookback, 2 * PivotK),
                                  AtrPeriod + RegimeWindowBars) + 1;
            if (CurrentBar < warmup)
                return;

            int t = ToTime(Time[0]);
            bool inSession = t >= SessionStart && t <= SessionEnd;

            // Holiday / thin-tape banner: on flagged dates, say WHY the tape is dead so
            // a gray morning reads as "expected" instead of "is the gate broken?".
            string thinName;
            if (thinDates.TryGetValue(Time[0].Date, out thinName))
                Draw.TextFixed(this, "thinBanner",
                    "THIN TAPE: " + thinName + " — low participation expected, trust the gray",
                    TextPosition.TopLeft, Brushes.Orange, new Gui.Tools.SimpleFont("Arial", 14),
                    Brushes.Transparent, Brushes.Transparent, 0);
            else
                RemoveDrawObject("thinBanner");

            // --- Invalidation: a flagged zone dies if price closes back below its low ---
            // (the higher-low failed = long thesis broke). Red X = "structure broke, stand
            // down" — a caution for your read, NOT a hard veto (a brief break can be a fakeout).
            if (activeZoneBar >= 0)
            {
                if (inSession && Close[0] < activeZoneLow)
                {
                    Draw.ArrowDown(this, "inval" + CurrentBar, false, 0,
                                   High[0] + 2 * TickSize, Brushes.Red);
                    activeZoneBar = -1;
                }
                else if (CurrentBar - activeZoneBar > ZoneLifeBars)
                {
                    activeZoneBar = -1;   // zone went stale without breaking — clear quietly
                }
            }

            // Condition #1 — up-context: fast above slow, and slow rising.
            bool slowRising  = slow[0] > slow[SlopeLookback];
            bool upContext   = fast[0] > slow[0] && slowRising;
            bool downContext = fast[0] < slow[0] && slow[0] < slow[SlopeLookback];

            // v2 leg-age counter: consecutive up-context bars ending at this bar. Updated
            // here BEFORE the pivot early-return so it counts every bar (== context.py run).
            if (upContext) legAge++; else legAge = 0;

            // Volatility read: dead tape = the AVERAGE ATR of the window is low (the
            // neighborhood is quiet, even if no single candle is extreme). Hot candles
            // tint amber for information only — high vol holds the signal's best trades.
            bool thisBarHot    = atr[0] > MaxAtr;
            bool deadRegime    = atrAvg[0] < MinAtr;
            bool extremeRegime = atrAvg[0] > MaxAvgAtr;

            // Backdrop — only during your session; clear (no tint) outside it. The two
            // suppressing regimes (slate dead / dense-amber extreme) override everything:
            // their tint marks exactly where arrows are dark.
            BackBrush = inSession
                ? (extremeRegime ? extremeBrush
                    : (deadRegime ? deadBrush
                        : (thisBarHot ? hotBrush
                            : (upContext ? upBrush : (downContext ? downBrush : null)))))
                : null;

            // A pivot low confirmed PivotK bars ago = lowest Low in the +/-PivotK window.
            double pivotLow = Low[PivotK];
            bool isPivot = true;
            for (int j = 1; j <= PivotK; j++)
                if (Low[PivotK - j] < pivotLow || Low[PivotK + j] < pivotLow)
                {
                    isPivot = false;
                    break;
                }

            if (!isPivot)
                return;

            // Condition #2 — higher low than the previous pivot.
            bool higherLow = pivotLow > prevPivotLow;

            // Condition #3 — a real drawdown into the pivot (dip from the recent high).
            bool drawdownOK = (recentHigh[PivotK] - pivotLow) >= MinDrawdownPts;

            if (upContext && higherLow && drawdownOK && inSession && !deadRegime && !extremeRegime
                && (CurrentBar - lastAlertBar) > CooldownBars)
            {
                lastAlertBar  = CurrentBar;
                activeZoneLow = pivotLow;      // arm the invalidation watch for this zone
                activeZoneBar = CurrentBar;

                // v2 leg-age layer: dim the arrow when the up-leg is old (> MaxLegAge), and
                // flag ONLY those with a bright "late N" chip below the bar (a solid amber
                // plaque so it reads over the candles). Fresh arrows stay clean lime, no
                // label. This marks, never suppresses — the arrow still draws + alerts.
                bool freshLeg = legAge <= MaxLegAge;
                Draw.ArrowUp(this, "copilot" + CurrentBar, false, 0,
                             Low[0] - 2 * TickSize, freshLeg ? Brushes.Lime : staleBrush);
                if (!freshLeg)
                    Draw.Text(this, "legtxt" + CurrentBar, false, "late " + legAge, 0,
                              Low[0], -30, Brushes.Black,
                              new Gui.Tools.SimpleFont("Arial", 12) { Bold = true },
                              System.Windows.TextAlignment.Center,
                              Brushes.Transparent, Brushes.Orange, 90);

                Alert("NQEdgeCoPilot", Priority.High,
                      string.Format("NQ Edge: setup zone @ {0} ({1:HH:mm:ss})", Close[0], Time[0]),
                      Globals.InstallDir + @"\sounds\Alert4.wav",
                      10, Brushes.Black, Brushes.Lime);
            }

            // Track every confirmed pivot so the higher-low comparison stays correct.
            prevPivotLow = pivotLow;
        }

        #region Parameters
        [NinjaScriptProperty, Range(2, int.MaxValue)]
        [Display(Name = "Fast MA period", Order = 1, GroupName = "Parameters")]
        public int FastPeriod { get; set; }

        [NinjaScriptProperty, Range(2, int.MaxValue)]
        [Display(Name = "Slow MA period", Order = 2, GroupName = "Parameters")]
        public int SlowPeriod { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Slow-MA slope lookback", Order = 3, GroupName = "Parameters")]
        public int SlopeLookback { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Pivot strength (k bars)", Order = 4, GroupName = "Parameters")]
        public int PivotK { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Drawdown lookback window", Order = 5, GroupName = "Parameters")]
        public int DrawdownWindow { get; set; }

        [NinjaScriptProperty, Range(0.0, double.MaxValue)]
        [Display(Name = "Min drawdown (points)", Order = 6, GroupName = "Parameters")]
        public double MinDrawdownPts { get; set; }

        [NinjaScriptProperty, Range(0, int.MaxValue)]
        [Display(Name = "Alert cooldown (bars)", Order = 7, GroupName = "Parameters")]
        public int CooldownBars { get; set; }

        [NinjaScriptProperty, Range(0, 235959)]
        [Display(Name = "Session start (HHmmss)", Order = 8, GroupName = "Parameters")]
        public int SessionStart { get; set; }

        [NinjaScriptProperty, Range(0, 235959)]
        [Display(Name = "Session end (HHmmss)", Order = 9, GroupName = "Parameters")]
        public int SessionEnd { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Zone life (bars, for invalidation)", Order = 10, GroupName = "Parameters")]
        public int ZoneLifeBars { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "ATR period (volatility gate)", Order = 11, GroupName = "Parameters")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty, Range(0.0, double.MaxValue)]
        [Display(Name = "Max ATR (amber tint above, info only)", Order = 12, GroupName = "Parameters")]
        public double MaxAtr { get; set; }

        [NinjaScriptProperty, Range(0.0, double.MaxValue)]
        [Display(Name = "Min avg ATR (dead tape below)", Order = 13, GroupName = "Parameters")]
        public double MinAtr { get; set; }

        [NinjaScriptProperty, Range(0.0, double.MaxValue)]
        [Display(Name = "Max avg ATR (extreme, stand down above)", Order = 15, GroupName = "Parameters")]
        public double MaxAvgAtr { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Avg ATR window (bars)", Order = 14, GroupName = "Parameters")]
        public int RegimeWindowBars { get; set; }

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "Max leg age (bars, v2 dim above)", Order = 17, GroupName = "Parameters")]
        public int MaxLegAge { get; set; }

        // Deliberately NOT [NinjaScriptProperty]: that attribute bakes the value into
        // the chart's indicator label, and a nine-holiday string wrecks the title bar.
        // Still shows in the settings panel and persists with the workspace.
        [Display(Name = "Thin-tape dates (yyyyMMdd=Name, comma-sep)", Order = 16, GroupName = "Parameters")]
        public string ThinDates { get; set; }
        #endregion
    }
}
