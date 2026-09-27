// تست پنل «پنج مظنه»ی سایدبار — عددِ سرور عیناً نمایش داده شود و بی‌داده، بی‌داده بماند
// پنلِ پیشینِ رویِ چارت سطرها را از قیمت و حجمِ کل *می‌ساخت* (#29). این تست همان
// را به‌عنوانِ قراردادِ نگه‌دارنده ثبت می‌کند: هیچ برچسب «شبیه‌سازی» برنمی‌گردد.
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { SidebarOrderBook } from '@features/technical/components/SidebarOrderBook';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

/** پنج خطِ نمونه — همان قالبِ /api/order-book (blDsِ تابلو، ریال) */
const LEVELS = [
  { buy_px: 70791, buy_vol: 1250000, buy_cnt: 7, sell_px: 70800, sell_vol: 980000, sell_cnt: 4 },
  { buy_px: 70790, buy_vol: 860000, buy_cnt: 3, sell_px: 70810, sell_vol: 120000, sell_cnt: 2 },
  { buy_px: 70785, buy_vol: 430000, buy_cnt: 5, sell_px: 70820, sell_vol: 76000, sell_cnt: 1 },
  { buy_px: 70780, buy_vol: 120000, buy_cnt: 1, sell_px: 70830, sell_vol: 54000, sell_cnt: 3 },
  { buy_px: 70770, buy_vol: 61000, buy_cnt: 2, sell_px: 70840, sell_vol: 30000, sell_cnt: 6 },
];

function reply(body: unknown) {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => body });
}

function panel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <SidebarOrderBook symbol="فولاد" />
    </QueryClientProvider>,
  );
}

describe('پنل پنج مظنه', () => {
  it('هر پنج خطِ خرید و پنج خطِ فروشِ سرور رندر می‌شود، با همان عددِ سرور', async () => {
    reply({
      status: 'ok',
      symbol: 'فولاد',
      levels: LEVELS,
      session: { d_even: 14050705, h_even: 61040, updated_at: '2026-09-27 11:30:42' },
      totals: { buy_vol: 2721000, buy_cnt: 18, sell_vol: 1260000, sell_cnt: 16 },
    });
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    expect(document.querySelectorAll('[data-testid="sidebar-orderbook-rows"] li')).toHaveLength(10);
    const text = document.body.textContent ?? '';
    for (const ln of LEVELS) {
      expect(text).toContain(fmtInt(ln.buy_px));
      expect(text).toContain(fmtInt(ln.sell_px));
      expect(text).toContain(fmtInt(ln.buy_vol));
    }
    expect(text).toContain(fmtInt(2721000));
    expect(text).toContain(toFaDigits('18'));
      expect(text).toContain('همگامِ ساعتِ ۱۱:۳۰');
  });

  it('هیچ نشان «شبیه‌سازی» و هیچ سطرِ ساخته‌شده‌ای در پنل نیست', async () => {
    reply({
      status: 'ok',
      symbol: 'فولاد',
      levels: LEVELS,
      session: { d_even: 14050705, h_even: 61040, updated_at: '2026-09-27 11:30:42' },
      totals: {},
    });
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    expect(screen.queryByText('شبیه‌سازی')).toBeNull();
    expect(screen.queryByText('نمایش تقریبی')).toBeNull();
  });

  it('بی‌داده یعنی پیامِ سرور و صفر سطر، نه پنج سطرِ صفر', async () => {
    reply({ status: 'no_data', symbol: 'فولاد', levels: [], message: 'عمقِ این نماد ذخیره نشده' });
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-empty')).toBeInTheDocument());
    expect(screen.getByTestId('sidebar-orderbook-empty').textContent).toContain('ذخیره نشده');
    expect(screen.queryByTestId('sidebar-orderbook-rows')).toBeNull();
  });
});
