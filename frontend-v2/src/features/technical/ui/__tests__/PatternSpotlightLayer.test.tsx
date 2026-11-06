/**
 * ui/__tests__/PatternSpotlightLayer.test.tsx
 *
 * آزمون‌های لایهٔ اسپات‌لایت ۳D (B3):
 * - گرامر p12: اسلب اکسترودشده (وجه جلو/بالا/کنار)، پاهای سایه‌دار، برچسب اصلی، تگ BREAK و ریل TP1/TP2/SL
 * - یک برچسب اسپات‌لایت برای هر الگوی اصلی (W/M)
 * - انیمیشن یک‌باره (بدون infinite) و احترام به prefers-reduced-motion
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Chart } from 'klinecharts';
import { PatternSpotlightLayer } from '../PatternSpotlightLayer';
import type { SpotlightModel } from '../../model/spotlight/types';

const CSS = readFileSync(resolve(process.cwd(), 'src/features/technical/ui/patternSpotlight.css'), 'utf8');

function mockChart(): Chart {
  const chart = {
    convertToPixel: ({ dataIndex, value }: { dataIndex?: number; value?: number }) => {
      if (typeof dataIndex === 'number') return { x: 80 + dataIndex * 6, y: 300 };
      if (typeof value === 'number') return { x: 80, y: 520 - value * 3.5 };
      return { x: 0, y: 0 };
    },
    getDataList: () => Array.from({ length: 60 }, (_, i) => ({ timestamp: i })),
    getSize: () => ({ width: 900, height: 600 }),
    subscribeAction: vi.fn(),
    unsubscribeAction: vi.fn(),
  };
  return chart as unknown as Chart;
}

const at = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

const wm: SpotlightModel = {
  id: 'double-top-10-30',
  source: 'doubleTap',
  kind: 'DOUBLE_TOP',
  kindLabel: 'DOUBLE TOP',
  direction: 'bearish',
  status: 'active',
  grade: 'A',
  score: 93,
  quality: 72,
  anchorIndex: 34,
  points: [at(10, 110), at(18, 100), at(30, 110.5)],
  upper: 110.5,
  lower: 110,
  neckline: 100,
  target: 89,
  stop: 111.2,
  breakoutIndex: 34,
  tp1: 89,
  tp2: 82.9,
  legs: [at(2, 90), at(10, 110), at(18, 100), at(30, 110.5), at(34, 99.5)],
  scoreBreakdown: { match: 25, rsi: 20, volume: 7.5, height: 15, symmetry: 10, trend: 15 },
  atr: 2,
};

afterEach(cleanup);

describe('PatternSpotlightLayer', () => {
  it('renders the p12 main label with grade, BREAK and TP/SL rails', () => {
    render(<PatternSpotlightLayer chart={mockChart()} primary={wm} isLight={false} />);

    const label = screen.getByTestId('spotlight-label');
    expect(label.textContent).toContain('DOUBLE TOP');
    expect(label.textContent).toContain('Grade A');
    expect(label.textContent).toContain('۹۳');

    expect(screen.getByTestId('spotlight-break-tag').textContent).toContain('BREAK');
    expect(screen.getByTestId('spotlight-tp1').textContent).toContain('TP1');
    expect(screen.getByTestId('spotlight-tp2').textContent).toContain('TP2');
    expect(screen.getByTestId('spotlight-sl').textContent).toContain('SL');
  });

  it('builds the 3D slab with front/top/side polygons and a shadowed leg path', () => {
    render(<PatternSpotlightLayer chart={mockChart()} primary={wm} isLight={false} />);

    for (const id of ['spotlight-slab-front', 'spotlight-slab-top', 'spotlight-slab-side']) {
      expect(screen.getByTestId(id).tagName.toLowerCase()).toBe('polygon');
    }
    expect(screen.getByTestId('spotlight-legs').tagName.toLowerCase()).toBe('polyline');
    expect(screen.getByTestId('spotlight-leg-shadow').tagName.toLowerCase()).toBe('polyline');
    expect(screen.getByTestId('spotlight-neckline')).toBeTruthy();
  });

  it('keeps exactly one spotlight label per primary pattern', () => {
    render(<PatternSpotlightLayer chart={mockChart()} primary={wm} isLight={false} />);
    expect(screen.getAllByTestId('spotlight-label')).toHaveLength(1);
  });

  it('renders nothing without a primary or without a chart', () => {
    const { rerender } = render(<PatternSpotlightLayer chart={mockChart()} primary={null} />);
    expect(screen.queryByTestId('spotlight-overlay')).toBeNull();
    rerender(<PatternSpotlightLayer chart={null} primary={wm} />);
    expect(screen.queryByTestId('spotlight-overlay')).toBeNull();
  });

  it('uses one-shot animations only and a 12px text floor', () => {
    expect(CSS).not.toContain('infinite');
    expect(CSS).toContain('700ms');
    expect(CSS).toContain('200ms');
    expect(CSS).toContain('150ms');
    expect(CSS).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(CSS).not.toMatch(/font-size:\s*(?:[0-9]|1[01])px/);
  });

  it('honors prefers-reduced-motion by switching the layer to static', () => {
    const matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal('matchMedia', matchMedia);
    try {
      render(<PatternSpotlightLayer chart={mockChart()} primary={wm} isLight />);
      const overlay = screen.getByTestId('spotlight-overlay');
      expect(overlay.className).toContain('spotlight-reduced');
      // محتوا در حالت static هم کامل است.
      expect(screen.getByTestId('spotlight-label').textContent).toContain('Grade A');
      expect(screen.getByTestId('spotlight-sl')).toBeTruthy();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
