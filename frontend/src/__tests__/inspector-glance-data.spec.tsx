// تست Stage-2 «در یک نگاه»: سه قیمتِ روزانه از /api/market، روند و I1..I5 از
// همان پاسخِ قیف، و عمقِ پنج‌سطحیِ تنبل با محافظت از رقابتِ تعویضِ نماد.
// هیچ عددی اینجا از خودِ UI نمی‌آید: مقدارها را درِ payload می‌گذاریم و می‌سنجیم
// رابط *همان* را نشان می‌دهد — و «صفر»، «ناموجود» و «مقدارِ معتبر» سه چیزند.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';
import { FUNNEL_FIXTURE, REGISTRY_FIXTURE } from './fixtures/funnelApi';

// ── ردیفِ تابلو با سه قیمتِ روزانه ───────────────────────────────────────────
// p_first=0 → «اولین مبادله هنوز نیفتاده» (نه قیمتِ صفر، نه پرکردن با آخرین).
// p_max معتبر، p_min *نیامده* (کلید حذف) → «—». این سه حالت نباید یکی شوند.
const board = (over: Partial<MarketRow> = {}): MarketRow => ({
  ins_code: 'C-FOULAD',
  symbol: 'فولاد',
  name: 'فولاد مبارکه اصفهان',
  p_last: 980,
  p_closing: 975,
  price_yesterday: 950,
  percent_change: 2.63,   // ٪پایانی (p_closing÷دیروز)
  percent_last: 3.16,     // ٪آخرین (p_last÷دیروز) — باید از ٪پایانی جدا بماند
  tvol: 1200000,
  q_tot_cap: 1.1e9,
  mcap: 4.2e13,
  mcap_src: 'tse_raw',
  z_tot_tran: 640,
  buyer_power: 1.8,
  f_jet: true,
  ...over,
} as MarketRow);

function mountBoard(rows: MarketRow[]) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  qc.setQueryData(MARKET_FEED_KEY, { status: 'success', data: rows, count: rows.length });
  return qc;
}

// قیف از همان پاسخِ /api/funnel (FUNNEL_FIXTURE) می‌آید؛ کلیدِ کوئری را حدس
// نمی‌زنیم (preset از horizon/prefs می‌آید) — fetch را می‌بندیم و async می‌خوانیم.
// درِ فولاد: weekly='up' daily='down'، ind_values i1..i4، indsِ همۀ pass.
const resp = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  });

const restoreFetch: Array<() => void> = [];
function mockFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  restoreFetch.push(() => { globalThis.fetch = handler as unknown as typeof fetch; });
  const real = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    handler(String(input), init)) as unknown as typeof fetch;
  restoreFetch.push(() => { globalThis.fetch = real; });
}
// fetchِ اولیه را یک‌بار ذخیره می‌کنیم تا هر تست بعد از خودِش بازگردانده شود.
const REAL_FETCH = globalThis.fetch;
afterEach(() => {
  while (restoreFetch.length) restoreFetch.pop()!();
  globalThis.fetch = REAL_FETCH;
});

async function renderGlance(rows: MarketRow[]) {
  mockFetch((url) => {
    if (url.includes('/api/funnel/registry')) return resp(REGISTRY_FIXTURE);
    if (url.includes('/api/funnel')) return resp(FUNNEL_FIXTURE);
    if (url.includes('/api/order-book')) return resp({ status: 'no_data', levels: [] });
    return resp({ status: 'no_data' }, 404);
  });
  const qc = mountBoard(rows);
  useSymbolStore.setState({ symbol: 'فولاد' });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/market']}><SymbolInspector /></MemoryRouter>
    </QueryClientProvider>,
  );
  // قیف async است؛ تا روند از همان پاسخِ سرور ننشیند ادامه نمی‌دهیم.
  await waitFor(() => expect(screen.getByTestId('inspector-trend-هفتگی').textContent)
    .toBe('صعودی'));
  return qc;
}

describe('«در یک نگاه» — بخشِ قیمت', () => {
  it('پایانی و ٪آخرین جدا از ٪پایانی نشان داده می‌شوند (یکی جای دیگری نمی‌نشیند)', async () => {
    await renderGlance([board()]);
    expect(screen.getByTestId('inspector-p-closing').textContent).toContain(fmtInt(975));
    expect(screen.getByTestId('inspector-percent-last').textContent).toContain(fmtPct(3.16));
    // این دو نباید با هم یکی شوند (٪آخرین ≠ ٪پایانی):
    expect(screen.getByTestId('inspector-percent-last').textContent).not.toContain(fmtPct(2.63));
  });

  it('اولین=۰ ⇒ «—» (مبادله نبود) ولی بیشینه معتبر و کمینۀ نیامده ⇒ «—»', async () => {
    await renderGlance([board({ p_first: 0, p_max: 990, p_min: undefined })]);
    // صفرِ اولین با هیچِ بیشینه/کمینه قاطی نمی‌شود:
    expect(screen.getByTestId('inspector-p-first').textContent).toBe('—');
    expect(screen.getByTestId('inspector-p-max').textContent).toContain(fmtInt(990));
    expect(screen.getByTestId('inspector-p-min').textContent).toBe('—');
  });

  it('مقدارِ معتبرِ اولین/بیشینه/کمینه از فیلدهایِ تازه خوانده می‌شود', async () => {
    await renderGlance([board({ p_first: 958, p_max: 992, p_min: 951 })]);
    expect(screen.getByTestId('inspector-p-first').textContent).toContain(fmtInt(958));
    expect(screen.getByTestId('inspector-p-max').textContent).toContain(fmtInt(992));
    expect(screen.getByTestId('inspector-p-min').textContent).toContain(fmtInt(951));
  });
});

describe('«در یک نگاه» — روند و پنج‌شاخصه (از همان قیف)', () => {
  it('روندِ روزانۀ نزولی و هفتگیِ صعودی از خروجیِ canonicalِ قیف می‌آید', async () => {
    await renderGlance([board()]);
    expect(screen.getByTestId('inspector-trend-روزانۀ').textContent).toBe('نزولی');
    // جتِ canonical (f_jet=true) روشن است — نه روندِ اختراعی.
    expect(screen.getByTestId('inspector-jet').textContent).toContain('✓');
  });

  it('پنج شاخص با همان مقدارِ قیف؛ بی‌مقدار ⇒ «—» نه صفر', async () => {
    await renderGlance([board()]);
    // FUNNEL_FIXTURE فولاد: i1=52 (٪)، i2=318، i3=26 (٪)، i4=0.41، i5=pricing_mode
    expect(screen.getByTestId('inspector-ind-i1').textContent).toContain(fmtPct(52));
    expect(screen.getByTestId('inspector-ind-i2').textContent).toContain(fmtInt(318));
    expect(screen.getByTestId('inspector-ind-i3').textContent).toContain(fmtPct(26));
    expect(screen.getByTestId('inspector-ind-i4').textContent).toContain(toFaDigits('0.41'));
    // I5 مقدارِ عددی ندارد؛ نرخ‌گذاری متنی است نه صفر.
    expect(screen.getByTestId('inspector-ind-i5').textContent).not.toContain(fmtPct(0));
  });
});

describe('«جزئیات بازار» — عمقِ تنبل و ضدِ رقابت', () => {
  const bookFor = (sym: string, px: number) => ({
    status: 'ok', symbol: sym,
    levels: Array.from({ length: 5 }, (_, i) => ({
      buy_px: px - i, buy_vol: 1000 + i, buy_cnt: 1,
      sell_px: px + 10 + i, sell_vol: 900 + i, sell_cnt: 1,
    })),
    session: { d_even: 14050717, h_even: 110000, updated_at: '2026-10-08 11:00:00' },
    totals: { buy_vol: 5000, buy_cnt: 5, sell_vol: 5000, sell_cnt: 5 },
  });

  it('بی‌بازکردنِ جزئیات، هیچ درخواستِ عمقی زده نمی‌شود', () => {
    const spy = vi.fn();
    mockFetch((url) => {
      spy(url);
      if (url.includes('/api/funnel')) return resp(FUNNEL_FIXTURE);
      return resp({ status: 'no_data' }, 404);
    });
    const qc = mountBoard([board()]);
    useSymbolStore.setState({ symbol: 'فولاد' });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}><SymbolInspector /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(spy.mock.calls.filter((u) => String(u[0]).includes('/api/order-book')).length).toBe(0);
    expect(screen.queryByTestId('sidebar-orderbook')).not.toBeInTheDocument();
  });

  it('بازکردنِ جزئیات + پنج مظنه، عمقِ *همین نماد* را می‌گیرد', async () => {
    mockFetch((url) => {
      if (url.includes('/api/funnel')) return resp(FUNNEL_FIXTURE);
      const m = /\/api\/order-book\/(.+)$/.exec(url);
      if (m) return resp(bookFor(decodeURIComponent(m[1]), 980));
      return resp({ status: 'ok' });
    });
    const qc = mountBoard([board()]);
    useSymbolStore.setState({ symbol: 'فولاد' });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}><SymbolInspector /></MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByTestId('inspector-tab-detail'));
    fireEvent.click(screen.getByTestId('inspector-quotes-toggle'));
    await waitFor(() => expect(screen.getByTestId('sidebar-orderbook-rows')).toBeInTheDocument());
    // قیمتِ سطرِ اولِ همان نماد (980) باید دیده شود.
    expect((document.body.textContent ?? '')).toContain(fmtInt(980));
  });

  it('پاسخِ دیررسِ نمادِ قبلی رویِ نمادِ تازه رندر نمی‌شود (۱۰ جابه‌جاییِ سریع)', async () => {
    // هر نماد یک قیمتِ منحصربه‌فرد دارد؛ پاسخِ S1 عمداً کند است تا اگر UI
    // نگهبانِ تطابقِ نماد نداشت، عددِ اشتباه رویِ نمادِ تازه بنشیند. نام‌های
    // ASCII تا خطایِ رقمِ فارسی/لاتین درِ خودِ تست نتیجه را مبهم نکند، و قیمت
    // در بازۀ ۹۰۰٬۰۰۰ تا است تا با هیچ حجم/سطرِ دیگری درِ بدنه قاطی نشود.
    const prices: Record<string, number> = {};
    const syms: string[] = [];
    for (let i = 1; i <= 10; i++) { const s = `S${i}`; syms.push(s); prices[s] = 900000 + i * 1000; }
    let lastRequested = '';
    mockFetch((url) => {
      if (url.includes('/api/funnel')) return resp(FUNNEL_FIXTURE);
      const m = /\/api\/order-book\/(.+)$/.exec(url);
      if (m) {
        const sym = decodeURIComponent(m[1]);
        lastRequested = sym;
        const delay = sym === 'S1' ? 80 : 0;   // S1 کُند، بقیه سریع
        return new Promise<Response>((res) => setTimeout(
          () => res(resp(bookFor(sym, prices[sym]))), delay));
      }
      return resp({ status: 'ok' });
    });
    const rows = syms.map((s) => board({ symbol: s, ins_code: `C-${s}`, name: s, p_last: prices[s] }));
    const qc = mountBoard(rows);
    useSymbolStore.setState({ symbol: 'S1' });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}><SymbolInspector /></MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByTestId('inspector-tab-detail'));
    fireEvent.click(screen.getByTestId('inspector-quotes-toggle'));
    await waitFor(() => expect(lastRequested).toBe('S1'));
    // سریع تا S10 عبور کن، سپس همان را بنشان.
    for (const s of syms.slice(1)) useSymbolStore.getState().setSymbol(s);
    useSymbolStore.getState().setSymbol('S10');
    // به پاسخِ کُندِ S1 (=۱۰۰۱) فرصتِ رسیدن بده؛ بعد از آن فقط S10 (=۱۰۱۰) مجاز است.
    await new Promise((r) => setTimeout(r, 180));
    const bodyText = document.body.textContent ?? '';
    expect(bodyText).toContain(fmtInt(prices['S10']));    // ۱۰۱۰ = نمادِ جاری
    expect(bodyText).not.toContain(fmtInt(prices['S1']));  // ۱۰۰۱ = دیررسِ نمادِ قبلی
  });
});
