// __tests__/user-watchlist.spec.tsx — WS-3: واچ‌لیستِ ماندگار ≠ انتخابِ موقت
//
// چهار ادعایِ task اینجا نگهبانی می‌شود:
//   §۳  افزودن/حذف به همان `user_watchlists` بک‌اند می‌نشیند (نه storageِ فرانت)
//   §۵  ★ و ☑ دو چیزند؛ هیچ‌کدام دیگری را روشن نمی‌کند
//   §۳۱ یکِ منبعِ حقیقت: ستارۀ یکِ نماد درِ دو سطح، یک حالت را نشان می‌دهد
//   §۸  add/remove optimistic است و فقط کوئریِ واچ‌لیست را بازنویسی می‌کند
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import WatchlistStar from '@shared/components/WatchlistStar';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import { useUserWatchlist } from '@shared/api/userWatchlist';
import { useSelectedSymbolsStore } from '@shared/stores/selectedSymbolsStore';

type Call = { method: string; url: string; body?: string };
let calls: Call[] = [];
let rows: { norm: string; symbol: string; name: string; note: string; added_at: string }[] = [];

beforeEach(() => {
  localStorage.clear();
  useSelectedSymbolsStore.setState({ items: [] });
  calls = [];
  rows = [{ norm: 'فولاد', symbol: 'فولاد', name: 'فولاد مبارکه', note: '', added_at: '2026-10-08T10:00:00' }];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = String(init?.method ?? 'GET');
    calls.push({ method, url, body: init?.body ? String(init.body) : undefined });
    if (!url.includes('/api/watchlist')) {
      return new Response(JSON.stringify({ status: 'no_data' }), { status: 404 });
    }
    if (method === 'POST') {
      const b = JSON.parse(String(init!.body));
      const norm = String(b.symbol).replace(/ي/g, 'ی').replace(/ك/g, 'ک');
      rows = [{ norm, symbol: b.symbol, name: b.name ?? '', note: '', added_at: '2026-10-08T11:00:00' },
              ...rows.filter((r) => r.norm !== norm)];
    } else if (method === 'DELETE') {
      const sym = decodeURIComponent(url.split('/api/watchlist/')[1] ?? '');
      const norm = sym.replace(/ي/g, 'ی').replace(/ك/g, 'ک');
      rows = rows.filter((r) => r.norm !== norm);
    }
    return new Response(JSON.stringify({ status: 'success', count: rows.length, data: rows, limit: 60 }),
      { status: 200, headers: { 'content-type': 'application/json' } });
  }));
});

afterEach(() => vi.unstubAllGlobals());

const withClient = (ui: React.ReactElement) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
};

describe('ستارهٔ واچ‌لیست', () => {
  it('از پاسخِ سرور می‌ساید و با کلیک، POST /api/watchlist می‌زند', async () => {
    withClient(<WatchlistStar symbol="شپنا" name="پالایش شهرکرد" />);
    const star = await screen.findByTestId('watch-star-شپنا');
    expect(star).toHaveAttribute('data-in-list', '0');
    fireEvent.click(star);
    // optimistic: بی‌صبر‌کردنِ refetch، همان کلیک ستاره را روشن می‌کند (§۸)
    await waitFor(() => expect(screen.getByTestId('watch-star-شپنا'))
      .toHaveAttribute('data-in-list', '1'));
    expect(calls.some((c) => c.method === 'POST' && c.url.includes('/api/watchlist')
                              && /شپنا/.test(c.body ?? ''))).toBe(true);
  });

  it('ستارۀ خاموش ⇒ حذف، و نامِ نماد درِ مسیرِ DELETE می‌رود', async () => {
    withClient(<WatchlistStar symbol="فولاد" />);
    const star = await screen.findByTestId('watch-star-فولاد');
    await waitFor(() => expect(star).toHaveAttribute('data-in-list', '1'));
    fireEvent.click(star);
    await waitFor(() => expect(screen.getByTestId('watch-star-فولاد'))
      .toHaveAttribute('data-in-list', '0'));
    // مسیرِ DELETE درصدگانcoding می‌شود؛ مقایسه باید با متنِ باز باشد
    expect(calls.some((c) => c.method === 'DELETE'
                           && decodeURIComponent(c.url).endsWith('/api/watchlist/فولاد'))).toBe(true);
  });

  it('یکِ منبعِ حقیقت: دو سطح، یک حالت (§۳۱)', async () => {
    withClient(
      <div>
        <WatchlistStar symbol="خودرو" name="خودروسازی" />
        <WatchlistStar symbol="خودرو" name="خودروسازی" />
      </div>,
    );
    await screen.findAllByTestId('watch-star-خودرو');
    const stars = screen.getAllByTestId('watch-star-خودرو');
    expect(stars.map((s) => s.getAttribute('data-in-list'))).toEqual(['0', '0']);
    fireEvent.click(stars[0]);
    await waitFor(() => {
      expect(screen.getAllByTestId('watch-star-خودرو').every((s) => s.getAttribute('data-in-list') === '1'))
        .toBe(true);
    });
  });

  it('املایِ عربی همان ردیفِ فارسی است (کلیدِ نرمالِ بک‌اند)', async () => {
    withClient(<WatchlistStar symbol="داريک" />);
    const star = await screen.findByTestId('watch-star-داريک');
    expect(star).toHaveAttribute('data-in-list', '0');
    fireEvent.click(star);
    await waitFor(() => expect(screen.getByTestId('watch-star-داريک'))
      .toHaveAttribute('data-in-list', '1'));
    // پس از refetch، سرور ردیفِ «داریک» را برمی‌گرداند؛ باید همان ستاره روشن بماند
    await waitFor(() => expect(screen.getByTestId('watch-star-داريک'))
      .toHaveAttribute('data-in-list', '1'), { timeout: 3000 });
  });
});

describe('انتخاب ≠ واچ‌لیست (§۵)', () => {
  it('زدنِ ☑ هیچ درخواستِ /api/watchlistی نمی‌زند', async () => {
    withClient(
      <div>
        <SymbolSelectBox symbol="فولاد" name="فولاد مبارکه" />
        <WatchlistStar symbol="فولاد" name="فولاد مبارکه" />
      </div>,
    );
    await screen.findByTestId('watch-star-فولاد');
    calls = [];
    fireEvent.click(screen.getByTestId('select-box-فولاد'));
    expect(useSelectedSymbolsStore.getState().items.map((i) => i.symbol)).toEqual(['فولاد']);
    await waitFor(() => expect(screen.getByTestId('watch-star-فولاد'))
      .toHaveAttribute('data-in-list', '1'));   // از پیش درِ فهرست بود
    // ☑ هیچ نوشتۀ‌ای به واچ‌لیست نمی‌فرستد (خواندنِ کشیدۀ GET حساب نیست)
    expect(calls.filter((c) => c.url.includes('/api/watchlist') && c.method !== 'GET'))
      .toHaveLength(0);
  });

  it('زدنِ ★ انتخابِ موقت را روشن نمی‌کند', async () => {
    withClient(<div>
      <SymbolSelectBox symbol="شپنا" />
      <WatchlistStar symbol="شپنا" />
    </div>);
    fireEvent.click(await screen.findByTestId('watch-star-شپنا'));
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(0);
    expect(screen.getByTestId('select-box-شپنا')).toHaveAttribute('aria-checked', 'false');
  });
});

describe('واچ‌لیستِ پرتفوی', () => {
  it('count/limit از خودِ پاسخِ سرور است، نه شمارشِ محلی', async () => {
    function Probe() {
      const { count, limit, ready } = useUserWatchlist();
      return <div data-testid="probe">{ready ? `${count}/${limit}` : '…'}</div>;
    }
    withClient(<Probe />);
    await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('1/60'));
  });
});
