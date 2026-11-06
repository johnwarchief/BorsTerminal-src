import { describe, expect, it, vi } from 'vitest';
import { eventFigures } from '../eventOverlay';
import type { ChartEvent, ScanResult } from '../../model/events/types';

const at = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

const params = {
  chart: {
    convertToPixel: vi.fn(({ dataIndex, value }: { dataIndex?: number; value?: number }) => ({
      x: (dataIndex ?? 0) * 2,
      y: (value ?? 0) * 2,
    })),
  },
} as never;

function channelEvent(id: string, quality: number): ChartEvent {
  return {
    id,
    family: 'channel',
    kind: 'PIVOT_CHANNEL',
    direction: 'neutral',
    status: 'forming',
    anchor: at(150, 100.3),
    interval: [50, 239],
    quality,
    metrics: { touchesUpper: 3, touchesLower: 4 },
    evidence: { ruleRef: 'CHANNEL_PIVOT', source: 'telegram' },
    draw: {
      lines: [
        { from: at(50, 100.3), to: at(150, 100.3), style: 'solid' },
        { from: at(50, 90.3), to: at(150, 90.3), style: 'solid' },
      ],
      labelAt: at(150, 100.3),
    },
  };
}

function retestEvent(): ChartEvent {
  return {
    id: 'sr:1',
    family: 'breakout',
    kind: 'SR_RETEST',
    direction: 'bullish',
    status: 'confirmed',
    anchor: at(206, 99.8),
    interval: [30, 239],
    quality: 62,
    metrics: { retestIndex: 206, volumeBalanceAvailable: 0 },
    evidence: { ruleRef: 'EVENT:SR_RETEST', source: 'telegram' },
    draw: {
      zone: { fromIndex: 30, toIndex: 239, top: 100.3, bottom: 99.6 },
      labelAt: at(206, 99.8),
    },
  };
}

function makeScan(): ScanResult {
  const channel = channelEvent('channel:primary', 83);
  const secondary = channelEvent('channel:secondary', 70);
  return {
    at: 1,
    timeframe: '1D',
    adjustmentMode: 3,
    seriesBasis: 'functional',
    bars: 240,
    events: [channel, secondary, retestEvent()],
    primary: { channel: channel.id, breakout: 'sr:1' },
    configHash: 'test',
  };
}

describe('event overlay — p19/p21 compact grammar', () => {
  it('draws only the primary channel band plus the retest zone', () => {
    const figures = eventFigures(params, makeScan());
    const lines = figures.filter((f) => f.type === 'line');
    const rects = figures.filter((f) => f.type === 'rect');
    const texts = figures.filter((f) => f.type === 'text');

    // فقط کانال اصلی: دقیقاً دو خط مرزی؛ کانال دوم رسم نمی‌شود.
    expect(lines).toHaveLength(2);
    expect(rects).toHaveLength(1);
    expect(texts).toHaveLength(2);
    const zone = rects[0].attrs as { x: number; y: number; width: number; height: number };
    expect(Math.abs(zone.width)).toBeGreaterThan(0);
    expect(Math.abs(zone.height)).toBeGreaterThan(0);
  });

  it('never draws a W/M zigzag through pattern events', () => {
    const scan = makeScan();
    scan.events.push({
      ...channelEvent('pattern:wm', 90),
      family: 'pattern',
      kind: 'DOUBLE_TOP',
    });
    scan.primary.pattern = 'pattern:wm';
    const figures = eventFigures(params, scan);
    const lines = figures.filter((f) => f.type === 'line');
    expect(lines.every((line) => (line.attrs as { coordinates?: unknown[] }).coordinates?.length === 2)).toBe(true);
  });

  it('labels the pivot channel and the S/R retest in Persian', () => {
    const texts = eventFigures(params, makeScan())
      .filter((f) => f.type === 'text')
      .map((f) => String((f.attrs as { text?: unknown }).text ?? ''));
    expect(texts.some((text) => text.includes('کانال پیوتی'))).toBe(true);
    expect(texts.some((text) => text.includes('ریتست سطح'))).toBe(true);
  });

  it('returns nothing without a scan', () => {
    expect(eventFigures(params, null)).toHaveLength(0);
  });
});
