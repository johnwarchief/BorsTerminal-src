import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EliteFunnelHub } from '../features/master/ui/EliteFunnelHub';
import { useSymbolStore } from '../shared/stores/symbolStore';

// موک‌کردن هوک‌های داده
vi.mock('@features/fundamental/api/useFtsScreen', () => ({
  useFtsScreen: () => ({
    data: {
      status: 'ok',
      count: 2,
      data: [
        {
          symbol: 'فولاد',
          name: 'فولاد مبارکه',
          sector_name: 'فلزات اساسی',
          pricing_mode: 'آزاد',
          score: 5,
          rev_growth: 42.5,
          gross_margin: 31.0,
          sales_to_mcap: 1.25,
          tech_trend_w: 'up',
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
          tech_trend_w: 'up',
          tech_fib_zone: '38.2%',
          excluded: false,
        },
        {
          // ستاپِ روزانه دارد ولی وتوی سختِ هفتگی (چارت ۳) بر آن حاکم است
          symbol: 'خار',
          name: 'فولاد خار‌ساز',
          sector_name: 'محصولات فلزی',
          pricing_mode: 'آزاد',
          score: 5,
          rev_growth: 61.0,
          gross_margin: 34.0,
          sales_to_mcap: 1.8,
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
          tech_trend_w: 'na',
          tech_matrix_decision: 'UNKNOWN',
          tech_fib_zone: '61.8-70',
          excluded: false,
        },
      ],
    },
  }),
}));

vi.mock('@features/market/api/useMarketFeed', () => ({
  useMarketFeed: () => ({
    data: {
      data: [
        { symbol: 'فولاد', vol_ratio: 2.3, f_jet: true, f_clock: true, p_last: 6200, buy_power_i: 1.8 },
        { symbol: 'شپنا', vol_ratio: 1.5, f_jet: false, f_clock: false, p_last: 4800, buy_power_i: 1.2 },
      ],
    },
  }),
}));

vi.mock('@features/portfolio/api/usePortfolio', () => ({
  usePortfolio: () => ({
    data: {
      portfolio: [
        { symbol: 'فولاد', sector: 'فلزات اساسی', weight_eff_pct: 18, price: 5800, stop_loss: 5400 },
      ],
      decisions: [],
      limits: { weight_cap_pct: 20, sum_weight_pct: 18 },
    },
  }),
  useMarketCloses: () => ({
    data: new Map([
      ['فولاد', 6200],
      ['شپنا', 4800],
    ]),
  }),
}));

function renderHub() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EliteFunnelHub />
    </QueryClientProvider>,
  );
}

describe('ماژول قیف غربالگری نخبگان FTS (EliteFunnelHub)', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
  });

  it('هر ۳ تب سوییچر قیف نخبگان با استایل بلومبرگ رندر می‌شوند', () => {
    renderHub();
    expect(screen.getByText('قیف غربالگری نخبگان FTS (Elite Funnel Hub)')).toBeInTheDocument();
    expect(screen.getByText('۵۰ نماد بنیادی')).toBeInTheDocument();
    expect(screen.getByText('۱۰ واچلیست داغ 🔥')).toBeInTheDocument();
    expect(screen.getByText('پورتفوی فعال')).toBeInTheDocument();
  });

  it('تب ۵۰ نماد بنیادی نمادها و ستون‌های FTS را نشان می‌دهد', () => {
    renderHub();
    expect(screen.getAllByText('فولاد').length).toBeGreaterThan(0);
    expect(screen.getAllByText('شپنا').length).toBeGreaterThan(0);
    expect(screen.getByText(/رشد فروش YTD/)).toBeInTheDocument();
    expect(screen.getByText(/حاشیه سود ناخالص/)).toBeInTheDocument();
  });

  it('کلیک روی نماد، آن را در استور سراسری فعال می‌کند', () => {
    renderHub();
    const row = screen.getAllByText('فولاد')[0];
    fireEvent.click(row);
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
  });

  it('سوییچ به تب واچلیست داغ، ستاپ‌های معاملاتی را نمایش می‌دهد', () => {
    renderHub();
    fireEvent.click(screen.getByText('۱۰ واچلیست داغ 🔥'));
    expect(screen.getByText('ستاپ معاملاتی')).toBeInTheDocument();
    expect(screen.getByText('پرتاب ستاپ جت')).toBeInTheDocument();
  });

  it('وتوی سختِ هفتگی با ستاپِ روزانه دور زده نمی‌شود؛ بی‌داده وتو نیست', () => {
    renderHub();
    // هر چهار نماد در مرحلهٔ ۵۰تایی بنیادی دیده می‌شوند (هیچ‌کس پنهان نمی‌شود)
    expect(screen.getAllByText('خار').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('۱۰ واچلیست داغ 🔥'));
    // ولی سهمِ نزولیِ هفتگی با وجود f_jet وارد مرحلهٔ ۱۰نفره نمی‌شود
    expect(screen.queryAllByText('خار')).toHaveLength(0);
    // سهمِ تازه‌وارد (trend=na / decision=UNKNOWN) وتو نمی‌شود و باقی می‌ماند
    expect(screen.getAllByText('نوین').length).toBeGreaterThan(0);
  });

  it('سوییچ به تب پورتفوی فعال، وضعیت وزن و سقف ۲۰٪ را نمایش می‌دهد', () => {
    renderHub();
    fireEvent.click(screen.getByText('پورتفوی فعال'));
    expect(screen.getByText(/وزن در سبد/)).toBeInTheDocument();
    expect(screen.getByText(/۱۸٪/)).toBeInTheDocument();
  });

  it('دکمه جمع‌کردن جدول وضعیت را تاشو می‌کند', () => {
    renderHub();
    const collapseBtn = screen.getByTitle('جمع‌کردن جدول');
    fireEvent.click(collapseBtn);
    expect(screen.getByText('نمایش قیف ▼')).toBeInTheDocument();
  });
});
