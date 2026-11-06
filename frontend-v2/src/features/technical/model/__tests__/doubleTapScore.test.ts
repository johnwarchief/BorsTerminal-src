import { describe, expect, it } from 'vitest';
import { rsiSeries, scoreDoubleTap } from '../doubleTapScore';

describe('scoreDoubleTap — p12 weights', () => {
  it('gives 100 / grade A when every component is full and volume diverges', () => {
    const result = scoreDoubleTap({
      matchPct: 1,
      rsiDivergence: true,
      volumeDivergence: true,
      volumeKnown: true,
      heightAtr: 3,
      symmetry: 1,
      priorTrendRatio: 1,
    });
    expect(result.score).toBe(100);
    expect(result.grade).toBe('A');
    expect(result.breakdown).toEqual({ match: 25, rsi: 20, volume: 15, height: 15, symmetry: 10, trend: 15 });
  });

  it('scores 0 / grade C when nothing matches', () => {
    const result = scoreDoubleTap({
      matchPct: 0,
      rsiDivergence: false,
      volumeDivergence: false,
      volumeKnown: true,
      heightAtr: 0,
      symmetry: 0,
      priorTrendRatio: 0,
    });
    expect(result.score).toBe(0);
    expect(result.grade).toBe('C');
    expect(result.breakdown).toEqual({ match: 0, rsi: 0, volume: 0, height: 0, symmetry: 0, trend: 0 });
  });

  it('awards half of the volume weight (7.5) when volume is unknown', () => {
    const result = scoreDoubleTap({
      matchPct: 0,
      rsiDivergence: false,
      volumeDivergence: false,
      volumeKnown: false,
      heightAtr: 0,
      symmetry: 0,
      priorTrendRatio: 0,
    });
    expect(result.breakdown.volume).toBe(7.5);
    expect(result.score).toBe(8); // p12: math.round(7.5)
    expect(result.grade).toBe('C');
  });

  it('caps height at 3 ATR, match/symmetry/trend at 1 and grades B at 55+', () => {
    const pastThreeAtr = scoreDoubleTap({
      matchPct: 1.4,
      rsiDivergence: true,
      volumeDivergence: false,
      volumeKnown: true,
      heightAtr: 12,
      symmetry: 2,
      priorTrendRatio: 1.2,
    });
    // ۲۵ + ۲۰ + ۰ + ۱۵ + ۱۰ + ۱۵ = ۸۵
    expect(pastThreeAtr.score).toBe(85);
    expect(pastThreeAtr.breakdown.height).toBe(15);
    expect(pastThreeAtr.breakdown.match).toBe(25);
    expect(pastThreeAtr.breakdown.symmetry).toBe(10);
    expect(pastThreeAtr.breakdown.trend).toBe(15);

    const belowOne = scoreDoubleTap({
      matchPct: 0,
      rsiDivergence: true,
      volumeDivergence: true,
      volumeKnown: true,
      heightAtr: 1.5,
      symmetry: 0,
      priorTrendRatio: -0.5,
    });
    // ۰ + ۲۰ + ۱۵ + ۷٫۵ + ۰ + ۰ = ۴۲٫۵ ⇒ ۴۳
    expect(belowOne.score).toBe(43);
    expect(belowOne.grade).toBe('C');

    const gradeB = scoreDoubleTap({
      matchPct: 1,
      rsiDivergence: true,
      volumeDivergence: true,
      volumeKnown: true,
      heightAtr: 0,
      symmetry: 0,
      priorTrendRatio: 0,
    });
    expect(gradeB.score).toBe(60);
    expect(gradeB.grade).toBe('B');
  });

  it('treats a missing/NaN input as zero instead of producing NaN', () => {
    const result = scoreDoubleTap({
      matchPct: Number.NaN,
      rsiDivergence: false,
      volumeDivergence: false,
      volumeKnown: true,
      heightAtr: Number.NaN,
      symmetry: Number.NaN,
      priorTrendRatio: Number.NaN,
    });
    expect(Number.isFinite(result.score)).toBe(true);
    expect(result.score).toBe(0);
  });
});

describe('rsiSeries', () => {
  it('returns 100 for an all-gain series and 0 for an all-loss series', () => {
    const up = Array.from({ length: 30 }, (_, i) => 100 + i);
    const down = Array.from({ length: 30 }, (_, i) => 100 - i);
    expect(rsiSeries(up, 14).at(-1)).toBe(100);
    expect(rsiSeries(down, 14).at(-1)).toBe(0);
  });
});
