/**
 * frontend-v2/src/features/technical/model/types.ts
 *
 * تعاریف جامع تایپ‌های ماژول تکنیکال و کوانت:
 * - داده‌های کندلی، زون‌های SMC، و الگوهای پرایس‌اکشن
 * - پیش‌بینی سری زمانی و کان‌های احتمالاتی (Forecast / Prediction)
 * - ابزارهای رسم و کاتالوگ ترسیم (Drawing Tools)
 * - وضعیت و اکشن‌های استور Zustand
 */

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ----------------------------------------------------------------------------
// انواع پیش‌بینی سری زمانی (Prediction / Forecasting)
// ----------------------------------------------------------------------------

export interface ForecastStep {
  stepIndex: number;
  timestamp: number;
  p10: number; // کران پایین احتمالاتی (۱۰٪)
  p50: number; // میانه پیش‌بینی (۵۰٪)
  p90: number; // کران بالای احتمالاتی (۹۰٪)
}

export interface PredictionData {
  symbol: string;
  generatedAt: number;
  horizon: number;
  isLiquid: boolean;
  liquidityNote?: string;
  historicalEnd?: number;
  forecastSteps: ForecastStep[];
  upsideProbability?: number;
  volatilityAmplification?: number;
  modelUsed?: string;
}

// ----------------------------------------------------------------------------
// پرایس‌اکشن، ساختار بازار و SMC (Smart Money Concepts)
// ----------------------------------------------------------------------------

export type ZoneType = 'FVG' | 'ORDER_BLOCK';

export interface PriceZone {
  id: string;
  type: ZoneType;
  isBullish: boolean;
  top: number;
  bottom: number;
  equilibrium: number;
  startIndex: number;
  startTs: number;
  mitigated: boolean;
  mitigatedTs?: number;
}

export type MarketStructureType = 'BOS' | 'CHoCH';

export interface MarketStructurePoint {
  type: MarketStructureType;
  isBullish: boolean;
  price: number;
  timestamp: number;
  index?: number;
}

export type MarketRegime = 'TRENDING_BULL' | 'TRENDING_BEAR' | 'RANGING';

export type CandlePatternType =
  | 'HAMMER'
  | 'INVERTED_HAMMER'
  | 'BULLISH_ENGULFING'
  | 'BEARISH_ENGULFING'
  | 'MORNING_STAR'
  | 'EVENING_STAR'
  | 'DOJI'
  | 'BULLISH_PINBAR'
  | 'BEARISH_PINBAR'
  | 'NEUTRAL';

export interface DetectedPattern {
  type: CandlePatternType;
  nameFa: string;
  nameEn: string;
  isBullish: boolean;
  index: number;
  timestamp: number;
}

export interface CandleEdgeReport {
  symbol: string;
  patternName: string;
  winRate1Bar: number;
  winRate3Bar: number;
  winRate5Bar: number;
  profitFactor: number;
  riskRewardRatio: number;
  sampleCount: number;
  marketRegime: MarketRegime;
  activeZones: PriceZone[];
  recentStructures: MarketStructurePoint[];
}

// ----------------------------------------------------------------------------
// کاتالوگ و انواع ابزارهای رسم (Drawing Tools)
// ----------------------------------------------------------------------------

export type DrawingToolType =
  | 'trendLine'
  | 'horizontalLine'
  | 'horizontalRay'
  | 'rayLine'
  | 'verticalLine'
  | 'parallelChannel'
  | 'regressionChannel'
  | 'fibonacciRetracement'
  | 'fibonacciExtension'
  | 'fibonacciFan'
  | 'andrewsPitchfork'
  | 'gannBox'
  | 'rectZone'
  | 'priceRange'
  | 'riskReward';

export type DrawingCategory = 'lines' | 'fibonacci' | 'shapes';

export interface DrawingToolItem {
  id: DrawingToolType;
  nameFa: string;
  nameEn: string;
  category: DrawingCategory;
  icon: string;
  overlayName: string;
  descriptionFa: string;
}

// ----------------------------------------------------------------------------
// حالت‌های کانال چندحالته و انواع خانواده RSI
// ----------------------------------------------------------------------------

export type ChannelMode = 'regression' | 'retest_channel' | 'donchian';

export type RsiVariant = 'standard' | 'fibo' | 'bb' | 'smooth_ma';

export type DrawerTab = 'top50' | 'indicators' | 'scanner' | 'edge';

export type FormationConfidence = 'none' | 'low' | 'medium' | 'high';

export interface FormationEstimate {
  probability: number | null;
  successes: number;
  failures: number;
  resolved: number;
  confidence: FormationConfidence;
  horizon: number;
  method: 'same-symbol' | 'market-cohort';
  qualityBucket?: number;
  intervalLow?: number;
  intervalHigh?: number;
}

export interface DoubleTapPattern {
  id: string;
  type: 'DOUBLE_TOP' | 'DOUBLE_BOTTOM';
  origin?: { index: number; price: number; timestamp: number };
  peak1: { index: number; price: number; timestamp: number };
  neckline: { index: number; price: number; timestamp: number };
  peak2: { index: number; price: number; timestamp: number };
  retest?: { index: number; price: number; timestamp: number };
  breakoutIndex?: number;
  breakoutTs?: number;
  target1: number;
  target2: number;
  stopLoss: number;
  /** شباهت هندسی قدیمی؛ برای سازگاری نمایش حفظ شده است. */
  score: number;
  /** کیفیت ساختار ۰–۱۰۰؛ احتمال نیست. */
  quality: number;
  height: number;
  status: 'forming' | 'active' | 'tp1_hit' | 'tp2_hit' | 'invalidated';
  trendContext?: boolean;
  profile?: 'source' | 'precision';
  formation?: FormationEstimate;
}

export interface PullbackSignal {
  id: string;
  type: 'BULLISH' | 'BEARISH';
  index: number;
  timestamp: number;
  price: number;
  superTrendPrice: number;
  qualityScore: number;
}

export interface CHoCHSignal {
  id: string;
  type: 'CHoCH' | 'BOS';
  isBullish: boolean;
  index: number;
  timestamp: number;
  levelPrice: number;
  brokenPrice: number;
}

// ----------------------------------------------------------------------------
// وضعیت استور تکنیکال (Technical Store State)
export interface CorporateEventItem {
  date: string;
  type: string;
  kind?: 'M' | 'D' | 'E';
  from?: any;
  to?: any;
  source?: string | null;
  titleFa?: string;
  descriptionFa?: string;
}

export interface TechnicalState {
  timeframe: string;
  activeDrawingTool: DrawingToolType | null;
  showPredictionCone: boolean;
  showSMCZones: boolean;
  activeUserIndicators: string[];
  selectedSymbol: string;
  predictionData: PredictionData | null;
  candleEdgeData: CandleEdgeReport | null;
  isLoadingForecast: boolean;
  isLoadingEdge: boolean;
  forecastHorizon: number;
  forecastModel: 'mini' | 'small' | 'base';
  adjustmentMode: number;
  showCorporateEvents: boolean;
  isLogScale: boolean;
  isAutoScale: boolean;
  isMagnetMode: boolean;
  isLockedAllDrawings: boolean;
  isHideAllDrawings: boolean;
  corporateEvents: CorporateEventItem[];

  // تنظیمات جدید کانال چندحالته، خانواده RSI و سایدبار عریض
  channelMode: ChannelMode;
  rsiVariant: RsiVariant;
  doubleTapProfile: 'precision' | 'source';
  /**
   * overrideهای پنل تنظیماتِ هر اندیکاتور. خالی یعنی از مقادیرِ رجیستری
   * (DOUBLE_TAP_DEFAULTS و هم‌خانواده‌ها) استفاده شود.
   */
  indicatorParams: Record<string, Record<string, number>>;
  /** سقفِ شکل‌های رسم‌شده به‌ازای هر اندیکاتور؛ الگوهای قدیمی‌تر حذف می‌شوند */
  maxDrawnPatterns: number;
  isLeftDrawerOpen: boolean;
  leftDrawerWidth: number;
  activeDrawerTab: DrawerTab;
  detectedDoubleTapPatterns: DoubleTapPattern[];
  detectedPullbackSignals: PullbackSignal[];
  detectedCHoCHSignals: CHoCHSignal[];

  setTimeframe: (tf: string) => void;
  setActiveDrawingTool: (tool: DrawingToolType | null) => void;
  togglePredictionCone: () => void;
  toggleSMCZones: () => void;
  setShowSMCZones: (show: boolean) => void;
  toggleLogScale: () => void;
  toggleAutoScale: () => void;
  toggleUserIndicator: (indicatorId: string) => void;
  setSelectedSymbol: (sym: string) => void;
  setPredictionData: (data: PredictionData | null) => void;
  setCandleEdgeData: (data: CandleEdgeReport | null) => void;
  setIsLoadingForecast: (loading: boolean) => void;
  setIsLoadingEdge: (loading: boolean) => void;
  setForecastHorizon: (horizon: number) => void;
  setForecastModel: (model: 'mini' | 'small' | 'base') => void;
  setAdjustmentMode: (mode: number) => void;
  toggleCorporateEvents: () => void;
  toggleMagnetMode: () => void;
  toggleLockAllDrawings: () => void;
  toggleHideAllDrawings: () => void;
  setCorporateEvents: (events: CorporateEventItem[]) => void;

  setChannelMode: (mode: ChannelMode) => void;
  setRsiVariant: (variant: RsiVariant) => void;
  setDoubleTapProfile: (profile: 'precision' | 'source') => void;
  setIndicatorParam: (indicatorId: string, key: string, value: number) => void;
  resetIndicatorParams: (indicatorId: string) => void;
  setMaxDrawnPatterns: (count: number) => void;
  setIsLeftDrawerOpen: (open: boolean) => void;
  toggleLeftDrawer: () => void;
  setLeftDrawerWidth: (width: number) => void;
  setActiveDrawerTab: (tab: DrawerTab) => void;
  setDetectedDoubleTapPatterns: (patterns: DoubleTapPattern[]) => void;
  setDetectedPullbackSignals: (signals: PullbackSignal[]) => void;
  setDetectedCHoCHSignals: (signals: CHoCHSignal[]) => void;
  enableDefaultIndicators: () => void;

  reset: () => void;
}
