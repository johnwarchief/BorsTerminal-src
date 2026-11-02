//+------------------------------------------------------------------+
//|                         Human_Level_Structure_Engine_v2.mq5      |
//| Human-Level SMC Market Structure Engine + CHoCH Fibo & FVG Retest|
//|                                                                  |
//| Features:                                                        |
//|   - Single-Pass Chronological Break Engine (Zero lag/ghosting)   |
//|   - Major Swing Detection (HH, HL, LH, LL)                       |
//|   - Auto-drawn Fibonacci on Confirmed CHoCH                      |
//|   - 50% Retest Buy/Sell Signals (Wingdings 233/234)              |
//|   - 3-Candle Post-CHoCH FVG Detection & Mitigation Signals       |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Quantitative SMC Engine"
#property link        "https://www.mql5.com"
#property version     "2.70"
#property description "Human-Level SMC Market Structure Engine with CHoCH Fibo & FVG Mitigation Signals."
#property indicator_chart_window
#property indicator_plots 0

//+------------------------------------------------------------------+
//| Enumerations                                                     |
//+------------------------------------------------------------------+
enum ENUM_SWING_TYPE
  {
   SW_NONE = 0,
   SW_HIGH,
   SW_LOW
  };

enum ENUM_LABEL_TYPE
  {
   LB_NONE = 0,
   LB_HH,
   LB_HL,
   LB_LH,
   LB_LL
  };

enum ENUM_TREND_STATE
  {
   TREND_UNKNOWN = 0,
   TREND_BULL,
   TREND_BEAR
  };

//+------------------------------------------------------------------+
//| Structures                                                       |
//+------------------------------------------------------------------+
struct SSwingPoint
  {
   int               bar_idx;
   datetime          time;
   double            price;
   ENUM_SWING_TYPE   type;
   ENUM_LABEL_TYPE   label;
  };

struct SBreakEvent
  {
   int               break_bar;
   int               swing_bar;
   int               anchor_bar;     // Origin swing bar for Fibonacci anchor
   bool              is_bullish;
   bool              is_choch;
   double            level;          // Broken level (100%)
   double            anchor_level;   // Origin level (0%)
   datetime          t_start;
   datetime          t_end;
  };

struct SFiboSignal
  {
   int               bar_idx;
   datetime          time;
   double            price;
   bool              is_buy;
   double            fibo_50_level;
  };

struct SFVGZone
  {
   int               fvg_idx;
   int               choch_evt_idx;
   int               formed_bar;
   datetime          t_start;
   datetime          t_end;
   double            top;
   double            bottom;
   bool              is_bullish;
   bool              is_mitigated;
   int               mitigate_bar;
   datetime          mitigate_time;
   double            mitigate_price;
  };

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group "=== Structural Wave & Pivot Filter ==="
input int             InpSwingStrength       = 15;            // Pivot Strength (Bars on Left/Right)
input double          InpMinPullbackATR      = 0.85;          // Minimum Pullback Depth (ATR Multiplier)
input int             InpATRPeriod           = 14;            // ATR Period
input int             InpMaxBars             = 2000;          // Max Lookback Bars

input group "=== Visuals: Swings & Labels ==="
input bool            InpShowSwingPoints     = true;          // Show Dot Markers at Swings
input bool            InpShowStructureLabels = true;          // Show HH / HL / LH / LL Labels
input int             InpTextSize            = 9;             // Label Font Size
input color           InpBullishColor        = C'0,225,120';  // Bullish Color (HH / HL / BOS ↑ / CHoCH ↑)
input color           InpBearishColor        = C'255,75,90';   // Bearish Color (LH / LL / BOS ↓ / CHoCH ↓)

input group "=== Visuals: BOS & CHoCH ==="
input bool            InpShowBOS             = true;          // Show BOS (Continuation)
input bool            InpShowCHoCH           = true;          // Show CHoCH (Reversal)
input bool            InpShowBreakLines      = true;          // Show Break Lines
input bool            InpUseCloseForBreak    = true;          // Confirm Break by Candle Close (false = Wick)
input int             InpBreakLineWidth      = 1;             // Line Width
input ENUM_LINE_STYLE InpBreakLineStyle      = STYLE_DASH;    // Line Style
input int             InpEventTextSize       = 8;             // Event Label Size

input group "=== CHoCH Fibonacci & 50% Retest Signals ==="
input bool            InpShowCHoCHFibo       = true;          // Draw Fibonacci on CHoCH
input color           InpFiboColor           = clrYellow;     // Fibonacci Color
input int             InpFiboWidth           = 1;             // Fibonacci Line Width
input ENUM_LINE_STYLE InpFiboStyle           = STYLE_SOLID;   // Fibonacci Line Style
input bool            InpShowRetestSignals   = true;          // Show 50% Fibo Retest Signals
input int             InpSignalArrowSize     = 2;             // Signal Arrow Size (Wingdings 233/234)
input bool            InpShowSignalText      = true;          // Show Buy/Sell Text Label

input group "=== CHoCH Post-3-Candle FVG & Mitigation Signals ==="
input bool            InpShowCHoCHFVG        = true;          // Detect & Draw FVG after CHoCH
input bool            InpShowFVGSignals      = true;          // Show FVG Mitigation Buy/Sell Signals
input color           InpBullishFVGColor     = C'0,120,65';   // Bullish FVG Box Color
input color           InpBearishFVGColor     = C'130,35,45';  // Bearish FVG Box Color
input bool            InpFillFVGBox          = true;          // Fill FVG Box
input int             InpFVGTextSize         = 8;             // FVG Text Size

input group "=== Display & Dashboard ==="
input bool            InpShowStatus          = true;          // Show Status HUD
input bool            InpDeleteObjectsOnExit = true;          // Delete Objects on Remove

//+------------------------------------------------------------------+
//| Globals & Runtime Caches                                         |
//+------------------------------------------------------------------+
const string PREFIX = "SMC_PRO_";
MqlRates     Rates[];
double       ATR[];
int          BarsCount = 0;

string       g_active_objects[];
int          g_active_count = 0;

//+------------------------------------------------------------------+
//| Object Tracker (Prevents Screen Flickering)                      |
//+------------------------------------------------------------------+
void ResetActiveTracker()
  {
   ArrayResize(g_active_objects, 0);
   g_active_count = 0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void RegisterActiveObject(const string name)
  {
   ArrayResize(g_active_objects, g_active_count + 1);
   g_active_objects[g_active_count] = name;
   g_active_count++;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CleanupUnusedObjects()
  {
   int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i, -1, -1);
      if(StringFind(name, PREFIX) == 0 || StringFind(name, "HLSE2_") == 0 || StringFind(name, "HLSE_") == 0)
        {
         bool is_active = false;
         for(int j = 0; j < g_active_count; j++)
           {
            if(name == g_active_objects[j])
              {
               is_active = true;
               break;
              }
           }
         if(!is_active)
            ObjectDelete(0, name);
        }
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DeleteAllIndicatorObjects()
  {
   ObjectsDeleteAll(0, PREFIX);
   ObjectsDeleteAll(0, "HLSE2_");
   ObjectsDeleteAll(0, "HLSE_");
  }

//+------------------------------------------------------------------+
//| ATR Calculation                                                  |
//+------------------------------------------------------------------+
void CalcATR()
  {
   ArrayResize(ATR, BarsCount);
   if(BarsCount <= 0)
      return;

   int p = MathMax(1, InpATRPeriod);
   double tr[];
   ArrayResize(tr, BarsCount);

   tr[0] = Rates[0].high - Rates[0].low;
   for(int i = 1; i < BarsCount; i++)
     {
      double a = Rates[i].high - Rates[i].low;
      double b = MathAbs(Rates[i].high - Rates[i - 1].close);
      double c = MathAbs(Rates[i].low  - Rates[i - 1].close);
      tr[i] = MathMax(a, MathMax(b, c));
     }

   double sum = 0.0;
   for(int i = 0; i < BarsCount; i++)
     {
      sum += tr[i];
      if(i >= p)
         sum -= tr[i - p];
      ATR[i] = sum / MathMin(i + 1, p);
     }
  }

//+------------------------------------------------------------------+
//| Fractal Pivot Detection                                          |
//+------------------------------------------------------------------+
bool IsPivotHigh(int idx)
  {
   int s = MathMax(1, InpSwingStrength);
   if(idx < s || idx + s >= BarsCount)
      return false;

   double h = Rates[idx].high;
   for(int k = 1; k <= s; k++)
     {
      if(Rates[idx - k].high >= h || Rates[idx + k].high >= h)
         return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsPivotLow(int idx)
  {
   int s = MathMax(1, InpSwingStrength);
   if(idx < s || idx + s >= BarsCount)
      return false;

   double l = Rates[idx].low;
   for(int k = 1; k <= s; k++)
     {
      if(Rates[idx - k].low <= l || Rates[idx + k].low <= l)
         return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Build Alternating Major Structural Swings                        |
//+------------------------------------------------------------------+
int BuildCleanSwings(SSwingPoint &swings[])
  {
   ArrayResize(swings, 0);
   int s = MathMax(1, InpSwingStrength);

   SSwingPoint raw[];
   int raw_cnt = 0;

   for(int i = s; i < BarsCount - s; i++)
     {
      bool hi = IsPivotHigh(i);
      bool lo = IsPivotLow(i);

      if(!hi && !lo)
         continue;

      SSwingPoint sp;
      sp.bar_idx = i;
      sp.time    = Rates[i].time;
      sp.label   = LB_NONE;

      if(hi && !lo)
        {
         sp.type  = SW_HIGH;
         sp.price = Rates[i].high;
        }
      else
         if(lo && !hi)
           {
            sp.type  = SW_LOW;
            sp.price = Rates[i].low;
           }
         else
           {
            if(Rates[i].close > (Rates[i].high + Rates[i].low) * 0.5)
              {
               sp.type  = SW_HIGH;
               sp.price = Rates[i].high;
              }
            else
              {
               sp.type  = SW_LOW;
               sp.price = Rates[i].low;
              }
           }

      ArrayResize(raw, raw_cnt + 1);
      raw[raw_cnt] = sp;
      raw_cnt++;
     }

   if(raw_cnt == 0)
      return 0;

   for(int i = 0; i < raw_cnt; i++)
     {
      int n = ArraySize(swings);
      if(n == 0)
        {
         ArrayResize(swings, 1);
         swings[0] = raw[i];
         continue;
        }

      SSwingPoint last = swings[n - 1];

      if(raw[i].type == last.type)
        {
         if(raw[i].type == SW_HIGH && raw[i].price > last.price)
            swings[n - 1] = raw[i];
         else
            if(raw[i].type == SW_LOW && raw[i].price < last.price)
               swings[n - 1] = raw[i];
        }
      else
        {
         double min_pullback = (ATR[raw[i].bar_idx] > 0) ? (ATR[raw[i].bar_idx] * InpMinPullbackATR) : (15 * _Point);
         double delta = MathAbs(raw[i].price - last.price);

         if(delta >= min_pullback)
           {
            ArrayResize(swings, n + 1);
            swings[n] = raw[i];
           }
        }
     }

   return ArraySize(swings);
  }

//+------------------------------------------------------------------+
//| Structural Classification (HH / LH / HL / LL)                    |
//+------------------------------------------------------------------+
void ClassifySwings(SSwingPoint &swings[])
  {
   double last_high = -1.0;
   double last_low  = DBL_MAX;

   int n = ArraySize(swings);
   for(int i = 0; i < n; i++)
     {
      swings[i].label = LB_NONE;

      if(swings[i].type == SW_HIGH)
        {
         if(last_high < 0.0)
            swings[i].label = LB_HH;
         else
            if(swings[i].price > last_high + (_Point * 0.5))
               swings[i].label = LB_HH;
            else
               swings[i].label = LB_LH;

         last_high = swings[i].price;
        }
      else
         if(swings[i].type == SW_LOW)
           {
            if(last_low == DBL_MAX)
               swings[i].label = LB_HL;
            else
               if(swings[i].price < last_low - (_Point * 0.5))
                  swings[i].label = LB_LL;
               else
                  swings[i].label = LB_HL;

            last_low = swings[i].price;
           }
     }
  }

//+------------------------------------------------------------------+
//| Single-Pass Chronological BOS & CHoCH Engine                    |
//+------------------------------------------------------------------+
void DetectBreaksChronological(const SSwingPoint &swings[], SBreakEvent &events[], ENUM_TREND_STATE &final_trend)
  {
   ArrayResize(events, 0);
   int n = ArraySize(swings);
   if(n < 2)
     {
      final_trend = TREND_UNKNOWN;
      return;
     }

   ENUM_TREND_STATE current_trend = TREND_UNKNOWN;

   for(int i = 0; i < MathMin(3, n); i++)
     {
      if(swings[i].label == LB_HH || swings[i].label == LB_HL)
         current_trend = TREND_BULL;
      else
         if(swings[i].label == LB_LH || swings[i].label == LB_LL)
            current_trend = TREND_BEAR;
     }

   int next_swing_idx  = 0;
   int active_high_idx = -1;
   int active_low_idx  = -1;

   for(int b = 0; b < BarsCount; b++)
     {
      while(next_swing_idx < n && swings[next_swing_idx].bar_idx <= b)
        {
         if(swings[next_swing_idx].type == SW_HIGH)
            active_high_idx = next_swing_idx;
         else
            if(swings[next_swing_idx].type == SW_LOW)
               active_low_idx = next_swing_idx;

         next_swing_idx++;
        }

      // 1. High Break
      if(active_high_idx >= 0)
        {
         double target_h = swings[active_high_idx].price;
         bool broken_h = InpUseCloseForBreak ? (Rates[b].close > target_h) : (Rates[b].high > target_h);

         if(broken_h && b > swings[active_high_idx].bar_idx)
           {
            bool is_choch = (swings[active_high_idx].label == LB_LH) || (current_trend == TREND_BEAR);

            int anchor_idx = active_low_idx;
            if(anchor_idx < 0 || anchor_idx >= active_high_idx)
              {
               for(int k = active_high_idx - 1; k >= 0; k--)
                 {
                  if(swings[k].type == SW_LOW)
                    {
                     anchor_idx = k;
                     break;
                    }
                 }
              }

            SBreakEvent ev;
            ev.break_bar     = b;
            ev.swing_bar     = swings[active_high_idx].bar_idx;
            ev.anchor_bar    = (anchor_idx >= 0) ? swings[anchor_idx].bar_idx : swings[active_high_idx].bar_idx;
            ev.is_bullish    = true;
            ev.is_choch      = is_choch;
            ev.level         = target_h;
            ev.anchor_level  = (anchor_idx >= 0) ? swings[anchor_idx].price : target_h;
            ev.t_start       = swings[active_high_idx].time;
            ev.t_end         = Rates[b].time;

            int cnt = ArraySize(events);
            ArrayResize(events, cnt + 1);
            events[cnt] = ev;

            current_trend   = TREND_BULL;
            active_high_idx = -1;
           }
        }

      // 2. Low Break
      if(active_low_idx >= 0)
        {
         double target_l = swings[active_low_idx].price;
         bool broken_l = InpUseCloseForBreak ? (Rates[b].close < target_l) : (Rates[b].low < target_l);

         if(broken_l && b > swings[active_low_idx].bar_idx)
           {
            bool is_choch = (swings[active_low_idx].label == LB_HL) || (current_trend == TREND_BULL);

            int anchor_idx = active_high_idx;
            if(anchor_idx < 0 || anchor_idx >= active_low_idx)
              {
               for(int k = active_low_idx - 1; k >= 0; k--)
                 {
                  if(swings[k].type == SW_HIGH)
                    {
                     anchor_idx = k;
                     break;
                    }
                 }
              }

            SBreakEvent ev;
            ev.break_bar     = b;
            ev.swing_bar     = swings[active_low_idx].bar_idx;
            ev.anchor_bar    = (anchor_idx >= 0) ? swings[anchor_idx].bar_idx : swings[active_low_idx].bar_idx;
            ev.is_bullish    = false;
            ev.is_choch      = is_choch;
            ev.level         = target_l;
            ev.anchor_level  = (anchor_idx >= 0) ? swings[anchor_idx].price : target_l;
            ev.t_start       = swings[active_low_idx].time;
            ev.t_end         = Rates[b].time;

            int cnt = ArraySize(events);
            ArrayResize(events, cnt + 1);
            events[cnt] = ev;

            current_trend  = TREND_BEAR;
            active_low_idx = -1;
           }
        }
     }

   final_trend = current_trend;
  }

//+------------------------------------------------------------------+
//| Detect 50% Retest Signals after CHoCH                            |
//+------------------------------------------------------------------+
void DetectFiboRetestSignals(const SBreakEvent &events[], SFiboSignal &signals[])
  {
   ArrayResize(signals, 0);
   int event_cnt = ArraySize(events);

   for(int i = 0; i < event_cnt; i++)
     {
      if(!events[i].is_choch)
         continue;

      double p_0   = events[i].anchor_level; // 0.0%
      double p_100 = events[i].level;        // 100.0%
      double p_50  = p_0 + (p_100 - p_0) * 0.50; // 50% level

      for(int b = events[i].break_bar + 1; b < BarsCount; b++)
        {
         if(events[i].is_bullish)
           {
            if(Rates[b].low <= p_50)
              {
               SFiboSignal sig;
               sig.bar_idx       = b;
               sig.time          = Rates[b].time;
               sig.price         = Rates[b].low;
               sig.is_buy        = true;
               sig.fibo_50_level = p_50;

               int sc = ArraySize(signals);
               ArrayResize(signals, sc + 1);
               signals[sc] = sig;
               break;
              }
           }
         else
           {
            if(Rates[b].high >= p_50)
              {
               SFiboSignal sig;
               sig.bar_idx       = b;
               sig.time          = Rates[b].time;
               sig.price         = Rates[b].high;
               sig.is_buy        = false;
               sig.fibo_50_level = p_50;

               int sc = ArraySize(signals);
               ArrayResize(signals, sc + 1);
               signals[sc] = sig;
               break;
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Detect 3-Candle Post-CHoCH FVG & Mitigation Taps                 |
//+------------------------------------------------------------------+
void DetectCHoCHFVGs(const SBreakEvent &events[], SFVGZone &fvgs[])
  {
   ArrayResize(fvgs, 0);
   int event_cnt = ArraySize(events);

   for(int i = 0; i < event_cnt; i++)
     {
      if(!events[i].is_choch)
         continue;

      int cb = events[i].break_bar;
      int max_scan = MathMin(cb + 3, BarsCount - 2);

      bool found_fvg = false;
      SFVGZone fvg;

      // Scan 3-candle sequence starting from CHoCH bar up to next 3 candles
      for(int k = cb; k <= max_scan; k++)
        {
         if(k - 1 < 0 || k + 1 >= BarsCount)
            continue;

         if(events[i].is_bullish)
           {
            // Bullish FVG: Low of candle 3 > High of candle 1
            if(Rates[k + 1].low > Rates[k - 1].high + (_Point * 2))
              {
               fvg.fvg_idx        = ArraySize(fvgs);
               fvg.choch_evt_idx  = i;
               fvg.formed_bar     = k + 1;
               fvg.t_start        = Rates[k - 1].time;
               fvg.t_end          = Rates[BarsCount - 1].time;
               fvg.top            = Rates[k + 1].low;
               fvg.bottom         = Rates[k - 1].high;
               fvg.is_bullish     = true;
               fvg.is_mitigated   = false;
               fvg.mitigate_bar   = -1;
               found_fvg          = true;
               break;
              }
           }
         else
           {
            // Bearish FVG: High of candle 3 < Low of candle 1
            if(Rates[k + 1].high < Rates[k - 1].low - (_Point * 2))
              {
               fvg.fvg_idx        = ArraySize(fvgs);
               fvg.choch_evt_idx  = i;
               fvg.formed_bar     = k + 1;
               fvg.t_start        = Rates[k - 1].time;
               fvg.t_end          = Rates[BarsCount - 1].time;
               fvg.top            = Rates[k - 1].low;
               fvg.bottom         = Rates[k + 1].high;
               fvg.is_bullish     = false;
               fvg.is_mitigated   = false;
               fvg.mitigate_bar   = -1;
               found_fvg          = true;
               break;
              }
           }
        }

      if(!found_fvg)
         continue;

      // Check subsequent bars for FVG Mitigation Tap
      for(int b = fvg.formed_bar + 1; b < BarsCount; b++)
        {
         if(fvg.is_bullish)
           {
            // Price taps down into Bullish FVG
            if(Rates[b].low <= fvg.top && Rates[b].high >= fvg.bottom)
              {
               fvg.is_mitigated   = true;
               fvg.mitigate_bar   = b;
               fvg.mitigate_time  = Rates[b].time;
               fvg.mitigate_price = Rates[b].low;
               fvg.t_end          = Rates[b].time; // Trim box to tap candle
               break;
              }
           }
         else
           {
            // Price taps up into Bearish FVG
            if(Rates[b].high >= fvg.bottom && Rates[b].low <= fvg.top)
              {
               fvg.is_mitigated   = true;
               fvg.mitigate_bar   = b;
               fvg.mitigate_time  = Rates[b].time;
               fvg.mitigate_price = Rates[b].high;
               fvg.t_end          = Rates[b].time; // Trim box to tap candle
               break;
              }
           }
        }

      int fc = ArraySize(fvgs);
      ArrayResize(fvgs, fc + 1);
      fvgs[fc] = fvg;
     }
  }

//+------------------------------------------------------------------+
//| Graphics Drawing Routines                                        |
//+------------------------------------------------------------------+
void DrawTextObj(const string name, datetime t, double price, string text, int size, color clr, ENUM_ANCHOR_POINT anchor)
  {
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   else
      ObjectMove(0, name, 0, t, price);

   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetString(0, name, OBJPROP_FONT, "Segoe UI Bold");
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawLineObj(const string name, datetime t1, double p1, datetime t2, double p2, color clr, int width, ENUM_LINE_STYLE style)
  {
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }

   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawArrowObj(const string name, datetime t, double price, uchar arrow_code, color clr, int width)
  {
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   else
      ObjectMove(0, name, 0, t, price);

   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, arrow_code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawRectangleObj(const string name, datetime t1, double p1, datetime t2, double p2, color clr, bool fill)
  {
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }

   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, fill);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawFiboObj(const string name, datetime t1, double p1, datetime t2, double p2, color clr, int width, ENUM_LINE_STYLE style)
  {
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_FIBO, 0, t1, p1, t2, p2);
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }

   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);

   ObjectSetInteger(0, name, OBJPROP_LEVELS, 6);

   double levels[6] = {0.0, 0.236, 0.382, 0.50, 0.618, 1.0};
   string descs[6]  = {"0.0", "23.6", "38.2", "50.0", "61.8", "100.0"};

   for(int i = 0; i < 6; i++)
     {
      ObjectSetDouble(0, name, OBJPROP_LEVELVALUE, i, levels[i]);
      ObjectSetString(0, name, OBJPROP_LEVELTEXT, i, descs[i]);
      ObjectSetInteger(0, name, OBJPROP_LEVELCOLOR, i, clr);
      ObjectSetInteger(0, name, OBJPROP_LEVELSTYLE, i, style);
      ObjectSetInteger(0, name, OBJPROP_LEVELWIDTH, i, width);
     }
  }

//+------------------------------------------------------------------+
//| Render Swings                                                    |
//+------------------------------------------------------------------+
void RenderSwings(const SSwingPoint &swings[])
  {
   int n = ArraySize(swings);
   for(int i = 0; i < n; i++)
     {
      double atr_val = (ATR[swings[i].bar_idx] > 0) ? ATR[swings[i].bar_idx] : (15 * _Point);
      double off = atr_val * 0.35;

      bool is_bull = (swings[i].label == LB_HH || swings[i].label == LB_HL);
      color clr = is_bull ? InpBullishColor : InpBearishColor;

      string lbl = "";
      if(swings[i].label == LB_HH)
         lbl = "HH";
      else
         if(swings[i].label == LB_HL)
            lbl = "HL";
         else
            if(swings[i].label == LB_LH)
               lbl = "LH";
            else
               if(swings[i].label == LB_LL)
                  lbl = "LL";

      if(InpShowStructureLabels && lbl != "")
        {
         double y_lbl = (swings[i].type == SW_HIGH) ? (swings[i].price + off) : (swings[i].price - off);
         ENUM_ANCHOR_POINT anchor = (swings[i].type == SW_HIGH) ? ANCHOR_LOWER : ANCHOR_UPPER;
         DrawTextObj(PREFIX + "LBL_" + IntegerToString(i), swings[i].time, y_lbl, lbl, InpTextSize, clr, anchor);
        }

      if(InpShowSwingPoints)
        {
         double y_dot = (swings[i].type == SW_HIGH) ? (swings[i].price + (off * 0.2)) : (swings[i].price - (off * 0.2));
         ENUM_ANCHOR_POINT anchor = (swings[i].type == SW_HIGH) ? ANCHOR_LOWER : ANCHOR_UPPER;
         DrawTextObj(PREFIX + "DOT_" + IntegerToString(i), swings[i].time, y_dot, "●", InpTextSize - 1, clr, anchor);
        }
     }
  }

//+------------------------------------------------------------------+
//| Render Centered BOS / CHoCH Lines & Fibo                         |
//+------------------------------------------------------------------+
void RenderBreaks(const SBreakEvent &events[])
  {
   int n = ArraySize(events);
   for(int i = 0; i < n; i++)
     {
      if(events[i].is_choch && !InpShowCHoCH)
         continue;
      if(!events[i].is_choch && !InpShowBOS)
         continue;

      color clr = events[i].is_bullish ? InpBullishColor : InpBearishColor;

      // 1. Break Line
      if(InpShowBreakLines)
        {
         DrawLineObj(PREFIX + "LINE_" + IntegerToString(i),
                     events[i].t_start, events[i].level,
                     events[i].t_end, events[i].level,
                     clr, InpBreakLineWidth, InpBreakLineStyle);
        }

      // 2. Centered Text Tag
      datetime t_center = (datetime)(((long)events[i].t_start + (long)events[i].t_end) / 2);
      double off = (ATR[events[i].break_bar] > 0) ? (ATR[events[i].break_bar] * 0.15) : (5 * _Point);
      double y_pos = events[i].is_bullish ? (events[i].level + off) : (events[i].level - off);
      ENUM_ANCHOR_POINT anchor = events[i].is_bullish ? ANCHOR_LOWER : ANCHOR_UPPER;

      string tag = events[i].is_choch ? (events[i].is_bullish ? "CHoCH ↑" : "CHoCH ↓")
                   : (events[i].is_bullish ? "BOS ↑"   : "BOS ↓");

      DrawTextObj(PREFIX + "EVT_" + IntegerToString(i), t_center, y_pos, tag, InpEventTextSize, clr, anchor);

      // 3. Draw Fibo on CHoCH
      if(events[i].is_choch && InpShowCHoCHFibo)
        {
         datetime t_anchor = Rates[events[i].anchor_bar].time;
         DrawFiboObj(PREFIX + "FIBO_" + IntegerToString(i),
                     t_anchor, events[i].anchor_level,
                     events[i].t_start, events[i].level,
                     InpFiboColor, InpFiboWidth, InpFiboStyle);
        }
     }
  }

//+------------------------------------------------------------------+
//| Render FVG Zones & Mitigation Signals                            |
//+------------------------------------------------------------------+
void RenderFVGs(const SFVGZone &fvgs[])
  {
   if(!InpShowCHoCHFVG)
      return;

   int n = ArraySize(fvgs);
   for(int i = 0; i < n; i++)
     {
      color clr = fvgs[i].is_bullish ? InpBullishFVGColor : InpBearishFVGColor;

      // 1. Draw FVG Box
      DrawRectangleObj(PREFIX + "FVG_BOX_" + IntegerToString(i),
                       fvgs[i].t_start, fvgs[i].top,
                       fvgs[i].t_end, fvgs[i].bottom,
                       clr, InpFillFVGBox);

      // 2. Draw FVG Label
      double mid_price = (fvgs[i].top + fvgs[i].bottom) * 0.5;
      DrawTextObj(PREFIX + "FVG_TXT_" + IntegerToString(i), fvgs[i].t_start, mid_price, "FVG", InpFVGTextSize, clrSilver, ANCHOR_LEFT);

      // 3. Render Mitigation Signal
      if(fvgs[i].is_mitigated && InpShowFVGSignals)
        {
         double atr_val = (ATR[fvgs[i].mitigate_bar] > 0) ? ATR[fvgs[i].mitigate_bar] : (15 * _Point);
         double off = atr_val * 0.40;

         if(fvgs[i].is_bullish)
           {
            // Buy Signal: Wingdings 233 (↑)
            double y_arrow = fvgs[i].mitigate_price - off;
            DrawArrowObj(PREFIX + "FVG_SIG_ARR_" + IntegerToString(i), fvgs[i].mitigate_time, y_arrow, 233, InpBullishColor, InpSignalArrowSize + 1);

            if(InpShowSignalText)
              {
               DrawTextObj(PREFIX + "FVG_SIG_TXT_" + IntegerToString(i), fvgs[i].mitigate_time, y_arrow - off * 0.7, "BUY (FVG TAP)", InpTextSize, InpBullishColor, ANCHOR_UPPER);
              }
           }
         else
           {
            // Sell Signal: Wingdings 234 (↓)
            double y_arrow = fvgs[i].mitigate_price + off;
            DrawArrowObj(PREFIX + "FVG_SIG_ARR_" + IntegerToString(i), fvgs[i].mitigate_time, y_arrow, 234, InpBearishColor, InpSignalArrowSize + 1);

            if(InpShowSignalText)
              {
               DrawTextObj(PREFIX + "FVG_SIG_TXT_" + IntegerToString(i), fvgs[i].mitigate_time, y_arrow + off * 0.7, "SELL (FVG TAP)", InpTextSize, InpBearishColor, ANCHOR_LOWER);
              }
           }

         // Mitigation marker dot
         DrawTextObj(PREFIX + "FVG_SIG_DOT_" + IntegerToString(i), fvgs[i].mitigate_time, mid_price, "◆", InpTextSize, clrWhite, ANCHOR_CENTER);
        }
     }
  }

//+------------------------------------------------------------------+
//| Render Retest Signals (Buy/Sell Arrow 233/234 + Text)            |
//+------------------------------------------------------------------+
void RenderSignals(const SFiboSignal &signals[])
  {
   if(!InpShowRetestSignals)
      return;

   int n = ArraySize(signals);
   for(int i = 0; i < n; i++)
     {
      double atr_val = (ATR[signals[i].bar_idx] > 0) ? ATR[signals[i].bar_idx] : (15 * _Point);
      double off = atr_val * 0.40;

      if(signals[i].is_buy)
        {
         // BUY Signal: Wingdings 233 (↑)
         double y_arrow = signals[i].price - off;
         DrawArrowObj(PREFIX + "SIG_ARR_" + IntegerToString(i), signals[i].time, y_arrow, 233, InpBullishColor, InpSignalArrowSize);

         if(InpShowSignalText)
           {
            DrawTextObj(PREFIX + "SIG_TXT_" + IntegerToString(i), signals[i].time, y_arrow - off * 0.7, "BUY (50% FIBO)", InpTextSize, InpBullishColor, ANCHOR_UPPER);
           }
        }
      else
        {
         // SELL Signal: Wingdings 234 (↓)
         double y_arrow = signals[i].price + off;
         DrawArrowObj(PREFIX + "SIG_ARR_" + IntegerToString(i), signals[i].time, y_arrow, 234, InpBearishColor, InpSignalArrowSize);

         if(InpShowSignalText)
           {
            DrawTextObj(PREFIX + "SIG_TXT_" + IntegerToString(i), signals[i].time, y_arrow + off * 0.7, "SELL (50% FIBO)", InpTextSize, InpBearishColor, ANCHOR_LOWER);
           }
        }

      // Touch Dot at 50% Line
      DrawTextObj(PREFIX + "SIG_DOT_" + IntegerToString(i), signals[i].time, signals[i].fibo_50_level, "■", InpTextSize - 2, clrWhite, ANCHOR_CENTER);
     }
  }

//+------------------------------------------------------------------+
//| Status HUD                                                       |
//+------------------------------------------------------------------+
void RenderHUD(ENUM_TREND_STATE trend, int swing_count, int break_count, int fibo_sigs, int fvg_sigs)
  {
   if(!InpShowStatus)
      return;

   string name = PREFIX + "HUD";
   RegisterActiveObject(name);

   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 20);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 25);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, name, OBJPROP_FONT, "Segoe UI Semibold");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 10);
     }

   string trend_str = (trend == TREND_BULL) ? "BULLISH" : (trend == TREND_BEAR) ? "BEARISH" : "NEUTRAL / RANGE";
   color  trend_clr = (trend == TREND_BULL) ? InpBullishColor : (trend == TREND_BEAR) ? InpBearishColor : clrSilver;

   string text = StringFormat("SMC Engine v2.7 | Structure: %s | Swings: %d | Breaks: %d | Fibo 50%% Sigs: %d | FVG Taps: %d",
                              trend_str, swing_count, break_count, fibo_sigs, fvg_sigs);

   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, trend_clr);
  }

//+------------------------------------------------------------------+
//| Core Execution Loop                                              |
//+------------------------------------------------------------------+
void RunEngine()
  {
   if(BarsCount < (InpSwingStrength * 2) + 20)
      return;

   ResetActiveTracker();
   CalcATR();

   SSwingPoint swings[];
   int total_swings = BuildCleanSwings(swings);

   if(total_swings == 0)
     {
      CleanupUnusedObjects();
      return;
     }

   ClassifySwings(swings);
   RenderSwings(swings);

   SBreakEvent events[];
   ENUM_TREND_STATE active_trend = TREND_UNKNOWN;
   DetectBreaksChronological(swings, events, active_trend);
   RenderBreaks(events);

   SFiboSignal signals[];
   DetectFiboRetestSignals(events, signals);
   RenderSignals(signals);

   SFVGZone fvgs[];
   DetectCHoCHFVGs(events, fvgs);
   RenderFVGs(fvgs);

   int fvg_taps = 0;
   for(int k = 0; k < ArraySize(fvgs); k++)
     {
      if(fvgs[k].is_mitigated)
         fvg_taps++;
     }

   RenderHUD(active_trend, total_swings, ArraySize(events), ArraySize(signals), fvg_taps);

   CleanupUnusedObjects();
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| MT5 Event Handlers                                               |
//+------------------------------------------------------------------+
int OnInit()
  {
   DeleteAllIndicatorObjects();
   IndicatorSetString(INDICATOR_SHORTNAME, "Human-Level Structure Engine v2.7 (Fibo & FVG Retest)");
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   int wanted = MathMin(rates_total, MathMax(250, InpMaxBars));
   ArrayResize(Rates, wanted);

   int copied = CopyRates(_Symbol, _Period, 0, wanted, Rates);
   if(copied <= 0)
      return prev_calculated;

   BarsCount = copied;

   RunEngine();

   return rates_total;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(InpDeleteObjectsOnExit)
      DeleteAllIndicatorObjects();

   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
