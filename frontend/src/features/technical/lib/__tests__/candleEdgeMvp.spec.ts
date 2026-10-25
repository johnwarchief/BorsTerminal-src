import { describe, expect, it } from 'vitest';
import fixture from '../../signals/candleedge/__tests__/fixtures/apal-d-adjusted.json';
import { scanPatterns } from '../../signals/candleedge';
import type { Candle, DetectorId, PatternEvent } from '../../signals/candleedge';
import { toFaDigits } from '@shared/lib/fmt';
import { parseCandleTimestamp, epochToJalali } from '../jalaliDate';
import {
  CANDLEEDGE_MVP_DETECTORS,
  CANDLEEDGE_MVP_METHOD,
  buildCandleEdgeAnalysis,
  buildCandleEdgeGroups,
  buildCandleEdgeOverlays,
  candleEdgeCounts,
  candleEdgeDate,
  filterCandleEdgeEvents,
  selectCandleEdgeChartEvents,
} from '../candleEdgeMvp';
import type { CandleEdgeBar, CandleEdgeChartData } from '../candleEdgeMvp';

type Row = [string, number, number, number, number, number];

const candles: Candle[] = (fixture.bars as unknown as Row[]).map(
  ([time, open, high, low, close, volume]) => ({ time, open, high, low, close, volume }),
);

const bars: CandleEdgeBar[] = candles.map((c) => ({
  timestamp: c.time,
  open: c.open,
  high: c.high,
  low: c.low,
  close: c.close,
}));

const scan = scanPatterns(candles);
const events = filterCandleEdgeEvents(scan.events);
const data: CandleEdgeChartData = {
  symbol: 'اپال',
  timeframe: 'D',
  bars,
  events,
  error: null,
};

const expectedDate = (time: number | string) =>
  toFaDigits(epochToJalali(parseCandleTimestamp(time)));
const firstOf = (detector: DetectorId): PatternEvent => {
  const found = events.find((event) => event.detector === detector);
  if (!found) throw new Error(`fixture has no ${detector}`);
  return found;
};

describe('CandleEdge MVP detector scope', () => {
  it('keeps exactly the eight validated detectors and drops the research-only ones', () => {
    expect(CANDLEEDGE_MVP_DETECTORS).toHaveLength(8);
    const kept = new Set(events.map((event) => event.detector));
    expect([...kept].sort()).toEqual([...CANDLEEDGE_MVP_DETECTORS].sort());
    const dropped = scan.events.filter((event) => !kept.has(event.detector));
    expect(dropped.length).toBeGreaterThan(0);
    for (const event of events) expect(event.status).toBe('confirmed');
  });

  it('splits confirmed events into bullish and bearish counts', () => {
    const counts = candleEdgeCounts(events);
    expect(counts.total).toBe(events.length);
    expect(counts.bullish + counts.bearish + counts.neutral).toBe(events.length);
    expect(counts.bullish).toBeGreaterThan(0);
    expect(counts.bearish).toBeGreaterThan(0);
    expect(counts.neutral).toBe(0);
  });
});

describe('CandleEdge MVP salience grouping', () => {
  it('documents structure_first as the single MVP ordering', () => {
    expect(CANDLEEDGE_MVP_METHOD).toBe('structure_first');
  });

  it('orders every event exactly once and keeps groups locally bounded', () => {
    const { groups, method } = buildCandleEdgeGroups('اپال|D', events);
    expect(method).toBe('structure_first');
    const flattened = groups.flatMap((group) => group.events.map((event) => event.key));
    expect(flattened.sort()).toEqual(events.map((event) => event.key).sort());
    expect(new Set(flattened).size).toBe(flattened.length);
    for (const group of groups) {
      expect(group.latestConfirmedAtIndex - group.earliestConfirmedAtIndex).toBeLessThanOrEqual(5);
    }
    const firstFamily = groups[0]?.events[0]?.family;
    expect(['market_structure', 'chart_structure', 'candlestick']).toContain(firstFamily);
  });
});

describe('CandleEdge MVP chart clutter control', () => {
  const { groups } = buildCandleEdgeGroups('اپال|D', events);

  it('draws one representative per leading group instead of every event', () => {
    const chartEvents = selectCandleEdgeChartEvents(groups, null, 3);
    expect(chartEvents.length).toBeLessThanOrEqual(3);
    expect(chartEvents.length).toBeGreaterThan(0);
    const leadingKeys = new Set(
      groups.slice(0, 3).flatMap((group) => group.events.map((event) => event.key)),
    );
    for (const event of chartEvents) expect(leadingKeys.has(event.key)).toBe(true);
  });

  it('uses the newest confirmed event of each leading group', () => {
    const chartEvents = selectCandleEdgeChartEvents(groups, null, 3);
    for (const group of groups.slice(0, 3)) {
      const expected = [...group.events].sort(
        (a, b) => b.confirmedAtIndex - a.confirmedAtIndex || a.key.localeCompare(b.key),
      )[0];
      const picked = chartEvents.find((event) => group.events.some((e) => e.key === event.key));
      expect(picked?.key).toBe(expected.key);
    }
  });

  it('always keeps a selected event even when its group is far down the list', () => {
    const deep = groups[groups.length - 1].events[0];
    const chartEvents = selectCandleEdgeChartEvents(groups, deep.key, 3);
    expect(chartEvents.some((event) => event.key === deep.key)).toBe(true);
    expect(chartEvents.length).toBeLessThanOrEqual(4);
  });
});

describe('CandleEdge MVP event analysis', () => {
  it('keeps pivot confirmation separate from the BOS break bar', () => {
    const event = firstOf('bos_bullish');
    const analysis = buildCandleEdgeAnalysis(event, data);
    const pivot = event.anchors.find((anchor) => anchor.role === 'high')!;
    const breakBar = event.anchors.reduce((a, b) => (a.index > b.index ? a : b));

    expect(analysis.title).toContain('BOS');
    expect(analysis.level).toBe(event.level);
    expect(analysis.formationDate).toBe(expectedDate(breakBar.time));
    expect(analysis.confirmationDate).toBe(expectedDate(event.confirmedAt));
    expect(analysis.anchors).toHaveLength(2);
    expect(analysis.anchors[0].pivotConfirmedDate).toBe(
      expectedDate(bars[pivot.confirmedAtIndex!].timestamp),
    );
    expect(pivot.confirmedAtIndex!).toBeLessThanOrEqual(breakBar.index);
    expect(analysis.invalidation).toContain('سطح');
    expect(analysis.candles.map((candle) => candle.index).sort()).toEqual(
      [pivot.index, breakBar.index].sort(),
    );
  });

  it('shows the double pattern confirmed after its second pivot, never before', () => {
    const event = firstOf('double_top');
    const analysis = buildCandleEdgeAnalysis(event, data);
    const second = event.anchors[1];

    expect(analysis.formationDate).toBe(expectedDate(second.time));
    expect(analysis.confirmationDate).toBe(expectedDate(event.confirmedAt));
    expect(parseCandleTimestamp(second.time)).toBeLessThan(
      parseCandleTimestamp(event.confirmedAt),
    );
    expect(analysis.invalidation).toContain('سقف دوم');
    expect(analysis.limits.join(' ')).toContain('گردن');
  });

  it('formats both numeric chart times and the fixture date strings as Jalali', () => {
    expect(candleEdgeDate('2024-08-24')).toBe(expectedDate('2024-08-24'));
    expect(candleEdgeDate(parseCandleTimestamp('2024-08-24'))).toBe(expectedDate('2024-08-24'));
    expect(candleEdgeDate(null)).toBe('');
  });
});

describe('CandleEdge MVP chart overlays', () => {
  it('draws one glyph per event, with no text labels until an event is selected', () => {
    const overlays = buildCandleEdgeOverlays(events, bars, null);
    const markers = overlays.filter((overlay) => overlay.name === 'simpleAnnotation');
    expect(markers).toHaveLength(events.length);
    expect(overlays.filter((overlay) => overlay.name === 'segment')).toHaveLength(0);
    for (const marker of markers) {
      expect(['▲', '▼']).toContain(marker.extendData);
    }
  });

  it('places bullish markers below the bar and bearish markers above it', () => {
    const overlays = buildCandleEdgeOverlays(events, bars, null);
    for (const event of events) {
      const bar = bars[event.confirmedAtIndex];
      const marker = overlays.find((overlay) => overlay.meta?.eventKey === event.key)!;
      const value = marker.points[0].value;
      if (event.bias === 'bullish') expect(value).toBeLessThan(bar.low);
      else expect(value).toBeGreaterThan(bar.high);
    }
  });

  it('adds the broken-level segment only for the selected BOS event', () => {
    const selected = firstOf('bos_bullish');
    const overlays = buildCandleEdgeOverlays(events, bars, selected.key);
    const segments = overlays.filter((overlay) => overlay.name === 'segment');
    expect(segments).toHaveLength(1);
    const [segment] = segments;
    expect(segment.points).toHaveLength(2);
    expect(segment.points[0].value).toBe(selected.level);
    expect(segment.points[1].value).toBe(selected.level);
    const levelAnchor = selected.anchors.find((anchor) => anchor.role === 'high')!;
    expect(segment.points[0].timestamp).toBe(parseCandleTimestamp(levelAnchor.time));
    expect(segment.points[1].timestamp).toBe(parseCandleTimestamp(selected.confirmedAt));
    expect(segment.styles?.line).toMatchObject({ color: '#f0b90b', size: 2 });
    const levelLabel = overlays.find(
      (overlay) => overlay.meta?.kind === 'level' && overlay.name === 'simpleAnnotation',
    );
    expect(levelLabel?.extendData).toContain('سطح');

    const selectedMarker = overlays.find((overlay) => overlay.meta?.eventKey === selected.key)!;
    expect(selectedMarker.extendData).toContain('BOS');
    const otherMarkers = overlays.filter(
      (overlay) =>
        overlay.name === 'simpleAnnotation' && overlay.meta?.eventKey !== selected.key,
    );
    for (const marker of otherMarkers) expect(['▲', '▼']).toContain(marker.extendData);
  });

  it('connects the two pivots of a selected double pattern and scales levels for display', () => {
    const selected = firstOf('double_bottom');
    const overlays = buildCandleEdgeOverlays(events, bars, selected.key);
    const segments = overlays.filter((overlay) => overlay.name === 'segment');
    expect(segments).toHaveLength(1);
    expect(segments[0].points[0].timestamp).toBe(parseCandleTimestamp(selected.anchors[0].time));
    expect(segments[0].points[1].timestamp).toBe(parseCandleTimestamp(selected.anchors[1].time));

    const bos = firstOf('bos_bearish');
    const scaled = buildCandleEdgeOverlays(events, bars, bos.key, 2);
    const level = scaled
      .filter((overlay) => overlay.name === 'segment')
      .flatMap((overlay) => overlay.points.map((point) => point.value));
    expect(level).toEqual([bos.level! * 2, bos.level! * 2]);
  });
});
