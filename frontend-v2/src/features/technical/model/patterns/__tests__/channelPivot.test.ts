import { describe, expect, it } from 'vitest';
import type { EngineCandle } from '../../doubleTapEngine';
import { PATTERN_CONFIG } from '../config';
import {
  classifyChannelStructure,
  detectPivotChannel,
  isChannelLateStage,
  scoreChannelStructure,
  type ChannelGeometry,
} from '../detectChannelPivot';

const CFG = PATTERN_CONFIG.channelPivot;

function flatCandles(count: number, close = 105): EngineCandle[] {
  return Array.from({ length: count }, (_, i) => ({
    timestamp: 1_700_000_000_000 + i * 86_400_000,
    open: close,
    high: close,
    low: close,
    close,
    volume: 1_000,
  }));
}

function setBar(candles: EngineCandle[], index: number, high: number, low: number): void {
  candles[index] = { ...candles[index], high, low, open: (high + low) / 2, close: (high + low) / 2 };
}

function flatGeometry(spanEnd = 50): ChannelGeometry {
  return {
    upper: { from: { index: 0, price: 110 }, to: { index: spanEnd, price: 110 } },
    lower: { from: { index: 0, price: 100 }, to: { index: spanEnd, price: 100 } },
  };
}

describe('scoreChannelStructure — p19 formula parity', () => {
  it('matches the p19 components to 1e-9 (touches/balance/violations/span/recency/width)', () => {
    const candles = flatCandles(60);
    for (const i of [10, 20, 30]) {
      setBar(candles, i, 110, 100); // هر سه، هم لبهٔ بالا و هم لبهٔ پایین را لمس می‌کنند.
    }
    const atr = new Array<number>(60).fill(2);
    const result = scoreChannelStructure(candles, atr, flatGeometry(50), CFG, 59);
    expect(result).not.toBeNull();
    expect(result!.components.touch).toBeCloseTo(30, 9); // min(35, 6×5)
    expect(result!.components.balance).toBeCloseTo(15, 9);
    expect(result!.components.violation).toBeCloseTo(25, 9);
    expect(result!.components.span).toBeCloseTo(50 / 15, 9);
    expect(result!.components.recency).toBeCloseTo(10 - 9 * 0.15, 9);
    expect(result!.components.width).toBeCloseTo(5, 9);
    expect(result!.touchesUpper).toBe(3);
    expect(result!.touchesLower).toBe(3);
    expect(result!.score).toBeCloseTo(
      30 + 15 + 25 + 50 / 15 + (10 - 9 * 0.15) + 5,
      9,
    );
    expect(result!.widthAtr).toBeCloseTo(5, 9);
  });

  it('caps at 59 when either side has fewer than 2 touches and at 84 for fewer than 3', () => {
    const oneTouch = flatCandles(60);
    setBar(oneTouch, 10, 110, 100);
    const atr = new Array<number>(60).fill(2);
    expect(scoreChannelStructure(oneTouch, atr, flatGeometry(50), CFG, 59)!.score).toBeCloseTo(59, 9);

    const long = flatCandles(151);
    setBar(long, 50, 110, 100);
    setBar(long, 100, 110, 100);
    const longAtr = new Array<number>(151).fill(2);
    // raw ۲۰+۱۵+۲۵+۱۰+۱۰+۵ = ۸۵ ⇒ سقف ۸۴
    expect(scoreChannelStructure(long, longAtr, flatGeometry(150), CFG, 150)!.score).toBeCloseTo(84, 9);
  });

  it('applies the p19 imbalance penalty and caps', () => {
    const candles = flatCandles(151);
    // ۸ لمس بالا و ۵ لمس پایین ⇒ ratio 1.6؛ جریمه (1.6−1.5)×8 = 0.8
    for (const i of [20, 40, 60, 80, 100, 120, 140, 150]) setBar(candles, i, 110, 105);
    for (const i of [25, 55, 85, 115, 145]) {
      candles[i] = { ...candles[i], high: 105, low: 100, open: 105, close: 105 };
    }
    const atr = new Array<number>(151).fill(2);
    const result = scoreChannelStructure(candles, atr, flatGeometry(150), CFG, 150)!;
    expect(result.touchRatio).toBeCloseTo(1.6, 9);
    // 13 لمس ⇒ touchScore=35؛ balance=(1−3/13)×15
    const expected = 35 + (1 - 3 / 13) * 15 + 25 + 10 + 10 + 5 - 0.8;
    expect(result.score).toBeCloseTo(expected, 9);

    const lopsided = flatCandles(151);
    for (const i of [20, 40, 60, 80, 100, 120, 140, 150]) setBar(lopsided, i, 110, 105);
    setBar(lopsided, 30, 105, 100);
    const ratioFour = scoreChannelStructure(lopsided, atr, flatGeometry(150), CFG, 150)!;
    expect(ratioFour.touchRatio).toBeCloseTo(8, 9);
    expect(ratioFour.score).toBeLessThanOrEqual(59);
  });

  it('subtracts 3 per violation and reports per-bar ATR tolerance', () => {
    const candles = flatCandles(60);
    for (const i of [10, 20, 30]) setBar(candles, i, 110, 100);
    candles[40] = { ...candles[40], high: 111, low: 109, open: 111, close: 111 }; // violation upper
    const atr = new Array<number>(60).fill(2);
    const result = scoreChannelStructure(candles, atr, flatGeometry(50), CFG, 59)!;
    expect(result.violationsUpper).toBe(1);
    expect(result.components.violation).toBeCloseTo(22, 9);

    // لمس با ATR همان کندل (۳) پذیرفته می‌شود، نه ATR آخر (۱).
    const near = flatCandles(60);
    for (const i of [10, 20, 30]) setBar(near, i, 110, 100);
    const withLocalAtr = new Array<number>(60).fill(1);
    withLocalAtr[45] = 3;
    setBar(near, 45, 110.5, 105);
    const counted = scoreChannelStructure(near, withLocalAtr, flatGeometry(50), CFG, 59)!;
    expect(counted.touchesUpper).toBe(4);

    const withoutLocal = new Array<number>(60).fill(1);
    const notCounted = scoreChannelStructure(near, withoutLocal, flatGeometry(50), CFG, 59)!;
    expect(notCounted.touchesUpper).toBe(3);
  });
});

describe('classifyChannelStructure', () => {
  it('treats a slope difference of at most 10% of the larger slope as parallel', () => {
    expect(classifyChannelStructure(0.5, 0.5)).toBe('PIVOT_CHANNEL');
    expect(classifyChannelStructure(0.5, 0.55)).toBe('PIVOT_CHANNEL');
    expect(classifyChannelStructure(-0.5, -0.55)).toBe('PIVOT_CHANNEL');
    expect(classifyChannelStructure(0, 0)).toBe('PIVOT_CHANNEL');
    expect(classifyChannelStructure(0.5, 0.6)).not.toBe('PIVOT_CHANNEL');
  });

  it('classifies converging and expanding structures like p19', () => {
    expect(classifyChannelStructure(-0.2, 0.2)).toBe('SYMMETRIC_TRIANGLE');
    expect(classifyChannelStructure(-0.2, 0)).toBe('DESCENDING_TRIANGLE');
    expect(classifyChannelStructure(0, 0.2)).toBe('ASCENDING_TRIANGLE');
    expect(classifyChannelStructure(-0.2, -0.1)).toBe('CONVERGING_WEDGE');
    expect(classifyChannelStructure(0.6, 0.5)).toBe('EXPANDING_STRUCTURE');
  });
});

describe('isChannelLateStage', () => {
  it('triggers at width ≤ 1.5 ATR or ≤ 15 bars to apex', () => {
    expect(isChannelLateStage({ converging: true, apexPassed: false, widthAtr: 1.5, barsToApex: 40 }, CFG)).toBe(true);
    expect(isChannelLateStage({ converging: true, apexPassed: false, widthAtr: 1.6, barsToApex: 40 }, CFG)).toBe(false);
    expect(isChannelLateStage({ converging: true, apexPassed: false, widthAtr: 4, barsToApex: 15 }, CFG)).toBe(true);
    expect(isChannelLateStage({ converging: true, apexPassed: false, widthAtr: 4, barsToApex: 16 }, CFG)).toBe(false);
    expect(isChannelLateStage({ converging: false, apexPassed: false, widthAtr: 1, barsToApex: 5 }, CFG)).toBe(false);
    expect(isChannelLateStage({ converging: true, apexPassed: true, widthAtr: 1, barsToApex: 5 }, CFG)).toBe(false);
  });
});

/** کانال صعودی موازی: قله/دره‌ها لبه‌ها را لمس می‌کنند. */
function risingChannelBars(count: number): EngineCandle[] {
  const width = 20;
  const upper = (i: number) => 110 + 0.1 * i;
  const lower = (i: number) => 90 + 0.1 * i;
  const bars: EngineCandle[] = [];
  for (let i = 0; i < count; i++) {
    const dist = ((i - 40) % 80 + 80) % 80;
    const price = dist <= 40
      ? upper(i) - 2 - (dist / 40) * (width - 4)
      : lower(i) + 2 + ((dist - 40) / 40) * (width - 4);
    bars.push({
      timestamp: 1_700_000_000_000 + i * 86_400_000,
      open: price,
      high: price + 2,
      low: price - 2,
      close: price,
      volume: 1_000,
    });
  }
  return bars;
}

describe('detectPivotChannel', () => {
  it('finds a parallel pivot channel with touches on both rails', () => {
    const bars = risingChannelBars(381);
    const atr = new Array<number>(bars.length).fill(4.2);
    const candidates = detectPivotChannel(bars, atr, CFG);
    const channel = candidates.find((c) => c.kind === 'PIVOT_CHANNEL');
    expect(channel).toBeTruthy();
    expect(channel!.touches.upper).toBeGreaterThanOrEqual(2);
    expect(channel!.touches.lower).toBeGreaterThanOrEqual(2);
    expect(channel!.violations).toBe(0);
    expect(channel!.upper.from.index).toBeLessThan(channel!.upper.to.index);
    expect(channel!.lower.from.index).toBeLessThan(channel!.lower.to.index);
    expect(channel!.metrics.widthAtr).toBeGreaterThan(1);
    expect(['A', 'B', 'C']).toContain(channel!.grade);
    expect(channel!.lifecycle).toBe('active');
    expect(channel!.lateStage).toBe(false);
    expect(channel!.apexIndex).toBeUndefined();
  });

  it('is replay-safe: appending quiet bars does not change a past structure', () => {
    const prefix = risingChannelBars(300);
    const extended = [...prefix];
    for (let i = 300; i < 380; i++) {
      const mid = 100 + 0.1 * i;
      extended.push({
        timestamp: 1_700_000_000_000 + i * 86_400_000,
        open: mid, high: mid + 1, low: mid - 1, close: mid, volume: 1_000,
      });
    }
    const atrPrefix = new Array<number>(prefix.length).fill(4.2);
    const atrFull = new Array<number>(extended.length).fill(4.2);
    const before = detectPivotChannel(prefix, atrPrefix, CFG);
    const after = detectPivotChannel(extended, atrFull, CFG);
    const key = (c: (typeof before)[number]) =>
      `${c.upper.from.index}-${c.upper.to.index}-${c.lower.from.index}-${c.lower.to.index}`;
    const afterMap = new Map(after.map((c) => [key(c), c]));
    let compared = 0;
    for (const candidate of before) {
      const twin = afterMap.get(key(candidate));
      if (!twin) continue;
      compared += 1;
      expect(twin.kind).toBe(candidate.kind);
      expect(twin.upper).toEqual(candidate.upper);
      expect(twin.lower).toEqual(candidate.lower);
      expect(twin.touches).toEqual(candidate.touches);
      expect(twin.violations).toBe(candidate.violations);
    }
    expect(compared).toBeGreaterThan(0);
  });
});
