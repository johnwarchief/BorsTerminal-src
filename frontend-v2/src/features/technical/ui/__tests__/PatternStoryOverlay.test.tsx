import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Chart } from 'klinecharts';
import { PatternStoryOverlay } from '../PatternStoryOverlay';
import type { DoubleTapPattern } from '../../model/types';

function mockChart(): Chart {
  return {
    convertToPixel: vi.fn(({ dataIndex, value }: { dataIndex?: number; value?: number }) => ({
      x: 60 + (dataIndex ?? 0) * 30,
      y: 320 - (value ?? 0) * 0.2,
    })),
    subscribeAction: vi.fn(),
    unsubscribeAction: vi.fn(),
  } as unknown as Chart;
}

function pattern(overrides: Partial<DoubleTapPattern> = {}): DoubleTapPattern {
  return {
    id: 'double-top-1-2',
    type: 'DOUBLE_TOP',
    origin: { index: 0, price: 80, timestamp: 0 },
    peak1: { index: 1, price: 100, timestamp: 0 },
    neckline: { index: 2, price: 90, timestamp: 0 },
    peak2: { index: 3, price: 100.2, timestamp: 0 },
    retest: { index: 4, price: 90, timestamp: 0 },
    target1: 80,
    target2: 76.2,
    stopLoss: 101,
    score: 82,
    quality: 82,
    height: 10,
    status: 'forming',
    formation: {
      probability: 0.62,
      successes: 11,
      failures: 7,
      resolved: 18,
      confidence: 'low',
      horizon: 10,
      method: 'same-symbol',
    },
    ...overrides,
  };
}

describe('PatternStoryOverlay', () => {
  it('فقط آخرین الگو را با چیپ احتمال و نمونه نشان می‌دهد', () => {
    const { container } = render(
      <PatternStoryOverlay chart={mockChart()} patterns={[pattern()]} active />
    );
    expect(screen.getByTestId('pattern-story-overlay')).toBeTruthy();
    expect(container.textContent).toContain('در حال تشکیل');
    expect(container.textContent).toContain('۶۲٪');
    expect(container.textContent).toContain('۱۸ نمونه');
    expect(container.querySelectorAll('polyline')).toHaveLength(1);
    expect(container.querySelector('filter')).toBeNull();
    expect(container.innerHTML).not.toContain('infinite');
    expect(container.innerHTML).not.toContain('drop-shadow');
    expect(container.querySelector('polyline')?.getAttribute('pathLength')).toBe('1');
  });

  it('fallback کوهورت بازار را صریح برچسب می‌زند', () => {
    const { container } = render(
      <PatternStoryOverlay
        chart={mockChart()}
        patterns={[
          pattern({
            formation: {
              probability: 0.79,
              successes: 120,
              failures: 30,
              resolved: 150,
              confidence: 'high',
              horizon: 10,
              method: 'market-cohort',
            },
          }),
        ]}
        active
      />
    );
    expect(container.textContent).toContain('هم‌گروه بازار');
    expect(container.textContent).toContain('۱۵۰ نمونه');
    expect(container.textContent).toContain('اطمینان بالا');
  });

  it('اگر نمونهٔ کافی نیست، درصد نشان نمی‌دهد', () => {
    const { container } = render(
      <PatternStoryOverlay
        chart={mockChart()}
        patterns={[
          pattern({
            formation: {
              probability: null,
              successes: 3,
              failures: 1,
              resolved: 4,
              confidence: 'none',
              horizon: 10,
              method: 'same-symbol',
            },
          }),
        ]}
        active
      />
    );
    expect(container.textContent).toContain('نمونهٔ کافی نیست');
    expect(container.textContent).not.toContain('٪');
  });

  it('الگوی تأییدشده وضعیت تأیید را نشان می‌دهد', () => {
    const { container } = render(
      <PatternStoryOverlay
        chart={mockChart()}
        patterns={[pattern({ status: 'active', formation: undefined })]}
        active
      />
    );
    expect(container.textContent).toContain('الگو تأیید شد');
  });

  it('در حالت غیرفعال هیچ لایه‌ای نمی‌سازد', () => {
    const { container } = render(
      <PatternStoryOverlay chart={mockChart()} patterns={[pattern()]} active={false} />
    );
    expect(container.querySelector('[data-testid="pattern-story-overlay"]')).toBeNull();
  });
});
