// NQTapeLogger.cs — desktop NinjaTrader 8 indicator (VALIDATION TOOL, not the co-pilot).
//
// Purpose: compute buy_delta LIVE, exactly the way the Python backtest does (ticks.py),
// and log it per 20-second bar. Run it in Market Replay on a day we already have the
// Python buy_delta for, then diff the two. If the live number ranks like the backtest
// number, the tape gate transfers to live. If it doesn't, the edge was a backtest ghost.
//
// Backtest definition being matched (ticks.py load_bars):
//   per trade: sign = +1 if Last >= Ask, -1 if Last <= Bid, else 0
//   per bar:   buy_delta = sum(sign * volume) / sum(volume)     (in [-1, +1])
//
// Only REALTIME (replay/live) bars are logged, so historical backfill doesn't pollute it.
// Add to a 20-second NQ chart, then play a Market Replay session across it.

#region Using declarations
using System;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class NQTapeLogger : Indicator
    {
        private double curBid;   // most-recent best bid/ask, maintained from Level 1
        private double curAsk;
        private double barSvol;  // running signed volume for the current bar
        private double barVol;   // running total volume for the current bar
        private string logPath;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name        = "NQTapeLogger";
                Description = "Logs live buy_delta per 20s bar for backtest-vs-live validation.";
                Calculate   = Calculate.OnBarClose;   // one logged row per closed bar
                IsOverlay   = true;
            }
            else if (State == State.DataLoaded)
            {
                logPath = @"C:\Users\lgavi\OneDrive\Desktop\NQ Edge\Replay Data\live_tape_log.csv";
                curBid = curAsk = 0;
                barSvol = barVol = 0;
                // Start each load with a fresh file + header.
                try { File.WriteAllText(logPath, "time,close,volume,svol,buy_delta\r\n"); }
                catch { }
            }
        }

        // Fires on every Level 1 update (bid, ask, trade). This is the live code path that
        // has to match the export's Last;Bid;Ask classification.
        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (e.MarketDataType == MarketDataType.Bid)
                curBid = e.Price;
            else if (e.MarketDataType == MarketDataType.Ask)
                curAsk = e.Price;
            else if (e.MarketDataType == MarketDataType.Last)
            {
                double last = e.Price;
                double v    = e.Volume;
                double sign = (curAsk > 0 && last >= curAsk) ?  1.0
                            : ((curBid > 0 && last <= curBid) ? -1.0 : 0.0);
                barSvol += sign * v;
                barVol  += v;
            }
        }

        protected override void OnBarUpdate()
        {
            // Only log bars that formed from live/replay market data, not historical backfill.
            if (State != State.Realtime)
                return;

            double bd = barVol > 0 ? barSvol / barVol : 0.0;
            try
            {
                File.AppendAllText(logPath, string.Format(CultureInfo.InvariantCulture,
                    "{0:yyyy-MM-dd HH:mm:ss},{1},{2},{3},{4:0.######}\r\n",
                    Time[0], Close[0], barVol, barSvol, bd));
            }
            catch { }

            // Reset accumulators for the next bar.
            barSvol = 0;
            barVol  = 0;
        }
    }
}
