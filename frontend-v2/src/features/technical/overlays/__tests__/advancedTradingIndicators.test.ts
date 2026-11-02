/**
 * frontend-v2/src/features/technical/overlays/__tests__/advancedTradingIndicators.test.ts
 *
 * آزمون‌های محاسباتی و ترسیمی ۵ اندیکاتور پیشرفته تلگرام:
 * ۱. DoubleTap3D: شناسایی M و W، خط‌گردن نئونی، تارگت‌های فیبوناچی
 * ۲. SuperTrendPullback: زون ارزش دینامیک و سیگنال‌های پرایس‌اکشن پولبک
 * ۳. AutoTrendlineCHoCH: خطوط روند خودکار و سطوح تغییر ساختار بازار
 * ۴. MultiModeChannel: پشتیبانی کامل از سه مد رگرسیون، شکست/پولبک، و دانچیان
 * ۵. MultiVariantRSI: دراپ‌داون انواع RSI
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  ADVANCED_INDICATORS_REGISTRY,
  registerAllAdvancedIndicators,
  registerDoubleTap3DOverlay,
  registerSuperTrendPullbackOverlay,
  registerAutoTrendlineCHoCHOverlay,
  registerMultiModeChannelOverlay,
  registerMultiVariantRSIOverlay,
} from '../advancedTradingIndicators';
import { useTechnicalStore } from '../../model/technicalStore';

const registeredTemplates = new Map<string, any>();

vi.mock('klinecharts', () => ({
  registerOverlay: vi.fn((template: any) => {
    registeredTemplates.set(template.name, template);
  }),
}));

function createMockParams(overlayName: string, extendData: any = null, coordinates: any[] = []) {
  // ساخت ۲۵ کندل تست حاوی الگوی سقف دوقلو
  const testCandles = [
    { timestamp: 1730000000000, open: 1000, high: 1020, low: 990, close: 1010, volume: 50000 },
    { timestamp: 1730086400000, open: 1010, high: 1060, low: 1005, close: 1050, volume: 60000 },
    { timestamp: 1730172800000, open: 1050, high: 1120, low: 1040, close: 1110, volume: 80000 },
    { timestamp: 1730259200000, open: 1110, high: 1200, low: 1100, close: 1190, volume: 120000 }, // Peak 1
    { timestamp: 1730345600000, open: 1190, high: 1195, low: 1140, close: 1150, volume: 70000 },
    { timestamp: 1730432000000, open: 1150, high: 1160, low: 1080, close: 1090, volume: 90000 },
    { timestamp: 1730518400000, open: 1090, high: 1100, low: 1040, close: 1050, volume: 95000 }, // Neckline Low
    { timestamp: 1730604800000, open: 1050, high: 1110, low: 1045, close: 1100, volume: 65000 },
    { timestamp: 1730691200000, open: 1100, high: 1160, low: 1090, close: 1150, volume: 75000 },
    { timestamp: 1730777600000, open: 1150, high: 1205, low: 1140, close: 1195, volume: 110000 }, // Peak 2
    { timestamp: 1730864000000, open: 1195, high: 1198, low: 1130, close: 1140, volume: 85000 },
    { timestamp: 1730950400000, open: 1140, high: 1145, low: 1070, close: 1080, volume: 95000 },
    { timestamp: 1731036800000, open: 1080, high: 1085, low: 1020, close: 1030, volume: 140000 }, // Breakout below Neckline
    { timestamp: 1731123200000, open: 1030, high: 1040, low: 980, close: 990, volume: 160000 },
    { timestamp: 1731209600000, open: 990, high: 1010, low: 940, close: 950, volume: 180000 },
    { timestamp: 1731296000000, open: 950, high: 970, low: 920, close: 930, volume: 150000 },
    { timestamp: 1731382400000, open: 930, high: 960, low: 910, close: 940, volume: 130000 },
    { timestamp: 1731468800000, open: 940, high: 980, low: 935, close: 970, volume: 125000 },
    { timestamp: 1731555200000, open: 970, high: 1010, low: 960, close: 1000, volume: 110000 },
    { timestamp: 1731641600000, open: 1000, high: 1030, low: 990, close: 1020, volume: 95000 },
    { timestamp: 1731728000000, open: 1020, high: 1050, low: 1010, close: 1040, volume: 90000 },
    { timestamp: 1731814400000, open: 1040, high: 1070, low: 1030, close: 1060, volume: 85000 },
  ];

  return {
    chart: {
      getDataList: () => testCandles,
      convertToPixel: vi.fn(({ dataIndex, value }: any) => {
        if (typeof dataIndex === 'number') return { x: dataIndex * 35 + 40, y: 150 };
        if (typeof value === 'number') return { x: 40, y: Math.max(10, 600 - value * 0.3) };
        return { x: 0, y: 0 };
      }),
    },
    xAxis: {
      convertToPixel: (idx: number) => idx * 35 + 40,
      convertTimestampToPixel: (ts: number) => (ts - 1730000000000) / 5000000 + 40,
    },
    yAxis: {
      convertToPixel: (price: number) => Math.max(10, 600 - price * 0.3),
    },
    bounding: {
      width: 900,
      height: 600,
    },
    overlay: {
      name: overlayName,
      extendData,
    },
    coordinates,
  };
}

describe('Advanced Trading Indicators Registry & Overlays', () => {
  beforeEach(() => {
    registeredTemplates.clear();
    useTechnicalStore.getState().reset();
  });

  it('exports registry with all 5 advanced indicators', () => {
    expect(ADVANCED_INDICATORS_REGISTRY).toHaveLength(5);
    const ids = ADVANCED_INDICATORS_REGISTRY.map((i) => i.id);
    expect(ids).toContain('DoubleTap3D');
    expect(ids).toContain('SuperTrendPullback');
    expect(ids).toContain('AutoTrendlineCHoCH');
    expect(ids).toContain('MultiModeChannel');
    expect(ids).toContain('MultiVariantRSI');
  });

  it('contains valid Persian descriptions and metadata', () => {
    for (const item of ADVANCED_INDICATORS_REGISTRY) {
      expect(item.id.length).toBeGreaterThan(0);
      expect(item.nameFa.length).toBeGreaterThan(0);
      expect(item.descriptionFa.length).toBeGreaterThan(0);
      expect(typeof item.registerFn).toBe('function');
    }
  });

  it('registers all advanced overlays without throwing', () => {
    expect(() => registerDoubleTap3DOverlay()).not.toThrow();
    expect(() => registerSuperTrendPullbackOverlay()).not.toThrow();
    expect(() => registerAutoTrendlineCHoCHOverlay()).not.toThrow();
    expect(() => registerMultiModeChannelOverlay()).not.toThrow();
    expect(() => registerMultiVariantRSIOverlay()).not.toThrow();
    expect(() => registerAllAdvancedIndicators()).not.toThrow();
  });

  it('DoubleTap3D creates 3D extruded lines, glowing neckline and targets', () => {
    registerDoubleTap3DOverlay();
    const template = registeredTemplates.get('DoubleTap3D');
    expect(template).toBeDefined();

    const params = createMockParams('DoubleTap3D');
    const figures = template.createPointFigures(params);

    expect(figures.length).toBeGreaterThan(0);

    // بررسی خط‌گردن با رنگ درخشان #bc13fe
    const neckline = figures.find((f: any) => f.type === 'line' && f.styles.color === '#bc13fe');
    expect(neckline).toBeDefined();
    expect(neckline.styles.style).toBe('dashed');

    // بررسی پایه‌های سه‌بعدی ۵ نقطه‌ای (M کامل: P0 -> P1 -> Neckline -> P2 -> P3)
    const leg3D = figures.find((f: any) => f.type === 'line' && f.styles.color === '#ff2079');
    expect(leg3D).toBeDefined();
    expect(leg3D.attrs.coordinates).toHaveLength(5);

    // بررسی ثبت الگوها در استور همراه با نقطه آغاز و بازآزمایی
    const storedPatterns = useTechnicalStore.getState().detectedDoubleTapPatterns;
    expect(storedPatterns.length).toBeGreaterThan(0);
    expect(storedPatterns[0].score).toBeGreaterThan(50);
    expect(storedPatterns[0].origin).toBeDefined();
    expect(storedPatterns[0].retest).toBeDefined();
  });

  it('SuperTrendPullback creates supertrend line, value zones and pullback arrows', () => {
    registerSuperTrendPullbackOverlay();
    const template = registeredTemplates.get('SuperTrendPullback');
    expect(template).toBeDefined();

    const params = createMockParams('SuperTrendPullback');
    const figures = template.createPointFigures(params);

    expect(figures.length).toBeGreaterThan(0);
    const lines = figures.filter((f: any) => f.type === 'line');
    expect(lines.length).toBeGreaterThan(5);
  });

  it('AutoTrendlineCHoCH generates trendlines and CHoCH structural break levels', () => {
    registerAutoTrendlineCHoCHOverlay();
    const template = registeredTemplates.get('AutoTrendlineCHoCH');
    expect(template).toBeDefined();

    const params = createMockParams('AutoTrendlineCHoCH');
    const figures = template.createPointFigures(params);

    expect(figures.length).toBeGreaterThan(0);
  });

  it('MultiModeChannel renders differently across regression, retest, and donchian modes', () => {
    registerMultiModeChannelOverlay();
    const template = registeredTemplates.get('MultiModeChannel');
    expect(template).toBeDefined();

    // ۱. رگرسیون خطی
    useTechnicalStore.getState().setChannelMode('regression');
    const regFigures = template.createPointFigures(createMockParams('MultiModeChannel'));
    expect(regFigures.some((f: any) => f.type === 'polygon')).toBe(true);
    expect(regFigures.some((f: any) => f.styles?.color?.includes('218, 165, 32'))).toBe(true);

    // ۲. شکست و پولبک
    useTechnicalStore.getState().setChannelMode('retest_channel');
    const retestFigures = template.createPointFigures(createMockParams('MultiModeChannel'));
    expect(retestFigures.some((f: any) => f.styles?.color?.includes('16, 185, 129'))).toBe(true);

    // ۳. دانچیان
    useTechnicalStore.getState().setChannelMode('donchian');
    const donchianFigures = template.createPointFigures(createMockParams('MultiModeChannel'));
    expect(donchianFigures.some((f: any) => f.styles?.color === '#3b82f6')).toBe(true);
  });

  it('MultiVariantRSI creates signals for standard, fibo, bb, and smooth_ma variants', () => {
    registerMultiVariantRSIOverlay();
    const template = registeredTemplates.get('MultiVariantRSI');
    expect(template).toBeDefined();

    useTechnicalStore.getState().setRsiVariant('standard');
    const standardFigures = template.createPointFigures(createMockParams('MultiVariantRSI'));
    expect(Array.isArray(standardFigures)).toBe(true);

    useTechnicalStore.getState().setRsiVariant('fibo');
    const fiboFigures = template.createPointFigures(createMockParams('MultiVariantRSI'));
    expect(Array.isArray(fiboFigures)).toBe(true);

    useTechnicalStore.getState().setRsiVariant('bb');
    const bbFigures = template.createPointFigures(createMockParams('MultiVariantRSI'));
    expect(Array.isArray(bbFigures)).toBe(true);

    useTechnicalStore.getState().setRsiVariant('smooth_ma');
    const smoothFigures = template.createPointFigures(createMockParams('MultiVariantRSI'));
    expect(Array.isArray(smoothFigures)).toBe(true);
  });
});
