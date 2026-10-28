import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { MarketRow } from '@shared/types/market';
import { BoardTable } from '@features/market/components/BoardTable';
import { BoardToolbar } from '@features/market/components/BoardToolbar';
import { QuickDrawer } from '@features/market/components/QuickDrawer';
import { StatusStrip } from '@features/market/components/StatusStrip';
import { TapeBar } from '@features/market/components/TapeBar';
import { DEFAULT_BOARD_FILTER_VALUES } from '@features/market/lib/boardFilters';
import { defaultColumns } from '@features/market/lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import type { TapeKey } from '@features/market/lib/tapeFilters';

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

describe('status strip', () => {
  it('renders the four full-mode cards from the payload only', () => {
    const onMode = vi.fn();
    render(
      <StatusStrip
        feed={{ status: 'success', data: rows, count: 3, live_count: 2, fossil_count: 1 }}
        rows={rows}
        mode="full"
        onMode={onMode}
      />,
    );
    expect(screen.getByText('ارزش معاملات تابلو')).toBeTruthy();
    expect(screen.getByText('پهنا')).toBeTruthy();
    expect(screen.getByText('ترکیب تابلو')).toBeTruthy();
    expect(screen.getByText('تازگی داده')).toBeTruthy();
    expect(screen.getByText('مثبت')).toBeTruthy();
    fireEvent.click(screen.getByText('نوار'));
    expect(onMode).toHaveBeenLastCalledWith('ribbon');
  });

  it('switches from the ribbon and minimal modes', () => {
    const onMode = vi.fn();
    const { rerender } = render(<StatusStrip rows={rows} mode="ribbon" onMode={onMode} />);
    expect(screen.getByText('آخرین همگام‌سازی')).toBeTruthy();
    fireEvent.click(screen.getByText('کمینه'));
    expect(onMode).toHaveBeenLastCalledWith('minimal');

    rerender(<StatusStrip rows={rows} mode="minimal" onMode={onMode} />);
    expect(screen.getByText('آخرین همگام‌سازی')).toBeTruthy();
    expect(screen.getByText('همت')).toBeTruthy();
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

describe('quick drawer', () => {
  it('shows only the fields the feed carries and closes on request', () => {
    const onClose = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(
      JSON.stringify({ status: 'success', count: 0, data: [], limit: 50 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <QuickDrawer row={rows[0]!} filterConfig={DEFAULT_TAPE_FILTER_CONFIG} onClose={onClose} />
      </QueryClientProvider>,
    );
    expect(screen.getByText('آباد')).toBeTruthy();
    expect(screen.getByText('مشخصات بازار')).toBeTruthy();
    expect(screen.getByText('تابلوخوانی')).toBeTruthy();
    expect(screen.getByText('کپی نماد')).toBeTruthy();
    expect(screen.getByText('P/E')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('بستن جزئیات'));
    expect(onClose).toHaveBeenCalledTimes(1);
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
