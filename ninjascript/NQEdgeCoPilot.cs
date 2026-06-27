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

#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
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
        private int    lastAlertBar = -100000;
        private double prevPivotLow = double.MinValue;
        private double activeZoneLow = 0;
        private int    activeZoneBar = -1;   // -1 = no zone currently being watched
        private Brush  upBrush;
        private Brush  downBrush;

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
            }
            else if (State == State.DataLoaded)
            {
                fast       = SMA(Close, FastPeriod);
                slow       = SMA(Close, SlowPeriod);
                recentHigh = MAX(High, DrawdownWindow);

                // Faint background tints: green = up-context (longs on), red = downtrend (stand down).
                upBrush   = new SolidColorBrush(Color.FromArgb(22, 0, 180, 0));   upBrush.Freeze();
                downBrush = new SolidColorBrush(Color.FromArgb(22, 200, 0, 0));   downBrush.Freeze();
            }
        }

        protected override void OnBarUpdate()
        {
            // Need enough history for the MAs, the slope lookback, and a full pivot window.
            int warmup = Math.Max(SlowPeriod + SlopeLookback, 2 * PivotK) + 1;
            if (CurrentBar < warmup)
                return;

            int t = ToTime(Time[0]);
            bool inSession = t >= SessionStart && t <= SessionEnd;

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

            // Regime backdrop — only during your session; clear (no tint) outside it.
            BackBrush = inSession ? (upContext ? upBrush : (downContext ? downBrush : null)) : null;

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

            if (upContext && higherLow && drawdownOK && inSession
                && (CurrentBar - lastAlertBar) > CooldownBars)
            {
                lastAlertBar  = CurrentBar;
                activeZoneLow = pivotLow;      // arm the invalidation watch for this zone
                activeZoneBar = CurrentBar;

                Draw.ArrowUp(this, "copilot" + CurrentBar, false, 0,
                             Low[0] - 2 * TickSize, Brushes.Lime);

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
        #endregion
    }
}
