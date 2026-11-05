// model/patterns/__tests__/continuation.test.ts
import { describe, expect, it } from 'vitest';
import { detectContinuation } from '../detectContinuation';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/**
 * سری مصنوعی: هر پا یک خط بین دو قیمت بستهٔ چرخش است، پس پیوت‌های ۱/۱ دقیقاً
 * روی نقاط چرخش می‌افتند (R-PAT-4: فقط پنجرهٔ پیوت در تست کوچک می‌شود).
 */
function zigzag(start: number, legs: Array<[to: number, bars: number]>): EngineCandle[] {
  const closes = [start];
  for (const [to, bars] of legs) {
    const from = closes[closes.length - 1]!;
    const step = (to - from) / bars;
    for (let k = 1; k <= bars; k++) {
      closes.push(k === bars ? to : from + step * k);
    }
  }
  return closes.map((close, i) => ({
    timestamp: i * 60_000,
    open: close,
    high: close + 1,
    low: close - 1,
    close,
  }));
}

const FIXTURE_CONFIG = { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 };
const ATR = 2;

/** فقط دامنهٔ یک کندل را بازشکل می‌دهد؛ عدد آستانه‌ای تغییر نمی‌کند. */
function reshape(
  candles: EngineCandle[],
  index: number,
  shape: Partial<Pick<EngineCandle, 'high' | 'low' | 'close'>>,
): EngineCandle[] {
  candles[index] = { ...candles[index]!, ...shape };
  return candles;
}

/** لگ صعودی تند، بعد کانال نزولی موازی ۳ کندلی، بعد ادامه. */
function flagSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2], // درهٔ شروع لگ
    [130, 8], // قلهٔ پایان لگ
    [125.5, 3],
    [128, 3],
    [122.5, 3],
    [125, 3],
    [125, 1], // داخل کانال؛ پیوت قلهٔ قبلی را حفظ می‌کند
    [136, 4], // شکست و ادامه
  ]), 23, { low: 124.2 });
}

/** همان لگ، بعد کانال همگرا: سقف پایین‌آینده و کف بالارونده. */
function pennantSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2],
    [130, 8],
    [120, 3],
    [132, 3],
    [125, 3],
    [130, 3],
    [130, 1],
    [140, 4],
  ]), 23, { low: 129.2 });
}

/** سه‌گوشهٔ صعودی: سقف‌های هم‌سطح و کف‌های بالارونده. */
function ascendingTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [100, 3],
    [130, 6],
    [108, 6],
    [130, 6],
    [116, 6],
    [116, 1], // کف آخر را پیوت نگه می‌دارد
    [136, 4],
  ]);
}

/** سه‌گوشهٔ نزولی: کف‌های هم‌سطح و سقف‌های پایین‌آینده. */
function descendingTriangleSeries(): EngineCandle[] {
  return reshape(zigzag(120, [
    [128, 5],
    [100, 6],
    [126, 6],
    [100, 6],
    [124, 6],
    [100, 6],
    [101, 1], // برگشت کوچک تا کف آخر پیوت بماند
    [97, 1],
  ]), 36, { high: 100.9, low: 99.4, close: 100.5 });
}

/** سه‌گوشهٔ متقارن: سقف پایین‌آینده و کف بالارونده. */
function symmetricTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [126, 8],
    [108, 8],
    [130, 5],
  ]);
}

/** مستطیل: سقف و کف تخت، بعد شکست رو به بالا. */
function rectangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [130, 8],
    [100, 8],
    [134, 4],
  ]);
}

/** گُوهٔ برخاسته: سقف و کف بالارونده با همگرایی، شکست نزولی. */
function risingWedgeSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [134, 8],
    [120, 8],
    [120.1, 1],
  ]);
}

/** گُوهٔ افتاده: سقف و کف پایین‌آینده با همگرایی، شکست صعودی. */
function fallingWedgeSeries(): EngineCandle[] {
  return zigzag(120, [
    [136, 5],
    [110, 8],
    [120, 8],
    [104, 8],
    [120.5, 1],
  ]);
}

describe('continuation detectors', () => {
  it('finds a bull flag after an impulse leg', () => {
    const found = detectContinuation(flagSeries(), ATR, FIXTURE_CONFIG);
    expect(found.some((p) => p.kind === 'FLAG_BULL')).toBe(true);
    const flag = found.find((p) => p.kind === 'FLAG_BULL')!;
    expect(flag.family).toBe('continuation');
    expect(flag.direction).toBe('bullish');
    expect(flag.upper.to.price).toBeGreaterThan(flag.lower.to.price);
    expect(flag.quality).toBeGreaterThan(0);
    expect(found.some((p) => p.kind === 'PENNANT')).toBe(false);
  });

  it('does not invent a pattern on a straight line', () => {
    const flat: EngineCandle[] = Array.from({ length: 40 }, (_, i) => ({
      timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100,
    }));
    expect(detectContinuation(flat, 1.5, PATTERN_CONFIG)).toEqual([]);
  });

  it('finds a pennant when the consolidation converges', () => {
    const found = detectContinuation(pennantSeries(), ATR, FIXTURE_CONFIG);
    expect(found.some((p) => p.kind === 'PENNANT')).toBe(true);
    const pennant = found.find((p) => p.kind === 'PENNANT')!;
    expect(pennant.family).toBe('continuation');
    expect(pennant.direction).toBe('bullish');
    expect(pennant.quality).toBeGreaterThan(0);
    // همگرایی از مسیر خودش (نه از دروازهٔ عرض کانال پرچم) آمده است.
    expect(found.some((p) => p.kind === 'FLAG_BULL')).toBe(false);
  });

  it('finds an ascending triangle with flat highs and rising lows', () => {
    const found = detectContinuation(ascendingTriangleSeries(), ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_ASC');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('bullish');
    expect(triangle?.family).toBe('continuation');
  });

  it('finds a descending triangle with flat lows and falling highs', () => {
    const found = detectContinuation(descendingTriangleSeries(), ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_DESC');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('bearish');
    expect(triangle?.family).toBe('continuation');
  });

  it('finds a symmetric triangle when both boundaries converge', () => {
    const found = detectContinuation(symmetricTriangleSeries(), ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_SYM');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('neutral');
    expect(triangle?.family).toBe('continuation');
  });

  it('finds a rectangle with flat highs and flat lows', () => {
    const found = detectContinuation(rectangleSeries(), ATR, FIXTURE_CONFIG);
    const rectangle = found.find((p) => p.kind === 'RECTANGLE');
    expect(rectangle).toBeDefined();
    expect(rectangle?.direction).toBe('neutral');
    expect(rectangle?.family).toBe('continuation');
  });

  it('finds a rising wedge and reports its bearish resolution', () => {
    const found = detectContinuation(risingWedgeSeries(), ATR, FIXTURE_CONFIG);
    const wedge = found.find((p) => p.kind === 'WEDGE_RISING');
    expect(wedge).toBeDefined();
    expect(wedge?.direction).toBe('bearish');
    expect(wedge?.family).toBe('continuation');
  });

  it('finds a falling wedge and reports its bullish resolution', () => {
    const found = detectContinuation(fallingWedgeSeries(), ATR, FIXTURE_CONFIG);
    const wedge = found.find((p) => p.kind === 'WEDGE_FALLING');
    expect(wedge).toBeDefined();
    expect(wedge?.direction).toBe('bullish');
    expect(wedge?.family).toBe('continuation');
  });

  it('ignores non-positive ATR', () => {
    expect(detectContinuation(flagSeries(), 0, FIXTURE_CONFIG)).toEqual([]);
    expect(detectContinuation(flagSeries(), Number.NaN, FIXTURE_CONFIG)).toEqual([]);
  });
});
