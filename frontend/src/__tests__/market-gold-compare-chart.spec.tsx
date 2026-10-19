// تستِ مرحلۀ ۲ و ۴ درِ صفحۀ ۱/۳/۱۰/۱۱/۱۲ (طلا)، ۱۳ (مقایسه) و ۵ (چارت).
//
// jsdom است، نه مرورگرِ واقعی — درِ report هم به‌عنوانِ تستِ کامپوننت ثبت می‌شود.
// درِ صفحۀ ۵ موتورِ چارت با `vi.mock` جایگزین می‌شود تا همین‌جا ثابت شود که
// «انتخابِ نماد از دیده‌بان/تابلو واقعاً به موتورِ چارت می‌رسد»؛ خودِ رندرِ
// کندل‌ها درِ فاز ۵F با Edge و Playwright سنجیده شده و درِ مرورگر دوباره
// سنجیده می‌شود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GoldMarketSection } from '@features/market/components/GoldMarketSection';
import { MarketCompareSection } from '@features/market/components/MarketCompareSection';
import { MarketChartSection } from '@features/market/components/MarketChartSection';

vi.mock('@features/technical/nahayatnegar/components/KLineChartWrapper', () => ({
  default: (props: { initialSymbol: string; initialName?: string; onSymbolChange?: (s: { symbol: string; name: string; market: string }) => void }) => (
    <div data-testid="fake-engine">
      <span data-testid="fake-engine-symbol">{props.initialSymbol}</span>
      <span data-testid="fake-engine-name">{props.initialName}</span>
      <button
        type="button"
        data-testid="fake-engine-internal-change"
        onClick={() => props.onSymbolChange?.({ symbol: 'خودرو', name: 'ایران خودرو', market: 'tehran' })}
      >
        تغییرِ نماد از درِ موتور
      </button>
    </div>
  ),
}));

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;
const dead = () => ({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'not found' }) }) as unknown as Response;

const ASOF = { d_even: 20261012, h_even: 121500, client_d_even: 20261012, client_lag_days: false, depth: true, top50: 50, n: 1200 };
const DAYS = ['2026-09-01', '2026-09-02', '2026-09-03'];

const GOLD = {
  status: 'ok',
  asof: ASOF,
  computed_at: '2026-10-12T12:15:00',
  unit: { value_b_toman: 'میلیارد تومان', price: 'ریال' },
  basis: 'ردیف‌هایِ واقعیِ تابلو با cls/kindِ موتور',
  history_days: 60,
  history_source: 'price_history.close (پایانیِ خام)',
  symbols_count: 4,
  total_value_b_toman: 340,
  symbols: [
    { symbol: 'عيار', ins_code: '1180', name: 'صندوقِ طلایِ عيار', cls: 'fund', kind: 'gold', p_closing: 120000, p_last: 120500, p_yesterday: 118600, pct: 1.18, tone: 'pos', value_b_toman: 200, volume_m_share: 1.6, market_cap_b_toman: 900, trades: 800, value_share_pct: 58.8, spark: DAYS.map((d, i) => ({ d, v: 118000 + i * 1000 })) },
    { symbol: 'طلا', ins_code: '1181', name: 'صندوقِ طلایِ طلا', cls: 'fund', kind: 'gold', p_closing: 90000, p_last: 89000, p_yesterday: 90700, pct: -1.87, tone: 'neg', value_b_toman: 100, volume_m_share: 1.1, market_cap_b_toman: 600, trades: 400, value_share_pct: 29.4, spark: [{ d: '2026-09-03', v: 90000 }] },
    { symbol: 'نقره', ins_code: '1182', name: 'صندوقِ نقره', cls: 'fund', kind: 'silver', p_closing: null, p_last: null, p_yesterday: null, pct: null, tone: 'nodata', value_b_toman: 40, volume_m_share: 0.4, market_cap_b_toman: null, trades: 60, value_share_pct: 11.8, spark: [] },
    { symbol: 'ذر', ins_code: '1183', name: 'اوراقِ سلفِ طلا', cls: 'other', kind: 'other', p_closing: 45000, p_last: 45200, p_yesterday: 44900, pct: 0.67, tone: 'pos', value_b_toman: 12, volume_m_share: 0.3, market_cap_b_toman: null, trades: 90, value_share_pct: 3.5, spark: [] },
  ],
  no_source: [
    { key: 'ounce', label: 'اونسِ جهانیِ طلا', why: 'درِ این بانک ردیفی نیست', needed: 'خوراکِ مجازِ ارزی' },
    { key: 'forward_price', label: 'قیمتِ آینده', why: 'تعریفِ مرجع نامعلوم است — حدس نمی‌زنیم' },
  ],
  access_limits: [{ key: 'intrinsic_value', label: 'ارزش ذاتیِ صندوق', why: 'پشتِ ورود/عضویت قفل است', needed: 'دسترسیِ ثبت‌شده' }],
  source: 'local:market.db',
};

const SERIES = {
  status: 'ok',
  computed_at: '2026-10-12T12:15:00',
  days: 365,
  unit: 'ریال',
  basis: 'price_history.close = پایانیِ خام (سریِ تعدیل‌شده نیست)',
  symbols: ['عيار', 'فولاد'],
  series: {
    'عيار': DAYS.map((d, i) => ({ d, v: 100 + i * 5 })),
    فولاد: DAYS.map((d, i) => ({ d, v: 200 - i * 4 })),
  },
  points: { 'عيار': 3, فولاد: 3 },
  no_source: ['اونس'],
  first_date: { 'عيار': DAYS[0], فولاد: DAYS[0] },
  last_date: { 'عيار': DAYS[2], فولاد: DAYS[2] },
};

const TEDPIX = {
  status: 'ok',
  // همان شکلِ واقعیِ پاسخ: `time` رشتهٔ تاریخ است نه عدد (سنجشِ /api/index/tedpix)
  candles: DAYS.map((d, i) => {
    const c = 2_100_000 + i * 15_000;
    return { time: d, open: c - 5000, high: c + 5000, low: c - 8000, close: c };
  }),
  source: 'tsetmc',
  unit: 'واحد',
};

function mockRoutes(table: Record<string, unknown>) {
  fetchMock.mockImplementation((url: string) => {
    const hit = Object.keys(table).find((k) => String(url).includes(k));
    return Promise.resolve(hit ? json(table[hit]) : dead());
  });
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  fetchMock.mockReset();
  mockRoutes({});
});

describe('طلا، سکه و صندوق‌های طلا (صفحاتِ ۱/۳/۱۰/۱۱/۱۲)', () => {
  it('بی‌منبع‌ها و محدودیتِ دسترسی با علتِ خودِ سرور می‌آیند و عددی برایشان ساخته نمی‌شود', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('gold-nosource-ounce')).toBeInTheDocument());
    expect(screen.getByTestId('gold-nosource-forward_price').textContent).toContain('تعریفِ مرجع نامعلوم است');
    expect(screen.getByTestId('ms-gold-blocker').textContent).toContain('پشتِ ورود/عضویت قفل است');
    expect(screen.getByTestId('ms-gold').textContent).not.toMatch(/اونس[^\n]*۰۰۰/);
  });

  it('جدولِ طلا سه جدولِ جداست، نه یک جدولِ مخلوطِ تمامِ ابزارها', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('ms-gold-cards')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('ms-gold-tab-tables'));
    expect(screen.getByTestId('ms-gold-tbl-fund-scroller')).toBeInTheDocument();
    expect(screen.getByTestId('ms-gold-tbl-paper-scroller')).toBeInTheDocument();
    // جدولِ سومی هم حذف نمی‌شود؛ بی‌ردیف یعنی «این‌جا ردیفی از این طبقه نیست»
    expect(screen.getByTestId('ms-gold-tbl-other-empty')).toBeInTheDocument();
    expect(screen.getByTestId('ms-gold-tbl-fund-row-عيار')).toBeInTheDocument();
    expect(screen.queryByTestId('ms-gold-tbl-fund-row-ذر')).not.toBeInTheDocument();
    expect(screen.getByTestId('ms-gold-tbl-paper-row-ذر')).toBeInTheDocument();
    expect(screen.getByTestId('ms-gold-tables-unit')).toBeInTheDocument();
  });

  it('صفحۀ ۱۲ دو نمایِ مستقل دارد: حلقۀ ترکیب و نقشۀ قفل‌شده رویِ صندوقِ طلا', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('ms-gold-cards')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('ms-gold-tab-funds'));
    expect(screen.getByTestId('ms-gold-funds-donut')).toBeInTheDocument();
    expect(screen.getByTestId('ms-gold-funds-independent')).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('group=gold_fund'))).toBe(true),
    );
    expect(screen.getByTestId('ms-gold-treemap')).toBeInTheDocument();
  });

  it('حلقه فقط صندوق‌ها را می‌شمارد و پوشش را صریح اعلام می‌کند', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('ms-gold-donut-coverage')).toBeInTheDocument());
    expect(screen.getByTestId('ms-gold-donut-coverage').textContent).toContain('۳ از ۳');
    expect(screen.queryByTestId('ms-gold-donut-slice-ذر')).not.toBeInTheDocument();
  });

  it('معیارِ حلقه عوض می‌شود و بی‌داده (ارزش بازارِ نقره) از شمارش بیرون می‌ماند', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('ms-gold-donut-metric-cap')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('ms-gold-donut-metric-cap'));
    await waitFor(() => expect(screen.getByTestId('ms-gold-donut-coverage').textContent).toContain('۲ از ۳'));
    expect(screen.getByTestId('ms-gold-donut-metric-cap').getAttribute('aria-pressed')).toBe('true');
  });

  it('روندِ تجمعی با کمتر از دو نقطه خط نمی‌کشد', async () => {
    mockRoutes({ '/api/mstat/gold': { ...GOLD, symbols: GOLD.symbols.map((s) => ({ ...s, spark: [] })) } });
    wrap(<GoldMarketSection />);
    await waitFor(() => expect(screen.getByTestId('ms-gold-trend-nodata')).toBeInTheDocument());
    expect(screen.queryByTestId('ms-gold-trend-path')).not.toBeInTheDocument();
  });
});

describe('نمودارِ مقایسه‌ای (صفحۀ ۱۳)', () => {
  it('همۀ سری‌ها در یک درخواست می‌آیند، نه یک درخواست به‌ازای هر نماد', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-svg')).toBeInTheDocument());
    const urls = fetchMock.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/api/mstat/series'));
    expect(urls).toHaveLength(1);
    expect(decodeURIComponent(urls[0])).toContain('عيار,فولاد');
  });

  it('نرمال‌سازی رویِ پایۀ ۱۰۰ است و هر سری یک خطِ خودش دارد', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-legend')).toBeInTheDocument());
    const lines = ['شاخص کل', 'عيار', 'فولاد'].map((s) => screen.getByTestId(`ms-compare-line-${s}`));
    expect(lines).toHaveLength(3);
    for (const p of lines) expect(p.getAttribute('d')).toMatch(/^M[\d.]+ [\d.]+( L[\d.]+ [\d.]+){2}$/);
    // خطِ مرجع: پایۀ ۱۰۰ رویِ محورِ مشترک علامت می‌خورد
    expect(screen.getByTestId('ms-compare-svg').textContent).toContain('پایۀ ۱۰۰');
  });

  it('محورها خوانده می‌شوند و ترتیب/رنگِ سری‌ها پایدار است', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-svg')).toBeInTheDocument());
    // محورِ عمودی: پنج تیکِ درصدی؛ محورِ افقی: سه تاریخ.
    const y = screen.getByTestId('ms-compare-yaxis');
    expect(y.querySelectorAll('text')).toHaveLength(5);
    expect(y.textContent).toContain('٪');
    expect(screen.getByTestId('ms-compare-xaxis').querySelectorAll('text')).toHaveLength(3);
    // ترتیب: شاخص → طلا → سریِ خارج از فهرستِ طلا.
    const labels = Array.from(screen.getByTestId('ms-compare-legend').querySelectorAll('button'))
      .map((b) => b.textContent);
    expect(labels).toEqual(['کل بورس', 'عيار', 'فولاد']);
    // رنگ به نماد بسته است: حذفِ فولاد رنگِ عيار را عوض نمی‌کند.
    const before = screen.getByTestId('ms-compare-line-عيار').getAttribute('stroke');
    fireEvent.click(screen.getByTestId('ms-compare-unpick-فولاد'));
    await waitFor(() => expect(screen.getByTestId('ms-compare-line-عيار')).toBeInTheDocument());
    expect(screen.queryByTestId('ms-compare-line-فولاد')).not.toBeInTheDocument();
    expect(screen.getByTestId('ms-compare-line-عيار').getAttribute('stroke')).toBe(before);
  });

  it('سریِ بی‌منبع درِ فهرست «غیرفعال + علت» می‌نشیند و خطِ ساختگی نمی‌شود', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-cand-missing-ounce')).toBeInTheDocument());
    expect(screen.getByTestId('ms-compare-cand-missing-ounce')).toHaveAttribute('data-available', '0');
    expect(screen.getByTestId('ms-compare-cand-missing-ounce').textContent).toContain('درِ این بانک ردیفی نیست');
  });

  it('مقیاسِ log هندسه را واقعاً عوض می‌کند و بازه، درخواستِ تازه با daysِ تازه می‌سازد', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-svg')).toBeInTheDocument());
    const before = screen.getByTestId('ms-compare-line-عيار').getAttribute('d');
    fireEvent.click(screen.getByTestId('ms-compare-scale-log'));
    await waitFor(() => expect(screen.getByTestId('ms-compare-line-عيار').getAttribute('d')).not.toBe(before));
    fireEvent.click(screen.getByTestId('ms-compare-range-5y'));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/api/mstat/series') && String(c[0]).includes('days=1825'))).toBe(true),
    );
  });

  it('کوتاهیِ تاریخچه اعلام می‌شود: «۱ سال» یعنی ۳۶۵ ردیفِ معاملاتی، نه ۳۶۵ روزِ تقویمی', async () => {
    mockRoutes({ '/api/mstat/gold': GOLD, '/api/mstat/series': SERIES, '/api/index/tedpix': TEDPIX });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-span')).toBeInTheDocument());
    expect(screen.getByTestId('ms-compare-span').textContent)
      .toContain('کوتاه‌ترین سری فقط ۳ ردیف دارد');
    expect(screen.getByTestId('ms-compare-range-1y').getAttribute('title'))
      .toContain('۳۶۵ ردیفِ معاملاتی');
  });

  it('کمتر از دو زمانِ مشترک: نمودار نمی‌کشیم، «بی‌داده» می‌گوییم', async () => {
    mockRoutes({
      '/api/mstat/gold': GOLD,
      '/api/mstat/series': { ...SERIES, series: { 'عيار': [{ d: '2026-09-01', v: 100 }], فولاد: [{ d: '2026-09-02', v: 200 }] } },
      '/api/index/tedpix': TEDPIX,
    });
    wrap(<MarketCompareSection />);
    await waitFor(() => expect(screen.getByTestId('ms-compare-nodata')).toBeInTheDocument());
    expect(screen.queryByTestId('ms-compare-svg')).not.toBeInTheDocument();
  });
});

describe('نمودارِ پیشرفته (صفحۀ ۵)', () => {
  const WATCH = {
    status: 'success', count: 2, limit: 50,
    data: [
      { norm: 'فولاد', symbol: 'فولاد', name: 'مبارکه', note: '', added_at: '2026-10-01' },
      { norm: 'شپنا', symbol: 'شپنا', name: 'پتروشیمی', note: '', added_at: '2026-10-02' },
    ],
  };
  const BOARD = {
    status: 'ok', asof: ASOF, group: 'all', industry: '', sort: 'val', sort_col: 'val_b_toman',
    desc: true, total: 2, clock_hits: 0,
    rows: [
      { symbol: 'شپنا', ins_code: '1', name: 'پتروشیمی', industry: 'پترو', cls: 'stock', kind: 'stock', vol_b_shares: 1, trades: 900, val_b_toman: 30, p_last: 1000, p_closing: 995, p_first: 980, p_max: 1010, p_min: 970, pct_last: 1.4, pct_close: 1.5, clock_pct: 0, pc_buy: 1, pc_sell: 2, power: 0.5, flow_b_toman: -1 },
      { symbol: 'فولاد', ins_code: '2', name: 'مبارکه', industry: 'فلزات', cls: 'stock', kind: 'stock', vol_b_shares: 2, trades: 1500, val_b_toman: 90, p_last: 520, p_closing: 518, p_first: 510, p_max: 530, p_min: 505, pct_last: -2.1, pct_close: -2.3, clock_pct: 0, pc_buy: 3, pc_sell: 1, power: 2, flow_b_toman: 4 },
    ],
    source: 'local:market.db',
  };

  it('نماد از دیده‌بان و از تابلو به همان موتورِ چارت می‌رسد', async () => {
    mockRoutes({ '/api/watchlist': WATCH, '/api/mstat/mainwatch': BOARD });
    wrap(<MarketChartSection initialSymbol="عیار" />);
    await waitFor(() => expect(screen.getByTestId('fake-engine')).toBeInTheDocument());
    expect(screen.getByTestId('fake-engine-symbol')).toHaveTextContent('عیار');

    fireEvent.click(screen.getByTestId('ms-chart-watch-شپنا'));
    await waitFor(() => expect(screen.getByTestId('fake-engine-symbol')).toHaveTextContent('شپنا'));

    fireEvent.click(screen.getByTestId('ms-chart-board-list-row-فولاد'));
    await waitFor(() => expect(screen.getByTestId('fake-engine-symbol')).toHaveTextContent('فولاد'));
    expect(screen.getByTestId('fake-engine-name')).toHaveTextContent('مبارکه');
  });

  it('تغییرِ نماد از درِ موتور به وضعیتِ صفحه برمی‌گردد (یک منبعِ حقیقت)', async () => {
    mockRoutes({ '/api/watchlist': WATCH, '/api/mstat/mainwatch': BOARD });
    wrap(<MarketChartSection initialSymbol="فولاد" />);
    await waitFor(() => expect(screen.getByTestId('fake-engine')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('fake-engine-internal-change'));
    await waitFor(() => expect(screen.getByTestId('ms-chart-symbol')).toHaveTextContent('خودرو'));
    expect(screen.getByTestId('ms-chart-open-technical')).toHaveAttribute('href', '/technical/%D8%AE%D9%88%D8%AF%D8%B1%D9%88');
  });

  it('پرتراکنشِ تابلو به تعدادِ معاملاتِ واقعی رتبه می‌شود، نه به ترتیبِ پاسخ', async () => {
    mockRoutes({ '/api/watchlist': WATCH, '/api/mstat/mainwatch': BOARD });
    wrap(<MarketChartSection initialSymbol="فولاد" />);
    await waitFor(() => expect(screen.getByTestId('ms-chart-board-list')).toBeInTheDocument());
    const rows = [...screen.getByTestId('ms-chart-board-list').querySelectorAll('[data-testid^="ms-chart-board-list-row-"]')];
    expect(rows[0]).toHaveAttribute('data-testid', 'ms-chart-board-list-row-فولاد');
  });

  it('دیدۀ‌بانِ خالی، نمادِ مرجعِ بی‌ردیف را جعل نمی‌کند', async () => {
    mockRoutes({ '/api/watchlist': { status: 'success', count: 0, limit: 50, data: [] }, '/api/mstat/mainwatch': BOARD });
    wrap(<MarketChartSection initialSymbol="فولاد" />);
    await waitFor(() => expect(screen.getByTestId('ms-chart-watch-empty')).toBeInTheDocument());
    expect(screen.getByTestId('ms-chart-watch-empty').textContent).toContain('دیده‌بان خالی است');
    expect(screen.queryByText('BTCUSD')).not.toBeInTheDocument();
  });
});
