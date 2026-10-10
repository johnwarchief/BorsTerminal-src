// تستِ جدولِ زنده و پنلِ اجرای «دیده‌بان بازار»
//
// رأیِ مالک: دیده‌بان باید جدولِ زندهٔ کامل با ستون‌های تقاضا/عرضه باشد و پنلِ
// راست از امروز برایِ ربات آماده باشد، بی‌اینکه هیچ سفارشِ واقعی برود. پس این
// فایل سه چیز را می‌سنجد: (1) ستون‌هایِ تازه از همان فیدِ مشترک می‌آیند و
// صفرِ صف با «بی‌داده» و با «۰» یکی نمی‌شود؛ (2) کلیک رویِ ردیف هر سه پنلِ
// پایین را رویِ همان نماد می‌بَرَد؛ (3) درِ غیابِ سرویسِ اجرا، خرید/فروش و
// Kill Switch غیرفعال‌اند و دلیلش از پاسخِ سرویس خوانده می‌شود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WatchTable } from '@features/portfolio/components/WatchTable';
import { WatchSummaryPanel } from '@features/portfolio/components/WatchSummaryPanel';
import { deriveGate } from '@features/portfolio/lib/orderClient';
import { resetMarketFeedMirror } from '@shared/api/marketFeed';
import { useWatchSymbolsStore } from '@features/portfolio/stores/watchSymbolsStore';
import type { MarketFeed, MarketRow } from '@shared/types/marketRow';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا', name: 'پالایش نفت اصفهان', ins_code: 'A1',
    p_last: 1025, p_closing: 1000, p_first: 990, p_max: 1040, p_min: 980,
    percent_change: 2.5, q_tot_tran: 5_000_000, z_tot_tran: 320, q_tot_cap: 5_125_000_000,
    buy_q1_px: 1024, buy_q1_vol: 44_600, sell_q1_px: 1026, sell_q1_vol: 9_846,
    row_h: 102335, is_live: true, ...patch,
  } as MarketRow;
}

function feed(rows: MarketRow[]) {
  return { status: 'success', rev: 3, count: rows.length, live_count: rows.length,
           fossil_count: 0, meta: { d_even: 20261010, h_even: 102335 }, data: rows } as MarketFeed;
}

function mockFeed(rows: MarketRow[], status?: unknown) {
  fetchMock.mockImplementation((url: string) => {
    if (String(url).includes('/api/execution/status')) {
      return status === 'absent'
        ? Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response)
        : Promise.resolve(json(status));
    }
    return Promise.resolve(json(feed(rows)));
  });
}

/** خانۀ کندل حالا همیشه رندر می‌شود (حتی بی‌داده، با «—»ِ صریح)؛ پس «حاضر
 *  بودنش» دیگر نشانۀ رسیدنِ ردیف نیست — آزمون رویِ سطرِ خالی رد می‌شد و سبز
 *  می‌ماند (همان دامی که دورِ پیش درِ همین پرونده دیدیم). منتظر همان مقداری
 *  می‌نشینیم که فقط با ردیفِ فید رویِ سطر می‌آید. */
const cellHas = (testId: string, text: string) =>
  waitFor(() => expect(screen.getByTestId(testId).textContent).toContain(text), { timeout: 4000 });
const drawnCandles = () =>
  document.querySelectorAll('[data-testid="watch-day-candle"]:not([data-state="incomplete"])').length;
const candlesDrawn = (n: number) => waitFor(() => expect(drawnCandles()).toBe(n), { timeout: 4000 });

function renderTable(rows: MarketRow[], onSelect = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <WatchTable symbols={rows.map((r) => r.symbol)} selected="" onSelect={onSelect} onRemove={() => {}} />
    </QueryClientProvider>,
  );
  return onSelect;
}

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  useWatchSymbolsStore.setState({ symbols: [] });
});

describe('ستون‌هایِ مرجعِ جدول دیده‌بان', () => {
  it('قیمت و حجمِ تقاضا/عرضه از همان ردیفِ فید می‌آیند (بی‌درخواستِ عمق ردیف‌به‌ردیف)', async () => {
    mockFeed([row()]);
    renderTable([row()]);
    const tr = screen.getByTestId('watch-row-شپنا');
    await cellHas('watch-row-شپنا', '۱٬۰۲۴');
    expect(tr.textContent).toContain('۱٬۰۲۴');// قیمت تقاضا
    expect(tr.textContent).toContain('۱٬۰۲۶');// قیمت عرضه
    expect(tr.textContent).toContain('۴۴٬۶۰۰');// حجم تقاضا
    expect(tr.textContent).toContain('۹٬۸۴۶');// حجم عرضه
    expect(tr.textContent).toContain('۱۰:۲۳');   // ساعتِ خودِ ردیف
    // فقط یک درخواستِ فید؛ هیچ /api/order-book ردیف‌به‌ردیف زده نمی‌شود
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.filter((u) => u.includes('order-book'))).toHaveLength(0);
    expect(urls.filter((u) => u.includes('/api/market')).length).toBeLessThanOrEqual(1);
  });

  it('صفرِ واقعیِ صف «بی‌صف» است، نه «—» و نه «۰»؛ نبودِ کلید «—» است', async () => {
    const zero = row({ symbol: 'خودرو', sell_q1_px: 0, sell_q1_vol: 0 });
    const bare = row({ symbol: 'فولاد', buy_q1_px: undefined, buy_q1_vol: undefined });
    mockFeed([zero, bare]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <WatchTable symbols={['خودرو', 'فولاد']} selected="" onSelect={() => {}} onRemove={() => {}} />
      </QueryClientProvider>,
    );
    await cellHas('watch-row-خودرو', 'بی‌صف');
    expect(screen.getByTestId('watch-row-فولاد').textContent).toContain('—');
  });

  it('کندلِ روز از اول/بیشینه/کمینه/آخرینِ همان ردیف ساخته می‌شود و بی‌داده «—» است', async () => {
    const a = row(); const b = row({ symbol: 'بی‌کندل', p_max: null, p_min: null });
    mockFeed([a, b]);
    renderTable([a, b]);
    // هر دو ردیف خانۀ کندل دارند (خانه باید پیدا باشد تا «نکشیدہ» از «نبودِ
    // ستون» جدا بماند)؛ تفاوت درِ data-state است: رسم شدۀ SVG یا «—».
    await candlesDrawn(1);   // یک ردیف کندلِ رسم‌شده دارد، «بی‌كندل» نه
    const drawn = document.querySelector('[data-testid="watch-day-candle"][data-state="up"], [data-testid="watch-day-candle"][data-state="down"]');
    expect(drawn?.tagName.toLowerCase()).toBe('svg');
    expect(drawn?.getAttribute('aria-label')).toContain('بیشینه');
    const flat = document.querySelector('[data-testid="watch-day-candle"][data-state="incomplete"]');
    expect(flat?.textContent).toBe('—');
    expect(screen.getByTestId('watch-row-بی‌کندل').textContent).toContain('—');
  });

  it('کلیک رویِ ردیف همان نماد را به بالایِ صفحه می‌دهد (هماهنگیِ سه پنل)', async () => {
    mockFeed([row(), row({ symbol: 'فولاد', ins_code: 'A2' })]);
    const onSelect = renderTable([row(), row({ symbol: 'فولاد', ins_code: 'A2' })]);
    await cellHas('watch-row-فولاد', '۱٬۰۰۰');
    fireEvent.click(screen.getByTestId('watch-row-فولاد'));
    expect(onSelect).toHaveBeenCalledWith('فولاد');
  });
});

describe('پنلِ معامله: قراردادِ بی‌سفارشِ واقعی', () => {
  it('بی‌سرویسِ اجرا (۴۰۴) خرید/فروش و Kill Switch غیرفعال‌اند و دلیل می‌آید', async () => {
    mockFeed([row()], 'absent');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <WatchSummaryPanel symbol="شپنا" row={row()} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('watch-order-buy')).toBeDisabled());
    expect(screen.getByTestId('watch-order-sell')).toBeDisabled();
    expect(screen.getByTestId('watch-kill-switch')).toBeDisabled();
    expect(screen.getByTestId('watch-order-panel').getAttribute('data-can-trade')).toBe('false');
    expect(screen.getByTestId('watch-order-reason').textContent).toContain('هیچ سفارشی');
  });

  it('موجودیِ نرسیده صفر نمی‌شود؛ capabilities.balances=false صریح گفته می‌شود', async () => {
    mockFeed([row()], { status: 'success', adapter: 'mock', dry_run: true, live_enabled: false,
      blocked_on: ['D8: کدام سکوی کارگزاری'], capabilities: { place: true, balances: false } });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <WatchSummaryPanel symbol="شپنا" row={row()} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('watch-order-reason').textContent).toContain('D8'));
    expect(screen.getByTestId('watch-order-balance-note').textContent).toContain('صفر جا نمی‌زند');
    expect(screen.getByTestId('watch-order-reason').textContent).toContain('D8');
  });

  it('dry_run=true هرگز «قابلِ معامله» خوانده نمی‌شود، حتی با live_enabled', () => {
    const g = deriveGate({ status: 'success', adapter: 'mock', dry_run: true, live_enabled: true,
      capabilities: { place: true } }, 'ok');
    expect(g.canTrade).toBe(false);
    expect(g.reason).toContain('بدل');
  });

  it('ورودیِ مقدار سفارش فقط محلی است و هیچ درخواستی نمی‌فرستد', async () => {
    mockFeed([row()], 'absent');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <WatchSummaryPanel symbol="شپنا" row={row()} />
      </QueryClientProvider>,
    );
    const before = fetchMock.mock.calls.length;
    await waitFor(() => expect(screen.getByTestId('watch-order-qty')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰' } });
    fireEvent.click(screen.getByTestId('watch-order-buy'));
    expect(screen.getByTestId('watch-order-qty')).toHaveValue('');
    expect(fetchMock.mock.calls.length).toBe(before);
  });
});

describe('ورودِ بی‌کلیک به زیرتبِ دیده‌بان', () => {
  it('بی‌انتخابِ سراسری، هر سه پنل رویِ نخستین نمادِ رصد می‌نشینند (نه خالی)', async () => {
    // ستور درِ import از localStorage خوانده، پس برایِ این تست حالتش را مستقیم می‌گذارم
    useWatchSymbolsStore.setState({ symbols: ['شپنا', 'فولاد'] });
    mockFeed([row(), row({ symbol: 'فولاد', ins_code: 'A2' })], 'absent');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const W = (await import('@features/portfolio/components/WatchMarketWorkspace')).default;
    render(
      <QueryClientProvider client={qc}>
        <W />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('watch-chart')).toHaveAttribute('data-symbol', 'شپنا'));

    expect(screen.getByTestId('watch-orderbook')).toHaveAttribute('data-symbol', 'شپنا');
    expect(screen.getByTestId('watch-summary')).toHaveAttribute('data-symbol', 'شپنا');
  });
});

describe('تازگیِ بی‌دکمۀ دستی', () => {
  it('با رسیدنِ ردیفِ نو (revِ نو) عددِ همان ردیف عوض می‌شود، بی‌remount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      resetMarketFeedMirror();
      mockFeed([row()]);
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={qc}>
          <WatchTable symbols={['شپنا']} selected="" onSelect={() => {}} onRemove={() => {}} />
        </QueryClientProvider>,
      );
      await waitFor(() => expect(screen.getByTestId('watch-row-شپنا').textContent).toContain('۱٬۰۲۵'));
      fetchMock.mockImplementation((url: string) => {
        if (String(url).includes('execution/status')) {
          return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response);
        }
        return Promise.resolve(json(feed([row({ p_last: 1100, buy_q1_px: 1099, sell_q1_px: 1105 })])));
      });
      await act(async () => {
        vi.advanceTimersByTime(6 * 60_000 + 5_000);
      });
      await waitFor(() => expect(screen.getByTestId('watch-row-شپنا').textContent).toContain('۱٬۱۰۰'), { timeout: 4000 });
      expect(screen.getByTestId('watch-row-شپنا').textContent).toContain('۱٬۱۰۵');
    } finally {
      vi.useRealTimers();
    }
  });
});
