//+------------------------------------------------------------------+
//|BandsRSI
//+------------------------------------------------------------------+
#property indicator_separate_window
#property indicator_buffers 4
#property indicator_color1 CLR_NONE
#property indicator_color2 Green
#property indicator_color3 Red
#property indicator_color4 DodgerBlue

//#property indicator_minimum 0
//#property indicator_maximum 100

//---- indicator parameters
extern int    RSIPeriod=14;
extern int    BandsPeroid1=14;
//extern int    BandsShift=0;
extern double BandsDeviations=1.0;
extern string xxx="RSIPrice = o-Open, h-HIGH, l=Low, c-Close";
extern string RSIPrice = "c";
//---- buffers
double MovingBuffer[];
double UpperBuffer[];
double LowerBuffer[];
double RSI[];
//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int init()
  {
//---- indicators
   SetIndexStyle(0,DRAW_LINE);
   SetIndexBuffer(0,MovingBuffer);
   SetIndexStyle(1,DRAW_LINE);
   SetIndexBuffer(1,UpperBuffer);
   SetIndexStyle(2,DRAW_LINE);
   SetIndexBuffer(2,LowerBuffer);
   SetIndexStyle(3,DRAW_LINE);
   SetIndexBuffer(3,RSI);
//----
   SetIndexDrawBegin(0,RSIPeriod);
   SetIndexDrawBegin(1,RSIPeriod);
   SetIndexDrawBegin(2,RSIPeriod);
//----
   return(0);
  }
//+------------------------------------------------------------------+
//| Bollinger Bands                                                  |
//+------------------------------------------------------------------+
int start()
  {
   int    i,k,counted_bars=IndicatorCounted();
   double deviation;
   double sum,oldval,newres;
   int pr;
//----
   //if(Bars<=RSIPeriod) return(0);
//---- initial zero
	/*
   if(counted_bars<1)
      for(i=1;i<=RSIPeriod;i++)
        {
         MovingBuffer[Bars-i]=EMPTY_VALUE;
         UpperBuffer[Bars-i]=EMPTY_VALUE;
         LowerBuffer[Bars-i]=EMPTY_VALUE;
        }
   */
//----
   int limit=Bars-counted_bars;
   if(counted_bars>0) limit++;
	
		if(RSIPrice=="o") pr=PRICE_OPEN;
		else if(RSIPrice=="h") pr=PRICE_HIGH;
		else if(RSIPrice=="l") pr=PRICE_LOW;
		else if(RSIPrice=="c") pr=PRICE_CLOSE;
		else pr=PRICE_CLOSE;
		
		
   for(i=0; i<limit; i++)
			RSI[i]=iRSI(NULL,0,RSIPeriod,pr,i);
			
   for(i=0; i<limit; i++)
      MovingBuffer[i]=iMAOnArray(RSI, 0, BandsPeroid1, 0, MODE_SMA, i);

//----
   i=Bars-RSIPeriod+1;
   if(counted_bars>BandsPeroid1-1) i=Bars-counted_bars-1;
   while(i>=0)
     {
      sum=0.0;
      k=i+BandsPeroid1-1;
      oldval=MovingBuffer[i];
      while(k>=i)
        {
         //newres=Close[k]-oldval;
         newres=RSI[k]-oldval;
         sum+=newres*newres;
         k--;
        }
      deviation=BandsDeviations*MathSqrt(sum/BandsPeroid1);
      UpperBuffer[i]=oldval+deviation;
      LowerBuffer[i]=oldval-deviation;
      i--;
     }
//----
   return(0);
  }
//+------------------------------------------------------------------+