import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketPage } from '@features/market/routes/MarketPage';
import { useWorkspace } from '@shared/workspace/store';

vi.mock('@features/market/panels/BoardPanel', () => ({
  BoardPanel: ({ onSelect }: { onSelect: (row: unknown, day: number) => void }) => (
    <button type="button" data-testid="board-stub"
      onClick={() => onSelect({ symbol: 'الف', ins_code: '10', name: 'الف' }, 20261028)}>
      تابلو
    </button>
  ),
}));
vi.mock('@features/market/panels/SymbolPanel', () => ({
  SymbolPanel: ({ row }: { row: { symbol: string } | null }) => (
    <div data-testid="symbol-stub">{row?.symbol ?? 'خالی'}</div>
  ),
}));
vi.mock('@features/market/panels/WatchPanel', () => ({
  WatchPanel: () => <div data-testid="watch-stub">دیده‌بان</div>,
}));
vi.mock('@features/chart/ui/ChartPanel', () => ({ ChartPanel: () => <div data-testid="chart-stub" /> }));
vi.mock('@features/market/components/SnapshotStrip', () => ({
  SnapshotStrip: () => <div data-testid="strip-stub" />,
}));
vi.mock('@features/market/api/useBoard', () => ({
  useBoard: () => ({ data: { data: [], meta: { d_even: 20261028 } }, isLoading: false, isError: false }),
}));
vi.mock('@features/market/api/useMarketSnapshot', () => ({
  useMarketSnapshot: () => ({ data: undefined, isLoading: false, isError: false }),
}));

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

afterEach(cleanup);

describe('market workspace', () => {
  it('renders the default tiles', () => {
    render(<MarketPage />);
    expect(screen.getByTestId('board-stub')).toBeTruthy();
    expect(screen.getByTestId('symbol-stub')).toBeTruthy();
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
    expect(screen.getByTestId('strip-stub')).toBeTruthy();
  });

  it('sets the active symbol from the board without navigating', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('board-stub'));
    expect(useWorkspace.getState().activeSymbol).toBe('10');
    expect(screen.getByTestId('symbol-stub').textContent).toBe('الف');
  });

  it('closes the watch tile from its header', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(screen.queryByTestId('watch-stub')).toBeNull();
  });

  it('opens the chart tile from the symbol menu', () => {
    render(<MarketPage />);
    const before = screen.getAllByTestId(/^tile-header-/).length;
    fireEvent.click(screen.getByTestId('tile-menu-t-symbol'));
    fireEvent.click(screen.getByTestId('tile-split-t-symbol-col-chart'));
    expect(screen.getAllByTestId(/^tile-header-/).length).toBe(before + 1);
    expect(screen.getByText('چارت')).toBeTruthy();
  });
});
