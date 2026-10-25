import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { PatternEvent } from '../features/technical/signals/candleedge';
import { parseCandleTimestamp } from '../features/technical/lib/jalaliDate';
import type { CandleEdgeBar, CandleEdgeChartData } from '../features/technical/lib/candleEdgeMvp';
import { CandleEdgePatternPanel } from '../features/technical/components/CandleEdgePatternPanel';

const base = Date.UTC(2026, 0, 1);
const bars: CandleEdgeBar[] = Array.from({ length: 100 }, (_, index) => ({
  timestamp: base + index * 86_400_000,
  open: 1000 + index,
  high: 1020 + index,
  low: 980 + index,
  close: 1010 + index,
}));

const bos: PatternEvent = {
  key: 'bos_bullish@50',
  detector: 'bos_bullish',
  family: 'market_structure',
  bias: 'bullish',
  status: 'confirmed',
  confirmedAtIndex: 50,
  confirmedAt: bars[50].timestamp,
  startIndex: 20,
  level: 1510,
  anchors: [
    { index: 20, time: bars[20].timestamp, price: 1510, role: 'high', confirmedAtIndex: 25 },
    { index: 50, time: bars[50].timestamp, price: 1550, role: 'candle', confirmedAtIndex: 50 },
  ],
};

const sweep: PatternEvent = {
  key: 'liquidity_sweep_high@80',
  detector: 'liquidity_sweep_high',
  family: 'market_structure',
  bias: 'bearish',
  status: 'confirmed',
  confirmedAtIndex: 80,
  confirmedAt: bars[80].timestamp,
  startIndex: 30,
  level: 1820,
  anchors: [
    { index: 80, time: bars[80].timestamp, price: 1790, role: 'candle', confirmedAtIndex: 80 },
    { index: 30, time: bars[30].timestamp, price: 1820, role: 'high', confirmedAtIndex: 35 },
  ],
};

const data: CandleEdgeChartData = {
  symbol: 'فولاد',
  timeframe: 'D',
  bars,
  events: [bos, sweep],
  error: null,
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof CandleEdgePatternPanel>> = {}) {
  const props: React.ComponentProps<typeof CandleEdgePatternPanel> = {
    enabled: false,
    onEnabledChange: vi.fn(),
    data: null,
    onSelect: vi.fn(),
    engineId: 'klinecharts',
    ...overrides,
  };
  return { ...render(<CandleEdgePatternPanel {...props} />), props };
}

describe('CandleEdgePatternPanel', () => {
  it('offers an explicit experimental switch and nothing else while off', () => {
    renderPanel();
    const toggle = screen.getByRole('checkbox', { name: /نمایش الگوهای تکنیکال/ });
    expect(toggle).not.toBeChecked();
    expect(screen.getByText('آزمایشی')).toBeInTheDocument();
    expect(screen.queryByTestId('ce-counts')).not.toBeInTheDocument();
  });

  it('reports the confirmed total and the bullish/bearish split', () => {
    renderPanel({ enabled: true, data });
    const counts = screen.getByTestId('ce-counts');
    expect(counts.textContent).toContain('۲');
    expect(counts.textContent).toContain('۱ صعودی');
    expect(counts.textContent).toContain('۱ نزولی');
    expect(screen.getByTestId('ce-legend').textContent).toContain('▲');
    expect(screen.getByTestId('ce-legend').textContent).toContain('▼');
    expect(screen.getByTestId('ce-event-bos_bullish@50')).toBeInTheDocument();
    expect(screen.getByTestId('ce-event-liquidity_sweep_high@80')).toBeInTheDocument();
  });

  it('opens the clicked event detail with its own times, level, limits and invalidation', () => {
    const { props } = renderPanel({ enabled: true, data });
    fireEvent.click(screen.getByTestId('ce-event-bos_bullish@50'));

    expect(props.onSelect).toHaveBeenCalledWith('bos_bullish@50');
    const detail = screen.getByTestId('ce-detail');
    expect(detail.textContent).toContain('شکست ساختار صعودی');
    expect(detail.textContent).toContain('۱٬۵۱۰');
    expect(detail.textContent).toContain('شکل‌گیری');
    expect(detail.textContent).toContain('تأیید');
    expect(detail.textContent).toContain('تأیید پیوت');
    expect(detail.textContent).toContain('شرط ابطال');
    expect(detail.textContent).toContain('سیگنال رسمی FTS');
    expect(detail.textContent).not.toContain('جاروی نقدینگی بالا');
  });

  it('drops both the old selection and the old detail when the series changes', () => {
    const { props, rerender } = renderPanel({ enabled: true, data });
    fireEvent.click(screen.getByTestId('ce-event-liquidity_sweep_high@80'));
    expect(screen.getByTestId('ce-detail')).toBeInTheDocument();

    const next: CandleEdgeChartData = {
      symbol: 'خودرو',
      timeframe: 'W',
      bars,
      events: [{ ...bos, key: 'bos_bullish@50' }],
      error: null,
    };
    rerender(<CandleEdgePatternPanel {...props} data={next} />);

    expect(props.onSelect).toHaveBeenLastCalledWith(null);
    expect(screen.queryByTestId('ce-detail')).not.toBeInTheDocument();
  });

  it('clears the selection when the refreshed series no longer contains it', () => {
    const { props, rerender } = renderPanel({ enabled: true, data });
    fireEvent.click(screen.getByTestId('ce-event-bos_bullish@50'));
    rerender(<CandleEdgePatternPanel {...props} data={{ ...data, events: [sweep] }} />);
    expect(props.onSelect).toHaveBeenLastCalledWith(null);
    expect(screen.queryByTestId('ce-detail')).not.toBeInTheDocument();
  });

  it('states why the layer is unavailable on the FFC engine instead of hiding it', () => {
    const { rerender, props } = renderPanel({ enabled: false, data, engineId: 'ffc' });
    expect(screen.getByRole('checkbox', { name: /نمایش الگوهای تکنیکال/ })).toBeDisabled();
    expect(screen.getByTestId('ce-engine-note').textContent).toContain('klinecharts');
    rerender(<CandleEdgePatternPanel {...props} enabled data={null} engineId="ffc" />);
    expect(screen.queryByTestId('ce-loading')).not.toBeInTheDocument();
  });

  it('shows an explicit empty state and an explicit scanner error', () => {
    const { rerender, props } = renderPanel({ enabled: true, data: { ...data, events: [] } });
    expect(screen.getByTestId('ce-empty').textContent).toContain('هیچ الگوی تأییدشده');
    rerender(
      <CandleEdgePatternPanel
        {...props}
        data={{ ...data, events: [], error: 'خوراک کندل نامعتبر است' }}
      />,
    );
    expect(screen.getByTestId('ce-error').textContent).toContain('خوراک کندل نامعتبر است');
  });

  it('formats event dates as Jalali, not as raw epoch values', () => {
    renderPanel({ enabled: true, data });
    fireEvent.click(screen.getByTestId('ce-event-bos_bullish@50'));
    const detail = screen.getByTestId('ce-detail').textContent ?? '';
    expect(detail).not.toContain(String(parseCandleTimestamp(bars[50].timestamp)));
    expect(detail).toMatch(/۱۴۰[۰-۹]\/[۰-۹]{2}\/[۰-۹]{2}/);
  });
});
