// تستِ «پنج مظنه» (`shared/components/OrderBookFive`) — چیدمانِ مرجع، بی‌عددِ ساختگی
//
// سارِ پیشینِ رویِ چارت (#29) سطرها را از قیمت و حجمِ کل *می‌ساخت*؛ این پروند
// همان را به‌عنوانِ قراردادِ نگه‌دارنده ثبت می‌کند و سه چیزِ بند ۱.۱ مأموریت را
// می‌گیرد: سه خانۀِ تعداد/حجم/قیمت درِ هر سطر، وضعیتِ صریحِ «سطر نیست» (بی‌صفر)،
// و کندلِ روزِ در حالِ تشکیل بالایِ سرستون‌ها.
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { OrderBookFive } from '@shared/components/OrderBookFive';
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

const CANDLE = { p_first: 70500, p_max: 70900, p_min: 70400, p_last: 70791, p_closing: 70600 };

function reply(body: unknown) {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => body });
}

function panel(props: Partial<Parameters<typeof OrderBookFive>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <OrderBookFive symbol="فولاد" testId="sidebar-orderbook" {...props} />
    </QueryClientProvider>,
  );
}

const ok = (over: Record<string, unknown> = {}) => ({
  status: 'ok', symbol: 'فولاد', levels: LEVELS,
  session: { d_even: 14050705, h_even: 61040, updated_at: '2026-09-27 11:30:42' },
  totals: { buy_vol: 2721000, buy_cnt: 18, sell_vol: 1260000, sell_cnt: 16 },
  ...over,
});

describe('پنل پنج مظنه', () => {
  it('هر پنج سطرِ خرید و فروشِ سرور رندر می‌شود، با همان عددِ سرور', async () => {
    reply(ok());
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    for (const side of ['buy', 'sell']) {
      expect(document.querySelectorAll(`[data-testid^="sidebar-orderbook-level-${side}-"]`)).toHaveLength(5);
    }
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

  it('سه خانۀ تعداد/حجم/قیمت درِ هر دو سو سرستون دارد', async () => {
    reply(ok());
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    for (const side of ['buy', 'sell']) {
      const head = screen.getByTestId(`sidebar-orderbook-cols-${side}`).textContent ?? '';
      expect(head).toContain('تعداد');
      expect(head).toContain('حجم');
      expect(head).toContain('قیمت');
    }
    expect(screen.getByTestId('sidebar-orderbook-head-buy').textContent).toContain('تقاضا');
    expect(screen.getByTestId('sidebar-orderbook-head-sell').textContent).toContain('عرضه');
  });

  it('تعدادِ هر سطر همان countِ سرور است، نه شمارشی از خودِ رابط', async () => {
    reply(ok());
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    const cell = screen.getByTestId('sidebar-orderbook-level-buy-1').textContent ?? '';
    expect(cell).toContain(toFaDigits('7'));   // buy_cntِ سطرِ اول
    expect(cell).toContain(fmtInt(70791));
    expect(cell).toContain(fmtInt(1250000));
  });

  it('کمتر از پنج سطر ⇒ خانۀِ باقی‌مانده «—» است با وضعیتِ صریح، نه صفر', async () => {
    reply(ok({ levels: LEVELS.slice(0, 3) }));
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    const missing = screen.getByTestId('sidebar-orderbook-level-buy-5');
    expect(missing.getAttribute('data-state')).toBe('no-row');
    expect(missing.textContent).toBe('———');
    expect(missing.textContent).not.toContain('۰');
    // سطرِ زندهی همان پنج‌خانه باید وضعیتِ خودش را داشته باشد
    expect(screen.getByTestId('sidebar-orderbook-level-buy-1').getAttribute('data-state')).toBe('live');
  });

  it('سطری با قیمتِ صفر (صفِ تهی) «بی‌سطر» خوانده می‌شود، نه قیمتِ صفر', async () => {
    reply(ok({ levels: [{ ...LEVELS[0], sell_px: 0, sell_vol: 0, sell_cnt: 0 }] }));
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    expect(screen.getByTestId('sidebar-orderbook-level-sell-1').getAttribute('data-state')).toBe('empty');
    expect(screen.getByTestId('sidebar-orderbook-level-buy-1').getAttribute('data-state')).toBe('live');
  });

  it('کندلِ روزِ در حالِ تشکیل بالایِ سرستون‌ها، با چهار قیمتِ خودِ تابلو', async () => {
    reply(ok());
    panel({ candle: CANDLE });
    // کندل از ردیفِ تابلو می‌آید و بی‌درنگ می‌نشیند؛ ترتیب را باید بعد از
    // رسیدنِ سطرها سنجید، وگرنه «ردیف نیست» را با «زیرِ کندل است» می‌خوانیم.
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    const strip = screen.getByTestId('sidebar-orderbook-candle');
    expect(strip.getAttribute('data-state')).toBe('up');       // آخرین > اول
    const text = strip.textContent ?? '';
    expect(text).toContain(fmtInt(70500));   // اول
    expect(text).toContain(fmtInt(70900));   // بیشینه
    expect(text).toContain(fmtInt(70400));   // کمینه
    expect(text).toContain(fmtInt(70791));   // آخرین
    expect(screen.getByTestId('sidebar-orderbook-candle-glyph').getAttribute('data-dir')).toBe('up');
    // سرستون‌ها باید زیرِ کندل بمانند (ترتیبِ مرجع: کندل، بعد مظنه‌ها)
    const candleEl = screen.getByTestId('sidebar-orderbook-candle');
    const rowsEl = screen.getByTestId('sidebar-orderbook-rows');
    // پیشِ کندل رویِ ردیف‌ها = ۲ در DOM زنده؛ «بعد» یعنی ۴
    expect(candleEl.compareDocumentPosition(rowsEl)).toBe(4);
  });

  it('بی‌چهارقیمتِ کامل ⇒ کندل رسم نمی‌شود و «—» با علتش می‌آید', async () => {
    reply(ok());
    panel({ candle: { p_first: null, p_max: 70900, p_min: null, p_last: 70791 } });
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-candle')).toBeInTheDocument());
    expect(screen.getByTestId('sidebar-orderbook-candle-glyph').getAttribute('data-state')).toBe('incomplete');
  });

  it('بی‌کندل (روشی که ردیفِ تابلو ندارد) ⇒ هیچ کندلی ساخته نمی‌شود', async () => {
    reply(ok());
    panel();
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    expect(screen.queryByTestId('sidebar-orderbook-candle')).toBeNull();
  });

  it('هیچ نشان «شبیه‌سازی» و هیچ سطرِ ساخته‌شده‌ای در پنل نیست', async () => {
    reply(ok({ totals: {} }));
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
