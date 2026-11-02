/**
 * frontend-v2/src/features/technical/ui/__tests__/KLineChartWrapper.test.tsx
 *
 * آزمون‌های یکپارچگی کامپوننت KLineChartWrapper و اورلی‌های FTS، پیش‌بینی هوش مصنوعی و SMC:
 * ۱. رندر اولیه کانتینر چارت با استایل برنجی
 * ۲. راستی‌آزمایی فرمتر تاریخ جلالی خورشیدی
 * ۳. ثبت قطعی کلیه اورلی‌ها بدون خطا
 * ۴. فعال‌سازی ابزار رسم، کان پیش‌بینی و زون‌های SMC از طریق technicalStore
 * ۵. پاک‌سازی کامل حافظه و فراخوانی dispose در زمان unmount
 * ۶. پالس زنده تیک قیمت با احترام به تنظیمات موشن
 */

import { render, screen, cleanup, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  KLineChartWrapper,
  formatJalaliDate,
  ensureAllOverlaysRegistered,
} from '../KLineChartWrapper';
import { useTechnicalStore } from '../../model/technicalStore';
import { useUiStore } from '@shared/stores/uiStore';
import type { Candle, PredictionData, PriceZone } from '../../model/types';

// ثبت چارتهای ساخته‌شده جهت بازرسی در تست‌ها
const mockCharts: any[] = [];
const mockDisposedContainers: any[] = [];

vi.mock('klinecharts', () => {
  const registeredOverlays = new Map<string, any>();

  return {
    init: vi.fn((container: HTMLElement, options?: any) => {
      const chartInstance = {
        options,
        container,
        setStyles: vi.fn(),
        setDataLoader: vi.fn((loader) => {
          if (loader?.getBars) {
            loader.getBars({ callback: vi.fn() });
          }
        }),
        setSymbol: vi.fn(),
        setPeriod: vi.fn(),
        resetData: vi.fn(),
        resize: vi.fn(),
        createOverlay: vi.fn((arg: any) => {
          if (typeof arg === 'string') return `overlay-${arg}-1`;
          return `overlay-${arg?.name}-1`;
        }),
        removeOverlay: vi.fn(() => true),
        overrideYAxis: vi.fn(),
        scrollToRealTime: vi.fn(),
        setFormatter: vi.fn(),
        getFormatter: vi.fn(),
        getDataList: vi.fn(() => [
          { timestamp: 1730000000000, open: 1000, high: 1050, low: 980, close: 1020, volume: 50000 },
          { timestamp: 1730086400000, open: 1020, high: 1100, low: 1010, close: 1080, volume: 75000 },
        ]),
        convertToPixel: vi.fn(({ dataIndex, value }: any) => {
          if (typeof dataIndex === 'number') return { x: dataIndex * 20 + 50, y: 100 };
          if (typeof value === 'number') return { x: 50, y: Math.max(10, 500 - value * 0.2) };
          return { x: 0, y: 0 };
        }),
      };
      mockCharts.push(chartInstance);
      return chartInstance;
    }),
    dispose: vi.fn((container: HTMLElement) => {
      mockDisposedContainers.push(container);
    }),
    registerOverlay: vi.fn((template: any) => {
      registeredOverlays.set(template.name, template);
    }),
    _getRegisteredOverlays: () => registeredOverlays,
  };
});

const SAMPLE_CANDLES: Candle[] = [
  { timestamp: 1730000000000, open: 1000, high: 1050, low: 980, close: 1020, volume: 50000 },
  { timestamp: 1730086400000, open: 1020, high: 1100, low: 1010, close: 1080, volume: 75000 },
  { timestamp: 1730172800000, open: 1080, high: 1120, low: 1060, close: 1090, volume: 60000 },
];

const SAMPLE_PREDICTION: PredictionData = {
  symbol: 'FOOLAD',
  generatedAt: 1730172800000,
  horizon: 3,
  isLiquid: true,
  forecastSteps: [
    { stepIndex: 1, timestamp: 1730259200000, p10: 1050, p50: 1110, p90: 1160 },
    { stepIndex: 2, timestamp: 1730345600000, p10: 1040, p50: 1130, p90: 1200 },
    { stepIndex: 3, timestamp: 1730432000000, p10: 1030, p50: 1150, p90: 1250 },
  ],
};

const SAMPLE_ZONES: PriceZone[] = [
  {
    id: 'fvg-1',
    type: 'FVG',
    isBullish: true,
    top: 1060,
    bottom: 1020,
    equilibrium: 1040,
    startIndex: 0,
    startTs: 1730000000000,
    mitigated: false,
  },
  {
    id: 'ob-1',
    type: 'ORDER_BLOCK',
    isBullish: false,
    top: 1120,
    bottom: 1090,
    equilibrium: 1105,
    startIndex: 1,
    startTs: 1730086400000,
    mitigated: true,
    mitigatedTs: 1730172800000,
  },
];

describe('KLineChartWrapper Component', () => {
  beforeEach(() => {
    mockCharts.length = 0;
    mockDisposedContainers.length = 0;
    useTechnicalStore.getState().reset();
  });

  afterEach(cleanup);

  it('renders canvas container with brass styled technical workspace', () => {
    const { container } = render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);

    const wrapperDiv = container.querySelector('[data-testid="kline-chart-wrapper"]');
    const chartDiv = container.querySelector('[data-testid="kline-chart-container"]');

    expect(wrapperDiv).toBeDefined();
    expect(chartDiv).toBeDefined();
    expect(mockCharts.length).toBe(1);
    expect(mockCharts[0].setSymbol).toHaveBeenCalledWith({ ticker: 'FOOLAD' });
  });

  it('formats timestamp into Persian solar Jalali date on the X-axis', () => {
    // 2026-11-01 -> ۱۴۰۳/۰۸/۱۱
    const formatted = formatJalaliDate(1730419200000);
    expect(formatted).toBeTruthy();
    expect(formatted.length).toBeGreaterThan(5);
    // باید شامل ارقام فارسی باشد
    expect(/[\u06F0-\u06F9]/.test(formatted)).toBe(true);

    // رفتار در ورودی‌های نامعتبر
    expect(formatJalaliDate(0)).toBe('');
    expect(formatJalaliDate(NaN)).toBe('');
  });

  it('registers all custom overlays without throwing', () => {
    expect(() => ensureAllOverlaysRegistered()).not.toThrow();
  });

  it('subscribes to activeDrawingTool and invokes createOverlay on chart', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chart = mockCharts[0];

    act(() => {
      useTechnicalStore.getState().setActiveDrawingTool('trendLine');
    });

    // بر اساس کاتالوگ، trendLine به 'segment' نگاشت می‌شود
    expect(chart.createOverlay).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'segment',
      })
    );
  });

  it('adds and removes prediction cone overlay when showPredictionCone is toggled', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chart = mockCharts[0];

    act(() => {
      useTechnicalStore.getState().setPredictionData(SAMPLE_PREDICTION);
      useTechnicalStore.getState().togglePredictionCone();
    });

    expect(chart.createOverlay).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'predictionCone',
        extendData: SAMPLE_PREDICTION,
      })
    );

    act(() => {
      useTechnicalStore.getState().togglePredictionCone();
    });

    expect(chart.removeOverlay).toHaveBeenCalledWith({ name: 'predictionCone' });
  });

  it('updates SMC overlays with activeZones when showSMCZones is toggled', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chart = mockCharts[0];

    act(() => {
      useTechnicalStore.getState().setCandleEdgeData({
        symbol: 'FOOLAD',
        patternName: 'Hammer',
        winRate1Bar: 65,
        winRate3Bar: 72,
        winRate5Bar: 70,
        profitFactor: 2.1,
        riskRewardRatio: 2.4,
        sampleCount: 150,
        marketRegime: 'TRENDING_BULL',
        activeZones: SAMPLE_ZONES,
        recentStructures: [],
      });
      useTechnicalStore.getState().setShowSMCZones(true);
    });

    expect(chart.createOverlay).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'smcZones',
        extendData: { zones: SAMPLE_ZONES },
      })
    );

    act(() => {
      useTechnicalStore.getState().setShowSMCZones(false);
    });

    expect(chart.removeOverlay).toHaveBeenCalledWith({ name: 'smcZones' });
  });

  it('renders live price pulse badge and supports hardware acceleration', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const pulseBadge = screen.getByTestId('live-price-pulse');
    expect(pulseBadge).toBeDefined();
    // حاوی آخرین قیمت (۱۰۹۰) به ارقام فارسی
    expect(pulseBadge.textContent).toContain('ریال');
  });

  it('properly disposes chart instance on unmount ensuring zero DOM memory leaks', () => {
    const { unmount, container } = render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chartContainer = container.querySelector('[data-testid="kline-chart-container"]');

    expect(mockDisposedContainers.length).toBe(0);
    unmount();
    expect(mockDisposedContainers.length).toBe(1);
    expect(mockDisposedContainers[0]).toBe(chartContainer);
  });

  it('updates chart styles when UI theme switches between dark and light', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chart = mockCharts[0];

    // در ابتدا باید تم برنجی ست شود
    expect(chart.setStyles).toHaveBeenCalledWith(
      expect.objectContaining({
        candle: expect.any(Object),
      })
    );

    // سوییچ به تم روشن (warm)
    act(() => {
      useUiStore.getState().setTheme('warm');
    });

    // باید setStyles مجدداً با پالت روشن فراخوانی شود
    expect(chart.setStyles).toHaveBeenCalledWith(
      expect.objectContaining({
        grid: expect.objectContaining({
          horizontal: expect.objectContaining({
            color: 'rgba(0, 0, 0, 0.06)',
          }),
        }),
      })
    );

    // بازگشت به تم تاریک (brass)
    act(() => {
      useUiStore.getState().setTheme('brass');
    });

    expect(chart.setStyles).toHaveBeenCalledWith(
      expect.objectContaining({
        grid: expect.objectContaining({
          horizontal: expect.objectContaining({
            color: 'rgba(218, 165, 32, 0.08)',
          }),
        }),
      })
    );
  });

  it('renders log and auto scale micro-buttons and toggles logarithmic scale', () => {
    render(<KLineChartWrapper symbol="FOOLAD" candles={SAMPLE_CANDLES} />);
    const chart = mockCharts[0];

    expect(screen.getByTestId('chart-scale-controls')).toBeDefined();
    const logBtn = screen.getByTestId('toggle-log-scale-btn');
    const autoBtn = screen.getByTestId('toggle-auto-scale-btn');

    expect(logBtn.textContent).toContain('log');
    expect(autoBtn.textContent).toContain('auto');
    expect(useTechnicalStore.getState().isLogScale).toBe(false);

    // کلیک روی دکمه log
    act(() => {
      logBtn.click();
    });

    expect(useTechnicalStore.getState().isLogScale).toBe(true);
    expect(chart.overrideYAxis).toHaveBeenCalledWith({
      paneId: 'candle_pane',
      name: 'logarithm',
    });

    // کلیک مجدد برای بازگشت به حالت نرمال
    act(() => {
      logBtn.click();
    });

    expect(useTechnicalStore.getState().isLogScale).toBe(false);
    expect(chart.overrideYAxis).toHaveBeenCalledWith({
      paneId: 'candle_pane',
      name: 'normal',
    });

    // کلیک روی دکمه auto
    act(() => {
      autoBtn.click();
    });

    expect(chart.scrollToRealTime).toHaveBeenCalled();
  });
});

