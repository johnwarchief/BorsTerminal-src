import { describe, expect, it } from 'vitest';
import type { DoubleTapPattern } from '../types';
import {
  DEFAULT_PRECISION_PARAMS,
  detectDoubleTapPatterns,
  estimateFormation,
  laplaceRate,
  selectLastFormingPattern,
} from '../doubleTapEngine';

type Bar = { timestamp: number; open: number; high: number; low: number; close: number; volume: number };

function bar(close: number, high: number, low: number, i: number): Bar {
  return { timestamp: i * 86_400_000, open: close, high, low, close, volume: 1_000 };
}

function makeMDoubleTop(secondPeak = 100.4): Bar[] {
  // 5 مصنوعی: قله ۱۰۰ در ایندکس ۵، خط گردن ۹۰ در ایندکس ۸، قله دوم در ۱۱، شکست در ۱۲.
  const closes = [95, 96, 97, 97.5, 98, 99.5, 97, 94, 90.5, 93, 96, 99.5, 89.5];
  const highs = [95.5, 96.5, 97.5, 98, 98.5, 100, 97.5, 94.5, 91.5, 93.5, 96.5, secondPeak, 90.5];
  const lows = [94.5, 95.5, 80, 96.5, 97, 98.5, 96.5, 93, 90, 92.5, 95.5, 98.5, 88.5];
  const bars = closes.map((c, i) => bar(c, highs[i], lows[i], i));
  for (let i = 13; i < 30; i++) bars.push(bar(88 - (i - 13) * 0.2, 88.2 - (i - 13) * 0.2, 87.8 - (i - 13) * 0.2, i));
  return bars;
}

function makeWDoubleBottom(): Bar[] {
  // آینهٔ M: کف ۱۰۰ در ۵، خط گردن ۱۱۰ در ۸، کف دوم ۹۹.۶ در ۱۱، شکست صعودی در ۱۲.
  const closes = [105, 104, 103, 102.5, 102, 100.5, 103, 106, 109.5, 107, 104, 100.5, 110.5];
  const highs = [105.5, 104.5, 103.5, 103, 102.5, 101.5, 103.5, 106.5, 110, 107.5, 104.5, 101.5, 111.5];
  const lows = [104.5, 103.5, 102.5, 101.5, 101, 100, 102.5, 105.5, 108.5, 106.5, 103.5, 99.6, 109.5];
  const bars = closes.map((c, i) => bar(c, highs[i], lows[i], i));
  for (let i = 13; i < 30; i++) bars.push(bar(112 + (i - 13) * 0.2, 112.2 + (i - 13) * 0.2, 111.8 + (i - 13) * 0.2, i));
  return bars;
}

function patternAt(peak2Index: number, type: 'DOUBLE_TOP' | 'DOUBLE_BOTTOM' = 'DOUBLE_TOP'): DoubleTapPattern {
  const isTop = type === 'DOUBLE_TOP';
  return {
    id: `${type}-${peak2Index}`,
    type,
    origin: { index: 0, price: isTop ? 80 : 120, timestamp: 0 },
    peak1: { index: peak2Index - 6, price: isTop ? 100 : 100, timestamp: 0 },
    neckline: { index: peak2Index - 3, price: isTop ? 90 : 110, timestamp: 0 },
    peak2: { index: peak2Index, price: isTop ? 100 : 100, timestamp: 0 },
    target1: isTop ? 80 : 120,
    target2: isTop ? 76.2 : 123.8,
    stopLoss: isTop ? 100.5 : 99.5,
    score: 0,
    quality: 80,
    height: 10,
    status: 'forming',
  };
}

describe('doubleTapEngine — detection', () => {
  it('یک سقف دوقلو معتبر را با تارگت اندازه‌گیری‌شده تشخیص می‌دهد', () => {
    const bars = makeMDoubleTop();
    const patterns = detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
    });
    const m = patterns.find((p) => p.type === 'DOUBLE_TOP');
    expect(m).toBeTruthy();
    expect(m!.peak1.index).toBe(5);
    expect(m!.peak2.index).toBe(11);
    expect(m!.neckline.price).toBeCloseTo(90, 5);
    const height = Math.max(m!.peak1.price, m!.peak2.price) - m!.neckline.price;
    expect(m!.target1).toBeCloseTo(m!.neckline.price - height, 5);
    expect(m!.target2).toBeCloseTo(m!.neckline.price - 1.618 * height, 5);
    expect(m!.status).toBe('active');
  });

  it('اختلاف بیش از حد دو قله را رد می‌کند', () => {
    const bars = makeMDoubleTop(103);
    const patterns = detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.45,
      requireTrendContext: false,
    });
    expect(patterns.filter((p) => p.type === 'DOUBLE_TOP')).toHaveLength(0);
  });

  it('پیوت آخرِ تأییدنشده را الگو نمی‌شمارد', () => {
    const bars = makeMDoubleTop();
    // قله دوم را به آخرین کندل منتقل می‌کنیم؛ دیگر pivRight کندل بعد ندارد.
    const moved = bars.slice(0, 12).map((b) => ({ ...b }));
    moved.push(bar(99.5, 100.4, 98.5, 12));
    const patterns = detectDoubleTapPatterns(moved, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
    });
    expect(patterns.some((p) => p.peak2.index === moved.length - 1)).toBe(false);
  });

  it('کف دوقلو W را تشخیص می‌دهد', () => {
    const bars = makeWDoubleBottom();
    const patterns = detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
    });
    const w = patterns.find((p) => p.type === 'DOUBLE_BOTTOM');
    expect(w).toBeTruthy();
    expect(w!.neckline.price).toBeCloseTo(110, 5);
    expect(w!.status).toBe('active');
  });

  it('کیفیت ساختار برای دو قلهٔ نزدیک‌تر بیشتر است', () => {
    const near = detectDoubleTapPatterns(makeMDoubleTop(100.1), {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.9,
      requireTrendContext: false,
    }).find((p) => p.type === 'DOUBLE_TOP');
    const far = detectDoubleTapPatterns(makeMDoubleTop(100.7), {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.9,
      requireTrendContext: false,
    }).find((p) => p.type === 'DOUBLE_TOP');
    expect(near && far).toBeTruthy();
    expect(near!.quality).toBeGreaterThan(far!.quality);
  });
});

describe('doubleTapEngine — p12 score and lifecycle', () => {
  const detect = (bars: Bar[], extra: Record<string, number> = {}) =>
    detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 2,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
      ...extra,
    });

  it('attaches the p12 score, grade and breakdown to the model', () => {
    const m = detect(makeMDoubleTop()).find((p) => p.type === 'DOUBLE_TOP');
    expect(m).toBeTruthy();
    expect(m!.p12Score).toBeGreaterThanOrEqual(0);
    expect(m!.p12Score).toBeLessThanOrEqual(100);
    expect(['A', 'B', 'C']).toContain(m!.grade);
    const breakdown = m!.scoreBreakdown!;
    expect(Math.round(breakdown.match + breakdown.rsi + breakdown.volume + breakdown.height + breakdown.symmetry + breakdown.trend))
      .toBe(m!.p12Score);
    expect(m!.atr).toBeGreaterThan(0);
  });

  it('marks the breakout close as breakoutPrice', () => {
    const m = detect(makeMDoubleTop()).find((p) => p.type === 'DOUBLE_TOP');
    expect(m!.breakoutIndex).toBe(12);
    expect(m!.breakoutPrice).toBeCloseTo(89.5, 5);
  });

  it('failed: stop hit after the break and before TP1', () => {
    const bars = makeMDoubleTop();
    // پیوت دوم با pivRight=1 در کندل ۱۲ تأیید می‌شود؛ کندل ۱۳ آزاد است تا استاپ را بزند.
    bars[13] = { timestamp: 13 * 86_400_000, open: 92, high: 102, low: 91, close: 99, volume: 1_000 };
    const m = detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 1,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
    }).find((p) => p.peak2.index === 11);
    expect(m).toBeTruthy();
    expect(m!.status).toBe('failed');
  });

  it('tp2_hit: the second target ends the lifecycle', () => {
    const bars = makeMDoubleTop();
    // TP2 = neck − 1.618×height ≈ ۷۳٫۲؛ کندل با low=۷۰ هر دو تارگت را رد می‌کند.
    bars[13] = { timestamp: 13 * 86_400_000, open: 89, high: 90, low: 70, close: 72, volume: 1_000 };
    const m = detect(bars).find((p) => p.peak2.index === 11);
    expect(m!.status).toBe('tp2_hit');
  });

  it('timed_out: expiry after the break without touching TP1 or the stop', () => {
    const bars = makeMDoubleTop();
    for (let i = 13; i < 210; i++) {
      const close = 89 + Math.sin(i / 3) * 0.5;
      bars.push({ timestamp: i * 86_400_000, open: close, high: close + 0.2, low: close - 0.2, close, volume: 1_000 });
    }
    const m = detect(bars).find((p) => p.peak2.index === 11);
    expect(m).toBeTruthy();
    expect(m!.breakoutIndex).toBe(12);
    expect(m!.status).toBe('timed_out');
  });

  it('invalidated: invalidation before any neckline break', () => {
    const bars = makeMDoubleTop();
    bars[12] = { timestamp: 12 * 86_400_000, open: 94, high: 96, low: 93, close: 95, volume: 1_000 };
    bars[13] = { timestamp: 13 * 86_400_000, open: 100, high: 104, low: 99, close: 103, volume: 1_000 };
    const m = detectDoubleTapPatterns(bars, {
      ...DEFAULT_PRECISION_PARAMS,
      pivLeft: 2,
      pivRight: 1,
      minSpan: 3,
      maxSpan: 30,
      tolAtr: 0.6,
      requireTrendContext: false,
    }).find((p) => p.peak2.index === 11);
    expect(m).toBeTruthy();
    expect(m!.status).toBe('invalidated');
  });
});

describe('doubleTapEngine — probability', () => {
  it('نرخ لاپلاس را درست حساب می‌کند', () => {
    expect(laplaceRate(3, 1)).toBeCloseTo(4 / 6, 6);
    expect(laplaceRate(0, 0)).toBeCloseTo(0.5, 6);
  });

  it('از نمونه‌های تاریخی، احتمال تشکیل را با نرخ لاپلاس می‌دهد', () => {
    const bars: Bar[] = [];
    for (let i = 0; i < 70; i++) bars.push(bar(95, 95.5, 94.5, i));
    // سه موفقیت: بسته‌شدن زیر خط گردن ۹۰
    bars[11] = bar(89, 89.5, 88.5, 11);
    bars[31] = bar(89, 89.5, 88.5, 31);
    bars[41] = bar(89, 89.5, 88.5, 41);
    // یک شکست: بسته‌شدن بالای سقف + ۰٫۵ ATR
    bars[21] = bar(103, 103.5, 102.5, 21);
    // نمونه‌ها با peak2 در ۱۰، ۲۰، ۳۰، ۴۰؛ الگوی جاری در ۵۰ و هنوز بی‌نتیجه.
    // ۸ نمونهٔ resolved لازم است، پس این مجموعه باید null بدهد.
    const patterns = [10, 20, 30, 40, 50].map((i) => patternAt(i));
    const current = patterns[4];
    const estimate = estimateFormation(patterns, bars, 2, current.id, 10);
    expect(estimate?.resolved).toBe(4);
    expect(estimate?.probability).toBeNull();
    expect(estimate?.confidence).toBe('none');
  });

  it('با ۸ نمونهٔ resolved درصد و اطمینان کم می‌دهد', () => {
    const bars: Bar[] = [];
    for (let i = 0; i < 120; i++) bars.push(bar(95, 95.5, 94.5, i));
    const indices = [10, 20, 30, 40, 50, 60, 70, 80];
    for (const i of indices) bars[i + 1] = bar(89, 89.5, 88.5, i + 1);
    const patterns = [...indices, 90].map((i) => patternAt(i));
    const estimate = estimateFormation(patterns, bars, 2, patterns[8].id, 10);
    expect(estimate?.resolved).toBe(8);
    expect(estimate?.successes).toBe(8);
    expect(estimate?.probability).toBeCloseTo(9 / 10, 6);
    expect(estimate?.confidence).toBe('low');
  });

  it('با نمونهٔ کم، به کوهورت بازار برمی‌گردد و برچسب آن را می‌دهد', () => {
    const bars: Bar[] = [];
    for (let i = 0; i < 70; i++) bars.push(bar(95, 95.5, 94.5, i));
    bars[11] = bar(89, 89.5, 88.5, 11);
    bars[21] = bar(103, 103.5, 102.5, 21);
    bars[31] = bar(89, 89.5, 88.5, 31);
    bars[41] = bar(89, 89.5, 88.5, 41);
    const patterns = [10, 20, 30, 40, 50].map((i) => patternAt(i));
    const estimate = estimateFormation(patterns, bars, 2, patterns[4].id, 10, {
      successes: 120,
      failures: 30,
      resolved: 150,
      band: 1,
      label: 'market',
    });
    expect(estimate?.method).toBe('market-cohort');
    expect(estimate?.resolved).toBe(150);
    expect(estimate?.probability).toBeCloseTo(121 / 152, 6);
    expect(estimate?.confidence).toBe('high');
  });

  it('اگر نمونهٔ همان نماد کافی باشد، کوهورت نادیده گرفته می‌شود', () => {
    const bars: Bar[] = [];
    for (let i = 0; i < 120; i++) bars.push(bar(95, 95.5, 94.5, i));
    const indices = [10, 20, 30, 40, 50, 60, 70, 80];
    for (const i of indices) bars[i + 1] = bar(89, 89.5, 88.5, i + 1);
    const patterns = [...indices, 90].map((i) => patternAt(i));
    const estimate = estimateFormation(patterns, bars, 2, patterns[8].id, 10, {
      successes: 0,
      failures: 100,
      resolved: 100,
    });
    expect(estimate?.method).toBe('same-symbol');
    expect(estimate?.resolved).toBe(8);
  });

  it('فقط آخرین الگوی در حال تشکیل را برمی‌گرداند', () => {
    const patterns = [patternAt(10), patternAt(20), patternAt(30)];
    const last = selectLastFormingPattern(patterns);
    expect(last?.peak2.index).toBe(30);
    const active = { ...patternAt(40), status: 'active' as const };
    expect(selectLastFormingPattern([...patterns, active])).toBeNull();
  });
});
