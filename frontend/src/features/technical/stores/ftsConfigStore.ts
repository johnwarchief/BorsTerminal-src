// features/technical/stores/ftsConfigStore.ts -- کلیدهای نمایشی و ابزارهای چارت FTS
// لایه‌های FTS (نمایش/پنهان) + نوع چارت، تایم‌فریم، مقیاس قیمت و اندیکاتورهای تریدینگ‌ویویی.
// مقادیر candle.type و yAxis.type دقیقاً از نگاشت klinecharts v10 گرفته شده‌اند
// (docs/CHART-PARITY-REFERENCE.md بخش ۷).
import { create } from 'zustand';

export type FtsLayerKey =
  | 'showMAs'
  | 'showJetTrigger'
  | 'showChoch'
  | 'enforceRiskGates'
  | 'showFtsCard'
  | 'showFibZones'
  | 'showSetupMarkers';

/** نوع نمایش چارت — مقادیر معتبر candle.type در klinecharts v10 + انواع ترنسفورم داخلی */
export type ChartType =
  | 'candle_solid'
  | 'candle_stroke'
  | 'ohlc'
  | 'line'
  | 'area'
  | 'heikin_ashi'
  | 'renko'
  | 'kagi'
  | 'pnf';
/** گزینه‌های ظاهری چارت (همه به استایل‌های واقعی klinecharts v10 نگاشت می‌شوند) */
export type ChartView = {
  yAxisReverse: boolean;
  yAxisInside: boolean;
  priceScalePos: 'right' | 'left';
  /** قفل تغییر مقیاس با درگ محور قیمت (yAxis.scrollZoomEnabled) */
  axisDragLock: boolean;
  /** حاشیهٔ برچسب‌های محور (tickText.marginStart/End) */
  axisTickMargin: number;
  background: 'theme' | 'classic' | 'dark' | 'light' | 'custom';
  customBgColor: string;
  candleUp: string | null;
  candleDown: string | null;
  borderUp: string | null;
  borderDown: string | null;
  wickUp: string | null;
  wickDown: string | null;
  showBorders: boolean;
  showWicks: boolean;
  /** سایهٔ کندل خاکستری (وگرنه هم‌رنگ بدنه) */
  wickGray: boolean;
  timezone: string;
  showLegend: boolean;
  showXAxis: boolean;
  showYAxis: boolean;
  /** چیدمان چارت: تک/۲/۴ پنل با همگام‌سازی */
  splitLayout: 1 | 2 | 4;
  statusShowOhlc: boolean;
  statusShowSymbol: boolean;
  statusShowIndicators: boolean;
  statusShowVolume: boolean;
  gridColor: string;
  gridStyle: 'solid' | 'dashed' | 'dotted' | 'none';
  showGridHorz: boolean;
  showGridVert: boolean;
  crosshairStyle: 'dashed' | 'dotted' | 'solid';
  watermarkOpacity: number;
  showWatermark: boolean;
  showCorporateActions: boolean;
  showDividends: boolean;
  showSplits: boolean;
  fibLogarithmic: boolean;
};

export const VIEW_DEFAULTS: ChartView = {
  yAxisReverse: false,
  yAxisInside: false,
  priceScalePos: 'right',
  axisDragLock: false,
  axisTickMargin: 3,
  background: 'dark',
  customBgColor: '#131722',
  candleUp: '#089981',
  candleDown: '#f23645',
  borderUp: '#089981',
  borderDown: '#f23645',
  wickUp: '#089981',
  wickDown: '#f23645',
  showBorders: true,
  showWicks: true,
  wickGray: false,
  timezone: 'Asia/Tehran',
  showLegend: true,
  showXAxis: true,
  showYAxis: true,
  splitLayout: 1,
  statusShowOhlc: true,
  statusShowSymbol: true,
  statusShowIndicators: true,
  statusShowVolume: true,
  gridColor: '#1e222d',
  gridStyle: 'solid',
  showGridHorz: true,
  showGridVert: true,
  crosshairStyle: 'dashed',
  watermarkOpacity: 5,
  showWatermark: true,
  showCorporateActions: true,
  showDividends: true,
  showSplits: true,
  fibLogarithmic: false,
};

/** موتور رندر چارت — پیش‌فرض klinecharts تا مهاجرت کامل شود */
export type ChartEngine = 'klinecharts' | 'lightweight';
/** تایم‌فریم — روزانه/هفتگی/ماهانه (بازنمونه‌گیری سمت کلاینت از کندل روزانه) */
export type Timeframe = 'day' | 'week' | 'month';
/** مقیاس محور قیمت — مقادیر معتبر yAxis.type در klinecharts v10 */
export type PriceScale = 'normal' | 'logarithm' | 'percentage';
export type IndicatorKey = 'rsi' | 'volMa';
export type DisplayKey = 'grid' | 'crosshair';

type FtsFlags = Record<FtsLayerKey, boolean>;

type FtsConfigState = FtsFlags & {
  chartType: ChartType;
  chartEngine: ChartEngine;
  view: ChartView;
  timeframe: Timeframe;
  priceScale: PriceScale;
  showGrid: boolean;
  showCrosshair: boolean;
  showRsi: boolean;
  showVolMa: boolean;
  toggle: (k: FtsLayerKey) => void;
  setChartType: (t: ChartType) => void;
  setChartEngine: (e: ChartEngine) => void;
  setView: (patch: Partial<ChartView>) => void;
  setTimeframe: (t: Timeframe) => void;
  setPriceScale: (p: PriceScale) => void;
  toggleDisplay: (k: DisplayKey) => void;
  toggleIndicator: (k: IndicatorKey) => void;
};

const STORAGE_KEY = 'fts.chart.settings.v1';
const LEGACY_STORAGE_KEY = '***';

export const DEFAULTS: FtsFlags = {
  showMAs: true,
  showJetTrigger: true,
  showChoch: true,
  enforceRiskGates: true,
  showFtsCard: true,
  showFibZones: true,
  showSetupMarkers: true,
};

type PersistedState = FtsFlags & {
  chartType: ChartType;
  chartEngine: ChartEngine;
  view: ChartView;
  timeframe: Timeframe;
  priceScale: PriceScale;
  showGrid: boolean;
  showCrosshair: boolean;
  showRsi: boolean;
  showVolMa: boolean;
};

const PERSIST_DEFAULTS: PersistedState = {
  ...DEFAULTS,
  chartType: 'candle_solid',
  chartEngine: 'klinecharts',
  view: VIEW_DEFAULTS,
  timeframe: 'day',
  priceScale: 'normal',
  showGrid: true,
  showCrosshair: true,
  showRsi: false,
  showVolMa: false,
};

function pick(s: PersistedState): PersistedState {
  return {
    showMAs: s.showMAs,
    showJetTrigger: s.showJetTrigger,
    showChoch: s.showChoch,
    enforceRiskGates: s.enforceRiskGates,
    showFtsCard: s.showFtsCard,
    showFibZones: s.showFibZones,
    showSetupMarkers: s.showSetupMarkers,
    chartType: s.chartType,
    chartEngine: s.chartEngine,
    view: s.view,
    timeframe: s.timeframe,
    priceScale: s.priceScale,
    showGrid: s.showGrid,
    showCrosshair: s.showCrosshair,
    showRsi: s.showRsi,
    showVolMa: s.showVolMa,
  };
}

function initial(): PersistedState {
  try {
    const raw = (typeof localStorage !== 'undefined' ? (localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY)) : null);
    if (!raw) return { ...PERSIST_DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<PersistedState>;

    // اعتبارسنجی مقیاس قیمت (سازگاری عقب‌رو با 'log' یا مقادیر ناشناخته)
    const rawScale = parsed.priceScale as string | undefined;
    const priceScale: PriceScale =
      rawScale === 'log' ? 'logarithm'
      : (rawScale === 'logarithm' || rawScale === 'percentage' || rawScale === 'normal')
      ? rawScale
      : PERSIST_DEFAULTS.priceScale;

    // پالایش و ایمن‌سازی مقادیر نمایشی
    const parsedView = parsed.view ?? {};
    const safeView: ChartView = {
      ...VIEW_DEFAULTS,
      ...parsedView,
      candleUp: (parsedView.candleUp && parsedView.candleUp !== 'transparent') ? parsedView.candleUp : VIEW_DEFAULTS.candleUp,
      candleDown: (parsedView.candleDown && parsedView.candleDown !== 'transparent') ? parsedView.candleDown : VIEW_DEFAULTS.candleDown,
      borderUp: (parsedView.borderUp && parsedView.borderUp !== 'transparent') ? parsedView.borderUp : (parsedView.candleUp || VIEW_DEFAULTS.borderUp),
      borderDown: (parsedView.borderDown && parsedView.borderDown !== 'transparent') ? parsedView.borderDown : (parsedView.candleDown || VIEW_DEFAULTS.borderDown),
      wickUp: (parsedView.wickUp && parsedView.wickUp !== 'transparent') ? parsedView.wickUp : (parsedView.candleUp || VIEW_DEFAULTS.wickUp),
      wickDown: (parsedView.wickDown && parsedView.wickDown !== 'transparent') ? parsedView.wickDown : (parsedView.candleDown || VIEW_DEFAULTS.wickDown),
      gridColor: parsedView.gridColor || VIEW_DEFAULTS.gridColor,
    };

    return {
      ...PERSIST_DEFAULTS,
      ...parsed,
      priceScale,
      view: safeView,
    };
  } catch {
    return { ...PERSIST_DEFAULTS };
  }
}

function persist(next: PersistedState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // نادیده بگیر
  }
}

export const useFtsConfigStore = create<FtsConfigState>((set) => ({
  ...initial(),
  toggle: (k) =>
    set((s) => {
      const next = { ...pick(s), [k]: !s[k] };
      persist(next);
      return { ...s, ...next };
    }),
  setChartType: (t) =>
    set((s) => {
      const next = { ...pick(s), chartType: t };
      persist(next);
      return { ...s, ...next };
    }),
  setChartEngine: (e) =>
    set((s) => {
      const next = { ...pick(s), chartEngine: e };
      persist(next);
      return { ...s, ...next };
    }),
  setView: (patch) =>
    set((s) => {
      const next = { ...pick(s), view: { ...s.view, ...patch } };
      persist(next);
      return { ...s, ...next };
    }),
  setTimeframe: (t) =>
    set((s) => {
      const next = { ...pick(s), timeframe: t };
      persist(next);
      return { ...s, ...next };
    }),
  setPriceScale: (p) =>
    set((s) => {
      const next = { ...pick(s), priceScale: p };
      persist(next);
      return { ...s, ...next };
    }),
  toggleDisplay: (k) =>
    set((s) => {
      const next = k === 'grid' ? { ...pick(s), showGrid: !s.showGrid } : { ...pick(s), showCrosshair: !s.showCrosshair };
      persist(next);
      return { ...s, ...next };
    }),
  toggleIndicator: (k) =>
    set((s) => {
      const next = k === 'rsi' ? { ...pick(s), showRsi: !s.showRsi } : { ...pick(s), showVolMa: !s.showVolMa };
      persist(next);
      return { ...s, ...next };
    }),
}));
