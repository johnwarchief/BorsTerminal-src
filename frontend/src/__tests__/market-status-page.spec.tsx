// تستِ صفحۀ مستقلِ «وضعیت بازار»: مسیر، منو، و سه حالتِ هر بلوک
//
// چرا این‌جا: رأیِ مالک این است که «یک کامپوننتِ موجود» اثباتِ قابلیت نیست —
// صفحه باید از ناوبری باز شود، داده‌اش را از اندپوینتِ خودش بخواند و وقتی داده
// نمی‌رسد عددِ ساختگی نشان ندهد. پس هر سه حالتِ بار/خطا/بی‌داده سنجیده می‌شود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketStatusPage from '@features/market/routes/MarketStatusPage';
import { mainRoutes } from '../routes';
import { NAV_SECTIONS } from '../app/components/Sidebar';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;
const dead = () => ({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'x' }) }) as unknown as Response;

const ASOF = { d_even: 20261010, h_even: 102343, client_d_even: 20261010, client_lag_days: false, depth: true, top50: 50, n: 2917 };

const HISTO = {
  status: 'ok',
  asof: ASOF,
  group: 'all',
  basis: 'closing_vs_yesterday',
  traded_only: true,
  histo12: [
    { key: '<-5', label: 'کمتر از ۵-', color: 'neg', count: 3 },
    { key: '-5..-4', label: '۵- تا ۴-', color: 'neg', count: 1 },
    { key: '0..1', label: '۰ تا ۱', color: 'pos', count: 9 },
  ],
  histo7: [],
  known: 13,
  nodata: 16,
  total: 1102,
  not_traded: 54,
  source: 'local:market.db',
};
const SPLIT = {
  status: 'ok',
  asof: ASOF,
  tab: 'all',
  symbols: 1102,
  retail: { buy_count: 233000, buy_b_toman: 18877.8, buy_pct: 57.5, sell_count: 497059, sell_b_toman: 22933.7, sell_pct: 69.9 },
  institutional: { buy_count: 2948, buy_b_toman: 13924.8, buy_pct: 42.5, sell_count: 2491, sell_b_toman: 9869.0, sell_pct: 30.1 },
  pc_buy_m_toman: 81.0,
  pc_sell_m_toman: 46.1,
  power: 1.76,
  money_flow_b_toman: -4055.9,
  source: 'local:market.db',
};
const PHASES = {
  status: 'ok',
  points: 19,
  ready: true,
  red: [{ key: 'p>s', label: 'مثبت به صف فروش', count: 3 }],
  green: [{ key: 'n>b', label: 'منفی به صف خرید', count: 1 }],
  source: 'local:market.db',
};
const MAINWATCH = {
  status: 'ok',
  asof: ASOF,
  group: 'eq_all',
  industry: '',
  sort: 'val',
  sort_col: 'val_b_toman',
  desc: true,
  total: 1,
  clock_hits: 1,
  clock_rule: { min_pct: 2, min_trades: 30, min_price: 0 },
  rows: [
    { symbol: 'شپنا', ins_code: '1', name: 'ش', industry: 'پتروشیمی', cls: 'stock', kind: 'stock',
      vol_b_shares: 1, trades: 100, val_b_toman: 5, p_last: 1000, p_closing: 990, pct_last: 1, pct_close: 1.01, clock_pct: 3.4 },
  ],
  source: 'local:market.db',
};
const INDUSTRIES = {
  status: 'ok',
  asof: ASOF,
  rows: [
    { industry: 'محصولات شيميايي', symbols: 66, positive: 52, negative: 14, avg_pct: 1.32, value_b_toman: 3148.6, flow_b_toman: -199.8, flow_pct_of_value: -6.35, buy_queue_b_toman: 2465.2, sell_queue_b_toman: 40.8, rank_value: 1, rank_flow: null, leader_score: 48, leader: false },
    { industry: 'خودرو', symbols: 12, positive: 3, negative: 9, avg_pct: null, value_b_toman: 100, flow_b_toman: 500, flow_pct_of_value: null, buy_queue_b_toman: 1, sell_queue_b_toman: 2, rank_value: 2, rank_flow: null, leader_score: 1, leader: false },
  ],
  leader: null,
  source: 'local:market.db',
};

function routeTo(url: string, table: Record<string, unknown>) {
  const hit = Object.keys(table).find((k) => String(url).includes(k));
  if (!hit) return Promise.resolve(dead());
  return Promise.resolve(json(table[hit]));
}

function renderPage(table: Record<string, unknown>) {
  fetchMock.mockImplementation((url: string) => routeTo(url, table));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/market-status']}>
        <MarketStatusPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// پاسخِ `/api/mstat/indexcards` — تنها پنلِ اینِ صفحه که `computed_at` دارد
// (سنجشِ زندهٔ ۱۴۰۵-۰۷-۲۴: histogram/clientsplit/phases/industries/mainwatch آنِ
// ستون را ندارند). بقیۀِ فیلدها درِ schema همگی `nullish`‌اند، پس اینِ نمونه‌یِ
// کوچکِ عمدی باِ خودِ اعتبارسنجی نمی‌جنگد.
const INDEXCARDS = {
  status: 'ok',
  computed_at: '2026-10-16T02:43:50',
  cards: [],
  source: 'market_index',
};

const FULL: Record<string, unknown> = {
  '/api/mstat/histogram': HISTO,
  '/api/mstat/clientsplit': SPLIT,
  '/api/mstat/phases': PHASES,
  '/api/mstat/mainwatch': MAINWATCH,
  '/api/mstat/industries': INDUSTRIES,
  '/api/mstat/indexcards': INDEXCARDS,
};

beforeEach(() => fetchMock.mockReset());

describe('مسیر و ناوبری', () => {
  it('«market-status» در جدولِ مسیرها ثبت شده است', () => {
    const paths = mainRoutes.map((r) => r.path);
    expect(paths).toContain('market-status');
  });

  it('نوارِ کناری «وضعیت بازار» را به همان مسیر می‌بندد', () => {
    const items = NAV_SECTIONS.flatMap((s) => s.items);
    const hit = items.find((i) => i.label === 'وضعیت بازار');
    expect(hit).toBeTruthy();
    expect(hit?.to).toBe('/market-status');
  });
});

describe('صفحۀ «وضعیت بازار» با داده', () => {
  it('توزیعِ درصد را از اندپوینتش می‌سازد و ساعتِ داده را از همان پاسخ می‌گوید', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('histo-bucket-0..1')).toBeInTheDocument());
    expect(screen.getByTestId('status-histogram').textContent).toContain('۹');
    expect(screen.getByTestId('status-histogram-asof').textContent).toContain('۱۰:۲۳');
    expect(screen.getByTestId('status-histogram-foot').textContent).toContain('بی‌داده');
  });

  it('تفکیکِ مشتری و فازها رندر می‌شوند', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('clientsplit-retail')).toBeInTheDocument());
    expect(screen.getByTestId('phase-n>b')).toBeInTheDocument();
    expect(screen.getByTestId('phase-p>s')).toBeInTheDocument();
  });

  it('جدول‌های صنایع و نمادهای زیرِ نظر ردیف می‌سازند', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('mainwatch-row-شپنا')).toBeInTheDocument());
    expect(screen.getByTestId('industry-row-محصولات شيميايي')).toBeInTheDocument();
  });

  it('مرتب‌سازیِ صنایع واقعاً ترتیب را عوض می‌کند', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('industry-row-محصولات شيميايي')).toBeInTheDocument());
    const before = Array.from(document.querySelectorAll('[data-testid^="industry-row-"]')).map((el) => el.getAttribute('data-testid'));
    fireEvent.click(screen.getByTestId('industries-sort-flow'));
    await waitFor(() => {
      const after = Array.from(document.querySelectorAll('[data-testid^="industry-row-"]')).map((el) => el.getAttribute('data-testid'));
      expect(after).not.toEqual(before);
    });
  });
});

describe('تازگیِ به‌ازایِ ویجت (فاز D)', () => {
  it('سرِصفحۀ «نمای کلی» چهارِ برچسب دارد، یکی به‌ازایِ هرِ ویجتِ مستقل', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('histo-bucket-0..1')).toBeInTheDocument());
    const chips = Array.from(
      screen.getByTestId('section-freshness-ms-sec-overview').querySelectorAll('[data-testid="widget-freshness"]'),
    );
    expect(chips).toHaveLength(4);
    // نامِ هرِ ویجت درِ برچسبِ خودش می‌ماند، تاِ دوِ بخش باِ هم یکی خوانده نشوند
    expect(chips.map((c) => c.textContent).join('|')).toContain('کارت‌های شاخص');
    expect(chips.map((c) => c.textContent).join('|')).toContain('فازهای نشست');
  });

  it('ساعتِ ساختِ پاسخ را از خودِ همانِ پنل می‌خواند، نه از همسایه', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('histo-bucket-0..1')).toBeInTheDocument());
    const texts = Array.from(
      screen.getByTestId('section-freshness-ms-sec-overview').querySelectorAll('[data-testid="widget-freshness"]'),
    ).map((c) => c.textContent ?? '');
    // `computed_at` فقط درِ پاسخِ indexcards است ⇒ همانِ یک «ساعتِ منبع» دارد
    expect(texts.filter((t) => t.includes('ساعتِ منبع: ۰۲:۴۳:۵۰'))).toHaveLength(1);
    // وِ سه پنلِ بی‌`computed_at` باید صریح بگویند «نیامد» — نه ساعتِ همسایه، نه صفر
    expect(texts.filter((t) => t.includes('زمانِ داده از منبع نیامد')).length).toBeGreaterThanOrEqual(3);
  });

  it('برچسبِ سراسریِ بالایِ صفحه جایِ برچسبِ هیچِ ویجتی را نمی‌گیرد', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('histo-bucket-0..1')).toBeInTheDocument());
    // پنلِ تازگیِ سراسری هنوز هست (اتصال/دریافت/عوض‌شدنِ عدد)، ولی جدا ازِ سنجهایِ بخش‌ها
    expect(screen.getByTestId('market-status-panel')).toBeInTheDocument();
    const secs = ['ms-sec-overview', 'ms-sec-tops', 'ms-sec-orders', 'ms-sec-tables'];
    for (const id of secs) {
      expect(screen.getByTestId(`section-freshness-${id}`)).toBeInTheDocument();
    }
  });
});

describe('حالت‌های نبودِ داده و خطا', () => {
  it('خطای هر اندپوینت فقط بلوکِ خودش را می‌سوزاند و دکمۀ تلاش دوباره می‌آید', async () => {
    renderPage({ ...FULL, '/api/mstat/histogram': undefined });
    // undefined ⇒ مسیر در جدول نیست ⇒ پاسخ ۵۰۰
    await waitFor(() => expect(screen.getByTestId('status-histogram-error')).toBeInTheDocument());
    expect(screen.getByTestId('status-clientsplit')).toBeInTheDocument();
    const callsBefore = fetchMock.mock.calls.filter((c) => String(c[0]).includes('histogram')).length;
    fireEvent.click(screen.getByTestId('status-histogram-retry'));
    await waitFor(() => {
      const after = fetchMock.mock.calls.filter((c) => String(c[0]).includes('histogram')).length;
      expect(after).toBeGreaterThan(callsBefore);
    });
  });

  it('هیستوگرامِ بی‌سطل «بی‌داده» می‌گوید، نه ستونِ صفر', async () => {
    renderPage({ ...FULL, '/api/mstat/histogram': { ...HISTO, histo12: [], known: 0 } });
    await waitFor(() => expect(screen.getByTestId('status-histogram-empty')).toBeInTheDocument());
    expect(document.querySelectorAll('[data-testid^="histo-bucket-"]')).toHaveLength(0);
  });

  it('سایدبارِ صنایع با سنجۀ نرسیده به‌جای صفر خط تیره می‌گذارد', async () => {
    renderPage(FULL);
    await waitFor(() => expect(screen.getByTestId('industry-row-خودرو')).toBeInTheDocument());
    const row = screen.getByTestId('industry-row-خودرو');
    // avg_pct و flow_b_toman این صنعت null اند؛ هیچ‌کدام ۰ نمی‌شوند
    expect(row.textContent).toContain('—');
    expect(row.textContent).not.toMatch(/\s۰\s*٪/);
  });
});
