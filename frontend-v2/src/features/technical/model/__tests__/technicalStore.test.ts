import { describe, it, expect, beforeEach } from 'vitest';
import { useTechnicalStore } from '../technicalStore';
import {
  DRAWING_CATEGORIES,
  DRAWING_TOOLS_CATALOG,
  getDrawingToolById,
  getDrawingToolsByCategory,
} from '../drawingCatalog';
import type { PredictionData, CandleEdgeReport } from '../types';

describe('useTechnicalStore', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  it('initializes with default values', () => {
    const state = useTechnicalStore.getState();
    expect(state.timeframe).toBe('1D');
    expect(state.activeDrawingTool).toBeNull();
    expect(state.showPredictionCone).toBe(false);
    expect(state.showSMCZones).toBe(false);
    expect(state.activeUserIndicators).toEqual([]);
    expect(state.selectedSymbol).toBe('FOOLAD');
    expect(state.predictionData).toBeNull();
    expect(state.candleEdgeData).toBeNull();
    expect(state.isLoadingForecast).toBe(false);
    expect(state.isLoadingEdge).toBe(false);
  });

  it('updates timeframe correctly', () => {
    useTechnicalStore.getState().setTimeframe('1W');
    expect(useTechnicalStore.getState().timeframe).toBe('1W');
  });

  it('sets and clears active drawing tool', () => {
    useTechnicalStore.getState().setActiveDrawingTool('trendLine');
    expect(useTechnicalStore.getState().activeDrawingTool).toBe('trendLine');

    useTechnicalStore.getState().setActiveDrawingTool('fibonacciRetracement');
    expect(useTechnicalStore.getState().activeDrawingTool).toBe('fibonacciRetracement');

    useTechnicalStore.getState().setActiveDrawingTool(null);
    expect(useTechnicalStore.getState().activeDrawingTool).toBeNull();
  });

  it('toggles prediction cone and SMC zones visibility', () => {
    expect(useTechnicalStore.getState().showPredictionCone).toBe(false);
    useTechnicalStore.getState().togglePredictionCone();
    expect(useTechnicalStore.getState().showPredictionCone).toBe(true);
    useTechnicalStore.getState().togglePredictionCone();
    expect(useTechnicalStore.getState().showPredictionCone).toBe(false);

    expect(useTechnicalStore.getState().showSMCZones).toBe(false);
    useTechnicalStore.getState().toggleSMCZones();
    expect(useTechnicalStore.getState().showSMCZones).toBe(true);
    useTechnicalStore.getState().toggleSMCZones();
    expect(useTechnicalStore.getState().showSMCZones).toBe(false);

    expect(useTechnicalStore.getState().isLogScale).toBe(false);
    useTechnicalStore.getState().toggleLogScale();
    expect(useTechnicalStore.getState().isLogScale).toBe(true);

    expect(useTechnicalStore.getState().isAutoScale).toBe(true);
    useTechnicalStore.getState().toggleAutoScale();
    expect(useTechnicalStore.getState().isAutoScale).toBe(false);
  });

  it('toggles user indicators on and off', () => {
    useTechnicalStore.getState().toggleUserIndicator('BreakoutRetestPro');
    expect(useTechnicalStore.getState().activeUserIndicators).toEqual(['BreakoutRetestPro']);

    useTechnicalStore.getState().toggleUserIndicator('SuperTrendHeikinAshi');
    expect(useTechnicalStore.getState().activeUserIndicators).toEqual([
      'BreakoutRetestPro',
      'SuperTrendHeikinAshi',
    ]);

    useTechnicalStore.getState().toggleUserIndicator('BreakoutRetestPro');
    expect(useTechnicalStore.getState().activeUserIndicators).toEqual(['SuperTrendHeikinAshi']);
  });

  it('sets selected symbol and loading states', () => {
    useTechnicalStore.getState().setSelectedSymbol('SHAPNA');
    expect(useTechnicalStore.getState().selectedSymbol).toBe('SHAPNA');

    useTechnicalStore.getState().setIsLoadingForecast(true);
    expect(useTechnicalStore.getState().isLoadingForecast).toBe(true);

    useTechnicalStore.getState().setIsLoadingEdge(true);
    expect(useTechnicalStore.getState().isLoadingEdge).toBe(true);
  });

  it('stores prediction and candle edge reports', () => {
    const dummyPrediction: PredictionData = {
      symbol: 'FOOLAD',
      generatedAt: 1700000000,
      horizon: 12,
      isLiquid: true,
      forecastSteps: [
        { stepIndex: 1, timestamp: 1700000000 + 86400, p10: 1000, p50: 1050, p90: 1100 },
      ],
    };
    useTechnicalStore.getState().setPredictionData(dummyPrediction);
    expect(useTechnicalStore.getState().predictionData).toEqual(dummyPrediction);

    const dummyEdge: CandleEdgeReport = {
      symbol: 'FOOLAD',
      patternName: 'Hammer',
      winRate1Bar: 62.5,
      winRate3Bar: 68.0,
      winRate5Bar: 71.2,
      profitFactor: 2.15,
      riskRewardRatio: 1.8,
      sampleCount: 45,
      marketRegime: 'TRENDING_BULL',
      activeZones: [],
      recentStructures: [],
    };
    useTechnicalStore.getState().setCandleEdgeData(dummyEdge);
    expect(useTechnicalStore.getState().candleEdgeData).toEqual(dummyEdge);
  });

  it('flushes detected patterns, signals, and predictions when selected symbol changes', () => {
    useTechnicalStore.getState().setSelectedSymbol('FOOLAD');
    useTechnicalStore.getState().setDetectedDoubleTapPatterns([
      {
        id: 'pat-1',
        type: 'DOUBLE_TOP',
        peak1: { index: 5, price: 1000, timestamp: 100 },
        neckline: { index: 8, price: 900, timestamp: 200 },
        peak2: { index: 12, price: 1005, timestamp: 300 },
        target1: 800,
        target2: 700,
        stopLoss: 1050,
        score: 85,
        quality: 85,
        height: 100,
        status: 'active',
      },
    ]);
    useTechnicalStore.getState().setDetectedPullbackSignals([
      { id: 'pb-1', type: 'BULLISH', index: 10, timestamp: 100, price: 950, superTrendPrice: 900, qualityScore: 80 },
    ]);
    useTechnicalStore.getState().setDetectedCHoCHSignals([
      { id: 'ch-1', type: 'CHoCH', isBullish: true, index: 14, timestamp: 100, levelPrice: 980, brokenPrice: 1000 },
    ]);

    expect(useTechnicalStore.getState().detectedDoubleTapPatterns).toHaveLength(1);

    // تغییر نماد به فملی باید داده‌های نماد قبلی را کاملاً پاک کند
    useTechnicalStore.getState().setSelectedSymbol('FMELLI');
    expect(useTechnicalStore.getState().selectedSymbol).toBe('FMELLI');
    expect(useTechnicalStore.getState().detectedDoubleTapPatterns).toEqual([]);
    expect(useTechnicalStore.getState().detectedPullbackSignals).toEqual([]);
    expect(useTechnicalStore.getState().detectedCHoCHSignals).toEqual([]);
  });

  it('enables default telegram indicators via enableDefaultIndicators', () => {
    expect(useTechnicalStore.getState().activeUserIndicators).toEqual([]);
    useTechnicalStore.getState().enableDefaultIndicators();
    expect(useTechnicalStore.getState().activeUserIndicators).toEqual([
      'DoubleTap3D',
      'SuperTrendPullback',
      'AutoTrendlineCHoCH',
      'MultiModeChannel',
    ]);
  });

  it('manages channel modes, RSI variants, drawer width, and tabs', () => {
    useTechnicalStore.getState().setChannelMode('retest_channel');
    expect(useTechnicalStore.getState().channelMode).toBe('retest_channel');

    useTechnicalStore.getState().setRsiVariant('smooth_ma');
    expect(useTechnicalStore.getState().rsiVariant).toBe('smooth_ma');

    // تست محدودسازی عرض سایدبار بین ۳۶۰ و ۶۵۰
    useTechnicalStore.getState().setLeftDrawerWidth(200);
    expect(useTechnicalStore.getState().leftDrawerWidth).toBe(360);

    useTechnicalStore.getState().setLeftDrawerWidth(900);
    expect(useTechnicalStore.getState().leftDrawerWidth).toBe(650);

    useTechnicalStore.getState().setActiveDrawerTab('scanner');
    expect(useTechnicalStore.getState().activeDrawerTab).toBe('scanner');

    // کشو پیش‌فرض بسته است تا چارت قهرمان بماند.
    expect(useTechnicalStore.getState().isLeftDrawerOpen).toBe(false);
    useTechnicalStore.getState().toggleLeftDrawer();
    expect(useTechnicalStore.getState().isLeftDrawerOpen).toBe(true);
  });

  it('resets state back to initial values', () => {
    useTechnicalStore.getState().setTimeframe('1H');
    useTechnicalStore.getState().setActiveDrawingTool('rectZone');
    useTechnicalStore.getState().togglePredictionCone();
    useTechnicalStore.getState().toggleUserIndicator('FiboRSI8');
    useTechnicalStore.getState().setSelectedSymbol('KHORASAN');

    useTechnicalStore.getState().reset();

    const state = useTechnicalStore.getState();
    expect(state.timeframe).toBe('1D');
    expect(state.activeDrawingTool).toBeNull();
    expect(state.showPredictionCone).toBe(false);
    expect(state.showSMCZones).toBe(false);
    expect(state.activeUserIndicators).toEqual([]);
    expect(state.selectedSymbol).toBe('FOOLAD');
  });
});

describe('drawingCatalog', () => {
  it('contains all required categories', () => {
    expect(DRAWING_CATEGORIES.map((c) => c.id)).toEqual(['lines', 'fibonacci', 'shapes']);
  });

  it('contains tools for all three categories', () => {
    const lineTools = getDrawingToolsByCategory('lines');
    const fibTools = getDrawingToolsByCategory('fibonacci');
    const shapeTools = getDrawingToolsByCategory('shapes');

    expect(lineTools.length).toBeGreaterThanOrEqual(5);
    expect(fibTools.length).toBeGreaterThanOrEqual(4);
    expect(shapeTools.length).toBeGreaterThanOrEqual(3);

    expect(DRAWING_TOOLS_CATALOG.length).toBe(
      lineTools.length + fibTools.length + shapeTools.length
    );
  });

  it('retrieves tools by id accurately', () => {
    const trend = getDrawingToolById('trendLine');
    expect(trend).toBeDefined();
    expect(trend?.nameFa).toBe('خط روند');
    expect(trend?.overlayName).toBe('segment');

    const fib = getDrawingToolById('fibonacciRetracement');
    expect(fib?.nameFa).toBe('فیبوناچی اصلاحی');

    const pitchfork = getDrawingToolById('andrewsPitchfork');
    expect(pitchfork?.nameFa).toBe('چنگال اندروز');

    const rect = getDrawingToolById('rectZone');
    expect(rect?.nameFa).toBe('مستطیل عرضه و تقاضا');

    expect(getDrawingToolById(null)).toBeUndefined();
  });
});
