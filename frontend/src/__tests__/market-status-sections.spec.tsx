// تستِ مرحلۀ ۱ و ۲ِ «وضعیت بازار»: معماریِ بخش‌ها + پنل‌هایِ رتبه‌ای، سفارش،
// مالکیت و کارتِ شاخص.
//
// چرا این‌جا: رأیِ مالک این است که «یک کامپوننتِ موجود» اثباتِ قابلیت نیست.
// پس این فایل سه چیزی را می‌سنجد که درِ مرجع مهم‌اند و درِ رابطِ ساختگی به‌راحتی
// می‌شکنند: (۱) ناوبریِ بخش‌ها واقعاً به بخش می‌رود، (۲) «اعمال فیلتر» فقط
// دکمه نیست و تا اعمال نشود عدد عوض نمی‌شود، (۳) سفارش از معامله و مالکیت از
// جریانِ پول درِ همان رندر جدا می‌مانند.
//
// توجه: همه‌جا jsdom. این‌ها تستِ کامپوننت‌اند، نه تستِ مرورگرِ واقعی — درِ
// report هم همین‌طور ثبت می‌شوند.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketStatusPage from '@features/market/routes/MarketStatusPage';
import { IndexCards } from '@features/market/components/IndexCards';
import { MarketSectionNav, SectionHeading } from '@features/market/components/MarketSectionNav';
import { MarketTreemap } from '@features/market/components/MarketTreemap';
import { OrdersPanel, OwnershipPanel } from '@features/market/components/OrderOwnershipSection';
import { RankedPanelCard, TopListsGrid } from '@features/market/components/RankedPanels';
import type { IndexCardsFeed, OrderFlowsFeed, OwnershipFeed, RankedPanel } from '@features/market/api/useMarketPanels';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;
const dead = () => ({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'x' }) }) as unknown as Response;
const ASOF = { d_even: 20261012, h_even: 121500, client_d_even: 20261012, client_lag_days: false, depth: true, top50: 50, n: 1200 };

/** ردیفِ پنلِ رتبه‌ای — `value_field` درِ ردیف هم نام‌گذاری شده تا میله با مقدار برابری شود */
function panel(key: string, title: string, value_field: string, values: [string, number, number][]): RankedPanel {
  const max = Math.max(...values.map((v) => Math.abs(v[1])), 1);
  return {
    key,
    title,
    unit: 'میلیارد تومان',
    formula: `${title} = تعریفِ سرور`,
    value_field,
    candidates: values.length + 3,
    note: null,
    rows: values.map(([symbol, value, pct], i) => ({
      rank: i + 1,
      symbol,
      ins_code: `i${i}`,
      name: `نامِ ${symbol}`,
      industry: 'فلزات',
      bar_pct: (Math.abs(value) / max) * 100,
      tone: pct > 0 ? 'pos' : pct < 0 ? 'neg' : 'zero',
      pct,
      p_closing: 1000 + i,
      [value_field]: value,
    })),
  } as unknown as RankedPanel;
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(() => Promise.resolve(dead()));
  // jsdom scrollIntoView ندارد و ناوبری بی‌آن درِ jump می‌شکند
  Element.prototype.scrollIntoView = vi.fn();
});

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

describe('ناوبریِ بخش‌ها (مرحلۀ ۱)', () => {
  const SECTIONS = [
    { id: 'a-sec', label: 'نمای کلی', pages: [6, 7] },
    { id: 'b-sec', label: 'نقشۀ بازار', pages: [2] },
  ];

  it('هر بخش یک دکمه دارد و کلیک، همان بخش را فعال می‌کند', () => {
    const changed = vi.fn();
    wrap(
      <>
        <MarketSectionNav sections={SECTIONS} onActiveChange={changed} />
        <SectionHeading id="a-sec" title="نمای کلی" pages={[6, 7]} />
        <SectionHeading id="b-sec" title="نقشۀ بازار" pages={[2]} />
      </>,
    );
    expect(screen.getByTestId('market-section-a-sec')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('market-section-b-sec'));
    expect(screen.getByTestId('market-section-b-sec')).toHaveAttribute('aria-current', 'true');
    expect(changed).toHaveBeenCalledWith('b-sec');
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('سرِصفحه شماره‌های مرجع را می‌نویسد تا ماتریسِ تحویل با صفحه یکی خوانده شود', () => {
    wrap(<SectionHeading id="a-sec" title="نمای کلی" pages={[6, 7]} desc="توضیح" />);
    expect(screen.getByTestId('section-heading-a-sec').textContent).toContain('۶، ۷');
  });

  it('مشاهده‌شدنِ واقعیِ بخش (IntersectionObserver) هایلایت را عوض می‌کند', async () => {
    const instances = (globalThis.IntersectionObserver as unknown as { instances: { fire: (e: unknown[]) => void }[] }).instances;
    wrap(
      <>
        <MarketSectionNav sections={SECTIONS} />
        <SectionHeading id="a-sec" title="نمای کلی" pages={[6, 7]} />
        <SectionHeading id="b-sec" title="نقشۀ بازار" pages={[2]} />
      </>,
    );
    const io = instances[instances.length - 1];
    expect(io).toBeTruthy();
    io.fire([
      { isIntersecting: true, target: document.getElementById('b-sec'), intersectionRatio: 0.4 },
      { isIntersecting: false, target: document.getElementById('a-sec'), intersectionRatio: 0 },
    ]);
    await waitFor(() =>
      expect(screen.getByTestId('market-section-b-sec')).toHaveAttribute('aria-current', 'true'),
    );
  });
});

describe('صفحۀ بازسازی‌شداده — هر هفت بخش', () => {
  it('همۀ بخش‌ها با سرِصفحۀ شماره‌دار رندر می‌شوند، حتی وقتی هیچ اندپوینتی جواب نمی‌دهد', async () => {
    wrap(<MarketStatusPage />);
    for (const id of [
      'ms-sec-overview', 'ms-sec-treemap', 'ms-sec-tops', 'ms-sec-orders',
      'ms-sec-gold', 'ms-sec-compare', 'ms-sec-chart', 'ms-sec-tables',
    ]) {
      await waitFor(() => expect(screen.getByTestId(`section-heading-${id}`)).toBeInTheDocument());
    }
  });

  // هر بخش اندپوینتِ خودش را صدا می‌زند؛ «خطای یک بلوک بقیه را نمی‌سوزاند» درِ
  // تستِ خودِ کامپوننت سنجیده شده (ms-toplists/-orders/-ownership-error) و این‌جا
  // صبر برایِ هفت اندپوینت با backoffِ ۵۰۰ در jsdom، زمانِ بی‌دلیلِ تست است.
  it('بخش‌های تازه هر کدام اندپوینتِ خودش را می‌خوانند', async () => {
    wrap(<MarketStatusPage />);
    await waitFor(
      () => {
        const urls = fetchMock.mock.calls.map((c) => String(c[0]));
        for (const p of [
          '/api/mstat/treemap',
          '/api/mstat/tops',
          '/api/mstat/orderflows',
          '/api/mstat/ownership',
          '/api/mstat/indexcards',
          '/api/mstat/gold',
          '/api/mstat/series',
        ]) {
          expect(urls.some((u) => u.includes(p))).toBe(true);
        }
      },
      { timeout: 12_000 },
    );
  }, 20_000);

  // مرحلۀ ۱ مأموریت (2026-10-19): کارت‌های شاخص باید *اولین* بلوکِ صفحه باشند و
  // «نگاهی به بازار» ازِ نمایِ اصلی برود. این دو را درِ خودِ DOM می‌سنجم، نه با
  // خواندنِ متنِ فایل — گاردهایی که متنِ سورس را grep می‌کنند، جابه‌جاییِ واقعی
  // را نمی‌بینند.
  it('کارت‌های شاخص اولین بلوکِ صفحه‌اند و «نگاهی به بازار» دیگر نیست', async () => {
    wrap(<MarketStatusPage />);
    await waitFor(() => expect(screen.getByTestId('ms-index-cards')).toBeInTheDocument());
    const page = screen.getByTestId('market-status-page');
    expect(page.firstElementChild).toBe(screen.getByTestId('ms-index-cards'));
    expect(screen.queryByTestId('ms-glance')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ms-glance-grid')).not.toBeInTheDocument();
  });
});

describe('نقشۀ بازار (صفحۀ ۲ و ۱۲)', () => {
  const TREEMAP = {
    status: 'ok',
    asof: ASOF,
    computed_at: '2026-10-12T12:15:00',
    group: 'eq_all',
    group_label: 'سهام، حق تقدم و ص.سهامی',
    industry: '',
    metric: 'value',
    metric_label: 'ارزش معاملات',
    metric_unit: 'میلیارد تومان',
    basis: 'same_session_snapshot',
    formula: { pct: 'p_closing ÷ p_yesterday − 1' },
    total_nodes: 3,
    shown: 2,
    skipped_nodata: 1,
    total_size: 300,
    rows: [
      { symbol: 'فولاد', ins_code: '1', name: 'مبارکه', industry: 'فلزات', cls: 'stock', kind: 'stock', pct: 1.8, tone: 'pos', size: 200, size_field: 'value_b_toman', unit: 'میلیارد تومان', share_pct: 66.7, p_closing: 520 },
      { symbol: 'خودرو', ins_code: '2', name: 'ایران خودرو', industry: 'خودرو', cls: 'stock', kind: 'stock', pct: -2.4, tone: 'neg', size: 100, size_field: 'value_b_toman', unit: 'میلیارد تومان', share_pct: 33.3, p_closing: 145 },
    ],
    groups: [{ industry: 'فلزات', symbols: 1, size: 200, share_pct: 66.7, pos: 1, neg: 0, nodata: 0 }],
    no_source: [],
    source: 'local:market.db',
  };

  beforeEach(() => {
    // jsdom clientWidth را صفر می‌دهد و چیدمان بی‌عرض هیچ مستطیلی نمی‌سازد؛
    // عرضِ ثابتِ ۱۰۲۴ یعنی همان هندسه‌ای که مرورگر دسکتاپ می‌بیند.
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 1024 });
  });

  function renderTreemap(body: unknown = TREEMAP, props: Partial<{ fixedGroup: string; testId: string }> = {}) {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(String(url).includes('/api/mstat/treemap') ? json(body) : dead()),
    );
    return wrap(<MarketTreemap {...props} />);
  }

  it('سطحِ هر خانه از size خودِ ردیف می‌آید و رنگ از tone سرور', async () => {
    renderTreemap();
    await waitFor(() => expect(screen.getByTestId('treemap-cell-فولاد')).toBeInTheDocument());
    const big = screen.getByTestId('treemap-cell-فولاد').querySelector('rect');
    const small = screen.getByTestId('treemap-cell-خودرو').querySelector('rect');
    const areaOf = (r: Element | null) => Number(r?.getAttribute('width') ?? 0) * Number(r?.getAttribute('height') ?? 0);
    // ۲۰۰ در برابرِ ۱۰۰ ⇒ سطحِ دوبل، با تلورانسِ ۱٪ِ چیدمانِ squareified
    expect(areaOf(small)).toBeGreaterThan(0);
    expect(areaOf(big) / areaOf(small)).toBeGreaterThan(1.8);
    expect(areaOf(big) / areaOf(small)).toBeLessThan(2.2);
    expect(screen.getByTestId('treemap-cell-فولاد')).toHaveAttribute('data-tone', 'pos');
    expect(screen.getByTestId('treemap-cell-خودرو')).toHaveAttribute('data-tone', 'neg');
  });

  it('«اعمال فیلتر» تا کلیک نشود معیار را عوض نمی‌کند', async () => {
    renderTreemap();
    await waitFor(() => expect(screen.getByTestId('ms-treemap-apply')).toBeDisabled());
    fireEvent.change(screen.getByTestId('ms-treemap-metric'), { target: { value: 'volume' } });
    expect(screen.getByTestId('ms-treemap-dirty')).toBeInTheDocument();
    expect(screen.getByTestId('ms-treemap-apply')).toBeEnabled();
    // هنوز اعمال نشده: درخواستِ دوم با معیارِ تازه ساخته نمی‌شود
    const before = fetchMock.mock.calls.filter((c) => String(c[0]).includes('metric=volume')).length;
    expect(before).toBe(0);
    fireEvent.click(screen.getByTestId('ms-treemap-apply'));
    await waitFor(() => expect(screen.queryByTestId('ms-treemap-dirty')).not.toBeInTheDocument());
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('metric=volume'))).toBe(true);
  });

  it('بی‌معامله‌ها درِ چیدمان نمی‌نشینند و شمارشان اعلام می‌شود', async () => {
    renderTreemap();
    await waitFor(() => expect(screen.getByTestId('ms-treemap-count')).toBeInTheDocument());
    expect(screen.getByTestId('ms-treemap-count').textContent).toContain('۱ نمادِ بی‌');
    expect(screen.getByTestId('ms-treemap-legend').children).toHaveLength(4);
  });

  it('صفحۀ ۱۲ همان کامپوننت است، با دامنهٔ قفل‌شده و بی‌کرکرۀ دامنه', async () => {
    renderTreemap({ ...TREEMAP, group: 'gold_fund', group_label: 'صندوق‌های طلا' }, { fixedGroup: 'gold_fund', testId: 'ms-gold-treemap' });
    await waitFor(() => expect(screen.getByTestId('treemap-cell-فولاد')).toBeInTheDocument());
    expect(screen.queryByTestId('ms-gold-treemap-group')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ms-gold-treemap-apply')).toBeDisabled();
  });

  it('خطای سرویس با HTTP 200 «خانه‌ای نماند» نمی‌شود — علتِ خودش را می‌گوید', async () => {
    // این همان حالتِ top50 در پایۀِ قبل از اصلاح بود: دروازۀ mstat استثنا را
    // درِ بدنه می‌گذارد و HTTP 200 است، پس رابط آن را «بی‌داده» می‌خواند.
    renderTreemap({ status: 'error', message: "argument of type 'NoneType' is not a container",
      source: 'local:market.db' });
    await waitFor(() => expect(screen.getByTestId('ms-treemap-error')).toBeInTheDocument());
    const err = screen.getByTestId('ms-treemap-error');
    expect(err.getAttribute('data-error-kind')).toBe('service-error');
    expect(err.textContent).toContain('NoneType');
    expect(screen.queryByText(/خانه‌ای نماند/)).not.toBeInTheDocument();
  });

  it('معیارِ بی‌منبع (ارزش بازار در بانکِ بی‌ستون) صریح اعلام می‌شود، نه با صفر', async () => {
    renderTreemap({
      ...TREEMAP,
      rows: [],
      shown: 0,
      no_source: [{ key: 'cap', label: 'ارزش بازار', why: 'ستونِ market_cap در این بانک نیست', needed: null }],
    });
    await waitFor(() => expect(screen.getByTestId('ms-treemap-nodata')).toBeInTheDocument());
    expect(screen.getByTestId('ms-treemap-no_source').textContent).toContain('ستونِ market_cap');
  });
});

describe('پنل‌های رتبه‌ای (صفحۀ ۸)', () => {
  const PANELS = [
    panel('impact_pos', 'بیشترین اثرِ مثبت بر شاخص', 'impact_points', [['فولاد', 120, 1.8], ['وشمال', 60, 0.9]]),
    panel('impact_neg', 'بیشترین اثرِ منفی بر شاخص', 'impact_points', [['خودرو', -80, -2.4]]),
    panel('most_value', 'بیشترین ارزشِ معامله', 'value_b_toman', [['شپنا', 300, 0.4]]),
    panel('most_volume', 'بیشترین حجم', 'volume_m_share', [['خرام', 900, -0.2]]),
  ];

  it('چهار پنلِ جدا رندر می‌شوند و عنوان/یکا/فرمول از خودِ پاسخ می‌آیند', () => {
    wrap(<TopListsGrid panels={PANELS} isLoading={false} isError={false} onRetry={() => {}} />);
    for (const p of PANELS) {
      expect(screen.getByTestId(`ms-toplists-${p.key}`)).toBeInTheDocument();
      expect(screen.getByTestId(`ms-toplists-${p.key}-formula`).textContent).toBe(p.formula);
    }
    expect(screen.getByTestId('ms-toplists-impact_pos-link-فولاد')).toHaveAttribute('href', '/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF');
  });

  it('«اثر بر شاخص» درصدِ رشد نیست: یکا و ستونِ معیار جدا چاپ می‌شوند', () => {
    wrap(<RankedPanelCard panel={PANELS[0]} testId="p" />);
    expect(screen.getByTestId('p-row-فولاد').textContent).toContain('۱۲۰.۰');
    expect(screen.getByTestId('p-bar-فولاد')).toBeInTheDocument();
    expect(screen.getByTestId('p-candidates').textContent).toContain('«impact_points»');
  });

  it('پسماندِ اعلام‌شدۀ اثرِ شاخص عیناً از پاسخ می‌آید و برازش نمی‌شود', () => {
    wrap(
      <TopListsGrid
        panels={PANELS}
        isLoading={false}
        isError={false}
        onRetry={() => {}}
        reconciliation={{ sum_of_impacts: -43577, official_index_change: -34771, rel_diff_pct: 25.3, meaning: 'پسماند عمدتاً از سهامِ آزادِ شناورِ نبوده است' }}
      />,
    );
    expect(screen.getByTestId('ms-toplists-reconciliation').textContent).toContain('پسماند عمدتاً از سهامِ آزادِ شناورِ نبوده است');
    expect(screen.getByTestId('ms-toplists-reconciliation').textContent).toContain('۲۵.۳');
  });

  it('خطا فقط همین بلوک را می‌سوزاند و دکمۀ تلاشِ دوباره می‌آید', () => {
    const onRetry = vi.fn();
    wrap(<TopListsGrid panels={[]} isLoading={false} isError onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId('ms-toplists-retry'));
    expect(onRetry).toHaveBeenCalled();
  });

  it('پنلِ بی‌ردیف «یادداشتِ سرور» را می‌نویسد، نه ردیفِ صفر', () => {
    wrap(<RankedPanelCard panel={{ ...PANELS[1], rows: [], note: 'در این دامنه نمادی اثرِ منفیِ سنجیده ندارد' }} testId="p" />);
    expect(screen.getByTestId('p-empty').textContent).toContain('اثرِ منفیِ سنجیده ندارد');
  });
});

describe('سفارش‌ها و مالکیت (صفحۀ ۹)', () => {
  const ORDERS = {
    status: 'ok', asof: ASOF, computed_at: 'x', group: 'all', orders_available: true,
    symbols_with_orders: 512, symbols_in_scope: 1200, unit: 'میلیون سهم',
    basis: 'buy_q_vol/sell_q_vol', formula: { order: 'Σ buy_q_vol', executed: 'q_tot_tran' },
    totals: {
      buy_order_m_share: 640.5, sell_order_m_share: 380.2, net_order_m_share: 260.3,
      executed_m_share: 1290.7, buy_sell_ratio: 1.68,
      order_vs_executed_note: 'سفارشِ مانده با حجمِ معاملهٔ انجام‌شده یکی نیست',
    },
    buy_panels: panel('buy_q', 'بیشترین صفِ خرید', 'buy_order_m_share', [['فولاد', 90, 1.2]]),
    sell_panels: panel('sell_q', 'بیشترین صفِ فروش', 'sell_order_m_share', [['خودرو', 40, -2.1]]),
    no_source: [], source: 'local:market.db',
  } as unknown as OrderFlowsFeed;

  const OWNER = {
    status: 'ok', asof: ASOF, computed_at: 'x', group: 'all', symbols_with_client_data: 700,
    unit: 'میلیون سهم', basis: 'buy_n_vol/sell_n_vol',
    formula: { legal_net: '(buy_n_vol − sell_n_vol)', pct_of_capital: 'سهمِ شرکت', not_to_be_confused: 'این عدد نه خالصِ ورودِ پول است و نه سرانه' },
    totals: { legal_net_m_share: -120.4, real_net_m_share: 120.4 },
    client_data_lags_session: true,
    to_legal_panel: panel('to_legal', 'سهمِ منتقل‌شده به حقوقی', 'legal_net_m_share', [['فولاد', 12, 0.3]]),
    to_real_panel: panel('to_real', 'سهمِ منتقل‌شده به حقیقی', 'real_net_m_share', [['خودرو', 9, -0.4]]),
    no_source: [], source: 'local:market.db',
  } as unknown as OwnershipFeed;

  it('حجمِ سفارش از حجمِ معامله جدا و با عددِ خودش می‌نشیند', () => {
    wrap(<OrdersPanel data={ORDERS} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('ms-orders-buy').textContent).toContain('۶۴۰.۵');
    expect(screen.getByTestId('ms-orders-exec').textContent).toContain('۱۲۹۰.۷');
    expect(screen.getByTestId('ms-orders-exec').textContent).not.toContain('۶۴۰.۵');
    expect(screen.getByTestId('ms-orders-note').textContent).toContain('سفارشِ مانده با حجمِ معاملهٔ انجام‌شده یکی نیست');
    expect(screen.getByTestId('ms-orders-buy-panel')).toBeInTheDocument();
  });

  it('دفترِ سفارشِ نخورده، پنل را بی‌عدد می‌گذارد و علت را می‌نویسد', () => {
    wrap(
      <OrdersPanel
        data={{ ...ORDERS, orders_available: false, totals: null, no_source: [{ key: 'depth', label: 'دفترِ سفارش', why: 'buy_q_vol در این نشست نرسیده', needed: null }] }}
        isLoading={false}
        isError={false}
        onRetry={() => {}}
      />,
    );
    expect(screen.getByTestId('ms-orders-nodata')).toBeInTheDocument();
    expect(screen.queryByTestId('ms-orders-buy')).not.toBeInTheDocument();
    expect(screen.getByTestId('ms-orders-no_source').textContent).toContain('buy_q_vol');
  });

  it('تغییرِ مالکیت با یکایِ سهم است و با «خالصِ ورودِ پول» اشتباه نمی‌شود', () => {
    wrap(<OwnershipPanel data={OWNER} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('ms-ownership-legal').textContent).toContain('میلیون سهم');
    expect(screen.getByTestId('ms-ownership-diff').textContent).toContain('نه خالصِ ورودِ پول');
    expect(screen.getByTestId('ms-ownership-lag')).toBeInTheDocument();
    expect(screen.getByTestId('ms-ownership-to-legal')).toBeInTheDocument();
  });

  it('ردیفِ تفکیکِ نرسیده: بی‌داده با علت، نه صفر', () => {
    wrap(<OwnershipPanel data={{ ...OWNER, symbols_with_client_data: 0 }} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('ms-ownership-nodata')).toBeInTheDocument();
    expect(screen.queryByTestId('ms-ownership-legal')).not.toBeInTheDocument();
  });
});

describe('کارت‌های شاخص (صفحۀ ۶/۷)', () => {
  const CARDS = {
    status: 'ok', computed_at: 'x',
    cards: [
      { key: 'tedpix', label: 'شاخص کل', available: true, value: 2145000, change: -34771, pct: -1.6, unit: 'واحد', tone: 'neg', spark: [2150000, 2145000], formula: 'وزنیِ ارزشی', asof_d_even: 20261012 },
      { key: 'ewindex', label: 'شاخص هم‌وزن', available: true, value: 19000, change: 12, pct: 0.6, unit: 'واحد', tone: 'pos', spark: [], formula: 'هم‌وزن', asof_d_even: 20261012 },
      { key: 'vwprice', label: 'قیمتِ وزنیِ ارزشی', available: false, value: null, change: null, pct: null, unit: 'ریال', tone: 'nodata', spark: null, formula: 'q_tot_cap ÷ q_tot_tran', asof_d_even: null },
    ],
    source: 'local:market.db', history_points: 20, history_days: [20261001, 20261012], trades: 1200,
    market_total_b_toman: 2485700, market_total_source: 'tsetmc official', note: 'x', blockers: [],
  } as unknown as IndexCardsFeed;

  it('فقط شاخصی که موتورِ چارت می‌شناسد لینک می‌گیرد؛ بقیه صریح «بی‌کندل» می‌مانند', () => {
    wrap(<IndexCards data={CARDS} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('index-card-chart-tedpix')).toBeInTheDocument();
    expect(screen.getByTestId('index-card-nochart-ewindex')).toHaveTextContent('بی‌کندل');
    expect(screen.getByTestId('index-card-missing-vwprice')).toHaveTextContent('عددی ساخته نمی‌شود');
    expect(screen.getByTestId('index-card-vwprice').textContent).not.toMatch(/[۰-۹0-9]{4}/);
  });

  it('تاریخچۀ کوتاه درِ همان کارت اعلام می‌شود، نه به‌عنوان سریِ کامل', () => {
    wrap(<IndexCards data={{ ...CARDS, history_points: 2 }} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('ms-index-cards-span').textContent).toContain('۲ روزِ شاخصِ رسمی');
  });

  // ── مرحلۀ ۱ مأموریت (2026-10-19): کارت‌های شاخص به بالایِ صفحه رفتند، پس
  //    قراردادِ هر چهار فیلد (مقدار، تغییرِ مطلق، درصد، جهت) باید همین‌جا میخکوب
  //    شود — و «بی‌ساعت» با «بی‌داده» یکی نشود.
  const fa = (t: unknown) => (String(t ?? '').match(/[۰-۹]/g) ?? [])
    .map((c) => String(c.charCodeAt(0) - 0x06f0)).join('');

  it('مقدار، تغییرِ مطلق، درصد و جهت هر چهار از خودِ پاسخ نوشته می‌شوند', () => {
    wrap(<IndexCards data={CARDS} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(fa(screen.getByTestId('index-card-value-tedpix').textContent)).toBe('2145000');
    expect(fa(screen.getByTestId('index-card-change-tedpix').textContent)).toContain('34771');
    const pct = screen.getByTestId('index-card-pct-tedpix').textContent ?? '';
    expect(pct).toContain('٪');
    expect(pct.trim().startsWith('-')).toBe(true);
    expect(fa(pct)).toBe('16');
    expect(screen.getByTestId('index-card-arrow-tedpix').textContent).toBe('▼');
    expect(screen.getByTestId('index-card-arrow-ewindex').textContent).toBe('▲');
    // رنگ از همان toneِ پاسخ می‌آید، نه از حدسِ خودِ رابط (توکنِ طراحیِ سراسری)
    expect(screen.getByTestId('index-card-tedpix').getAttribute('data-tone')).toBe('neg');
    expect(screen.getByTestId('index-card-value-tedpix').className).toContain('text-tone-neg');
    expect(screen.getByTestId('index-card-value-ewindex').className).toContain('text-tone-pos');
  });

  it('بی‌درصد: نه فلشِ جهت ساخته می‌شود نه ٪', () => {
    const base = CARDS.cards ?? [];
    const noPct = {
      ...CARDS,
      cards: [{ ...base[0], pct: null }, base[1], base[2]],
    } as unknown as IndexCardsFeed;
    wrap(<IndexCards data={noPct} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('index-card-arrow-tedpix').textContent).toBe('');
    expect(screen.getByTestId('index-card-pct-tedpix').textContent).toBe('—');
  });

  it('ساعت نیامده ولی روزِ معاملۀ ردیف آمده ⇒ «روزِ داده»، نه «بی‌داده»', () => {
    wrap(<IndexCards data={CARDS} isLoading={false} isError={false} onRetry={() => {}} />);
    const asof = screen.getByTestId('ms-index-cards-asof').textContent ?? '';
    expect(asof).toContain('روزِ داده');
    expect(fa(asof)).toBe('20261012');
    expect(asof).not.toContain('بی‌داده');
  });

  it('نه ساعت نه روز ⇒ همان «بی‌داده» می‌ماند (روز از خودِ رابط نمی‌آید)', () => {
    const noDay = {
      ...CARDS,
      cards: (CARDS.cards ?? []).map((c) => ({ ...c, asof_d_even: null })),
    } as unknown as IndexCardsFeed;
    wrap(<IndexCards data={noDay} isLoading={false} isError={false} onRetry={() => {}} />);
    expect(screen.getByTestId('ms-index-cards-asof').textContent).toContain('بی‌داده');
  });
});
