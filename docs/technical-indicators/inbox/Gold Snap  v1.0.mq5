//+------------------------------------------------------------------+
//|                     Gold Snap Clean Room v1.00.mq5               |
//| Independent support/resistance breakout implementation           |
//+------------------------------------------------------------------+
#property copyright "Simple Forex Tools"
#property version   "1.00"
#property link      "https://t.me/simpleforextools"
#property strict
#property description "Adaptive XAU support/resistance breakout with fast profit capture"

#include <Trade/Trade.mqh>

enum GS_LOT_MODE { GS_FIXED_LOT=0, GS_RISK_PERCENT=1 };

input group "===== GOLD SNAP CLEAN ROOM ====="
input long              InpMagic                 = 26981;
input GS_LOT_MODE       InpLotMode               = GS_FIXED_LOT;
input double            InpFixedLot              = 0.01;
input double            InpRiskPercent           = 1.00;
input bool              InpAllowBuy              = true;
input bool              InpAllowSell             = true;

input group "===== EMBEDDED BEST-PERFORMANCE LOGIC ====="
input ENUM_TIMEFRAMES   InpStructureTimeframe    = PERIOD_H1;
input int               InpPivotWing             = 2;
input int               InpMaximumPivotAgeHours  = 1440;
input int               InpPendingExpiryHours    = 18;
input double            InpEntryBufferPrice      = 0.00;
input double            InpMinimumLevelDistance  = 5.00;
input double            InpMaximumLevelDistance  = 180.00;
input double            InpMaximumSpreadPrice    = 0.50;

input group "===== ADAPTIVE PROTECTION ====="
input int               InpATRPeriod             = 14;
input double            InpStopATRMultiplier     = 0.60;
input double            InpMinimumStopPrice      = 7.50;
input double            InpMaximumStopPrice      = 9.20;
input double            InpRewardRisk            = 1.90;
input double            InpTrailArmPrice         = 1.60;
input double            InpTrailDistancePrice    = 0.30;
input double            InpTrailStepPrice        = 0.15;
input bool              InpUseTwoStageTrail      = false;
input double            InpBreakEvenLockPrice    = 0.20;
input double            InpRunnerArmPrice        = 5.00;
input bool              InpDeleteFriday          = true;
input int               InpFridayDeleteHour      = 20;

input group "===== DISPLAY ====="
input bool              InpShowPanel             = true;
input bool              InpDarkChart             = true;

CTrade trade;
int atr_handle=INVALID_HANDLE;
datetime last_scan_bar=0;
string ui_prefix="GSCR_";
string status_text="INITIALIZING";
bool render_panel=false;
const color C_BG=C'9,14,25',C_CARD=C'20,29,46',C_EDGE=C'198,156,69',C_TEXT=C'235,238,244',C_MUTED=C'142,156,181',C_GREEN=C'31,222,156',C_RED=C'255,79,112',C_CYAN=C'70,209,255',C_GOLD=C'241,190,76';

double TickSize()
{
   double value=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(value<=0.0) value=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   return value;
}

double NormalizePrice(const double price)
{
   const double tick=TickSize();
   const int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   if(tick<=0.0) return NormalizeDouble(price,digits);
   return NormalizeDouble(MathRound(price/tick)*tick,digits);
}

double Clamp(const double value,const double low,const double high)
{
   return MathMax(low,MathMin(high,value));
}

double BrokerMinimumDistance()
{
   const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   const long stops=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   const long freeze=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   return MathMax((double)MathMax(stops,freeze)*point,TickSize()*2.0);
}

double CurrentSpread()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return DBL_MAX;
   return tick.ask-tick.bid;
}

bool IsGold()
{
   string upper=_Symbol;
   StringToUpper(upper);
   return StringFind(upper,"XAU")>=0 || StringFind(upper,"GOLD")>=0;
}

bool SpreadAllowed()
{
   return CurrentSpread()<=MathMax(BrokerMinimumDistance(),InpMaximumSpreadPrice);
}

double ATRValue()
{
   double value[1];
   if(atr_handle==INVALID_HANDLE || CopyBuffer(atr_handle,0,1,1,value)!=1) return 0.0;
   return value[0];
}

double NormalizeVolume(double lots)
{
   const double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0) step=minimum;
   lots=Clamp(lots,minimum,maximum);
   lots=MathFloor(lots/step+1e-8)*step;
   return NormalizeDouble(lots,8);
}

double EntryLots(const ENUM_ORDER_TYPE type,const double entry,const double sl)
{
   if(InpLotMode==GS_FIXED_LOT) return NormalizeVolume(InpFixedLot);
   const double budget=AccountInfoDouble(ACCOUNT_BALANCE)*Clamp(InpRiskPercent,0.05,10.0)/100.0;
   double loss=0.0;
   if(!OrderCalcProfit(type,_Symbol,1.0,entry,sl,loss) || loss>=0.0) return NormalizeVolume(InpFixedLot);
   return NormalizeVolume(budget/MathAbs(loss));
}

bool MarginAvailable(const ENUM_ORDER_TYPE type,const double lots,const double entry)
{
   double margin=0.0;
   if(!OrderCalcMargin(type,_Symbol,lots,entry,margin)) return false;
   return AccountInfoDouble(ACCOUNT_MARGIN_FREE)>margin*1.10;
}

bool OurPosition(ulong &ticket,long &type,double &open,double &sl,double &tp)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      const ulong candidate=PositionGetTicket(i);
      if(candidate==0 || PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      ticket=candidate; type=PositionGetInteger(POSITION_TYPE); open=PositionGetDouble(POSITION_PRICE_OPEN);
      sl=PositionGetDouble(POSITION_SL); tp=PositionGetDouble(POSITION_TP); return true;
   }
   return false;
}

int PendingCount(const int side)
{
   int count=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      const ulong ticket=OrderGetTicket(i);
      if(ticket==0 || OrderGetString(ORDER_SYMBOL)!=_Symbol || OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      const ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if((side>0 && type==ORDER_TYPE_BUY_STOP) || (side<0 && type==ORDER_TYPE_SELL_STOP)) count++;
   }
   return count;
}

void DeletePending(const string reason)
{
   trade.SetExpertMagicNumber(InpMagic);
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      const ulong ticket=OrderGetTicket(i);
      if(ticket==0 || OrderGetString(ORDER_SYMBOL)!=_Symbol || OrderGetInteger(ORDER_MAGIC)!=InpMagic) continue;
      const ENUM_ORDER_TYPE type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type!=ORDER_TYPE_BUY_STOP && type!=ORDER_TYPE_SELL_STOP) continue;
      if(!trade.OrderDelete(ticket)) PrintFormat("Gold Snap CR delete rejected %I64u (%u): %s",ticket,trade.ResultRetcode(),trade.ResultRetcodeDescription());
   }
   if(reason!="") status_text=reason;
}

bool FreshHigh(const MqlRates &rates[],const int shift)
{
   const double level=rates[shift].high;
   for(int i=1;i<=InpPivotWing;i++) if(rates[shift-i].high>=level || rates[shift+i].high>level) return false;
   for(int newer=0;newer<shift;newer++) if(rates[newer].high>=level) return false;
   return true;
}

bool FreshLow(const MqlRates &rates[],const int shift)
{
   const double level=rates[shift].low;
   for(int i=1;i<=InpPivotWing;i++) if(rates[shift-i].low<=level || rates[shift+i].low<level) return false;
   for(int newer=0;newer<shift;newer++) if(rates[newer].low<=level) return false;
   return true;
}

bool FindFreshLevels(double &buy_level,double &sell_level)
{
   buy_level=0.0; sell_level=0.0;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return false;
   const int bars=MathMax(200,InpMaximumPivotAgeHours*60/PeriodSeconds(InpStructureTimeframe)+InpPivotWing+10);
   MqlRates rates[];
   ArraySetAsSeries(rates,true);
   const int copied=CopyRates(_Symbol,InpStructureTimeframe,0,bars,rates);
   if(copied<InpPivotWing*2+20) return false;
   double newer_high=-DBL_MAX;
   double newer_low=DBL_MAX;
   for(int i=0;i<=InpPivotWing;i++)
   {
      newer_high=MathMax(newer_high,rates[i].high);
      newer_low=MathMin(newer_low,rates[i].low);
   }
   for(int shift=InpPivotWing+1;shift<copied-InpPivotWing;shift++)
   {
      const double age_hours=(double)(TimeCurrent()-rates[shift].time)/3600.0;
      if(age_hours>InpMaximumPivotAgeHours) break;
      bool older_high_ok=true,older_low_ok=true;
      for(int wing=1;wing<=InpPivotWing;wing++)
      {
         if(rates[shift+wing].high>rates[shift].high) older_high_ok=false;
         if(rates[shift+wing].low<rates[shift].low) older_low_ok=false;
      }
      if(buy_level==0.0 && rates[shift].high>newer_high && older_high_ok)
      {
         const double level=NormalizePrice(rates[shift].high+InpEntryBufferPrice);
         const double distance=level-tick.ask;
         if(distance>=InpMinimumLevelDistance && distance<=InpMaximumLevelDistance) buy_level=level;
      }
      if(sell_level==0.0 && rates[shift].low<newer_low && older_low_ok)
      {
         const double level=NormalizePrice(rates[shift].low-InpEntryBufferPrice);
         const double distance=tick.bid-level;
         if(distance>=InpMinimumLevelDistance && distance<=InpMaximumLevelDistance) sell_level=level;
      }
      if(buy_level>0.0 && sell_level>0.0) break;
      newer_high=MathMax(newer_high,rates[shift].high);
      newer_low=MathMin(newer_low,rates[shift].low);
   }
   return buy_level>0.0 || sell_level>0.0;
}

bool PlaceStop(const int side,const double entry)
{
   if(entry<=0.0 || !SpreadAllowed() || PendingCount(side)>0) return false;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return false;
   const double minimum=BrokerMinimumDistance()*1.15;
   if((side>0 && entry-tick.ask<minimum) || (side<0 && tick.bid-entry<minimum)) return false;
   const double atr=ATRValue();
   if(atr<=0.0) return false;
   const double sl_distance=MathMax(minimum,Clamp(atr*InpStopATRMultiplier,InpMinimumStopPrice,InpMaximumStopPrice));
   const double tp_distance=MathMax(minimum,sl_distance*InpRewardRisk);
   const double sl=NormalizePrice(entry-side*sl_distance);
   const double tp=NormalizePrice(entry+side*tp_distance);
   const ENUM_ORDER_TYPE type=side>0 ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
   const double lots=EntryLots(type,entry,sl);
   if(lots<=0.0 || !MarginAvailable(type,lots,entry)) return false;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   const datetime expiry=TimeCurrent()+InpPendingExpiryHours*3600;
   const bool sent=side>0 ? trade.BuyStop(lots,entry,_Symbol,sl,tp,ORDER_TIME_SPECIFIED,expiry,"GSCR BUY")
                          : trade.SellStop(lots,entry,_Symbol,sl,tp,ORDER_TIME_SPECIFIED,expiry,"GSCR SELL");
   if(!sent) PrintFormat("Gold Snap CR pending rejected (%u): %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
   return sent;
}

void ScanLevels()
{
   ulong ticket; long type; double open,sl,tp;
   if(OurPosition(ticket,type,open,sl,tp)) { DeletePending(""); return; }
   if(!SpreadAllowed()) { status_text="SPREAD HOLD"; return; }
   double buy_level,sell_level;
   if(!FindFreshLevels(buy_level,sell_level)) { status_text="SCANNING LEVELS"; return; }
   bool placed=false;
   if(InpAllowBuy && buy_level>0.0) placed|=PlaceStop(1,buy_level);
   if(InpAllowSell && sell_level>0.0) placed|=PlaceStop(-1,sell_level);
   status_text=placed ? "BREAKOUTS ARMED" : "LEVELS MONITORED";
}

void ManageTrailing()
{
   ulong ticket; long type; double open,sl,tp;
   if(!OurPosition(ticket,type,open,sl,tp)) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;
   const int side=type==POSITION_TYPE_BUY ? 1 : -1;
   const double current=side>0 ? tick.bid : tick.ask;
   const double profit=side*(current-open);
   if(profit<InpTrailArmPrice) return;
   const double minimum=BrokerMinimumDistance()*1.15;
   const double distance=MathMax(InpTrailDistancePrice,minimum);
   const double step=MathMax(InpTrailStepPrice,TickSize());
   double candidate=NormalizePrice(current-side*distance);
   if(InpUseTwoStageTrail && profit<InpRunnerArmPrice)
      candidate=NormalizePrice(open+side*InpBreakEvenLockPrice);
   if(side>0)
   {
      candidate=MathMin(candidate,NormalizePrice(tick.bid-minimum));
      if((sl==0.0 || candidate>sl+step) && candidate<tick.bid) trade.PositionModify(ticket,candidate,tp);
   }
   else
   {
      candidate=MathMax(candidate,NormalizePrice(tick.ask+minimum));
      if((sl==0.0 || candidate<sl-step) && candidate>tick.ask) trade.PositionModify(ticket,candidate,tp);
   }
}

void FridayCleanup()
{
   if(!InpDeleteFriday) return;
   MqlDateTime now;
   TimeToStruct(TimeCurrent(),now);
   if(now.day_of_week==5 && now.hour>=InpFridayDeleteHour) DeletePending("WEEKEND PROTECTION");
}

void Rect(const string id,const int x,const int y,const int w,const int h,const color bg,const color border)
{
   const string name=ui_prefix+id;
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER); ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,w); ObjectSetInteger(0,name,OBJPROP_YSIZE,h); ObjectSetInteger(0,name,OBJPROP_BGCOLOR,bg); ObjectSetInteger(0,name,OBJPROP_COLOR,border);
   ObjectSetInteger(0,name,OBJPROP_BORDER_TYPE,BORDER_FLAT); ObjectSetInteger(0,name,OBJPROP_BACK,false); ObjectSetInteger(0,name,OBJPROP_HIDDEN,true); ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

void Label(const string id,const int x,const int y,const string text,const int size,const color clr)
{
   const string name=ui_prefix+id;
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER); ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(0,name,OBJPROP_TEXT,text); ObjectSetString(0,name,OBJPROP_FONT,"Times New Roman"); ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size); ObjectSetInteger(0,name,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true); ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}

void DeletePanel()
{
   for(int i=ObjectsTotal(0)-1;i>=0;i--)
   {
      const string name=ObjectName(0,i);
      if(StringFind(name,ui_prefix)==0) ObjectDelete(0,name);
   }
}

void DrawPanel()
{
   if(!render_panel) return;
   Rect("BG",18,35,430,250,C_BG,C_EDGE); Rect("HDR",28,47,410,54,C_CARD,C_EDGE);
   Label("TITLE",45,58,"GOLD SNAP CLEAN ROOM",18,C_TEXT); Label("SUB",46,82,"ADAPTIVE STRUCTURE BREAKOUT",8,C_GOLD);
   Rect("A",28,111,195,58,C_CARD,C_EDGE); Rect("B",233,111,205,58,C_CARD,C_EDGE);
   Label("AL",43,122,"ENGINE STATUS",8,C_MUTED); Label("AV",43,141,status_text,11,C_CYAN);
   Label("BL",248,122,"LIVE SPREAD",8,C_MUTED); Label("BV",248,141,DoubleToString(CurrentSpread(),2),14,SpreadAllowed()?C_GREEN:C_RED);
   Rect("C",28,179,410,45,C_CARD,C_EDGE); Label("CL",43,190,"EXPOSURE",8,C_MUTED);
   Label("CV",43,207,StringFormat("%d POSITION  •  %d BUY STOP  •  %d SELL STOP",PositionsTotal(),PendingCount(1),PendingCount(-1)),10,C_TEXT);
   Label("FOOT",43,232,StringFormat("%s  •  %s",_Symbol,EnumToString(InpStructureTimeframe)),8,C_MUTED);
   ChartRedraw();
}

int OnInit()
{
   if(!IsGold()) { Print("Gold Snap CR supports XAUUSD/GOLD symbols and broker suffixes."); return INIT_PARAMETERS_INCORRECT; }
   atr_handle=iATR(_Symbol,InpStructureTimeframe,InpATRPeriod);
   if(atr_handle==INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic); trade.SetTypeFillingBySymbol(_Symbol); trade.SetAsyncMode(false);
   render_panel=InpShowPanel && !(bool)MQLInfoInteger(MQL_TESTER);
   TesterHideIndicators(true);
   if(InpDarkChart) { ChartSetInteger(0,CHART_COLOR_BACKGROUND,C'5,8,14'); ChartSetInteger(0,CHART_COLOR_FOREGROUND,C_TEXT); ChartSetInteger(0,CHART_COLOR_GRID,C'19,27,42'); }
   EventSetTimer(1); ScanLevels(); DrawPanel(); return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer(); if(atr_handle!=INVALID_HANDLE) IndicatorRelease(atr_handle); DeletePanel();
}

void OnTick()
{
   ManageTrailing(); FridayCleanup();
   ulong ticket; long type; double open,sl,tp;
   if(OurPosition(ticket,type,open,sl,tp)) DeletePending("");
   const datetime bar=iTime(_Symbol,PERIOD_M30,0);
   if(bar!=0 && bar!=last_scan_bar) { last_scan_bar=bar; ScanLevels(); }
}

void OnTimer()
{
   DrawPanel();
}

void OnTradeTransaction(const MqlTradeTransaction &transaction,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(transaction.type!=TRADE_TRANSACTION_DEAL_ADD || transaction.deal==0) return;
   if(!HistoryDealSelect(transaction.deal) || HistoryDealGetString(transaction.deal,DEAL_SYMBOL)!=_Symbol || HistoryDealGetInteger(transaction.deal,DEAL_MAGIC)!=InpMagic) return;
   const ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(transaction.deal,DEAL_ENTRY);
   if(entry==DEAL_ENTRY_IN) DeletePending("");
   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY) { status_text="CYCLE COMPLETE"; ScanLevels(); }
}
