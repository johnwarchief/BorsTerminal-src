/**
 * frontend-v2/src/features/technical/model/technicalStore.ts
 *
 * استور مرکزی وضعیت فضای کاری تکنیکال (Technical Workspace State) بر پایه Zustand:
 * مدیریت تایم‌فریم، ابزار رسم فعال، اورلی‌های SMC، کان پیش‌بینی، رویدادهای شرکتی و ارگونومی ترسیم.
 */

import { create } from 'zustand';
import type {
  DrawingToolType,
  PredictionData,
  CandleEdgeReport,
  CorporateEventItem,
  TechnicalState,
  ChannelMode,
  RsiVariant,
  DrawerTab,
  DoubleTapPattern,
  PullbackSignal,
  CHoCHSignal,
} from './types';

export const DEFAULT_ACTIVE_INDICATORS = [
  'DoubleTap3D',
  'SuperTrendPullback',
  'AutoTrendlineCHoCH',
  'MultiModeChannel',
] as const;

const INITIAL_STATE = {
  timeframe: '1D',
  activeDrawingTool: null as DrawingToolType | null,
  showPredictionCone: false,
  showSMCZones: false,
  activeUserIndicators: [] as string[],
  selectedSymbol: 'FOOLAD',
  predictionData: null as PredictionData | null,
  candleEdgeData: null as CandleEdgeReport | null,
  isLoadingForecast: false,
  isLoadingEdge: false,
  forecastHorizon: 12,
  forecastModel: 'small' as 'mini' | 'small' | 'base',
  adjustmentMode: 3, // ۳: عملکردی (سود نقدی + افزایش سرمایه)
  showCorporateEvents: true,
  isLogScale: false,
  isAutoScale: true,
  isMagnetMode: false,
  isLockedAllDrawings: false,
  isHideAllDrawings: false,
  corporateEvents: [] as CorporateEventItem[],

  channelMode: 'regression' as ChannelMode,
  rsiVariant: 'smooth_ma' as RsiVariant,
  doubleTapProfile: 'precision' as 'precision' | 'source',
  indicatorParams: {} as Record<string, Record<string, number>>,
  maxDrawnPatterns: 1,
  isLeftDrawerOpen: false,
  leftDrawerWidth: 460,
  activeDrawerTab: 'top50' as DrawerTab,
  detectedDoubleTapPatterns: [] as DoubleTapPattern[],
  detectedPullbackSignals: [] as PullbackSignal[],
  detectedCHoCHSignals: [] as CHoCHSignal[],
};

export const useTechnicalStore = create<TechnicalState>((set) => ({
  ...INITIAL_STATE,

  setTimeframe: (tf: string) => set({ timeframe: tf }),

  setActiveDrawingTool: (tool: DrawingToolType | null) => set({ activeDrawingTool: tool }),

  togglePredictionCone: () =>
    set((state) => ({ showPredictionCone: !state.showPredictionCone })),

  toggleSMCZones: () =>
    set((state) => ({ showSMCZones: !state.showSMCZones })),

  setShowSMCZones: (show: boolean) => set({ showSMCZones: show }),

  toggleLogScale: () =>
    set((state) => ({ isLogScale: !state.isLogScale })),

  toggleAutoScale: () =>
    set((state) => ({ isAutoScale: !state.isAutoScale })),

  toggleUserIndicator: (indicatorId: string) =>
    set((state) => {
      const exists = state.activeUserIndicators.includes(indicatorId);
      return {
        activeUserIndicators: exists
          ? state.activeUserIndicators.filter((id) => id !== indicatorId)
          : [...state.activeUserIndicators, indicatorId],
      };
    }),

  setSelectedSymbol: (sym: string) =>
    set((state) => {
      if (state.selectedSymbol === sym) return state;
      return {
        selectedSymbol: sym,
        detectedDoubleTapPatterns: [],
        detectedPullbackSignals: [],
        detectedCHoCHSignals: [],
        predictionData: null,
        candleEdgeData: null,
      };
    }),

  setPredictionData: (data: PredictionData | null) => set({ predictionData: data }),

  setCandleEdgeData: (data: CandleEdgeReport | null) => set({ candleEdgeData: data }),

  setIsLoadingForecast: (loading: boolean) => set({ isLoadingForecast: loading }),

  setIsLoadingEdge: (loading: boolean) => set({ isLoadingEdge: loading }),

  setForecastHorizon: (horizon: number) => set({ forecastHorizon: horizon }),

  setForecastModel: (model: 'mini' | 'small' | 'base') => set({ forecastModel: model }),

  setAdjustmentMode: (mode: number) => set({ adjustmentMode: mode }),

  toggleCorporateEvents: () =>
    set((state) => ({ showCorporateEvents: !state.showCorporateEvents })),

  toggleMagnetMode: () =>
    set((state) => ({ isMagnetMode: !state.isMagnetMode })),

  toggleLockAllDrawings: () =>
    set((state) => ({ isLockedAllDrawings: !state.isLockedAllDrawings })),

  toggleHideAllDrawings: () =>
    set((state) => ({ isHideAllDrawings: !state.isHideAllDrawings })),

  setCorporateEvents: (events: CorporateEventItem[]) => set({ corporateEvents: events }),

  setChannelMode: (mode: ChannelMode) => set({ channelMode: mode }),

  setRsiVariant: (variant: RsiVariant) => set({ rsiVariant: variant }),

  setDoubleTapProfile: (profile) => set({ doubleTapProfile: profile }),

  setIndicatorParam: (indicatorId, key, value) =>
    set((state) => ({
      indicatorParams: {
        ...state.indicatorParams,
        [indicatorId]: { ...(state.indicatorParams[indicatorId] ?? {}), [key]: value },
      },
    })),

  resetIndicatorParams: (indicatorId) =>
    set((state) => {
      const next = { ...state.indicatorParams };
      delete next[indicatorId];
      return { indicatorParams: next };
    }),

  setMaxDrawnPatterns: (count) => set({ maxDrawnPatterns: Math.max(1, Math.min(20, Math.round(count))) }),

  setIsLeftDrawerOpen: (open: boolean) => set({ isLeftDrawerOpen: open }),

  toggleLeftDrawer: () => set((state) => ({ isLeftDrawerOpen: !state.isLeftDrawerOpen })),

  setLeftDrawerWidth: (width: number) =>
    set({ leftDrawerWidth: Math.min(Math.max(width, 360), 650) }),

  setActiveDrawerTab: (tab: DrawerTab) => set({ activeDrawerTab: tab }),

  setDetectedDoubleTapPatterns: (patterns: DoubleTapPattern[]) =>
    set({ detectedDoubleTapPatterns: patterns }),

  setDetectedPullbackSignals: (signals: PullbackSignal[]) =>
    set({ detectedPullbackSignals: signals }),

  setDetectedCHoCHSignals: (signals: CHoCHSignal[]) =>
    set({ detectedCHoCHSignals: signals }),

  enableDefaultIndicators: () =>
    set({ activeUserIndicators: [...DEFAULT_ACTIVE_INDICATORS] }),

  reset: () => set(INITIAL_STATE),
}));
