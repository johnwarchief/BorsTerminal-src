import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { toFaDigits } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';
import { OrderBookFive } from '@features/market/components/OrderBookFive';
import { TapeHistoryPanel } from '@features/market/components/TapeHistoryPanel';
import { WatchlistButton } from '@features/market/components/WatchlistButton';
import { WatchPanel } from '@features/market/panels/WatchPanel';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';

vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
vi.mock('@features/fundamental/api/useFtsCard', async (original) => {
  const mod = await original<typeof import('@features/fundamental/api/useFtsCard')>();
  return { ...mod, useFtsCard: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});

function client(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

function withClient(ui: ReactElement): ReactElement {
  return <QueryClientProvider client={client()}>{ui}</QueryClientProvider>;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    ins_code: '1',
    symbol: 'فولاد',
    name: 'فولاد مبارکه',
    sector_name: 'فلزات اساسی',
    p_last: 1030,
    p_closing: 1000,
    price_yesterday: 980,
    percent_change: 2,
    percent_last: 5.1,
    q_tot_tran: 4000,
    q_tot_cap: 4_000_000,
    z_tot_tran: 100,
    vol_ratio_file: 4,
    prior30_vol: 1000,
    hist_sessions: 60,
    min_low_29: 900,
    is_live: true,
    f_clock: false,
    f_susp: false,
    f_roobi: false,
    ...patch,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('دیده‌بان‌های تابلو', () => {
  it('از تبِ ساعت شروع می‌کند، عضویت ساعت را از داوری canonical می‌گیرد و نماد را تحویل می‌دهد', () => {
    const onSelect = vi.fn();
    const rows = [
      row(),
      row({ ins_code: '2', symbol: 'خساپا', p_last: 1000, f_clock: true }),
    ];
    render(
      <WatchPanel
        rows={rows}
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        onSelect={onSelect}
        onPickSector={() => undefined}
      />,
    );

    expect(screen.getByTestId('watch-row-clock-1')).toBeTruthy();
    expect(screen.queryByTestId('watch-row-clock-2')).toBeNull();
    fireEvent.click(screen.getByTestId('watch-row-clock-1'));
    expect(onSelect).toHaveBeenCalledWith('1');
  });

  it('تعدادِ کاملِ دیده‌بان را نشان می‌دهد، نه فقط سقفِ ردیف‌های نمایش', () => {
    const rows = Array.from({ length: 18 }, (_, index) => row({
      ins_code: String(index + 1),
      symbol: `نماد${index + 1}`,
    }));
    render(
      <WatchPanel
        rows={rows}
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        onSelect={() => undefined}
      />,
    );

    expect(screen.getByTestId('watch-scope-label').textContent).toContain('کل تابلو');
    expect(screen.getByTestId('watch-count-clock').textContent).toContain('۱۵ از ۱۸');
    expect(screen.getAllByTestId(/^watch-row-clock-/)).toHaveLength(15);
  });

  it('حجم مشکوک و کف‌روبی نیز پرچمِ خامِ مخالفِ فرمول را قبول نمی‌کنند', () => {
    const rows = [
      row(),
      row({ ins_code: '2', symbol: 'خساپا', vol_ratio_file: 1, f_susp: true }),
      row({
        ins_code: '3', symbol: 'شپنا', p_last: 900, tmin: 900,
        percent_last: -2, buy_q1_cnt: 2, buy_q1_vol: 200,
      }),
    ];
    render(
      <WatchPanel
        rows={rows}
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        onSelect={() => undefined}
      />,
    );

    fireEvent.click(screen.getByTestId('watch-tab-susp'));
    expect(screen.getByTestId('watch-row-susp-1')).toBeTruthy();
    expect(screen.queryByTestId('watch-row-susp-2')).toBeNull();
    expect(screen.getByTestId('watch-row-roobi-3')).toBeTruthy();
  });

  it('صنعت را از خوراک واقعی می‌خواند و کلیک آن را به فیلتر تابلو تحویل می‌دهد', async () => {
    const onPickSector = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({
      status: 'success',
      leader: 'فلزات اساسی',
      rows: [
        { industry: 'فلزات اساسی', flow_b_toman: 120, avg_pct: 1.4 },
        { industry: 'خودرو', flow_b_toman: 90, avg_pct: 2.1 },
        { industry: 'بی‌داده', flow_b_toman: null, avg_pct: null },
      ],
    })));
    render(withClient(
      <WatchPanel
        rows={[]}
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        onSelect={() => undefined}
        onPickSector={onPickSector}
      />,
    ));

    fireEvent.click(screen.getByTestId('watch-tab-industries'));
    const pick = await screen.findByTestId('industry-pick-فلزات اساسی');
    expect(screen.queryByTestId('industry-pick-بی‌داده')).toBeNull();
    fireEvent.click(pick);
    expect(onPickSector).toHaveBeenCalledWith('فلزات اساسی');
  });
});

describe('دفتر سفارش و سابقهٔ مشاهده‌شده', () => {
  it('صفرِ واقعی را از سطرِ ثبت‌نشده جدا نمایش می‌دهد و با ins_code مشترک می‌شود', async () => {
    let watchBody: unknown = null;
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/orderbook/watch') {
        watchBody = JSON.parse(String(init?.body));
        return Promise.resolve(json({ status: 'success' }));
      }
      if (url === '/api/order-book/%D9%81%D9%88%D9%84%D8%A7%D8%AF') {
        return Promise.resolve(json({
          status: 'success',
          symbol: 'فولاد',
          levels: [{ buy_px: 1000, buy_vol: 0, buy_cnt: 0, sell_px: 0, sell_vol: 0, sell_cnt: 0 }],
          session: { d_even: 20261027, updated_at: '2026-10-27 11:30:42' },
          totals: { buy_vol: 0, buy_cnt: 0, sell_vol: null, sell_cnt: null },
        }));
      }
      return Promise.reject(new Error(`unexpected ${url} ${init?.method ?? 'GET'}`));
    }));
    render(withClient(<OrderBookFive symbol="فولاد" insCode="1" boardDay={20261027} />));

    const buy = await screen.findByTestId('order-book-level-buy-1');
    const sell = screen.getByTestId('order-book-level-sell-1');
    expect(watchBody).toEqual({ ins_code: '1' });
    expect(buy.getAttribute('data-state')).toBe('live');
    expect(within(buy).getAllByText(toFaDigits('0'))).toHaveLength(2);
    expect(sell.getAttribute('data-state')).toBe('empty');
    expect(within(sell).queryByText(toFaDigits('0'))).toBeNull();
    expect(within(sell).getAllByText('—')).toHaveLength(3);
  });

  it('عمقِ نشستِ کهنه را کهنه می‌گوید و جمعِ نشستِ تازه را با آن مخلوط نمی‌کند', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/orderbook/watch') return Promise.resolve(json({ status: 'success' }));
      if (url === '/api/order-book/%D9%81%D9%88%D9%84%D8%A7%D8%AF') {
        return Promise.resolve(json({
          status: 'success',
          symbol: 'فولاد',
          levels: [{ buy_px: 1000, buy_vol: 500, buy_cnt: 3, sell_px: 1010, sell_vol: 400, sell_cnt: 2 }],
          session: { d_even: 20261026, updated_at: '2026-10-26 09:57:00' },
          totals: { buy_vol: 900, buy_cnt: 8, sell_vol: 800, sell_cnt: 7 },
        }));
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }));
    render(withClient(<OrderBookFive symbol="فولاد" insCode="1" boardDay={20261027} />));

    const buy = await screen.findByTestId('order-book-level-buy-1');
    expect(buy.getAttribute('data-state')).toBe('stale');
    expect(screen.getByTestId('order-book-session-note').textContent).toContain('کهنه');
    expect(screen.queryByTestId('order-book-totals')).toBeNull();
  });

  it('روزِ ثبت‌نشده را از فیلترِ رصدشدهٔ خاموش جدا می‌کند', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({
      status: 'success',
      days: [20261026, 20261027],
      reliable_from: 20261026,
      flags: ['f_clock', 'f_susp'],
      by_symbol: {
        '1': {
          f_clock: {
            days: {
              '20261026': { active: true, first_at: '10:00', last_at: '10:04', passes: 2, evidence: {} },
            },
            total: 1,
            last_seen_at: '2026-10-26 10:04:00',
          },
          f_susp: {
            days: {
              '20261026': { active: false, first_at: null, last_at: null, passes: 0, evidence: {} },
            },
            total: 0,
            last_seen_at: null,
          },
        },
      },
    })));
    render(withClient(<TapeHistoryPanel insCode="1" symbol="فولاد" />));

    await screen.findByTestId('tape-history-فولاد');
    expect(screen.getByTestId('tape-history-cell-فولاد-f_clock-20261026').textContent).toContain('✓');
    expect(screen.getByTestId('tape-history-cell-فولاد-f_clock-20261027').getAttribute('title')).toBe('ثبت نشده');
    expect(screen.getByTestId('tape-history-cell-فولاد-f_susp-20261026').getAttribute('title')).toBe('رصد شد، فیلتر روشن نبود');
    expect(screen.getByTestId('tape-history-note-فولاد').textContent).toContain('قابل‌اعتماد');
  });
});

describe('گردش‌کار نماد و واچ‌لیست', () => {
  it('مسیرهای ناموجود را فعال وانمود نمی‌کند و بخش‌های عمق و سابقه را دارد', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/tape-history')) {
        return Promise.resolve(json({ status: 'success', days: [], reliable_from: null, flags: [], by_symbol: {} }));
      }
      if (url.startsWith('/api/order-book/')) {
        return Promise.resolve(json({
          status: 'success', symbol: 'فولاد', levels: [], session: { updated_at: null },
          totals: { buy_vol: null, buy_cnt: null, sell_vol: null, sell_cnt: null },
        }));
      }
      return Promise.resolve(json({ status: 'success', count: 0, data: [], limit: 50 }));
    }));
    render(withClient(
      <SymbolSidebar
        row={row()}
        symbolKey="1"
        boardDay={null}
        chartOpen={false}
        fundamentalsOpen
        onToggleChart={() => undefined}
        onToggleFundamentals={() => undefined}
      />,
    ));

    await screen.findByTestId('order-book');
    fireEvent.click(screen.getByTestId('symbol-tab-history'));
    expect(await screen.findByTestId('tape-history-empty-فولاد')).toBeTruthy();
    expect(screen.getByTestId('symbol-fund-summary')).toBeTruthy();
    expect(screen.getByTestId('symbol-fund-unavailable').textContent).toContain('در دسترس نیست');
  });

  it('افزودن و حذف واچ‌لیست از همان پنل به API واقعی می‌رسد', async () => {
    let listed = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/watchlist' && (!init?.method || init.method === 'GET')) {
        return Promise.resolve(json({
          status: 'success', count: listed ? 1 : 0, limit: 50,
          data: listed ? [{ norm: 'فولاد', symbol: 'فولاد', name: 'فولاد مبارکه', note: '', added_at: '2026-10-27' }] : [],
        }));
      }
      if (url === '/api/watchlist' && init?.method === 'POST') {
        listed = true;
        return Promise.resolve(json({ status: 'success', count: 1, limit: 50, existed: false }));
      }
      if (url.startsWith('/api/watchlist/') && init?.method === 'DELETE') {
        listed = false;
        return Promise.resolve(json({ status: 'success', deleted: 1 }));
      }
      if (url.startsWith('/api/order-book/') || url.startsWith('/api/tape-history')) {
        return Promise.resolve(json({ status: 'success', levels: [], days: [], flags: [], by_symbol: {}, reliable_from: null }));
      }
      return Promise.reject(new Error(`unexpected ${url} ${init?.method ?? 'GET'}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(withClient(
      <SymbolSidebar
        row={row()}
        symbolKey="1"
        boardDay={null}
        chartOpen={false}
        fundamentalsOpen
        onToggleChart={() => undefined}
        onToggleFundamentals={() => undefined}
      />,
    ));

    const add = await screen.findByRole('button', { name: 'افزودن به واچ‌لیست' });
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(add);
    const remove = await screen.findByRole('button', { name: 'حذف از واچ‌لیست' });
    await waitFor(() => expect((remove as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(remove);
    await screen.findByRole('button', { name: 'افزودن به واچ‌لیست' });

    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === '/api/watchlist' && (init as RequestInit | undefined)?.method === 'POST')).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).startsWith('/api/watchlist/') && (init as RequestInit | undefined)?.method === 'DELETE')).toBe(true);
  });
});

describe('پاکت خطای واچ‌لیست', () => {
  it('خطای status=error با HTTP 200 را در خواندن ناموفق می‌داند', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ status: 'error', message: 'بانک واچ‌لیست در دسترس نیست' })));
    render(withClient(<WatchlistButton symbol="فولاد" name="فولاد مبارکه" />));

    const button = await screen.findByRole('button', { name: 'واچ‌لیست در دسترس نیست' });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('خطای status=error در نوشتن را نشان می‌دهد و ردیف خوش‌بینانه را برمی‌گرداند', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/watchlist' && init?.method === 'POST') {
        return Promise.resolve(json({ status: 'error', message: 'سقف واچ‌لیست (۶۰ سهم) پر است', limit: 60 }));
      }
      if (url === '/api/watchlist') {
        return Promise.resolve(json({ status: 'success', count: 0, data: [], limit: 60 }));
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }));
    render(withClient(<WatchlistButton symbol="فولاد" name="فولاد مبارکه" />));

    const add = await screen.findByRole('button', { name: 'افزودن به واچ‌لیست' });
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(add);

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('سقف واچ‌لیست');
    await screen.findByRole('button', { name: 'افزودن به واچ‌لیست' });
  });
});
