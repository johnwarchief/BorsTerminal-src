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
  DOUBLE_TAP_DEFAULTS,
  TRENDLINE_DEFAULTS,
  capPatternFigures,
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

/**
 * سریِ کندلِ آزمون. پیش از این ۲۲ کندل با قله در ایندکس ۳ و ۹ بود؛ با پنجرۀ
 * واقعیِ اورلی (pivLeft=6 ⇒ حلقه از ایندکس ۶ شروع می‌شود، swingLeft=5) آن قله‌ها
 * هرگز بررسی نمی‌شدند و تست فقط با پنجرۀ شلِ باگ‌دار سبز می‌شد.
 *
 * اینجا قله‌ها در ۱۰ و ۲ و کف‌ها در ۴ و ۶ نشسته‌اند، بیرونِ حاشیۀ پنجره‌ها،
 * و تستِ self-check پایین همین را اثبات می‌کند.
 */
function buildTestCandles() {
  // high, low به‌ازای هر میله — open از closeِ قبلی و close در میانه ساخته می‌شود
  const hl: Array<[number, number]> = [
    [965, 915], [990, 940], [1015, 965], [1005, 950], [985, 900], // 0-4  کفِ سوینگ در ۴
    [1030, 955], [1080, 1010], [1120, 1060], [1155, 1100], [1185, 1130], // 5-9  صعود
    [1200, 1140], [1170, 1120], [1140, 1095], [1120, 1075], [1100, 1065], // 10 قلهٔ اولِ M
    [1090, 1070], [1080, 1060], [1085, 1062], [1110, 1070], [1140, 1100], // 16 خط‌گردنِ M
    [1170, 1130], [1195, 1155], [1220, 1160], [1190, 1140], [1160, 1110], // 22 قلهٔ دومِ M
    [1120, 1070], [1080, 1030], [1050, 1010], // 23-27 شکستِ خط‌گردن
    [1010, 970], [980, 940], [950, 910], [930, 890], [920, 880], [910, 885], // 28-33 فرود
    [905, 860], [930, 880], [960, 910], [990, 945], [965, 920], // 34 کفِ اولِ W، 37 قلهٔ خط‌گردن
    [935, 895], [920, 870], [940, 885], [970, 910], [1000, 940], // 40 کفِ دومِ W (۶ میله بعد از ۳۴)
    [1030, 970], [1060, 1000], [1080, 1020], [1060, 1000], [1040, 980], // 41-45
    [1060, 1000], [1090, 1030], [1120, 1060], // 46-51 بازگشت
  ];
  let prevClose = 940;
  return hl.map(([high, low], i) => {
    const open = prevClose;
    const close = low + (high - low) * (i % 2 === 0 ? 0.7 : 0.35);
    prevClose = close;
    return {
      timestamp: 1730000000000 + i * 86400000,
      open,
      high,
      low,
      close,
      volume: 50000 + i * 1000,
    };
  });
}

function createMockParams(overlayName: string, extendData: any = null, coordinates: any[] = []) {
  const testCandles = buildTestCandles();

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

  it('fixture carries real pivots under the ACTUAL windows, not the old loose ones', () => {
    // این self-check نگهبانِ خودِ fixture است: اگر کسی سری را کوتاه یا قله‌ها را
    // به حاشیه برگرداند، پنجرۀ واقعیِ اورلی دیگر پیوتی نمی‌بیند و این قرمز می‌شود.
    const c = buildTestCandles();
    const n = c.length;
    const pivots = (left: number, right: number, kind: 'high' | 'low') => {
      const out: number[] = [];
      for (let i = left; i < n - right; i++) {
        let ok = true;
        for (let j = i - left; j <= i + right; j++) {
          if (j === i) continue;
          if (kind === 'high' && c[j].high > c[i].high) ok = false;
          if (kind === 'low' && c[j].low < c[i].low) ok = false;
        }
        if (ok) out.push(i);
      }
      return out;
    };
    const highs = pivots(DOUBLE_TAP_DEFAULTS.pivLeft, DOUBLE_TAP_DEFAULTS.pivRight, 'high');
    const swingHighs = pivots(TRENDLINE_DEFAULTS.swingLeft, TRENDLINE_DEFAULTS.swingRight, 'high');
    const swingLows = pivots(TRENDLINE_DEFAULTS.swingLeft, TRENDLINE_DEFAULTS.swingRight, 'low');
    expect(highs.length).toBeGreaterThanOrEqual(2);
    expect(swingHighs.length).toBeGreaterThanOrEqual(2);
    expect(swingLows.length).toBeGreaterThanOrEqual(2);
  });

  it('DoubleTap3D draws clean geometry and no misleading percent label', () => {
    registerDoubleTap3DOverlay();
    const template = registeredTemplates.get('DoubleTap3D');
    expect(template).toBeDefined();

    const params = createMockParams('DoubleTap3D');
    const figures = template.createPointFigures(params);

    expect(figures.length).toBeGreaterThan(0);

    // خط گردن آرام، بدون نئون
    const neckline = figures.find((f: any) => f.type === 'line' && f.styles.color === '#8a8580');
    expect(neckline).toBeDefined();
    expect(neckline.styles.style).toBe('dashed');

    // هندسهٔ ۵ نقطه‌ای با رنگ معنایی ملایم
    const leg = figures.find(
      (f: any) => f.type === 'line' && (f.styles.color === '#b45a6a' || f.styles.color === '#4f8f72')
    );
    expect(leg).toBeDefined();
    expect(leg.attrs.coordinates).toHaveLength(5);

    // هیچ برچسب درصدیِ گمراه‌کننده روی canvas نمی‌ماند
    expect(figures.some((f: any) => f.type === 'text' && String(f.attrs.text).includes('٪'))).toBe(false);

    // ثبت الگوها در استور همراه با کیفیت ساختار
    const storedPatterns = useTechnicalStore.getState().detectedDoubleTapPatterns;
    expect(storedPatterns.length).toBeGreaterThan(0);
    expect(storedPatterns[0].quality).toBeGreaterThan(0);
    expect(storedPatterns[0].origin).toBeDefined();
    expect(storedPatterns[0].retest).toBeDefined();
  });

  it('the drawn-pattern cap changes what is drawn but not what is detected', () => {
    // اثبات اثرِ دو کنترل روی مرزِ تصمیم، با هم:
    // ۱) indicatorParams واقعاً به حلقۀ تشخیص می‌رسد (شل‌کردن ⇒ الگوی بیشتر)
    // ۲) maxDrawnPatterns فقط رسم را کم می‌کند، نه تشخیص را
    registerDoubleTap3DOverlay();
    const template = registeredTemplates.get('DoubleTap3D');

    useTechnicalStore.getState().setIndicatorParam('DoubleTap3D', 'pivLeft', 3);
    useTechnicalStore.getState().setIndicatorParam('DoubleTap3D', 'pivRight', 2);
    useTechnicalStore.getState().setMaxDrawnPatterns(20);

    const all = template.createPointFigures(createMockParams('DoubleTap3D'));
    const detectedAll = useTechnicalStore.getState().detectedDoubleTapPatterns.length;
    expect(detectedAll).toBeGreaterThanOrEqual(1);

    useTechnicalStore.getState().setMaxDrawnPatterns(1);
    const capped = template.createPointFigures(createMockParams('DoubleTap3D'));
    const detectedCapped = useTechnicalStore.getState().detectedDoubleTapPatterns.length;

    expect(capped.length).toBeGreaterThan(0);
    expect(capped.length).toBeLessThanOrEqual(all.length);
    if (detectedAll > 1) expect(capped.length).toBeLessThan(all.length);
    expect(detectedCapped).toBe(detectedAll);

    // پروفایل پیش‌فرض نباید بیش از نسخهٔ شل الگو بسازد.
    useTechnicalStore.getState().resetIndicatorParams('DoubleTap3D');
    useTechnicalStore.getState().setMaxDrawnPatterns(20);
    const strict = template.createPointFigures(createMockParams('DoubleTap3D'));
    expect(useTechnicalStore.getState().detectedDoubleTapPatterns.length).toBeLessThanOrEqual(detectedAll);
    expect(strict.length).toBeLessThanOrEqual(all.length);
  });

  it('the cap keeps the last patterns by market time, not by loop order', () => {
    // حلقه اول همهٔ سقف‌ها را می‌سازد و بعد کف‌ها، پس «آخرینِ آرایه» با «آخرینِ
    // بازار» یکی نیست. با بریدنِ انتهای آرایه، هر سقفی قربانی می‌شد تا وقتی کف‌ها
    // به سقف برسند؛ سنجهٔ پیکسل همین را گرفت (فقط #00f0ff رسم می‌شد).
    const marks = [
      { figureStart: 0, barIndex: 100 }, // M قدیمی
      { figureStart: 6, barIndex: 300 }, // M جدید
      { figureStart: 12, barIndex: 200 }, // W
      { figureStart: 18, barIndex: 50 }, // W قدیمی
    ];
    // دو الگوی آخرِ زمانی: W@200 و M@300 ⇒ بازه‌های ۶..۱۲ و ۱۲..۱۸
    expect(capPatternFigures(marks, 24, 2)).toEqual([
      { from: 6, to: 12 },
      { from: 12, to: 18 },
    ]);
    // وقتی سقف از تعداد الگوها کمتر نیست، هیچ‌چیز بریده نمی‌شود
    expect(capPatternFigures(marks, 24, 4)).toEqual([]);
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
