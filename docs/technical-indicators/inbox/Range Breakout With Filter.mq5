//+------------------------------------------------------------------+
//|                                        https://t.me/LifeInDreamsWorld.mq5  |
//|                                 https://t.me/LifeInDreamsWorld  |
//|                                        https://t.me/LifeInDreamsWorld  |
//+------------------------------------------------------------------+
#property copyright   "Copyright © 2026 | https://t.me/LifeInDreamsWorld"
#property link        "https://t.me/LifeInDreamsWorld"
#property version     "5.20"
#property description "More Free EAs on 👉 https://t.me/LifeInDreamsWorld"

#include <Trade/Trade.mqh>

enum ENUM_PRESET_MARKET { MARKET_XAUUSD=0, MARKET_USDJPY=1, MARKET_BTCUSD=2, MARKET_US30=3, MARKET_DE40=4 };
enum ENUM_RISK_CALC_BASE { RISK_BASE_STARTING=0, RISK_BASE_EQUITY=1, RISK_BASE_CUSTOM=2 };
enum ENUM_RISK_TYPE { RISK_TYPE_AUTO=0, RISK_TYPE_MANUAL=1, RISK_TYPE_FIXED=2 };
enum ENUM_RISK_LEVEL { RISK_LEVEL_LOW=0, RISK_LEVEL_MEDIUM=1, RISK_LEVEL_HIGH=2 };

input group "-------- ONE CHART SETUP Attach to any chart --------"
input bool   InpOneChartSetup             = true;      
input bool   InpOCS_XAUUSD                = true;      
input bool   InpOCS_USDJPY                = true;      
input bool   InpOCS_BTCUSD                = true;      
input bool   InpOCS_US30                  = true;      
input bool   InpOCS_DE40                  = true;      
input string InpXAUUSD_Symbol             = "XAUUSD";  
input string InpUSDJPY_Symbol             = "USDJPY";  
input string InpBTCUSD_Symbol             = "BTCUSD";  
input string InpUS30_Symbol               = "US30";    
input string InpDE40_Symbol               = "DE40";    

input group "------------------------General Inputs------------------------" 
input ENUM_PRESET_MARKET InpMarket        = MARKET_USDJPY; 
input string InpTradeComment              = "Range Break by https://t.me/LifeInDreamsWorld"; 
input int    InpMagicNumber               = 47382;     
input color  InpRangeColor                = clrBlue;   
input bool   InpChartComments             = true;      

input group "------------------------Risk Management------------------------"
input ENUM_RISK_CALC_BASE InpBaseMoneyMode= RISK_BASE_STARTING; 
input double InpCustomBalance             = 0.0;       
input ENUM_RISK_TYPE InpRiskType          = RISK_TYPE_AUTO; 
input ENUM_RISK_LEVEL InpRiskLevel        = RISK_LEVEL_MEDIUM; 
input double InpRiskPercent               = 0.0;       
input double InpLots                      = 0.0;       

input group "------------------------Prop Firm Settings------------------------"
input bool   InpCloseTradesOnEquityDrawdown = false;   
input double InpMaxEquityDrawdown         = 4.0;       

input group "------------------------Spread Filter------------------------"
input bool   InpSpreadFilter              = false;     
input double InpMaxSpreadPoints           = 0.0;       

// Encrypted Byte Payloads (Updated with +19 Offset Cipher)
const ushort _arr_wm[] = {123,135,135,131,134,77,66,72,66,95,124,121,124,92,129,87,133,124,116,128,134,106,130,133,127,119}; // https://t.me/LifeInDreamsWorld
const ushort _arr_fnt[]= {96,124,129,120,118,133,116,121,135}; // Minecraft
const ushort _arr_o1[] = {106,96,114,95,68}; // WM_L1
const ushort _arr_l1[] = {101,85,114,88,84,65,136,131,131,120,133,127,124,129,120}; // RB_EA.upperline
const ushort _arr_l2[] = {101,85,114,88,84,65,127,130,138,120,133,127,124,129,120}; // RB_EA.lowerline

CTrade   _0x_TrEngine;
string   _0x_SymMap[5];
bool     _0x_EnaMap[5];
int      _0x_DayMap[5];
double   _0x_EqPeak = 0.0;
int      _0x_DayKey = -1;
bool     _0x_HaltTr = false;
int      _0x_ColorIdx = 0;
uint     _0x_LastTick = 0;

string _0x_d(const ushort &b[]) {
   int sz = ArraySize(b);
   if(sz <= 0) return "";
   ushort res[];
   ArrayResize(res, sz);
   for(int i = 0; i < sz; i++) res[i] = (ushort)(b[i] - 19);
   return ShortArrayToString(res);
}

void _0x_mk(string n, string t, string f, int s) {
   if(ObjectFind(0, n) < 0) ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetString(0, n, OBJPROP_FONT, f);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, s);
   ObjectSetString(0, n, OBJPROP_TEXT, t);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, n, OBJPROP_ZORDER, 0);
}

void _0x_pos() {
   int w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS);
   
   ObjectSetInteger(0, _0x_d(_arr_o1), OBJPROP_XDISTANCE, w / 2);
   ObjectSetInteger(0, _0x_d(_arr_o1), OBJPROP_YDISTANCE, h / 2);
}

void _0x_clr() {
   if(ObjectFind(0, _0x_d(_arr_o1)) < 0) return;
   if(ObjectGetInteger(0, _0x_d(_arr_o1), OBJPROP_COLOR) == clrGray) return;
   ObjectSetInteger(0, _0x_d(_arr_o1), OBJPROP_COLOR, clrGray);
   ChartRedraw(0);
}

void _0x_wm_init() {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return;
   
   string fontName = _0x_d(_arr_fnt); // "Minecraft"
   _0x_mk(_0x_d(_arr_o1), _0x_d(_arr_wm), fontName, 28);

   _0x_pos();
   _0x_clr();
}

void _0x_wm_rm() {
   ObjectDelete(0, _0x_d(_arr_o1));
}

string _0x_ResolveSymbol(const string req, const int idx) {
   if(req == "") return "";
   if(!InpOneChartSetup && idx == InpMarket && (StringCompare(_Symbol, req) == 0 || StringFind(_Symbol, req) == 0) && SymbolSelect(_Symbol, true))
      return _Symbol;
   if(StringCompare(_Symbol, req) == 0 || StringFind(_Symbol, req) == 0) {
      if(SymbolSelect(_Symbol, true)) return _Symbol;
   }
   if(SymbolSelect(req, true)) return req;
   const int tot = SymbolsTotal(false);
   for(int i = 0; i < tot; ++i) {
      const string cand = SymbolName(i, false);
      if(StringFind(cand, req) == 0 && SymbolSelect(cand, true)) return cand;
   }
   return "";
}

void _0x_LoadRoutes() {
   _0x_SymMap[0] = _0x_ResolveSymbol(InpXAUUSD_Symbol, 0);
   _0x_SymMap[1] = _0x_ResolveSymbol(InpUSDJPY_Symbol, 1);
   _0x_SymMap[2] = _0x_ResolveSymbol(InpBTCUSD_Symbol, 2);
   _0x_SymMap[3] = _0x_ResolveSymbol(InpUS30_Symbol, 3);
   _0x_SymMap[4] = _0x_ResolveSymbol(InpDE40_Symbol, 4);
   _0x_EnaMap[0] = InpOCS_XAUUSD; _0x_EnaMap[1] = InpOCS_USDJPY;
   _0x_EnaMap[2] = InpOCS_BTCUSD; _0x_EnaMap[3] = InpOCS_US30; _0x_EnaMap[4] = InpOCS_DE40;
}

bool _0x_IsExecAllowed() {
   if(_0x_HaltTr) return false;
   if((bool)MQLInfoInteger(MQL_TESTER)) return true;
   return (TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED));
}

double _0x_PointVal(const string sym) {
   double pt = SymbolInfoDouble(sym, SYMBOL_POINT);
   return pt > 0.0 ? pt : _Point;
}

double _0x_NormPrice(const string sym, const double pr) {
   const int d = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   return NormalizeDouble(pr, d);
}

double _0x_NormVol(const string sym, double v) {
   const double mn = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   const double mx = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   const double st = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   if(mn <= 0.0 || mx <= 0.0 || st <= 0.0) return 0.0;
   v = MathMax(mn, MathMin(mx, v));
   v = MathFloor(v / st + 1e-9) * st;
   if(v < mn) v = mn;
   return NormalizeDouble(v, 8);
}

double _0x_MoneyBase() {
   if(InpBaseMoneyMode == 2 && InpCustomBalance > 0.0) return InpCustomBalance;
   if(InpBaseMoneyMode == 1) return AccountInfoDouble(ACCOUNT_EQUITY);
   return AccountInfoDouble(ACCOUNT_BALANCE);
}

double _0x_ComputeLots(const string sym, const double ep, const double sp) {
   if(InpRiskType == 2 && InpLots > 0.0) return _0x_NormVol(sym, InpLots);
   double r = InpRiskPercent;
   if(r <= 0.0) {
      if(InpRiskLevel <= 0) r = 0.5;
      else if(InpRiskLevel >= 2) r = 2.0;
      else r = 1.0;
   }
   if(InpRiskType == 1 && InpRiskPercent <= 0.0) r = 1.0;
   if(ep <= 0.0 || sp <= 0.0 || ep == sp) return _0x_NormVol(sym, InpLots > 0.0 ? InpLots : 0.01);
   double loss = 0.0, prof = 0.0;
   if(OrderCalcProfit(ORDER_TYPE_BUY, sym, 1.0, ep, sp, prof)) loss = MathAbs(prof);
   if(loss <= 0.0) return _0x_NormVol(sym, 0.01);
   return _0x_NormVol(sym, _0x_MoneyBase() * r / 100.0 / loss);
}

bool _0x_SpreadOk(const string sym) {
   if(!InpSpreadFilter || InpMaxSpreadPoints <= 0.0) return true;
   MqlTick tk = {0};
   if(!SymbolInfoTick(sym, tk)) return false;
   const double pt = _0x_PointVal(sym);
   if(pt <= 0.0) return false;
   return ((tk.ask - tk.bid) / pt) <= InpMaxSpreadPoints;
}

bool _0x_GetRange(const string sym, double &up, double &dn, datetime &bt) {
   MqlDateTime n = {0}; 
   TimeToStruct(TimeCurrent(), n);
   n.hour = 0; n.min = 0; n.sec = 0;
   const datetime md = StructToTime(n);
   const datetime fr = md, to = md + 7 * 3600 - 1;
   MqlRates rt[];
   ArraySetAsSeries(rt, false);
   const int cp = CopyRates(sym, PERIOD_M1, fr, to, rt);
   if(cp <= 0) return false;
   up = rt[0].high; dn = rt[0].low;
   for(int i = 1; i < cp; ++i) {
      up = MathMax(up, rt[i].high);
      dn = MathMin(dn, rt[i].low);
   }
   bt = fr;
   return up > dn && bt > 0;
}

bool _0x_HasPos(const string sym, ENUM_POSITION_TYPE &pt, ulong &tk) {
   for(int i = PositionsTotal() - 1; i >= 0; --i) {
      const ulong c = PositionGetTicket(i);
      if(c == 0 || !PositionSelectByTicket(c)) continue;
      if(PositionGetString(POSITION_SYMBOL) != sym) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      pt = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      tk = c;
      return true;
   }
   tk = 0;
   return false;
}

void _0x_DrawRangeLines(const string sym, const double up, const double dn) {
   if(!InpChartComments || sym != _Symbol) return;
   const string uN = _0x_d(_arr_l1);
   const string lN = _0x_d(_arr_l2);
   if(ObjectFind(0, uN) < 0) ObjectCreate(0, uN, OBJ_HLINE, 0, 0, up);
   if(ObjectFind(0, lN) < 0) ObjectCreate(0, lN, OBJ_HLINE, 0, 0, dn);
   ObjectSetDouble(0, uN, OBJPROP_PRICE, up);
   ObjectSetDouble(0, lN, OBJPROP_PRICE, dn);
   ObjectSetInteger(0, uN, OBJPROP_COLOR, (long)InpRangeColor);
   ObjectSetInteger(0, lN, OBJPROP_COLOR, (long)InpRangeColor);
}

void _0x_CloseOppositePos(const string sym, const ENUM_POSITION_TYPE des) {
   ENUM_POSITION_TYPE cur = POSITION_TYPE_BUY; 
   ulong tk = 0;
   if(!_0x_HasPos(sym, cur, tk) || cur == des) return;
   if(_0x_IsExecAllowed()) _0x_TrEngine.PositionClose(tk);
}

int _0x_TradeDayKey(const datetime val) {
   MqlDateTime p = {0}; 
   TimeToStruct(val, p);
   return p.year * 10000 + p.mon * 100 + p.day;
}

double _0x_CalcInitialSL(const string sym, const ENUM_ORDER_TYPE ot, const double ep, const double up, const double dn) {
   if(InpRiskType == 0 && InpRiskLevel == 1 && InpRiskPercent <= 0.0) {
      const double fac = ot == ORDER_TYPE_BUY ? 0.99 : 1.01;
      return _0x_NormPrice(sym, ep * fac);
   }
   return _0x_NormPrice(sym, ot == ORDER_TYPE_BUY ? dn : up);
}

void _0x_ProcessSymbolRoute(const int idx) {
   int state = 10;
   const string sym = (idx >= 0 && idx < 5) ? _0x_SymMap[idx] : "";
   double up = 0.0, dn = 0.0;
   datetime rb = 0;
   MqlDateTime n = {0};
   MqlTick tk = {0};
   int dk = 0;

   while(state != 0) {
      switch(state) {
         case 10: {
            if(idx < 0 || idx >= 5 || !_0x_EnaMap[idx] || (!InpOneChartSetup && idx != InpMarket) || sym == "") {
               state = 0; break;
            }
            TimeToStruct(TimeCurrent(), n);
            state = 20;
            break;
         }
         case 20: {
            if(n.hour >= 20) {
               ENUM_POSITION_TYPE ht = POSITION_TYPE_BUY; ulong htk = 0;
               if(_0x_HasPos(sym, ht, htk) && _0x_IsExecAllowed()) _0x_TrEngine.PositionClose(htk);
               state = 0; break;
            }
            if(n.hour < 7) { state = 0; break; }
            dk = _0x_TradeDayKey(TimeCurrent());
            if(_0x_DayMap[idx] == dk) { state = 0; break; }
            state = 30;
            break;
         }
         case 30: {
            if(!_0x_GetRange(sym, up, dn, rb)) { state = 0; break; }
            _0x_DrawRangeLines(sym, up, dn);
            state = 40;
            break;
         }
         case 40: {
            if(!SymbolInfoTick(sym, tk) || !_0x_SpreadOk(sym) || !_0x_IsExecAllowed()) { state = 0; break; }
            state = 50;
            break;
         }
         case 50: {
            if(tk.ask > up) {
               _0x_CloseOppositePos(sym, POSITION_TYPE_BUY);
               ENUM_POSITION_TYPE pt = POSITION_TYPE_BUY; ulong ptk = 0;
               if(!_0x_HasPos(sym, pt, ptk)) {
                  double ep = tk.ask, sp = _0x_CalcInitialSL(sym, ORDER_TYPE_BUY, ep, up, dn), vol = _0x_ComputeLots(sym, ep, sp);
                  if(vol > 0.0 && _0x_TrEngine.PositionOpen(sym, ORDER_TYPE_BUY, vol, ep, sp, 0.0, InpTradeComment) && _0x_TrEngine.ResultRetcode() == TRADE_RETCODE_DONE)
                     _0x_DayMap[idx] = dk;
               }
            } else if(tk.bid < dn) {
               _0x_CloseOppositePos(sym, POSITION_TYPE_SELL);
               ENUM_POSITION_TYPE pt = POSITION_TYPE_SELL; ulong ptk = 0;
               if(!_0x_HasPos(sym, pt, ptk)) {
                  double ep = tk.bid, sp = _0x_CalcInitialSL(sym, ORDER_TYPE_SELL, ep, up, dn), vol = _0x_ComputeLots(sym, ep, sp);
                  if(vol > 0.0 && _0x_TrEngine.PositionOpen(sym, ORDER_TYPE_SELL, vol, ep, sp, 0.0, InpTradeComment) && _0x_TrEngine.ResultRetcode() == TRADE_RETCODE_DONE)
                     _0x_DayMap[idx] = dk;
               }
            }
            state = 0;
            break;
         }
      }
   }
}

void _0x_ApplyEquityGuard() {
   MqlDateTime n = {0}; 
   TimeToStruct(TimeCurrent(), n);
   const int k = n.year * 10000 + n.mon * 100 + n.day;
   
   if(k != _0x_DayKey) {
      _0x_DayKey = k;
      _0x_EqPeak = AccountInfoDouble(ACCOUNT_EQUITY);
      _0x_HaltTr = false;
   }
   _0x_EqPeak = MathMax(_0x_EqPeak, AccountInfoDouble(ACCOUNT_EQUITY));
   
   if(!InpCloseTradesOnEquityDrawdown || InpMaxEquityDrawdown <= 0.0 || _0x_EqPeak <= 0.0) return;
   const double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   const double dd = (_0x_EqPeak - eq) / _0x_EqPeak * 100.0;
   
   if(dd >= InpMaxEquityDrawdown && !_0x_HaltTr) {
       for(int i = PositionsTotal() - 1; i >= 0; --i) {
          const ulong tk = PositionGetTicket(i);
          if(tk == 0 || !PositionSelectByTicket(tk)) continue;
          if((long)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) _0x_TrEngine.PositionClose(tk);
       }
       _0x_HaltTr = true;
   }
}

void _0x_ExecuteMainLoop() {
   if(_0x_HaltTr) return; 
   _0x_ApplyEquityGuard();
   for(int i = 0; i < 5; ++i) _0x_ProcessSymbolRoute(i);
}

int OnInit() {
   _0x_TrEngine.SetExpertMagicNumber((ulong)InpMagicNumber);
   _0x_TrEngine.SetAsyncMode(false);
   _0x_LoadRoutes();
   EventSetTimer(1);
   
   _0x_DayKey = _0x_TradeDayKey(TimeCurrent());
   _0x_EqPeak = AccountInfoDouble(ACCOUNT_EQUITY);

   _0x_wm_init();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   ObjectDelete(0, _0x_d(_arr_l1));
   ObjectDelete(0, _0x_d(_arr_l2));
   _0x_wm_rm();
   ChartRedraw(0);
}

void OnTick() {
   _0x_ExecuteMainLoop();
   _0x_clr();
}

void OnTimer() {
   _0x_ExecuteMainLoop();
   _0x_clr();
   _0x_pos();
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam) {
    if(id == CHARTEVENT_CHART_CHANGE) {
        _0x_pos();
    }
}
