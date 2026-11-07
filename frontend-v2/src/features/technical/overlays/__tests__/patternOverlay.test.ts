import { beforeEach, describe, expect, it, vi } from 'vitest';
import { patternFigures } from '../patternOverlay';
import { selectFeaturedPatterns } from '../../model/patterns/registry';
import type { ChartPattern } from '../../model/patterns/types';
import { useUiStore, type Theme } from '@shared/stores/uiStore';

const p: ChartPattern = {
  id: 'X:4:1-2-3-4', kind: 'TRIANGLE_ASC', direction: 'bullish', family: 'continuation',
  anchor: { index: 10, price: 105, timestamp: 10_000 }, points: [],
  upper: { from: { index: 2, price: 110, timestamp: 2000 }, to: { index: 10, price: 110, timestamp: 10_000 } },
  lower: { from: { index: 2, price: 100, timestamp: 2000 }, to: { index: 10, price: 106, timestamp: 10_000 } },
  target: 120, stopLoss: 98, quality: 60, status: 'forming',
  formation: { probability: 0.62, successes: 14, failures: 9, resolved: 23, confidence: 'medium', horizon: 10, method: 'same-symbol' },
};

const params = { chart: { convertToPixel: vi.fn(() => ({ x: 10, y: 20 })) } } as never;

const at = (index: number, price: number) => ({ index, price, timestamp: index * 1000 });

type Figure = ReturnType<typeof patternFigures>[number];
interface FigureStyles {
  color?: string;
  size?: number;
  family?: string;
  style?: string;
}

function textOf(figure: Figure): string {
  const attrs = figure.attrs as { text?: unknown } | undefined;
  return String(attrs?.text ?? '');
}

function textFigures(figures: Figure[]): Figure[] {
  return figures.filter((f) => f.type === 'text');
}

function lineFigures(figures: Figure[]): Figure[] {
  return figures.filter((f) => f.type === 'line');
}

function texts(figures: Figure[]): string[] {
  return textFigures(figures).map(textOf);
}

function stylesOf(figure: Figure): FigureStyles {
  return (figure.styles ?? {}) as FigureStyles;
}

/** پس‌زمینهٔ پنلِ هر تم، مطابق `src/app/styles.css` (`--panel`). */
const PANEL_BACKGROUND: Record<Theme, string> = {
  brass: '#15181c',
  warm: '#fbf9f5',
  terminal: '#0a110d',
  cool: '#fafcfd',
};

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const n = Number.parseInt(hex.slice(1), 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('pattern overlay figures', () => {
  it('draws the pattern as a connected zig-zag through its pivots (R-PB-9)', () => {
    const pt = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
    const zigzag = { ...p, points: [pt(1, 101), pt(3, 110), pt(5, 103), pt(7, 112), pt(9, 106)], anchor: pt(9, 106) };
    const figures = patternFigures(params, [zigzag]);
    const polyline = figures.find((f) => f.type === 'line' && Array.isArray((f.attrs as { coordinates?: unknown[] }).coordinates) && ((f.attrs as { coordinates?: unknown[] }).coordinates as unknown[]).length === 5);
    expect(polyline).toBeTruthy();
    expect(figures.filter((f) => f.type === 'circle')).toHaveLength(5);
  });

  beforeEach(() => useUiStore.setState({ theme: 'brass' }));

  it('draws both boundaries and one label for a forming pattern', () => {
    const figures = patternFigures(params, [p]);
    expect(figures.filter((f) => f.type === 'line').length).toBeGreaterThanOrEqual(2);
    expect(figures.some((f) => f.type === 'text' && textOf(f).includes('۶۲٪'))).toBe(true);
  });

  it('renders a 0.5 formation rate as ۵۰٪', () => {
    const half: ChartPattern = {
      ...p,
      id: 'HALF',
      formation: { probability: 0.5, successes: 5, failures: 4, resolved: 9, confidence: 'medium', horizon: 10, method: 'same-symbol' },
    };
    expect(texts(patternFigures(params, [half]))[0]).toContain('۵۰٪');
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

  it('caps seven eligible patterns at six labels', () => {
    const seven: ChartPattern[] = Array.from({ length: 7 }, (_, i) => ({
      ...p,
      id: `ELIGIBLE_${i}`,
      family: i % 2 === 0 ? 'reversal' : 'continuation',
      status: i < 4 ? 'forming' : 'confirmed',
      anchor: at(10 + i, 105 + i),
    }));
    const labels = texts(patternFigures(params, seven));
    expect(labels.length).toBeLessThanOrEqual(6);
    expect(labels).toHaveLength(selectFeaturedPatterns(seven, 6).length);
  });

  it('draws nothing for invalidated patterns', () => {
    const invalidated: ChartPattern = { ...p, id: 'DEAD', status: 'invalidated' };
    expect(patternFigures(params, [invalidated])).toHaveLength(0);
  });

  it('skips a zero-length H&S upper line and a neckline identical to a boundary', () => {
    const neck = { from: at(2, 100), to: at(8, 104) };
    const hs: ChartPattern = {
      ...p,
      id: 'HS',
      kind: 'HEAD_SHOULDERS',
      direction: 'bearish',
      upper: { from: at(4, 110), to: at(4, 110) },
      lower: neck,
      neckline: { from: at(2, 100), to: at(8, 104) },
    };
    const lines = lineFigures(patternFigures(params, [hs]));
    expect(lines).toHaveLength(1);
    expect(stylesOf(lines[0]).style).toBe('solid');
  });

  it('never draws classic DOUBLE_TOP/DOUBLE_BOTTOM; W/M belongs to the DoubleTap engine only', () => {
    const doubleBottom: ChartPattern = {
      ...p,
      id: 'DT',
      kind: 'DOUBLE_BOTTOM',
      direction: 'bullish',
      upper: { from: at(6, 104), to: at(6, 104) },
      lower: { from: at(4, 100), to: at(4, 100) },
    };
    const doubleTop: ChartPattern = { ...doubleBottom, id: 'DT2', kind: 'DOUBLE_TOP', direction: 'bearish' };
    const figures = patternFigures(params, [doubleBottom, doubleTop]);
    expect(figures).toHaveLength(0);

    // یک الگوی کلاسیک دیگر هنوز رسم می‌شود؛ فیلتر فقط W/M را برمی‌دارد.
    const flag: ChartPattern = { ...p, id: 'FLAG', kind: 'FLAG_BULL' };
    const withFlag = patternFigures(params, [doubleBottom, doubleTop, flag]);
    expect(textFigures(withFlag)).toHaveLength(1);
    expect(texts(withFlag)[0]).toContain('پرچم صعودی');
    expect(withFlag.every((figure) => figure.type !== 'text' || !String((figure.attrs as { text?: unknown }).text).includes('دوقلو'))).toBe(true);
  });

  it('draws no boundary lines for double-tap patterns whose bounds are single points', () => {
    const triangle: ChartPattern = {
      ...p,
      id: 'TRI_SINGLE',
      kind: 'TRIANGLE_SYM',
      upper: { from: at(6, 104), to: at(6, 104) },
      lower: { from: at(4, 100), to: at(4, 100) },
    };
    const figures = patternFigures(params, [triangle]);
    expect(lineFigures(figures)).toHaveLength(0);
    expect(textFigures(figures)).toHaveLength(1);
  });

  it('draws the dashed neckline when it is distinct from both boundaries', () => {
    const withNeckline: ChartPattern = {
      ...p,
      id: 'NECKLINE',
      neckline: { from: at(2, 105), to: at(10, 103) },
    };
    const lines = lineFigures(patternFigures(params, [withNeckline]));
    expect(lines).toHaveLength(3);
    expect(lines.filter((f) => stylesOf(f).style === 'dashed')).toHaveLength(1);
  });

  it('uses an 11px label with a real font stack', () => {
    const [label] = textFigures(patternFigures(params, [p]));
    const styles = stylesOf(label);
    expect(styles.size).toBe(11);
    expect(styles.family).toBe('Vazirmatn, sans-serif');
  });

  it('flips the label inside the pane when the anchor sits at the right edge', () => {
    const edgeParams = {
      chart: { convertToPixel: vi.fn(() => ({ x: 1040, y: 200 })) },
      bounding: { width: 1052, height: 662, left: 0, right: 1052, top: 0, bottom: 662 },
    } as never;
    const [label] = textFigures(patternFigures(edgeParams, [p]));
    const attrs = label.attrs as { x: number; align: string };
    // برچسبِ لنگرِ چسبیده به لبه باید به چپ باز شود، نه بیرونِ کادر.
    expect(attrs.align).toBe('right');
    expect(attrs.x).toBeLessThan(1040);

    // وسطِ چارت همان چپ‌چینِ قبلی می‌ماند (بدون bounding هم امن است).
    const [center] = textFigures(patternFigures(params, [p]));
    expect((center.attrs as { align: string }).align).toBe('left');
  });

  it('keeps label contrast at or above 4.5:1 on every theme panel', () => {
    const directions = ['bullish', 'bearish', 'neutral'] as const;
    for (const theme of Object.keys(PANEL_BACKGROUND) as Theme[]) {
      useUiStore.setState({ theme });
      for (const direction of directions) {
        const [label] = textFigures(
          patternFigures(params, [{ ...p, id: `${theme}:${direction}`, direction }]),
        );
        const { color } = stylesOf(label);
        expect(color).toBeTruthy();
        expect(contrast(color as string, PANEL_BACKGROUND[theme])).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
