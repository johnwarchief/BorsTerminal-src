// features/technical/stores/ftsConfigStore.ts -- کلیدهای نمایشی و ابزارهای چارت FTS
// لایه‌های FTS (نمایش/پنهان) + نوع چارت، تایم‌فریم و اندیکاتورهای تریدینگ‌ویویی.
import { create } from 'zustand';

export type FtsLayerKey =
  | 'showMAs'
  | 'showJetTrigger'
  | 'showChoch'
  | 'enforceRiskGates'
  | 'showFtsCard'
  | 'showFibZones'
  | 'showSetupMarkers';

/** نوع نمایش چارت — مقادیر معتبر candle.type در klinecharts v10 */
export type ChartType = 'candle' | 'ohlc' | 'line' | 'area';
/** تایم‌فریم — روزانه/هفتگی/ماهانه (بازنمونه‌گیری سمت کلاینت از کندل روزانه) */
export type Timeframe = 'day' | 'week' | 'month';
export type IndicatorKey = 'rsi' | 'volMa';

type FtsFlags = Record<FtsLayerKey, boolean>;

type FtsConfigState = FtsFlags & {
  chartType: ChartType;
  timeframe: Timeframe;
  showRsi: boolean;
  showVolMa: boolean;
  toggle: (k: FtsLayerKey) => void;
  setChartType: (t: ChartType) => void;
  setTimeframe: (t: Timeframe) => void;
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

type PersistedState = FtsFlags & { chartType: ChartType; timeframe: Timeframe; showRsi: boolean; showVolMa: boolean };

const PERSIST_DEFAULTS: PersistedState = {
  ...DEFAULTS,
  chartType: 'candle',
  timeframe: 'day',
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
    timeframe: s.timeframe,
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
  setTimeframe: (t) =>
    set((s) => {
      const next = { ...pick(s), timeframe: t };
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

function persist(next: PersistedState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // نادیده بگیر
  }
}
