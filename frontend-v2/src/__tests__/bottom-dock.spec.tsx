import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BottomDock } from '@app/shell/BottomDock';

vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@features/fundamental/ui/FundamentalCards', () => ({
  FundamentalCards: ({ symbol }: { symbol: string }) => <div data-testid="cards-stub">{symbol}</div>,
}));

afterEach(cleanup);

function mount(patch: Partial<Parameters<typeof BottomDock>[0]> = {}) {
  return render(
    <BottomDock
      symbol="فولاد"
      chartOpen
      fundamentalsOpen
      height={200}
      chartShare={0.45}
      onToggleChart={() => undefined}
      onToggleFundamentals={() => undefined}
      onHeightChange={() => undefined}
      onChartShareChange={() => undefined}
      {...patch}
    />,
  );
}

describe('BottomDock', () => {
  it('splits the open dock into a chart on the right and the five cards beside it', () => {
    mount();
    expect(screen.getByTestId('bottom-dock').getAttribute('style')).toContain('height: 200px');
    expect(screen.getByTestId('chart-stub').textContent).toBe('فولاد');
    expect(screen.getByTestId('cards-stub').textContent).toBe('فولاد');
    expect(screen.getByTestId('dock-chart').getAttribute('style')).toContain('width: 45%');
    expect(screen.getAllByRole('separator')).toHaveLength(2);
  });

  it('gives the whole width to the single open group', () => {
    mount({ fundamentalsOpen: false });
    expect(screen.getByTestId('dock-chart').getAttribute('style')).toBeNull();
    expect(screen.queryByTestId('dock-fundamentals')).toBeNull();
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });

  it('collapses to two chips when both groups are closed', () => {
    const onToggleChart = vi.fn();
    const onToggleFundamentals = vi.fn();
    mount({ chartOpen: false, fundamentalsOpen: false, onToggleChart, onToggleFundamentals });
    expect(screen.queryByTestId('bottom-dock')).toBeNull();
    fireEvent.click(screen.getByTestId('dock-open-chart'));
    fireEvent.click(screen.getByTestId('dock-open-fundamental'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    expect(onToggleFundamentals).toHaveBeenCalledTimes(1);
  });

  it('keeps an honest empty message for each group without a symbol', () => {
    mount({ symbol: null });
    expect(screen.getByTestId('dock-chart-empty')).toBeTruthy();
    expect(screen.getByTestId('dock-fundamentals-empty')).toBeTruthy();
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    expect(screen.queryByTestId('cards-stub')).toBeNull();
  });
});
