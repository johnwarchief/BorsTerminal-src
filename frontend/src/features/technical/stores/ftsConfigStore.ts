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
  timeframe: Timeframe;
  priceScale: PriceScale;
  showGrid: boolean;
  showCrosshair: boolean;
  showRsi: boolean;
  showVolMa: boolean;
  toggle: (k: FtsLayerKey) => void;
  setChartType: (t: ChartType) => void;
  setChartEngine: (e: ChartEngine) => void;
  setTimeframe: (t: Timeframe) => void;
  setPriceScale: (p: PriceScale) => void;
  toggleDisplay: (k: DisplayKey) => void;
  toggleIndicator: (k: IndicatorKey) => void;
};

const STORAGE_KEY = '***';

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
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...PERSIST_DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    return { ...PERSIST_DEFAULTS, ...parsed };
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
