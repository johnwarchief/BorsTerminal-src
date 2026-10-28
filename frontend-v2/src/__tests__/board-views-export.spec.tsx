import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { csvCell, csvTextWithMeta, saveBlob } from '@shared/lib/tableExport';
import type { MarketFeed, MarketRow } from '@shared/types/market';
import { useBoard } from '@features/market/api/useBoard';
import { useWorkspace } from '@shared/workspace/store';
import { BoardTable } from '@features/market/components/BoardTable';
import { BoardToolbar } from '@features/market/components/BoardToolbar';
import { BoardViewMenu } from '@features/market/components/BoardViewMenu';
import { boardExportTable } from '@features/market/lib/boardExport';
import { DEFAULT_BOARD_FILTER_VALUES } from '@features/market/lib/boardFilters';
import { defaultColumns } from '@features/market/lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { MarketPage } from '@features/market/routes/MarketPage';
import { useMarketPrefs, type BoardViewState } from '@features/market/stores/prefs';
import { Topbar } from '../app/shell/Topbar';

vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@features/market/api/useMarketSnapshot', () => ({
  useMarketSnapshot: () => ({ data: undefined, isLoading: false, isError: false }),
}));
vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@shared/lib/marketHours', () => ({
  effectivePollMs: (ms: number) => ms,
  sessionPollMs: (ms: number) => ms,
  isMarketOpen: () => true,
  CLOSED_POLL_MS: 300_000,
}));
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 30,
      getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ key: index, index, start: index * 30 })),
      measure: () => undefined,
      scrollToIndex: () => undefined,
    }),
  };
});
vi.mock('@shared/lib/tableExport', async (orig) => {
  const mod = await orig<typeof import('@shared/lib/tableExport')>();
  return { ...mod, saveBlob: vi.fn() };
});
vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
vi.mock('@features/fundamental/api/useFtsCard', async (original) => {
  const mod = await original<typeof import('@features/fundamental/api/useFtsCard')>();
  return { ...mod, useFtsCard: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});

const mockedUseBoard = vi.mocked(useBoard);
const mockedSaveBlob = vi.mocked(saveBlob);
const noop = () => undefined;

function blobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

function blobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

function marketRow(patch: Partial<MarketRow> & { symbol: string }): MarketRow {
  return {
    ins_code: patch.symbol,
    name: `${patch.symbol} نام`,
    sector_name: 'فلزات اساسی',
    is_live: true,
    p_last: 100,
    p_closing: 98,
    price_yesterday: 95,
    percent_change: 3,
    q_tot_cap: 1_000_000_000,
    ...patch,
  };
}

const feed: MarketFeed = {
  status: 'success',
  data: [
    marketRow({ symbol: 'الف', q_tot_cap: 1_000_000_000 }),
    marketRow({ symbol: 'ب', q_tot_cap: 3_000_000_000, p_last: 200 }),
    marketRow({ symbol: 'مخفی', q_tot_cap: 9_000_000_000, is_live: false }),
  ],
  count: 3,
  live_count: 2,
  fossil_count: 1,
  rev: 7,
  rev_at: 400_000,
  meta: { d_even: 20261027, h_even: 120000, last_sync: '2026-10-27 12:00:00' },
};

const snapshot: BoardViewState = {
  query: 'فولاد',
  sortKey: 'pct_close',
  sortDir: 'asc',
  profile: 'trading',
  density: 'normal',
  quickFilters: ['f_clock'],
  quickLogic: 'or',
  assetTypes: ['stock'],
  visibleColumns: ['symbol', 'last', 'pct_close'],
  filters: {
    sector: 'فلزات اساسی',
    liveOnly: false,
    direction: 'pos',
    volRatioOn: true,
    volRatioMin: 4,
    exitAccum: true,
    showNumericSuffix: true,
  },
  pollMs: 15_000,
};

beforeEach(() => {
  localStorage.clear();
  useMarketPrefs.persist.clearStorage();
  useMarketPrefs.setState(useMarketPrefs.getInitialState(), true);
  useWorkspace.setState(useWorkspace.getInitialState(), true);
  mockedUseBoard.mockReturnValue({
    data: feed,
    dataUpdatedAt: 400_000,
    status: 'success',
    isError: false,
    isLoading: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useBoard>);
  vi.spyOn(Date, 'now').mockReturnValue(400_000);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('نماهای ذخیره‌شدهٔ تابلو', () => {
  it('ذخیره و بازیابی، همهٔ فیلترها و ستون‌ها را بدون ریزش برمی‌گرداند', () => {
    act(() => useMarketPrefs.getState().saveView('  صبح  ', snapshot));
    expect(useMarketPrefs.getState().savedViews.map((view) => view.name)).toEqual(['صبح']);

    act(() => {
      useMarketPrefs.getState().setProfile('fundamental');
      useMarketPrefs.getState().setQuickLogic('and');
      useMarketPrefs.getState().setFilters({ sector: '', direction: 'all' });
    });
    let restored: BoardViewState | null = null;
    act(() => { restored = useMarketPrefs.getState().restoreView('صبح'); });

    expect(restored).toEqual(snapshot);
    const state = useMarketPrefs.getState();
    expect(state.profile).toBe(snapshot.profile);
    expect(state.visibleColumns).toEqual(snapshot.visibleColumns);
    expect(state.quickFilters).toEqual(snapshot.quickFilters);
    expect(state.quickLogic).toBe(snapshot.quickLogic);
    expect(state.assetTypes).toEqual(snapshot.assetTypes);
    expect(state.filters).toEqual(snapshot.filters);
    expect(state.density).toBe(snapshot.density);
    expect(state.pollMs).toBe(snapshot.pollMs);
  });

  it('بازیابی از صفحه، جستجو و مرتب‌سازی محلی را هم برمی‌گرداند', () => {
    render(<MarketPage />);
    fireEvent.change(screen.getByTestId('board-search'), { target: { value: 'الف' } });
    fireEvent.click(document.querySelector('[data-sort="last"]')!);
    fireEvent.click(screen.getByTestId('saved-views-btn'));
    fireEvent.change(screen.getByTestId('view-name-input'), { target: { value: 'صبح' } });
    fireEvent.click(screen.getByTestId('save-view-btn'));

    fireEvent.change(screen.getByTestId('board-search'), { target: { value: '' } });
    fireEvent.click(document.querySelector('[data-sort="value"]')!);
    fireEvent.click(screen.getByTestId('view-apply-صبح'));

    expect((screen.getByTestId('board-search') as HTMLInputElement).value).toBe('الف');
    expect(document.querySelector('[data-sort="last"]')?.textContent).toContain('▼');
    expect(document.querySelector('[data-sort="value"]')?.textContent).not.toContain('▼');
  });

  it('نرخ پایشِ نمای ذخیره‌شده در ناظرِ نوار بالا هم اعمال می‌شود', () => {
    useMarketPrefs.setState({ pollMs: 15_000 });
    mockedUseBoard.mockClear();
    render(<Topbar />);
    expect(mockedUseBoard).toHaveBeenCalledWith(15_000);
  });

  it('Escape منوی نماها فوکوس را به دکمهٔ آغازگر برمی‌گرداند', () => {
    render(<BoardViewMenu views={[{ name: 'صبح', state: snapshot }]} onSave={noop} onApply={noop} onDelete={noop} />);
    const trigger = screen.getByTestId('saved-views-btn');
    fireEvent.click(trigger);
    expect(document.activeElement).toBe(screen.getByTestId('view-name-input'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('اعمالِ نما پس از بستنِ منو فوکوس را به دکمهٔ آغازگر برمی‌گرداند', () => {
    const onApply = vi.fn();
    render(<BoardViewMenu views={[{ name: 'صبح', state: snapshot }]} onSave={noop} onApply={onApply} onDelete={noop} />);
    const trigger = screen.getByTestId('saved-views-btn');
    fireEvent.click(trigger);
    fireEvent.click(screen.getByTestId('view-apply-صبح'));
    expect(onApply).toHaveBeenCalledWith('صبح');
    expect(document.activeElement).toBe(trigger);
  });

  it('حذفِ نما فوکوس را به ورودیِ نامِ نمای تازه می‌برد', () => {
    render(<BoardViewMenu views={[{ name: 'صبح', state: snapshot }]} onSave={noop} onApply={noop} onDelete={noop} />);
    fireEvent.click(screen.getByTestId('saved-views-btn'));
    const remove = screen.getByRole('button', { name: 'حذف نمای صبح' });
    act(() => remove.focus());
    fireEvent.click(remove);
    expect(document.activeElement).toBe(screen.getByTestId('view-name-input'));
  });
});

describe('خروجی تابلو', () => {
  it('سرستون و سلول‌ها را از ستون‌های واقعی همان نما می‌سازد', () => {
    const table = boardExportTable(
      [marketRow({ symbol: 'الف', f_clock: true })],
      ['symbol', 'last', 'patterns'],
      DEFAULT_TAPE_FILTER_CONFIG,
    );
    expect(table.columns).toEqual(['نماد', 'آخرین', 'الگو']);
    expect(table.rows).toHaveLength(1);
    expect(table.rows[0]?.[0]).toContain('الف');
    expect(table.rows[0]?.[1]).toBe('۱۰۰');
  });

  it('جداکننده، escaping و ردپای منبع را با قرارداد مرجع حفظ می‌کند', () => {
    const text = csvTextWithMeta(
      { columns: ['نماد', 'یادداشت'], rows: [['الف', ' نیم; "رصد"\n']] },
      [['منبع', '/api/market']],
    );
    expect(text.startsWith('sep=;\r\nنماد;یادداشت\r\n')).toBe(true);
    expect(text).toContain('" نیم; ""رصد""\n"');
    expect(text).toContain('\r\n\r\n# منبع;/api/market\r\n');
  });

  it('شروعِ فرمولیِ سلول‌های متنی را برای صفحه‌گسترده بی‌اثر می‌کند', () => {
    expect(csvCell('=1+1')).toBe("'=1+1");
    expect(csvCell(' =1+1')).toBe('"\' =1+1"');
    expect(csvCell('\t@SUM(1;2)')).toBe('"\'\t@SUM(1;2)"');
    expect(csvCell('+12')).toBe("'+12");
    expect(csvCell('-12')).toBe("'-12");
    expect(csvCell(-12)).toBe('-12');
    expect(csvCell('الف')).toBe('الف');
  });

  it('دانلود فقط ردیف‌های فیلترشده را به ترتیبِ روی تابلو و با BOM می‌دهد', async () => {
    useMarketPrefs.setState({ visibleColumns: ['symbol', 'last', 'value'] });
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('export-board'));

    expect(mockedSaveBlob).toHaveBeenCalledTimes(1);
    const [blob, filename] = mockedSaveBlob.mock.calls[0]!;
    const bytes = await blobBytes(blob);
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
    const text = await blobText(blob);
    expect(text).toContain('sep=;\r\n');
    expect(text).not.toContain('مخفی');
    const lines = text.split('\r\n').filter((line) => line.startsWith('الف — ') || line.startsWith('ب — '));
    expect(lines[0]?.startsWith('ب — ')).toBe(true);
    expect(lines[1]?.startsWith('الف — ')).toBe(true);
    expect(text).toContain('# منبع;/api/market');
    expect(filename).toMatch(/\.csv$/);
  });
});

describe('صفحه‌کلید و فوکوس', () => {
  it.each([{ ctrlKey: true }, { metaKey: true }])('میان‌بر جستجو با $ctrlKey/$metaKey فوکوس را می‌برد', (modifier) => {
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
    fireEvent.keyDown(window, { key: 'k', ...modifier });
    expect(document.activeElement).toBe(screen.getByTestId('board-search'));
  });

  it('پیکان‌ها و Home/End فوکوس سیار را حرکت می‌دهند و Enter/Space نماد را باز می‌کنند', async () => {
    const onSelect = vi.fn();
    const rows = [marketRow({ symbol: 'الف' }), marketRow({ symbol: 'ب' }), marketRow({ symbol: 'ج' })];
    render(
      <BoardTable
        rows={rows}
        columns={['symbol', 'last']}
        sortKey="value"
        sortDir="desc"
        density="compact"
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        selectedKey={null}
        resetKey="keyboard"
        onSort={noop}
        onSelect={onSelect}
      />,
    );
    const rendered = screen.getAllByTestId('board-row');
    expect(rendered.map((row) => row.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);

    act(() => rendered[0]!.focus());
    fireEvent.keyDown(rendered[0]!, { key: 'ArrowDown' });
    await waitFor(() => expect(document.activeElement).toBe(rendered[1]));
    fireEvent.keyDown(rendered[1]!, { key: 'End' });
    await waitFor(() => expect(document.activeElement).toBe(rendered[2]));
    fireEvent.keyDown(rendered[2]!, { key: 'Home' });
    await waitFor(() => expect(document.activeElement).toBe(rendered[0]));
    fireEvent.keyDown(rendered[0]!, { key: 'Enter' });
    expect(onSelect).toHaveBeenLastCalledWith(rows[0]);
    fireEvent.keyDown(rendered[0]!, { key: 'ArrowDown' });
    await waitFor(() => expect(document.activeElement).toBe(rendered[1]));
    fireEvent.keyDown(rendered[1]!, { key: ' ' });
    expect(onSelect).toHaveBeenLastCalledWith(rows[1]);
  });

  it('با کم‌شدن ردیف‌ها، توقفِ تب و فوکوس روی یک ردیفِ موجود می‌ماند', async () => {
    const rows = [marketRow({ symbol: 'الف' }), marketRow({ symbol: 'ب' }), marketRow({ symbol: 'ج' })];
    const props = {
      columns: ['symbol', 'last'] as const,
      sortKey: 'value' as const,
      sortDir: 'desc' as const,
      density: 'compact' as const,
      filterConfig: DEFAULT_TAPE_FILTER_CONFIG,
      selectedKey: null,
      resetKey: 'keyboard-shrink',
      onSort: noop,
      onSelect: noop,
    };
    const { rerender } = render(<BoardTable {...props} rows={rows} />);
    act(() => screen.getAllByTestId('board-row')[2]!.focus());

    rerender(<BoardTable {...props} rows={rows.slice(0, 1)} />);

    const remaining = screen.getAllByTestId('board-row');
    expect(remaining).toHaveLength(1);
    expect(remaining[0]!.getAttribute('tabindex')).toBe('0');
    await waitFor(() => expect(document.activeElement).toBe(remaining[0]));
  });

  it('میان‌بر جستجو با پنلِ نمادِ باز، فوکوس را به جستجو می‌برد', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MarketPage /></QueryClientProvider>);
    const first = screen.getAllByTestId('board-row')[0]!;
    act(() => first.focus());
    fireEvent.keyDown(first, { key: 'Enter' });
    await waitFor(() => expect(screen.getByTestId('symbol-title')).toBeTruthy());

    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('board-search')));
    client.clear();
  });

  it('ردیفِ هم‌نام با ins_code خودش باز می‌شود، نه اولین ردیفِ آن نماد', async () => {
    const duplicateFeed: MarketFeed = {
      ...feed,
      data: [
        marketRow({ symbol: 'دوقلو', name: 'تازه', ins_code: '10', q_tot_cap: 3_000_000_000, is_live: true }),
        marketRow({ symbol: 'دوقلو', name: 'قدیمی', ins_code: '20', q_tot_cap: 1_000_000_000, is_live: false }),
      ],
      count: 2,
      live_count: 1,
      fossil_count: 1,
    };
    mockedUseBoard.mockReturnValue({
      data: duplicateFeed,
      dataUpdatedAt: 400_000,
      status: 'success',
      isError: false,
      isLoading: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useBoard>);
    useMarketPrefs.setState({ filters: { ...DEFAULT_BOARD_FILTER_VALUES, liveOnly: false } });
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(<QueryClientProvider client={client}><MarketPage /></QueryClientProvider>);
    const old = screen.getAllByTestId('board-row').find((item) => item.textContent?.includes('قدیمی'));
    expect(old).toBeDefined();
    fireEvent.click(old!);

    const sidebar = await waitFor(() => screen.getByTestId('symbol-sidebar'));
    expect(sidebar.textContent).toContain('قدیمی');
    expect(sidebar.textContent).not.toContain('تازه');
    client.clear();
  });

  it('Enter روی ردیف، نماد را در پنل می‌نشاند و فوکوس روی همان ردیف می‌ماند', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/watchlist') {
        return Promise.resolve(new Response(JSON.stringify({ status: 'success', data: [], count: 0, limit: 50 }), { status: 200 }));
      }
      if (url.startsWith('/api/order-book/')) {
        const symbol = decodeURIComponent(url.slice('/api/order-book/'.length));
        return Promise.resolve(new Response(JSON.stringify({
          status: 'success', symbol, levels: [], session: { updated_at: null },
          totals: { buy_vol: null, buy_cnt: null, sell_vol: null, sell_cnt: null },
        }), { status: 200 }));
      }
      if (url === '/api/orderbook/watch') {
        return Promise.resolve(new Response(JSON.stringify({ status: 'success' }), { status: 200 }));
      }
      if (url.startsWith('/api/tape-history')) {
        return Promise.resolve(new Response(JSON.stringify({
          status: 'success', days: [], reliable_from: null, flags: [], by_symbol: {},
        }), { status: 200 }));
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><MarketPage /></QueryClientProvider>);
    const first = screen.getAllByTestId('board-row')[0]!;
    act(() => first.focus());
    fireEvent.keyDown(first, { key: 'Enter' });

    await waitFor(() => expect(screen.getByTestId('symbol-title')).toBeTruthy());
    await waitFor(() => expect(document.activeElement).toBe(first));
    client.clear();
  });
});
