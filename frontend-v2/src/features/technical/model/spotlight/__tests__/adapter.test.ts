import { describe, expect, it } from 'vitest';
import type { DoubleTapPattern } from '../../types';
import type { ChartPattern } from '../../patterns/types';
import { classicToSpotlight, doubleTapToSpotlight } from '../adapter';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 86_400_000 });

const doubleTop: DoubleTapPattern = {
  id: 'double-top-10-30',
  type: 'DOUBLE_TOP',
  origin: point(2, 90),
  peak1: point(10, 110),
  neckline: point(18, 100),
  peak2: point(30, 110.5),
  retest: point(34, 100),
  breakoutIndex: 34,
  breakoutPrice: 99.5,
  target1: 89,
  target2: 82.9,
  stopLoss: 111.2,
  score: 40,
  quality: 72,
  height: 10.5,
  status: 'tp1_hit',
  p12Score: 93,
  grade: 'A',
  scoreBreakdown: { match: 25, rsi: 20, volume: 7.5, height: 15, symmetry: 10, trend: 15 },
};

const flag: ChartPattern = {
  id: 'FLAG_BULL:40:20-30-40',
  kind: 'FLAG_BULL',
  direction: 'bullish',
  family: 'continuation',
  anchor: point(40, 106),
  points: [point(20, 100), point(30, 104), point(40, 106)],
  upper: { from: point(20, 105), to: point(40, 107) },
  lower: { from: point(20, 99), to: point(40, 101) },
  target: 112,
  stopLoss: 98,
  quality: 61,
  status: 'forming',
  tier: 1,
};

describe('doubleTapToSpotlight', () => {
  it('preserves kind, lifecycle status and p12 levels', () => {
    const model = doubleTapToSpotlight(doubleTop);
    expect(model.source).toBe('doubleTap');
    expect(model.kind).toBe('DOUBLE_TOP');
    expect(model.kindLabel).toBe('DOUBLE TOP');
    expect(model.direction).toBe('bearish');
    expect(model.status).toBe('tp1_hit');
    expect(model.grade).toBe('A');
    expect(model.score).toBe(93);
    expect(model.quality).toBe(72);
    expect(model.neckline).toBe(100);
    expect(model.upper).toBe(110.5);
    expect(model.lower).toBe(110);
    expect(model.target).toBe(89);
    expect(model.stop).toBe(111.2);
    expect(model.tp1).toBe(89);
    expect(model.tp2).toBe(82.9);
    expect(model.scoreBreakdown).toEqual(doubleTop.scoreBreakdown);
    expect(model.atr).toBeUndefined();
  });

  it('builds the W/M leg path including the breakout point', () => {
    const model = doubleTapToSpotlight(doubleTop);
    expect(model.legs?.map((p) => p.index)).toEqual([2, 10, 18, 30, 34]);
    expect(model.anchorIndex).toBe(34);
    expect(model.breakoutIndex).toBe(34);
  });

  it('labels a double bottom as bullish', () => {
    const model = doubleTapToSpotlight({
      ...doubleTop,
      id: 'double-bottom',
      type: 'DOUBLE_BOTTOM',
      peak1: point(10, 100),
      peak2: point(30, 99.5),
      neckline: point(18, 110),
      target1: 120,
      target2: 126.2,
      stopLoss: 98.8,
      status: 'forming',
      breakoutIndex: undefined,
      retest: undefined,
    });
    expect(model.kindLabel).toBe('DOUBLE BOTTOM');
    expect(model.direction).toBe('bullish');
    expect(model.target).toBe(120);
    expect(model.stop).toBe(98.8);
    expect(model.anchorIndex).toBe(30);
  });
});

describe('classicToSpotlight', () => {
  it('maps a tier-1 classic pattern to the shared model', () => {
    const model = classicToSpotlight(flag);
    expect(model.source).toBe('classic');
    expect(model.kind).toBe('FLAG_BULL');
    expect(model.kindLabel).toBe('پرچم صعودی');
    expect(model.direction).toBe('bullish');
    expect(model.status).toBe('forming');
    expect(model.quality).toBe(61);
    expect(model.anchorIndex).toBe(40);
    expect(model.points).toHaveLength(3);
    // مرز بالا/پایین در لنگر: ۱۰۷ و ۱۰۱.
    expect(model.upper).toBe(107);
    expect(model.lower).toBe(101);
    expect(model.target).toBe(112);
    expect(model.stop).toBe(98);
    expect(model.tp1).toBe(112);
    expect(model.tp2).toBeUndefined();
    expect(model.neckline).toBeUndefined();
  });

  it('keeps the neckline level when the classic pattern has one', () => {
    const hs: ChartPattern = {
      ...flag,
      kind: 'HEAD_SHOULDERS',
      direction: 'bearish',
      family: 'reversal',
      neckline: { from: point(20, 102), to: point(40, 100) },
    };
    expect(classicToSpotlight(hs).neckline).toBe(100);
  });
});
