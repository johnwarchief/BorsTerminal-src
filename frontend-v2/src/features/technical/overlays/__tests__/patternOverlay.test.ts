import { describe, expect, it, vi } from 'vitest';
import { patternFigures } from '../patternOverlay';
import { selectFeaturedPatterns } from '../../model/patterns/registry';
import type { ChartPattern } from '../../model/patterns/types';

const p: ChartPattern = {
  id: 'X:4:1-2-3-4', kind: 'TRIANGLE_ASC', direction: 'bullish', family: 'continuation',
  anchor: { index: 10, price: 105, timestamp: 10_000 }, points: [],
  upper: { from: { index: 2, price: 110, timestamp: 2000 }, to: { index: 10, price: 110, timestamp: 10_000 } },
  lower: { from: { index: 2, price: 100, timestamp: 2000 }, to: { index: 10, price: 106, timestamp: 10_000 } },
  target: 120, stopLoss: 98, quality: 60, status: 'forming',
  formation: { probability: 62, successes: 14, failures: 9, resolved: 23, confidence: 'medium', horizon: 10, method: 'same-symbol' },
};

const params = { chart: { convertToPixel: vi.fn(() => ({ x: 10, y: 20 })) } } as never;

function textOf(figure: ReturnType<typeof patternFigures>[number]): string {
  const attrs = figure.attrs as { text?: unknown } | undefined;
  return String(attrs?.text ?? '');
}

function texts(figures: ReturnType<typeof patternFigures>): string[] {
  return figures.filter((f) => f.type === 'text').map(textOf);
}

describe('pattern overlay figures', () => {
  it('draws both boundaries and one label for a forming pattern', () => {
    const figures = patternFigures(params, [p]);
    expect(figures.filter((f) => f.type === 'line').length).toBeGreaterThanOrEqual(2);
    expect(figures.some((f) => f.type === 'text' && textOf(f).includes('۶۲٪'))).toBe(true);
  });

  it('shows a single label per pattern', () => {
    expect(texts(patternFigures(params, [p]))).toHaveLength(1);
  });

  it('omits the percentage for a confirmed pattern even when formation exists', () => {
    const confirmed: ChartPattern = { ...p, id: 'CONFIRMED', status: 'confirmed' };
    const label = texts(patternFigures(params, [confirmed]));
    expect(label).toHaveLength(1);
    expect(label[0]).not.toContain('٪');
  });

  it('falls back to "در حال تشکیل" without a formation probability', () => {
    const withoutFormation: ChartPattern = { ...p, id: 'NO_FORMATION', formation: undefined };
    const [label] = texts(patternFigures(params, [withoutFormation]));
    expect(label).toContain('در حال تشکیل');
    expect(label).not.toContain('٪');
  });

  it('treats a null formation probability as unknown', () => {
    const nullProbability: ChartPattern = {
      ...p,
      id: 'NULL_PROB',
      formation: { probability: null, successes: 0, failures: 0, resolved: 0, confidence: 'none', horizon: 10, method: 'same-symbol' },
    };
    const [label] = texts(patternFigures(params, [nullProbability]));
    expect(label).toContain('در حال تشکیل');
    expect(label).not.toContain('٪');
  });

  it('never draws more than six featured shapes', () => {
    const many: ChartPattern[] = Array.from({ length: 10 }, (_, i) => ({
      ...p,
      id: `P${i}`,
      family: i % 2 === 0 ? 'continuation' : 'reversal',
      status: i % 3 === 0 ? 'confirmed' : 'forming',
      anchor: { index: 10 + i, price: 105, timestamp: 10_000 + i },
    }));
    const labels = texts(patternFigures(params, many));
    expect(labels.length).toBeLessThanOrEqual(6);
    expect(labels).toHaveLength(selectFeaturedPatterns(many, 6).length);
  });

  it('draws nothing for invalidated patterns', () => {
    const invalidated: ChartPattern = { ...p, id: 'DEAD', status: 'invalidated' };
    expect(patternFigures(params, [invalidated])).toHaveLength(0);
  });
});
