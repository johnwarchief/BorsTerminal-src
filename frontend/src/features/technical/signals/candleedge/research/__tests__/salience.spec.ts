import { describe, expect, it } from 'vitest';
import { buildSalience } from '../salience';
import type { SalienceInputEvent } from '../types';

function event(
  key: string,
  detector: string,
  family: string,
  bias: SalienceInputEvent['bias'],
  confirmedAtIndex: number,
  anchorIndices: number[],
  level?: number,
): SalienceInputEvent {
  return {
    key,
    detector,
    family,
    bias,
    confirmedAtIndex,
    anchors: anchorIndices.map((index) => ({
      index,
      role: 'high',
      price: 100 + index,
    })),
    level,
  };
}

/**
 * A/B share the break/sweep level at 45, D/E share the second peak at 70.
 * C is a lone candle event. No event may disappear from any grouping.
 */
function fixture(): SalienceInputEvent[] {
  return [
    event('bos_bullish@45', 'bos_bullish', 'market_structure', 'bullish', 45, [10, 45], 101),
    event('liquidity_sweep_high@45', 'liquidity_sweep_high', 'market_structure', 'bearish', 45, [45, 30], 101),
    event('doji@50', 'doji', 'candlestick', 'neutral', 50, [50]),
    event('double_top@70', 'double_top', 'chart_structure', 'bearish', 70, [60, 70]),
    event('lower_high@70', 'lower_high', 'market_structure', 'bearish', 70, [65, 70]),
  ];
}

describe('salience grouping', () => {
  it('groups events that share a structural anchor and keeps singletons', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    expect(result.groups).toHaveLength(3);
    const byEvents = result.groups.map((g) => [...g.eventKeys].sort());
    expect(byEvents).toEqual(
      expect.arrayContaining([
        ['bos_bullish@45', 'liquidity_sweep_high@45'],
        ['doji@50'],
        ['double_top@70', 'lower_high@70'],
      ]),
    );
    const all = result.groups.flatMap((g) => g.eventKeys).sort();
    expect(all).toEqual(fixture().map((e) => e.key).sort());
  });

  it('separates direction and reports mixed only when directional biases conflict', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const mixed = result.groups.find((g) => g.eventKeys.includes('bos_bullish@45'));
    const bearish = result.groups.find((g) => g.eventKeys.includes('double_top@70'));
    expect(mixed?.bias).toBe('mixed');
    expect(bearish?.bias).toBe('bearish');
  });

  it('records shared anchors, levels, evidence and age without inventing a score', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const group = result.groups.find((g) => g.eventKeys.includes('bos_bullish@45'));
    expect(group).toMatchObject({
      seriesKey: 'نماد|D',
      latestConfirmedAtIndex: 45,
      ageBars: 45,
    });
    expect(group?.sharedAnchorIndices).toEqual([45]);
    expect(group?.levels).toEqual([101]);
    expect(group?.detectors).toEqual(
      expect.arrayContaining(['bos_bullish', 'liquidity_sweep_high']),
    );
  });

  it('marks repeated detections of the identical anchor set', () => {
    const repeated = [
      event('doji@50', 'doji', 'candlestick', 'neutral', 50, [50]),
      event('doji@55', 'doji', 'candlestick', 'neutral', 55, [50]),
    ];
    const result = buildSalience('X|D', repeated, 60);
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0].repeatedDetectorAnchorSets).toBe(true);
    expect(result.repeatedGroups).toBe(1);
  });

  it('is deterministic and returns no groups for no events', () => {
    const a = buildSalience('X|D', fixture(), 90);
    const b = buildSalience('X|D', fixture(), 90);
    expect(a).toEqual(b);
    expect(buildSalience('X|D', [], 0).groups).toEqual([]);
  });

  it('does not chain separate structures through a shared anchor over many bars', () => {
    const chain = [
      event('e0', 'doji', 'candlestick', 'neutral', 0, [1]),
      event('e1', 'doji', 'candlestick', 'neutral', 5, [1, 2]),
      event('e2', 'doji', 'candlestick', 'neutral', 10, [2, 3]),
      event('e3', 'doji', 'candlestick', 'neutral', 15, [3, 4]),
    ];
    const result = buildSalience('X|D', chain, 20);
    expect(result.groups).toHaveLength(2);
    expect(result.groups.map((g) => [...g.eventKeys].sort())).toEqual([
      ['e0', 'e1'],
      ['e2', 'e3'],
    ]);
  });
});

describe('salience ranking methods', () => {
  it('orders by latest confirmation (recency only)', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const order = result.order.latest;
    expect(order).toHaveLength(3);
    expect(order[0]).toBe(result.groups.find((g) => g.latestConfirmedAtIndex === 70)?.id);
    expect(order[2]).toBe(result.groups.find((g) => g.latestConfirmedAtIndex === 45)?.id);
  });

  it('orders by an explicit family ordinal, then recency', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const ordered = result.order.structure_first.map(
      (id) => result.groups.find((g) => g.id === id)!,
    );
    expect(ordered[0].families).toContain('market_structure');
    expect(ordered.at(-1)?.families).toEqual(['candlestick']);
  });

  it('orders by distinct anchor count, then recency', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const ordered = result.order.evidence_count.map(
      (id) => result.groups.find((g) => g.id === id)!,
    );
    expect(ordered.at(-1)?.anchorIndices).toEqual([50]);
    expect(ordered[0].anchorIndices.length).toBeGreaterThanOrEqual(
      ordered[1].anchorIndices.length,
    );
  });

  it('keeps a stable id and series key on every group', () => {
    const result = buildSalience('نماد|D', fixture(), 90);
    const ids = new Set(result.groups.map((g) => g.id));
    expect(ids.size).toBe(result.groups.length);
    for (const group of result.groups) {
      expect(group.id).toContain('نماد|D');
      expect(group.newestEventKey).toBeTruthy();
      expect(group.oldestEventKey).toBeTruthy();
    }
  });
});
