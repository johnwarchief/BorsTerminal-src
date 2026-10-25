import { describe, expect, it } from 'vitest';
import fixture from '../../signals/candleedge/__tests__/fixtures/apal-d-adjusted.json';
import { scanPatterns } from '../../signals/candleedge';
import type { Candle, DetectorId, PatternEvent } from '../../signals/candleedge';
import { toFaDigits } from '@shared/lib/fmt';
import { parseCandleTimestamp, epochToJalali } from '../jalaliDate';
import {
  CANDLEEDGE_MARK_OVERLAY,
  CANDLEEDGE_MVP_DETECTORS,
  CANDLEEDGE_MVP_METHOD,
  CANDLEEDGE_TAG_OVERLAY,
  buildCandleEdgeAnalysis,
  buildCandleEdgeGroups,
  buildCandleEdgeOverlays,
  candleEdgeCounts,
  candleEdgeDate,
  filterCandleEdgeEvents,
  selectCandleEdgeChartEvents,
} from '../candleEdgeMvp';
import type {
  CandleEdgeBar,
  CandleEdgeChartData,
  CandleEdgeMarkData,
  CandleEdgeTagData,
} from '../candleEdgeMvp';

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
  it('draws family geometry for every event and no permanent text', () => {
    const overlays = buildCandleEdgeOverlays(events, bars, null);
    expect(overlays.filter((overlay) => overlay.name === CANDLEEDGE_TAG_OVERLAY)).toHaveLength(0);
    expect(overlays.some((overlay) => (overlay.name as string) === 'simpleAnnotation')).toBe(false);
    const marks = overlays.filter((overlay) => overlay.name === CANDLEEDGE_MARK_OVERLAY);
    expect(marks.length).toBeGreaterThan(0);
    for (const mark of marks) {
      expect(mark.meta.kind).toBe('break');
      expect(['up', 'down']).toContain((mark.extendData as CandleEdgeMarkData).dir);
    }
    for (const detector of CANDLEEDGE_MVP_DETECTORS) {
      const event = firstOf(detector);
      expect(overlays.some((overlay) => overlay.meta.eventKey === event.key)).toBe(true);
    }
    const engulfing = events.filter((event) => event.detector.endsWith('engulfing'));
    const rects = overlays.filter((overlay) => overlay.name === 'rect');
    expect(rects).toHaveLength(engulfing.length);
    for (const rect of rects) expect(rect.meta.kind).toBe('pattern');
  });

  it('keeps the BOS pivot time separate from the break time and scales the level', () => {
    const selected = firstOf('bos_bullish');
    const overlays = buildCandleEdgeOverlays(events, bars, selected.key);
    const mine = overlays.filter((overlay) => overlay.meta.eventKey === selected.key);
    const pivot = selected.anchors.find((anchor) => anchor.role === 'high' || anchor.role === 'low')!;

    const level = mine.find((overlay) => overlay.meta.kind === 'level')!;
    expect(level.points.map((point) => point.value)).toEqual([selected.level, selected.level]);
    expect(level.points[0].timestamp).toBe(parseCandleTimestamp(pivot.time));
    expect(level.points[1].timestamp).toBe(parseCandleTimestamp(selected.confirmedAt));
    expect(level.styles?.line).toMatchObject({ color: 'rgba(124, 196, 255, 0.95)', size: 1.8 });

    const tick = mine.find((overlay) => overlay.meta.kind === 'pivot')!;
    expect(tick.points[0].timestamp).toBe(tick.points[1].timestamp);
    expect(tick.points[0].timestamp).toBe(parseCandleTimestamp(pivot.time));

    const arrow = mine.find((overlay) => overlay.meta.kind === 'break')!;
    expect(arrow.name).toBe(CANDLEEDGE_MARK_OVERLAY);
    expect((arrow.extendData as CandleEdgeMarkData).dir).toBe('up');
    expect(arrow.points[0].timestamp).toBe(parseCandleTimestamp(selected.confirmedAt));
    const bar = bars[selected.confirmedAtIndex];
    expect(arrow.points[0].value).toBeGreaterThan(bar.high);

    const tag = mine.find((overlay) => overlay.meta.kind === 'tag')!;
    expect(tag.name).toBe(CANDLEEDGE_TAG_OVERLAY);
    expect((tag.extendData as CandleEdgeTagData).text).toBe('BOS ↗');
    expect((tag.extendData as CandleEdgeTagData).place).toBe('below');

    const bearish = firstOf('bos_bearish');
    const scaled = buildCandleEdgeOverlays([bearish], bars, bearish.key, 2);
    const scaledLevel = scaled.find((overlay) => overlay.meta.kind === 'level')!;
    expect(scaledLevel.points.map((point) => point.value)).toEqual([
      bearish.level! * 2,
      bearish.level! * 2,
    ]);
  });

  it('shows the sweep level and the crossing wick without inventing a level', () => {
    const selected = firstOf('liquidity_sweep_high');
    const overlays = buildCandleEdgeOverlays([selected], bars, selected.key);
    const bar = bars[selected.confirmedAtIndex];

    const level = overlays.find((overlay) => overlay.meta.kind === 'level')!;
    expect(level.points.every((point) => point.value === selected.level)).toBe(true);

    const wick = overlays.find((overlay) => overlay.meta.kind === 'pattern')!;
    expect(wick.points[0].timestamp).toBe(wick.points[1].timestamp);
    expect(wick.points[0].timestamp).toBe(parseCandleTimestamp(bar.timestamp));
    expect(wick.points[0].value).toBe(bar.high);
    expect(wick.points[1].value).toBe(bar.close);
    expect(wick.styles?.line).toMatchObject({ size: 3 });

    expect(
      (overlays.find((overlay) => overlay.meta.kind === 'tag')?.extendData as CandleEdgeTagData).text,
    ).toBe(selected.bias === 'bearish' ? 'جارو ↓' : 'جارو ↑');
  });

  it('marks both double pivots and connects them, without a neckline the output lacks', () => {
    const selected = firstOf('double_bottom');
    const overlays = buildCandleEdgeOverlays([selected], bars, selected.key);
    const pivots = overlays.filter((overlay) => overlay.meta.kind === 'pivot');
    expect(pivots).toHaveLength(2);
    expect(pivots.map((overlay) => overlay.points[0].timestamp).sort()).toEqual(
      selected.anchors.map((anchor) => parseCandleTimestamp(anchor.time)).sort(),
    );

    const connector = overlays.find((overlay) => overlay.meta.kind === 'pattern')!;
    expect(connector.points[0].timestamp).toBe(parseCandleTimestamp(selected.anchors[0].time));
    expect(connector.points[1].timestamp).toBe(parseCandleTimestamp(selected.anchors[1].time));
    expect(connector.points[0].value).toBe(selected.anchors[0].price);
    expect(connector.points[1].value).toBe(selected.anchors[1].price);
    expect(overlays.some((overlay) => overlay.meta.kind === 'level')).toBe(false);

    const scaled = buildCandleEdgeOverlays([selected], bars, selected.key, 2);
    const scaledConnector = scaled.find((overlay) => overlay.meta.kind === 'pattern')!;
    expect(scaledConnector.points.map((point) => point.value)).toEqual([
      selected.anchors[0].price * 2,
      selected.anchors[1].price * 2,
    ]);
  });

  it('labels only the selected or hovered event and dims the rest', () => {
    const selected = firstOf('bos_bullish');
    const other = firstOf('double_top');

    const tags = buildCandleEdgeOverlays([selected, other], bars, selected.key).filter(
      (overlay) => overlay.name === CANDLEEDGE_TAG_OVERLAY,
    );
    expect(tags).toHaveLength(1);
    expect(tags[0].meta.eventKey).toBe(selected.key);

    const hovered = buildCandleEdgeOverlays([other], bars, null, 1, other.key);
    const hoverTags = hovered.filter((overlay) => overlay.name === CANDLEEDGE_TAG_OVERLAY);
    expect(hoverTags).toHaveLength(1);
    expect(hoverTags[0].meta.eventKey).toBe(other.key);
    expect((hoverTags[0].extendData as CandleEdgeTagData).text).toContain('دوقلو');

    const neutral = buildCandleEdgeOverlays([other], bars, null).find(
      (overlay) => overlay.meta.kind === 'pattern',
    )!;
    const dimmed = buildCandleEdgeOverlays([selected, other], bars, selected.key).find(
      (overlay) => overlay.meta.eventKey === other.key && overlay.meta.kind === 'pattern',
    )!;
    expect(dimmed.styles?.line).not.toEqual(neutral.styles?.line);
  });
});
