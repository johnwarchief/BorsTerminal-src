import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { MarketRow } from '@shared/types/market';
import { BoardTable } from '@features/market/components/BoardTable';
import { BoardToolbar } from '@features/market/components/BoardToolbar';
import { SnapshotStrip } from '@features/market/components/SnapshotStrip';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';
import { TapeBar } from '@features/market/components/TapeBar';
import { DEFAULT_BOARD_FILTER_VALUES } from '@features/market/lib/boardFilters';
import { defaultColumns } from '@features/market/lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import type { TapeKey } from '@features/market/lib/tapeFilters';
import { useWorkspace } from '@shared/workspace/store';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const rows: MarketRow[] = [
  {
    symbol: 'آباد',
    name: 'توریستی ورفاهی آبادگران ایران',
    sector_name: 'هتل و رستوران',
    p_last: 1392,
    p_closing: 1392,
    price_yesterday: 1352,
    price_change: 40,
    percent_change: null,
    q_tot_tran: 217797702,
    q_tot_cap: 303174401184,
    pe: 8.4,
    mcap: 2.5e13,
    f_smart: 1,
    f_jet: 0,
  },
  {
    symbol: 'فولاد',
    name: 'فولاد مبارکه اصفهان',
    sector_name: 'فلزات اساسی',
    p_last: 5000,
    p_closing: 4980,
    price_yesterday: 5000,
    price_change: -20,
    percent_change: -0.4,
    q_tot_tran: 1_000_000_000,
    q_tot_cap: 5e12,
    f_smart: 0,
    f_jet: true,
  },
  {
    symbol: 'خساپا',
    name: 'سایپا',
    sector_name: 'خودرو',
    p_last: null,
    p_closing: 2100,
    price_yesterday: 2100,
    price_change: 0,
    percent_change: 0,
  },
];

const zeroCounts: Record<TapeKey, number> = {
  f_smart: 0,
  f_legal: 0,
  f_roobi: 0,
  f_susp: 0,
  f_clock: 0,
  f_noqteh: 0,
  f_jet: 0,
};

const noop = () => undefined;

describe('tape bar', () => {
  it('toggles tapes independently and switches the AND/OR verdict', () => {
    const onToggle = vi.fn();
    const onLogic = vi.fn();
    const { rerender } = render(
      <TapeBar
        counts={{ ...zeroCounts, f_smart: 7 }}
        unevaluated={zeroCounts}
        hiddenCounts={zeroCounts}
        baseCount={3}
        active={[]}
        logic="and"
        onToggle={onToggle}
        onClear={noop}
        onLogic={onLogic}
      />,
    );
    fireEvent.click(screen.getByTestId('tape-f_smart'));
    expect(onToggle).toHaveBeenLastCalledWith('f_smart');

    rerender(
      <TapeBar
        counts={zeroCounts}
        unevaluated={zeroCounts}
        hiddenCounts={zeroCounts}
        baseCount={3}
        active={['f_smart', 'f_jet']}
        logic="and"
        onToggle={onToggle}
        onClear={noop}
        onLogic={onLogic}
      />,
    );
    expect(screen.getByTestId('tape-f_smart').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('tape-f_jet').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('tape-f_smart'));
    expect(onToggle).toHaveBeenLastCalledWith('f_smart');
    fireEvent.click(screen.getByRole('button', { name: 'یا' }));
    expect(onLogic).toHaveBeenLastCalledWith('or');
  });

  it('clears every selected tape through «همه»', () => {
    const onClear = vi.fn();
    render(
      <TapeBar
        counts={zeroCounts}
        unevaluated={zeroCounts}
        hiddenCounts={zeroCounts}
        baseCount={3}
        active={['f_jet']}
        logic="and"
        onToggle={noop}
        onClear={onClear}
        onLogic={noop}
      />,
    );
    fireEvent.click(screen.getByText('همه'));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});

describe('snapshot strip', () => {
  it('renders one card per slot with board values and honest dashes', () => {
    useWorkspace.setState(useWorkspace.getInitialState(), true);
    render(<SnapshotStrip rows={rows} />);
    expect(screen.getByTestId('card-tedpix').textContent).toContain('—');
    expect(screen.getByTestId('card-retailValue').textContent).toContain('—');
    expect(screen.getByTestId('card-breadth').textContent).toContain('▲');
    expect(screen.getByTestId('card-boardValueComposition').textContent).toContain('همت');
  });

  it('the number of cards follows the saved slots', () => {
    useWorkspace.setState(useWorkspace.getInitialState(), true);
    render(<SnapshotStrip rows={rows} />);
    expect(screen.getAllByTestId(/^card-[a-zA-Z]+$/)).toHaveLength(4);
    act(() => {
      useWorkspace.getState().setSlots(['tedpix', 'retailValue', 'breadth', 'boardValueComposition', 'boardVolume']);
    });
    expect(screen.getAllByTestId(/^card-[a-zA-Z]+$/)).toHaveLength(5);
  });
});

describe('board toolbar', () => {
  it('changes the column profile', () => {
    const onProfile = vi.fn();
    render(
      <BoardToolbar
        query=""
        onQuery={noop}
        profile="general"
        onProfile={onProfile}
        density="compact"
        onDensity={noop}
        columns={defaultColumns('general')}
        onToggleColumn={noop}
        assetTypes={['stock', 'payeh', 'right', 'energy', 'fund']}
        onAssetTypes={noop}
        filters={DEFAULT_BOARD_FILTER_VALUES}
        onFilters={noop}
        sectors={[]}
        pollMs={5_000}
        onPollMs={noop}
      />,
    );
    fireEvent.click(screen.getByTestId('profile-fundamental'));
    expect(onProfile).toHaveBeenLastCalledWith('fundamental');
  });

  it('marks unreachable columns «وصل نیست» instead of showing fake data', () => {
    render(
      <BoardToolbar
        query=""
        onQuery={noop}
        profile="general"
        onProfile={noop}
        density="compact"
        onDensity={noop}
        columns={defaultColumns('general')}
        onToggleColumn={noop}
        assetTypes={['stock']}
        onAssetTypes={noop}
        filters={DEFAULT_BOARD_FILTER_VALUES}
        onFilters={noop}
        sectors={[]}
        pollMs={5_000}
        onPollMs={noop}
      />,
    );
    fireEvent.click(screen.getByTestId('columns-btn'));
    expect(screen.getAllByText('وصل نیست')).toHaveLength(2);
    expect(screen.getByText('EPS')).toBeTruthy();
    expect(screen.getByText('اسکن')).toBeTruthy();
  });
});

describe('symbol panel', () => {
  it('shows the feed fields and honest dashes', () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(
      JSON.stringify({ status: 'success', count: 0, data: [], limit: 50 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <SymbolSidebar
          variant="narrow"
          row={rows[0]!}
          symbolKey={rows[0]!.symbol}
          boardDay={null}
          chartOpen={false}
          fundamentalsOpen
          onToggleChart={noop}
          onToggleFundamentals={noop}
        />
      </QueryClientProvider>,
    );
    expect(screen.getByTestId('symbol-title').textContent).toContain('آباد');
    expect(screen.getByText('P/E')).toBeTruthy();
    expect(screen.getByTestId('symbol-stat-pe').textContent).toContain('۸');
    expect(screen.getByTestId('symbol-chart-toggle').textContent).toContain('باز');
    queryClient.clear();
  });
});

describe('board table', () => {
  it('renders the reachable headers and sorts on click', () => {
    const onSort = vi.fn();
    render(
      <BoardTable
        rows={rows}
        columns={defaultColumns('general')}
        sortKey="value"
        sortDir="desc"
        density="compact"
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        selectedKey={null}
        resetKey="test"
        onSort={onSort}
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByText('نماد')).toBeTruthy();
    expect(screen.getByText('آخرین')).toBeTruthy();
    expect(screen.getByText('ارزش بازار')).toBeTruthy();
    expect(screen.queryByText('EPS')).toBeNull();
    fireEvent.click(screen.getByText('آخرین'));
    expect(onSort).toHaveBeenLastCalledWith('last');
  });
});
