// __tests__/elite-funnel-hub.spec.tsx -- هابِ تحویل باید **رندرر** باشد، نه موتورِ داوری
//
// سه چیز را می‌پاید که خواستۀ بازطراحیِ کشفِ نماد بود:
//   ۱) هیچ گیتِ دست‌سازی درِ این فایل نیست: نه `score>=3`، نه `slice(0,50)`،
//      نه `slice(0,10)` — شمارشِ فهرست‌ها با شمارشِ خودِ قیف یکی است.
//   ۲) ارکانِ ۴گانه از `candidate.status` می‌آیند، نه از `phaseMarksFor`ِ دوم.
//   ۳) هیچ برچسبِ ستاپ/ساعت/ماشهِ اختراعی درِ UI نمی‌ماند.
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EliteFunnelHub } from '../features/master/ui/EliteFunnelHub';
import { useSymbolStore } from '../shared/stores/symbolStore';
import { useFunnelPrefsStore } from '../features/master/stores/funnelPrefsStore';

const SCREEN_ROWS = [
  {
    symbol: 'فولاد',
    name: 'فولاد مبارکه',
    sector_name: 'فلزات اساسی',
    pricing_mode: 'آزاد',
    score: 5,
    rev_growth: 42.5,
    gross_margin: 31.0,
    sales_to_mcap: 1.25,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    tech_trend_w: 'up',
    tech_matrix_decision: 'PERMITTED',
    tech_jet: true,
    excluded: false,
  },
  {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'فرآورده‌های نفتی',
    pricing_mode: 'آزاد',
    score: 4,
    rev_growth: 28.0,
    gross_margin: 18.5,
    sales_to_mcap: 0.95,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    tech_trend_w: 'up',
    tech_matrix_decision: 'PERMITTED',
    tech_fib_zone: '33-40',
    excluded: false,
  },
  {
    // ستاپِ روزانه دارد ولی وتوی سختِ هفتگی (چارت ۲) بر آن حاکم است
    symbol: 'خار',
    name: 'فولاد خار‌ساز',
    sector_name: 'محصولات فلزی',
    pricing_mode: 'آزاد',
    score: 5,
    rev_growth: 61.0,
    gross_margin: 34.0,
    sales_to_mcap: 1.8,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    tech_trend_w: 'down',
    tech_matrix_decision: 'REJECT',
    tech_jet: true,
    excluded: false,
  },
  {
    // روند هفتگی قابل تشخیص نیست ⇒ وتو نیست، فقط نظر داده نمی‌شود
    symbol: 'نوین',
    name: 'تازه‌وارد بدون دو پیوت',
    sector_name: 'فلزات اساسی',
    pricing_mode: 'آزاد',
    score: 4,
    rev_growth: 45.0,
    gross_margin: 26.0,
    sales_to_mcap: 0.9,
    i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true,
    tech_trend_w: 'na',
    tech_matrix_decision: 'UNKNOWN',
    tech_fib_zone: '61.8-70',
    excluded: false,
  },
];

vi.mock('@features/fundamental/api/useFtsScreen', () => ({
  useFtsScreen: () => ({ data: { status: 'ok', count: SCREEN_ROWS.length, data: SCREEN_ROWS, as_of: 1_730_000_000 }, isLoading: false }),
}));

vi.mock('@features/market/api/useMarketFeed', () => ({
  useMarketFeed: () => ({
    data: {
      data: [
        { symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات اساسي', is_live: true, vol_ratio: 2.3, f_jet: true, f_clock: true, p_last: 6200, p_closing: 6100, buy_power_i: 1.8 },
        { symbol: 'شپنا', name: 'پالایش نفت اصفهان', sector_name: 'فرآورده هاي نفتي', is_live: true, vol_ratio: 1.5, f_jet: false, f_clock: false, p_last: 4800, p_closing: 4800 },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock('@features/portfolio/api/usePortfolio', () => ({
  usePortfolio: () => ({
    data: {
      portfolio: [{ symbol: 'فولاد', sector: 'فلزات اساسی', weight_eff_pct: 18, price: 5800, stop_loss: 5400 }],
      decisions: [],
      limits: { weight_cap_pct: 20, sum_weight_pct: 18 },
    },
  }),
  useMarketCloses: () => ({ data: new Map([['فولاد', 6200], ['شپنا', 4800]]) }),
}));

// هوکِ رأیِ زنده موک می‌شود تا هیچ fetchِ واقعی درِ تست ساخته نشود؛ سقفِ واقعی
// برگردانده می‌شود تا صفِ بودجه با صفِ برنامه یکی بماند.
vi.mock('@features/master/api/useFtsTechBoard', () => ({
  TECH_QUERY_CAP: 60,
  useFtsTechBoard: () => ({
    map: new Map(),
    asOf: new Map<string, number>(),
    loading: false,
    wanted: 0,
    queued: 0,
    beyondCap: 0,
    resolved: 0,
  }),
}));

function renderHub() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EliteFunnelHub preset="custom" />
    </QueryClientProvider>,
  );
}

const listed = (sym: string) => screen.queryAllByText(sym).length;

describe('هابِ تحویلِ قیف FTS (EliteFunnelHub)', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
    useFunnelPrefsStore.getState().reset();
  });

  it('سه فهرست + نشانِ حالتِ کشف و مسیرِ داوری رندر می‌شود', () => {
    renderHub();
    expect(screen.getByText('فهرست‌هایِ تحویلِ قیف FTS')).toBeInTheDocument();
    for (const k of ['qualified', 'ready', 'portfolio']) {
      expect(screen.getByTestId(`hub-tab-${k}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('hub-mode-path').textContent).toContain('مهندسی معکوس');
  });

  it('مهندسیِ معکوس: فقط آنچه تابلو نشانه داده واردِ فهرستِ بنیادی می‌شود', () => {
    renderHub();
    // فولاد (ساعت/جت) از تابلو رد شده؛ شپنا هیچ فیلترِ دربِ روشنی ندارد
    expect(listed('فولاد')).toBeGreaterThan(0);
    expect(listed('شپنا')).toBe(0);
  });

  it('نمادِ درِ سبد به «آمادۀ تحویل» نمی‌رود — و بی‌داده هم اضافه نمی‌شود', () => {
    renderHub();
    fireEvent.click(screen.getByTestId('hub-tab-ready'));
    expect(listed('فولاد')).toBe(0);
    expect(screen.getByText(/هیچ نمادی هر چهار درِ/)).toBeInTheDocument();
  });

  it('مرورِ کامل بازار: universe از اسکرینر می‌آید و شمارش، شمارشِ خودِ مدل است', () => {
    useFunnelPrefsStore.getState().setMode('review');
    renderHub();
    expect(screen.getByTestId('hub-mode-path').textContent).toContain('مرورِ کامل بازار');
    for (const s of ['فولاد', 'شپنا', 'خار', 'نوین']) expect(listed(s)).toBeGreaterThan(0);
    // خطِ شمارشِ هاب همان عددِ قیف است (تک‌منبع) و هیچ slice‌ای پشتش نیست:
    // هر چهار واجد فهرست می‌شوند، نه ۵۰تا یا ۱۰تا به زور.
    expect(screen.getByTestId('hub-counts').textContent).toContain('۴ واجدِ بنیادی');
    expect(screen.getAllByRole('row')).toHaveLength(5); // سرستون + چهار نماد
  });

  it('وتوی سختِ هفتگی با ستاپِ روزانه دور زده نمی‌شود؛ بی‌داده وتو نیست', () => {
    useFunnelPrefsStore.getState().setMode('review');
    renderHub();
    fireEvent.click(screen.getByTestId('hub-tab-ready'));
    // خار: هفتگی نزولی + REJECT ⇒ درِ تکنیکال بسته، پس تحویل ندارد
    expect(listed('خار')).toBe(0);
    // نوین: UNKNOWN ⇒ «رد» نیست ولی «آماده» هم نیست — درِ بنیادیاش ماند
    expect(listed('نوین')).toBe(0);
    fireEvent.click(screen.getByTestId('hub-tab-qualified'));
    expect(listed('نوین')).toBeGreaterThan(0);
  });

  it('ستاپ و ماشه از خودِ موتور خوانده می‌شوند؛ برچسبِ اختراعی نمی‌ماند', () => {
    useFunnelPrefsStore.getState().setMode('review');
    renderHub();
    const body = document.body.textContent ?? '';
    expect(body).not.toContain('پولبک فیبو ۳۸-۶۲٪');
    expect(body).not.toContain('پرتاب ستاپ جت');
    expect(body).not.toContain('تا شکست');
    expect(body).not.toContain('الگوی ساعت فعال');
    fireEvent.click(screen.getByTestId('hub-tab-ready'));
    expect(screen.getByText('منبعِ رأیِ تکنیکال')).toBeInTheDocument();
  });

  it('کلیک روی نماد، آن را در استور سراسری فعال می‌کند', () => {
    renderHub();
    fireEvent.click(screen.getAllByText('فولاد')[0]);
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
  });

  it('تب سبد: وزن و سقف ۲۰٪ را نشان می‌دهد و هیچ نمادی را پنهان نمی‌کند', () => {
    renderHub();
    fireEvent.click(screen.getByTestId('hub-tab-portfolio'));
    expect(screen.getByText(/وزن در سبد/)).toBeInTheDocument();
    expect(screen.getByText(/۱۸٪/)).toBeInTheDocument();
  });

  it('دکمه جمع‌کردن جدول وضعیت را تاشو می‌کند', () => {
    renderHub();
    fireEvent.click(screen.getByTitle('جمع‌کردن جدول'));
    expect(screen.getByText('نمایش قیف ▼')).toBeInTheDocument();
  });
});
