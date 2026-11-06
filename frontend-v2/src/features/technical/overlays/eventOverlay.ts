import { registerOverlay } from 'klinecharts';
import type {
  OverlayCreateFiguresCallbackParams,
  OverlayFigure,
  OverlayTemplate,
} from 'klinecharts';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import type { ChartEvent, EventFamily, ScanResult } from '../model/events/types';
import { eventKindFa } from '../model/events/labels';

export const EVENT_OVERLAY_ID = 'chart-events';
const FAMILIES: EventFamily[] = ['divergence', 'pullback', 'breakout'];

const LINE_COLOR: Record<string, string> = {
  bullish: '#4f8f72',
  bearish: '#b45a6a',
  neutral: '#a89a6a',
};
const LABEL_DARK: Record<string, string> = {
  bullish: '#7fc4a0',
  bearish: '#e79aa7',
  neutral: '#d8c98d',
};
const LABEL_LIGHT: Record<string, string> = {
  bullish: '#2f6b52',
  bearish: '#8f3f4f',
  neutral: '#6f6132',
};

function isLightTheme(): boolean {
  try {
    const theme = useUiStore.getState().theme;
    return theme === 'warm' || theme === 'cool';
  } catch {
    return false;
  }
}

function px(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  index: number,
  price: number,
): { x: number; y: number } {
  const raw = params.chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}

function labelPlacement(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  anchor: { x: number; y: number },
  text: string,
): { x: number; y: number; align: 'left' | 'right' } {
  const width = params.bounding?.width ?? 0;
  const approxWidth = text.length * 7 + 8;
  const flip = width > 0 && anchor.x + approxWidth > width;
  return flip
    ? { x: anchor.x - 6, y: anchor.y - 8, align: 'right' }
    : { x: anchor.x + 6, y: anchor.y - 8, align: 'left' };
}

function primaryEvents(scan: ScanResult | null): ChartEvent[] {
  if (!scan) return [];
  return FAMILIES
    .map((family) => scan.primary[family])
    .filter((id): id is string => Boolean(id))
    .map((id) => scan.events.find((event) => event.id === id))
    .filter((event): event is ChartEvent => Boolean(event));
}

export function eventFigures(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  scan: ScanResult | null,
): OverlayFigure[] {
  const figures: OverlayFigure[] = [];
  const labelPalette = isLightTheme() ? LABEL_LIGHT : LABEL_DARK;
  for (const event of primaryEvents(scan)) {
    const color = LINE_COLOR[event.direction] ?? LINE_COLOR.neutral;
    const labelColor = labelPalette[event.direction] ?? labelPalette.neutral;
    for (const line of event.draw.lines ?? []) {
      figures.push({
        type: 'line',
        attrs: {
          coordinates: [
            px(params, line.from.index, line.from.price),
            px(params, line.to.index, line.to.price),
          ],
        },
        styles: {
          color,
          size: 1.4,
          style: line.style ?? 'solid',
          dashedValue: [4, 3],
        },
      });
    }
    if (event.family === 'divergence' && event.draw.lines?.length) {
      for (const point of [event.draw.lines[0].from, event.draw.lines[0].to]) {
        const screen = px(params, point.index, point.price);
        figures.push({
          type: 'circle',
          attrs: { x: screen.x, y: screen.y, r: 2.5 },
          styles: { style: 'fill', color, borderColor: color, borderSize: 0 },
        });
      }
    }
    const at = event.draw.labelAt ?? event.anchor;
    const anchor = px(params, at.index, at.price);
    const text = eventKindFa(event);
    const placement = labelPlacement(params, anchor, text);
    figures.push({
      type: 'text',
      attrs: {
        x: placement.x,
        y: placement.y,
        text,
        align: placement.align,
        baseline: 'bottom',
      },
      styles: { color: labelColor, size: 11, family: 'Vazirmatn, sans-serif' },
    });
  }
  return figures;
}

export function registerEventOverlay(): void {
  const template: OverlayTemplate = {
    name: 'ChartEvents',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params): OverlayFigure[] =>
      eventFigures(params, useTechnicalStore.getState().scanResult),
  };
  try {
    registerOverlay(template);
  } catch {
    // idempotent
  }
}
