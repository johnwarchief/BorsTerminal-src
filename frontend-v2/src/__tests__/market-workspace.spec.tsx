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
vi.mock('@features/market/panels/WatchPanel', () => ({
  WatchPanel: () => <div data-testid="watch-stub">دیده‌بان</div>,
}));
vi.mock('@app/shell/SymbolSidebar', () => ({
  SymbolSidebar: ({ row, symbolKey, boardDay }: {
    row: { symbol: string } | null;
    symbolKey: string | null;
    boardDay: number | null;
  }) => (
    <div data-testid="sidebar-stub" data-day={boardDay ?? ''}>{row?.symbol ?? symbolKey ?? 'خالی'}</div>
  ),
}));
vi.mock('@app/shell/BottomDock', () => ({
  BottomDock: ({ symbol }: { symbol: string | null }) => (
    <div data-testid="dock-stub">{symbol ?? 'خالی'}</div>
  ),
}));
vi.mock('@features/market/components/SnapshotStrip', () => ({
  SnapshotStrip: () => <div data-testid="strip-stub" />,
}));
vi.mock('@features/market/api/useBoard', () => ({
  useBoard: () => ({
    data: { data: [{ symbol: 'الف', ins_code: '10', name: 'الف' }], meta: { d_even: 20261028 } },
    isLoading: false, isError: false,
  }),
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
  it('renders the board, watch, sidebar and dock', () => {
    render(<MarketPage />);
    expect(screen.getByTestId('board-stub')).toBeTruthy();
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
    expect(screen.getByTestId('sidebar-stub')).toBeTruthy();
    expect(screen.getByTestId('dock-stub')).toBeTruthy();
    expect(screen.getByTestId('strip-stub')).toBeTruthy();
    expect(screen.queryByText('نماد')).toBeNull();
  });

  it('feeds the active row to the sidebar and the dock without navigating', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('board-stub'));
    expect(useWorkspace.getState().activeSymbol).toBe('10');
    expect(screen.getByTestId('sidebar-stub').textContent).toBe('الف');
    expect(screen.getByTestId('dock-stub').textContent).toBe('الف');
  });

  it('hands the feed board day to the sidebar before any row is clicked', () => {
    useWorkspace.setState({ activeSymbol: '10' });
    render(<MarketPage />);
    expect(screen.getByTestId('sidebar-stub').getAttribute('data-day')).toBe('20261028');
  });

  it('closes the watch tile and adds it back from the board menu', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(screen.queryByTestId('watch-stub')).toBeNull();
    fireEvent.click(screen.getByTestId('tile-menu-t-board'));
    fireEvent.click(screen.getByTestId('tile-add-watch'));
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
  });
});
