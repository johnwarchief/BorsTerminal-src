// model/patterns/__tests__/reversal.test.ts
import { describe, expect, it } from 'vitest';
import { detectReversal } from '../detectReversal';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/**
 * سری مصنوعی به سبک تست‌های ادامه‌دهنده: هر پا یک خط بین دو قیمت بستهٔ چرخش است،
 * پس پیوت‌های ۱/۱ دقیقاً روی نقاط چرخش می‌افتند (R-PAT-4: فقط پنجرهٔ پیوت در
 * تست کوچک می‌شود؛ همهٔ آستانه‌های هندسی از PATTERN_CONFIG می‌آیند).
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

/** سر و شانه: شانه‌های هم‌تراز، سر بلندتر، خط گردن و شکست نزولی. */
function headShouldersSeries(): EngineCandle[] {
  return zigzag(100, [
    [110, 3], // شانهٔ چپ (قلهٔ ۳)
    [100, 4], // درهٔ گردن (۷)
    [120, 5], // سر (۱۲)
    [101, 5], // درهٔ گردن دوم (۱۷)
    [110, 5], // شانهٔ راست (۲۲)
    [95, 4], // شکست نزولی خط گردن
  ]);
}

/** آینهٔ سر و شانه: شانه‌های هم‌تراز، سر پایین‌تر، شکست صعودی. */
function inverseHeadShouldersSeries(): EngineCandle[] {
  return zigzag(125, [
    [120, 3], // شانهٔ چپ (کف ۳)
    [130, 4], // قلهٔ گردن (۷)
    [110, 5], // سر (کف ۱۲)
    [129, 5], // قلهٔ گردن دوم (۱۷)
    [120, 5], // شانهٔ راست (کف ۲۲)
    [140, 4], // شکست صعودی خط گردن
  ]);
}

/** سه‌قلوی سقف: سه قلهٔ هم‌سطح با دو درهٔ میانی و شکست نزولی. */
function tripleTopSeries(): EngineCandle[] {
  return zigzag(110, [
    [104, 3], // درهٔ آغاز (۳)
    [110, 4], // قلهٔ ۱ (۷)
    [104, 4], // درهٔ ۱ (۱۱)
    [110, 4], // قلهٔ ۲ (۱۵)
    [104, 4], // درهٔ ۲ (۱۹)
    [110, 4], // قلهٔ ۳ (۲۳)
    [95, 4], // شکست نزولی
  ]);
}

/** سه‌قلوی کف: سه کف هم‌سطح با دو قلهٔ میانی و شکست صعودی. */
function tripleBottomSeries(): EngineCandle[] {
  return zigzag(110, [
    [116, 3], // قلهٔ آغاز (۳)
    [110, 4], // کف ۱ (۷)
    [116, 4], // قلهٔ ۱ (۱۱)
    [110, 4], // کف ۲ (۱۵)
    [116, 4], // قلهٔ ۲ (۱۹)
    [110, 4], // کف ۳ (۲۳)
    [125, 4], // شکست صعودی
  ]);
}

/** شانه‌ها ۲ واحد (بیش از 0.6×1.5=0.9) از هم فاصله دارند؛ بقیهٔ هندسه سر و شانه است. */
function shouldersApartSeries(): EngineCandle[] {
  return zigzag(100, [
    [110, 3], // شانهٔ چپ (قلهٔ ۳)
    [100, 4], // درهٔ گردن (۷)
    [120, 5], // سر (۱۲)
    [101, 5], // درهٔ گردن دوم (۱۷)
    [108, 5], // شانهٔ راست، ۲ واحد زیر شانهٔ چپ (۲۲)
    [95, 4], // شکست نزولی
  ]);
}

/** سر فقط 0.3 = 0.2×1.5 بالای شانهٔ بلندتر است؛ آستانهٔ سر 0.5 ATR است. */
function shallowHeadSeries(): EngineCandle[] {
  return zigzag(100, [
    [110, 3], // شانهٔ چپ (قلهٔ ۳)
    [100, 4], // درهٔ گردن (۷)
    [110.3, 5], // سر: 0.3 بالاتر از شانهٔ بلندتر (۱۲)
    [101, 5], // درهٔ گردن دوم (۱۷)
    [109.5, 5], // شانهٔ راست (۲۲)
    [95, 4], // شکست نزولی
  ]);
}

/**
 * سه قله با گام‌های 0.5 (درون levelToleranceAtr=0.5) ولی دامنهٔ 1.0 = یک ATR کامل (بیرون آستانه)؛
 * بررسی زنجیره‌ای جفتی این را می‌پذیرد، بررسی max−min باید رد کند.
 */
function spreadTripleTopSeries(): EngineCandle[] {
  return zigzag(110, [
    [104, 3], // درهٔ آغاز (۳)
    [110, 4], // قلهٔ ۱ (۷)
    [104, 4], // درهٔ ۱ (۱۱)
    [110.5, 4], // قلهٔ ۲ (۱۵)
    [104, 4], // درهٔ ۲ (۱۹)
    [111, 4], // قلهٔ ۳ (۲۳)
    [95, 4], // شکست نزولی
  ]);
}

/** بسته‌شدن بالای سر پیش از شکست خط گردن: الگو باید باطل شود، هرگز تأیید. */
function headShouldersBrokenAboveHeadSeries(): EngineCandle[] {
  return zigzag(100, [
    [110, 3], // شانهٔ چپ (قلهٔ ۳)
    [100, 4], // درهٔ گردن (۷)
    [120, 5], // سر (۱۲)
    [101, 5], // درهٔ گردن دوم (۱۷)
    [110, 5], // شانهٔ راست (۲۲)
    [105, 2], // درهٔ بالای خط گردن (۲۴)
    [125, 2], // بسته‌شدن بالای سر (۲۶)
    [125, 3], // ادامهٔ بالای خط گردن؛ شکست گردن رخ نمی‌دهد
  ]);
}

describe('reversal detectors', () => {
  it('finds a head & shoulders with a broken neckline', () => {
    const candles = headShouldersSeries();
    const found = detectReversal(candles, 1.5, FIXTURE_CONFIG);
    const hs = found.find((p) => p.kind === 'HEAD_SHOULDERS');
    expect(hs).toBeTruthy();
    expect(hs!.family).toBe('reversal');
    expect(hs!.direction).toBe('bearish');
    expect(hs!.neckline).toBeTruthy();
    expect(hs!.status).toBe('confirmed');
    expect(hs!.breakoutIndex! > hs!.anchor.index).toBe(true);
    // R-PAT-15: هدف زیر خط گردن و حد ضرر بالای سر.
    const neckline = Math.min(hs!.neckline!.from.price, hs!.neckline!.to.price);
    expect(hs!.target).toBeLessThan(neckline);
    expect(hs!.stopLoss).toBeGreaterThan(hs!.upper.from.price);
    // لنگر آخرین نقطه است، پس نقاط باید صعودی مرتب باشند.
    expect(hs!.points.map((p) => p.index)).toEqual(
      [...hs!.points.map((p) => p.index)].sort((a, b) => a - b),
    );
    expect(hs!.anchor.index).toBe(Math.max(...hs!.points.map((p) => p.index)));
  });

  it('finds an inverse head & shoulders with a broken neckline', () => {
    const candles = inverseHeadShouldersSeries();
    const found = detectReversal(candles, 1.5, FIXTURE_CONFIG);
    const ihs = found.find((p) => p.kind === 'INVERSE_HEAD_SHOULDERS');
    expect(ihs).toBeTruthy();
    expect(ihs!.family).toBe('reversal');
    expect(ihs!.direction).toBe('bullish');
    expect(ihs!.neckline).toBeTruthy();
    expect(ihs!.status).toBe('confirmed');
    expect(ihs!.breakoutIndex! > ihs!.anchor.index).toBe(true);
    // R-PAT-15: آینهٔ نزولی؛ هدف بالای خط گردن و حد ضرر زیر سر.
    const neckline = Math.max(ihs!.neckline!.from.price, ihs!.neckline!.to.price);
    expect(ihs!.target).toBeGreaterThan(neckline);
    expect(ihs!.stopLoss).toBeLessThan(ihs!.lower.from.price);
  });

  it('finds a triple top when three peaks share a level', () => {
    const candles = tripleTopSeries();
    const found = detectReversal(candles, 1.2, FIXTURE_CONFIG);
    const top = found.find((p) => p.kind === 'TRIPLE_TOP');
    expect(top).toBeTruthy();
    expect(top!.family).toBe('reversal');
    expect(top!.direction).toBe('bearish');
    expect(top!.status).toBe('confirmed');
    expect(top!.breakoutIndex! > top!.anchor.index).toBe(true);
    // R-PAT-15: هدف زیر خط گردن و حد ضرر بالای سقف‌ها.
    const neckline = Math.min(top!.neckline!.from.price, top!.neckline!.to.price);
    expect(top!.target).toBeLessThan(neckline);
    expect(top!.stopLoss).toBeGreaterThan(top!.upper.to.price);
  });

  it('finds a triple bottom when three troughs share a level', () => {
    const candles = tripleBottomSeries();
    const found = detectReversal(candles, 1.2, FIXTURE_CONFIG);
    const bottom = found.find((p) => p.kind === 'TRIPLE_BOTTOM');
    expect(bottom).toBeTruthy();
    expect(bottom!.family).toBe('reversal');
    expect(bottom!.direction).toBe('bullish');
    expect(bottom!.status).toBe('confirmed');
    expect(bottom!.breakoutIndex! > bottom!.anchor.index).toBe(true);
    // R-PAT-15: آینهٔ صعودی؛ هدف بالای خط گردن و حد ضرر زیر کف‌ها.
    const neckline = Math.max(bottom!.neckline!.from.price, bottom!.neckline!.to.price);
    expect(bottom!.target).toBeGreaterThan(neckline);
    expect(bottom!.stopLoss).toBeLessThan(bottom!.lower.to.price);
  });

  it('rejects a head & shoulders whose shoulders drift beyond shouldersToleranceAtr', () => {
    const found = detectReversal(shouldersApartSeries(), 1.5, FIXTURE_CONFIG);
    expect(found.filter((p) => p.kind === 'HEAD_SHOULDERS')).toEqual([]);
  });

  it('rejects a head only 0.2 ATR above the shoulders', () => {
    const found = detectReversal(shallowHeadSeries(), 1.5, FIXTURE_CONFIG);
    expect(found.filter((p) => p.kind === 'HEAD_SHOULDERS')).toEqual([]);
  });

  it('rejects a triple top whose peaks span more than levelToleranceAtr in total', () => {
    // گام‌های جفتی 0.5 ≤ tol، ولی دامنهٔ 1.0 > tol؛ قاعدهٔ max−min باید رد کند.
    const found = detectReversal(spreadTripleTopSeries(), 1, FIXTURE_CONFIG);
    expect(found.filter((p) => p.kind === 'TRIPLE_TOP')).toEqual([]);
  });

  it('invalidates a head & shoulders when price closes above the head before the neckline breaks', () => {
    const found = detectReversal(headShouldersBrokenAboveHeadSeries(), 1.5, FIXTURE_CONFIG);
    const hs = found.find((p) => p.kind === 'HEAD_SHOULDERS');
    expect(hs).toBeTruthy();
    expect(hs!.status).toBe('invalidated');
    expect(hs!.status).not.toBe('confirmed');
  });

  it('reads the minimum window span from config.reversal.minSpanBars', () => {
    // پنج پیوت با span=4: پیش‌فرض ۶ آن را رد می‌کند، بازنویسی ۴ می‌پذیرد.
    const candles = zigzag(100, [
      [110, 1], // شانهٔ چپ (۱)
      [100, 1], // درهٔ گردن (۲)
      [120, 1], // سر (۳)
      [101, 1], // درهٔ گردن دوم (۴)
      [110, 1], // شانهٔ راست (۵)
      [95, 1], // شکست نزولی
    ]);
    expect(detectReversal(candles, 1.5, FIXTURE_CONFIG).some((p) => p.kind === 'HEAD_SHOULDERS')).toBe(false);
    const shortSpan = { ...FIXTURE_CONFIG, reversal: { minSpanBars: 4 } };
    expect(detectReversal(candles, 1.5, shortSpan).some((p) => p.kind === 'HEAD_SHOULDERS')).toBe(true);
  });

  it('ignores non-positive ATR', () => {
    expect(detectReversal(headShouldersSeries(), 0, FIXTURE_CONFIG)).toEqual([]);
    expect(detectReversal(headShouldersSeries(), Number.NaN, FIXTURE_CONFIG)).toEqual([]);
  });
});
