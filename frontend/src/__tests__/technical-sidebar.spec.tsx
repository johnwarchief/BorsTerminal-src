// تست سایدبار راست تکنیکال — تبِ لایه‌های FTS پیش‌فرض، فیلترهای خالصِ اسکرینر
// و ترازهای نماد فعال. «دیده‌بان» عمداً از این سایدبار حذف شده (بند ب مأموریت)؛
// نبودنش همین‌جا قفل می‌شود تا با «فراموشی» برنگردد.
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { TechnicalSidebar } from '@features/technical/components/TechnicalSidebar';
import { SidebarFtsSignals } from '@features/technical/components/SidebarFtsSignals';
import { SidebarActiveLevels, type ActiveLevelsView } from '@features/technical/components/SidebarActiveLevels';
import { filterWatchlist, tradingValue } from '@features/technical/api/useWatchlist';
import {
  FTS_FILTERS_DEFAULT,
  filterFtsSignalRows,
  filterFtsSignals,
  firstScreenerSymbol,
  ftsSignalTags,
  type ScreenerRow,
} from '@features/technical/api/useScreener';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';
import type { MarketRow } from '@shared/types/marketRow';

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

function row(partial: Partial<MarketRow>): MarketRow {
  return { symbol: 'x', is_live: true, ...partial } as unknown as MarketRow;
}

function srow(partial: Partial<ScreenerRow>): ScreenerRow {
  return { symbol: 'x', ...partial } as unknown as ScreenerRow;
}

/** پیلود نمونهٔ سرور (/api/fts/{symbol}) — همان چیزی که پنل فقط نمایش می‌دهد */
const FTS: FtsAnalysisData = {
  fib: {
    retrace_base_low: 2010,
    zone_33_40: { lo: 2739, hi: 2839, in_zone: false },
    zone_618_70: { lo: 2346, hi: 2447, in_zone: false },
  },
  jet: { active: true, resistance: 2820 },
  point_hunt: { floor_price: 2450, touches: 3 },
  double_bottom: { neckline: 2600 },
  exit_engine: {
    verdict: 'caution',
    signals: ['ma14_watch', 'rsi_divergence'],
    l1: { hard_stop: 2819, stop_basis: 'entry', ma14: 2900, ma14_exit_pending: true, close: 2967 },
  },
};

const ACTIVE: ActiveLevelsView = {
  symbol: 'فولاد',
  fts: FTS,
  ma100: 2300,
  lastClose: 2967,
  setups: ['breakout'],
  context: ['fib_zone_33_40'],
  direction: 'bullish',
};

const ACTIVE_STOP_HIT: ActiveLevelsView = {
  ...ACTIVE,
  fts: {
    ...FTS,
    exit_engine: { verdict: 'stop', signals: ['stop_hard'], l1: { ...FTS.exit_engine?.l1, stop_hit: true } },
  },
};

/** همان شیئی که TechnicalPage از کوئریِ `/api/fts` می‌سازد — بی‌داده یا با داده */
const FTS_CONTEXT = {
  fts: FTS,
  status: 'ok',
  message: null,
  isLoading: false,
  isError: false,
  basis: 'tsetmc-adjusted',
  bars: 320,
  lastBarDate: '۱۴۰۴/۱۱/۲۱',
  fetchedAtMs: Date.parse('2026-05-12T09:30:00Z'),
  adjustmentEvents: 2,
  e3: null,
};

function renderSidebar(props: Partial<React.ComponentProps<typeof TechnicalSidebar>> = {}) {
  return withQuery(
    <TechnicalSidebar
      active={ACTIVE}
      symbol="فولاد"
      onSelect={() => undefined}
      ftsContext={FTS_CONTEXT}
      {...props}
    />,
  );
}

function screenerRow(partial: Partial<ScreenerRow>): ScreenerRow {
  return { symbol: 'x', ...partial } as ScreenerRow;
}

describe('فیلتر دیده‌بان', () => {
  it('ارزش معامله = قیمت × حجم', () => {
    expect(tradingValue(row({ p_last: 10, q_tot_tran: 5 }))).toBe(50);
    expect(tradingValue(row({ p_last: null, p_closing: 8, q_tot_tran: 5 }))).toBe(40);
  });

  it('ردیف مرده حذف و بر اساس ارزش معامله نزولی مرتب می‌شود', () => {
    const rows = [
      row({ symbol: 'کم', p_last: 10, q_tot_tran: 1 }),
      row({ symbol: 'زیاد', p_last: 100, q_tot_tran: 10 }),
      row({ symbol: 'مرده', is_live: false, p_last: 999, q_tot_tran: 9 }),
    ];
    const out = filterWatchlist(rows, '');
    expect(out.map((r) => r.symbol)).toEqual(['زیاد', 'کم']);
  });

  it('جستجو روی نماد و نام', () => {
    const rows = [row({ symbol: 'فولاد', name: 'فولاد مبارکه' }), row({ symbol: 'خودرو', name: 'ایران خودرو' })];
    expect(filterWatchlist(rows, 'مبارکه').map((r) => r.symbol)).toEqual(['فولاد']);
    expect(filterWatchlist(rows, 'خودرو').map((r) => r.symbol)).toEqual(['خودرو']);
  });
});

describe('فیلتر سیگنال‌های FTS', () => {
  it('برچسب ستاپ‌های فعال', () => {
    const tags = ftsSignalTags(srow({ tech_jet: true, tech_choch_bear: true, tech_fib_zone: 'in' }));
    expect(tags.map((t) => t.label)).toEqual(['جت', 'CHoCH نزولی', 'موقعیت فیبو in']);
    // فیبو زمینه است، پس به‌تنهایی نماد را واردِ فهرستِ «سیگنال‌ها» نمی‌کند
    expect(tags.filter((t) => t.role === 'context').map((t) => t.label)).toEqual(['موقعیت فیبو in']);
  });

  it('نماد بی‌سیگنال حذف می‌شود؛ فیبو زمینه است و «نگهداری» هم خروج نیست', () => {
    const rows = [
      srow({ symbol: 'الف', tech_jet: true }),
      srow({ symbol: 'ب' }),
      srow({ symbol: 'پ', tech_fib_zone: '33-40' }),
      srow({ symbol: 'ث', tech_exit_signals: ['rsi_rollover'], tech_exit_verdict: 'caution' }),
      srow({ symbol: 'ج', tech_exit_verdict: 'hold' }),
    ];
    expect(filterFtsSignals(rows, '').map((r) => r.symbol)).toEqual(['الف', 'ث']);
  });

  it('وتوی هفتگی و سیگنال خروج به فیلدهای واقعی وصل‌اند و تهی سیگنال نیست', () => {
    const rows = [
      srow({ symbol: 'وتو', tech_matrix_decision: 'REJECT', tech_trend_w: 'down' }),
      srow({ symbol: 'خروج', tech_exit_signals: ['ma14_trail'], tech_exit_verdict: 'exit' }),
      srow({ symbol: 'تهی', tech_exit_signals: null, tech_matrix_decision: null }),
    ];
    expect(filterFtsSignals(rows, '', { ...FTS_FILTERS_DEFAULT, kind: 'weekly_veto' }).map((r) => r.symbol)).toEqual(['وتو']);
    expect(filterFtsSignals(rows, '', { ...FTS_FILTERS_DEFAULT, kind: 'exit_signal' }).map((r) => r.symbol)).toEqual(['خروج']);
    expect(filterFtsSignals(rows, '').map((r) => r.symbol)).toEqual(['وتو', 'خروج']);
  });

  it('سقفِ نمایش پس از فیلتر شمرده می‌شود، نه پیش از آن', () => {
    const rows = Array.from({ length: 5 }, (_, i) => srow({ symbol: `س${i}`, tech_jet: true }));
    const r = filterFtsSignalRows(rows, '', FTS_FILTERS_DEFAULT, 2);
    expect(r.total).toBe(5);
    expect(r.rows.map((x) => x.symbol)).toEqual(['س0', 'س1']);
    expect(r.truncated).toBe(true);
  });
});

describe('پنل ترازها', () => {
  it('بدون نماد پیام راهنما می‌دهد', () => {
    render(<SidebarActiveLevels active={{ ...ACTIVE, symbol: '' }} />);
    expect(screen.getByTestId('sidebar-levels-empty')).toBeInTheDocument();
  });

  it('سه سبک حد ضرر، یکی‌یکی و از دادهٔ سرور', () => {
    render(<SidebarActiveLevels active={ACTIVE} />);
    const swing = screen.getByTestId('levels-stop-swing');
    const trend = screen.getByTestId('levels-stop-trend');
    const fund = screen.getByTestId('levels-stop-fund');
    // نوسان‌گیر = حد ضرر سختِ موتور (۵٪ زیرِ قیمتِ خریدِ سبد، نه کفِ فرکتالِ فرانت)
    expect(swing.textContent).toContain('۲,۸۱۹');
    expect(swing.getAttribute('title')).toContain('قیمتِ خریدِ ثبت‌شده در سبد');
    // روندگیر = MA(14) با وضعیتِ لایهٔ ۱
    expect(trend.textContent).toContain('MA(14)');
    expect(trend.textContent).toContain('۲,۹۰۰');
    expect(trend.getAttribute('title')).toContain('دورهٔ ۱۴');
    // بنیادی هیچ حد ضرر قیمتی ندارد (حکم ۸)
    expect(fund.textContent).toContain('بدون حد ضرر قیمتی');
  });

  it('حکمِ موتور خروج و لایه‌های فعالِ فارسی‌شده', () => {
    render(<SidebarActiveLevels active={ACTIVE} />);
    expect(screen.getByTestId('levels-exit-verdict').textContent).toContain('احتیاط');
    const panel = screen.getByTestId('sidebar-levels');
    expect(panel.textContent).toContain('نزدیکِ خروج MA(14)');
    expect(panel.textContent).toContain('واگرایی منفی RSI');
    // واژگانِ فنیِ انگلیسیِ سرور هرگز به چشم کاربر نمی‌آید
    expect(panel.textContent).not.toContain('ma14_watch');
  });

  it('بی‌حدِ ضررِ خوردنشده بنر خروج نیامده؛ با stop_hit می‌آید', () => {
    const { unmount } = render(<SidebarActiveLevels active={ACTIVE} />);
    expect(screen.queryByTestId('levels-stop-hit')).toBeNull();
    unmount();
    render(<SidebarActiveLevels active={ACTIVE_STOP_HIT} />);
    expect(screen.getByTestId('levels-stop-hit')).toBeInTheDocument();
    expect(screen.getByTestId('levels-exit-verdict').textContent).toContain('حد ضرر');
  });

  it('ترازها، مبنای فیبو و ستاپ از همان پیلود سرور', () => {
    render(<SidebarActiveLevels active={ACTIVE} />);
    const panel = screen.getByTestId('sidebar-levels');
    expect(panel.textContent).toContain('زون طلایی');
    expect(panel.textContent).toContain('MA(100)');
    expect(panel.textContent).toContain('جت (شکست سقف)');
    expect(panel.textContent).toContain('۲,۴۴۷');
    // «بدون داده» برای محوری که سرور نگفته — نه صفرِ ساختگی
    render(<SidebarActiveLevels active={{ ...ACTIVE, fts: null }} />);
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
  });
});

describe('شل سایدبار و تب‌ها', () => {
  it('پیش‌فرض «لایه‌های FTS» است: خلاصهٔ ساختاری و کاتالوگ کامل همان‌جا رندر می‌شوند', () => {
    renderSidebar();
    expect(screen.getByTestId('technical-sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-layers')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-fts')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-book')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-layers')).toBeInTheDocument();
    expect(screen.getByTestId('technical-structure-summary')).toHaveAttribute('data-state', 'ready');
    expect(screen.getByTestId('fts-layer-panel')).toBeInTheDocument();
  });

  it('«دیده‌بان» از سایدبار فنی کلاً حذف شده، نه فقط پیش‌فرضِ دیگری گرفته', () => {
    renderSidebar();
    expect(screen.queryByTestId('sidebar-tab-watch')).toBeNull();
    expect(screen.queryByTestId('sidebar-watchlist')).toBeNull();
    expect(screen.queryByLabelText('دیده‌بان')).toBeNull();
  });

  it('بی‌پیلود: خلاصه «بدون داده» است و هیچ روند/رأیی نمی‌سازد', () => {
    renderSidebar({
      ftsContext: { ...FTS_CONTEXT, fts: null, status: 'empty', isLoading: false, isError: false, basis: null, bars: null },
    });
    expect(screen.getByTestId('technical-structure-summary')).toHaveAttribute('data-state', 'empty');
    expect(screen.getByTestId('tech-summary-state').textContent).toContain('بدون داده');
    expect(screen.queryByTestId('tech-summary-trends')).toBeNull();
    expect(screen.queryByTestId('tech-summary-matrix')).toBeNull();
  });

  it('خطای موتور به «بدون داده» تبدیل نمی‌شود و علتش دیده می‌شود', () => {
    renderSidebar({
      ftsContext: {
        ...FTS_CONTEXT,
        fts: null,
        status: 'error',
        message: 'موتور تحلیل خطا داد',
        isLoading: false,
        isError: true,
      },
    });
    expect(screen.getByTestId('technical-structure-summary')).toHaveAttribute('data-state', 'error');
    expect(screen.getByTestId('tech-summary-state').textContent).toContain('موتور تحلیل خطا داد');
  });

  it('کلیک روی تب ترازها پنل نماد فعال را نشان می‌دهد', () => {
    renderSidebar();
    fireEvent.click(screen.getByTestId('sidebar-tab-levels'));
    expect(screen.getByTestId('sidebar-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-levels').textContent).toContain('فولاد');
  });

  it('تب «نبض کلان» حذف شده است', () => {
    renderSidebar();
    expect(screen.queryByTestId('sidebar-tab-macro')).toBeNull();
    expect(screen.queryByText('نبض کلان')).toBeNull();
  });

  it('تبِ سیگنال‌های FTS با کشوی تب باز می‌شود و فیلترهایش را می‌آورد', () => {
    renderSidebar();
    fireEvent.click(screen.getByTestId('sidebar-tab-fts'));
    expect(screen.getByTestId('sidebar-fts')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-fts-filters')).toBeInTheDocument();
  });
});

describe('فیلترهای کشوییِ سیگنال‌های FTS', () => {
  const ROWS: ScreenerRow[] = [
    screenerRow({ symbol: 'الف', name: 'نماد الف', tech_jet: true, tech_trend_w: 'up', tech_matrix_decision: 'PERMITTED' }),
    screenerRow({ symbol: 'ب', name: 'نماد ب', tech_double_bottom: true, tech_trend_w: 'down', tech_matrix_decision: 'REJECT' }),
    screenerRow({ symbol: 'پ', name: 'نماد پ', tech_choch_bear: true, tech_trend_w: 'up', tech_matrix_decision: 'UNKNOWN' }),
    screenerRow({ symbol: 'ت', name: 'نماد ت', tech_range_break: true }),
    screenerRow({
      symbol: 'ث',
      name: 'نماد ث',
      tech_exit_signals: ['rsi_rollover'],
      tech_exit_verdict: 'caution',
      tech_trend_w: 'up',
      tech_matrix_decision: 'PERMITTED',
    }),
  ];

  function renderSignals() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    qc.setQueryData(['technical-fts-screener'], { status: 'ok', count: ROWS.length, data: ROWS });
    return render(
      <QueryClientProvider client={qc}>
        <SidebarFtsSignals onSelect={() => undefined} />
      </QueryClientProvider>,
    );
  }

  const symbols = () => Array.from(screen.getByTestId('sidebar-fts-list').querySelectorAll('li')).map((li) => li.textContent);

  it('شمارشِ صادق و «گزارش نشده» جدا از رأیِ منفی', () => {
    renderSignals();
    expect(screen.getByTestId('sidebar-fts-count').textContent).toContain('۵ نماد');
    fireEvent.change(screen.getByTestId('sidebar-fts-filter-verdict'), { target: { value: 'not_reported' } });
    expect(symbols().length).toBe(1);
    expect(symbols()[0]).toContain('ت');
  });

  it('گزینه‌های وتوی هفتگی و سیگنال خروج از فیلدهای واقعی می‌آیند', () => {
    renderSignals();
    const kind = screen.getByTestId('sidebar-fts-filter-kind') as HTMLSelectElement;
    const values = Array.from(kind.options).map((o) => o.value);
    expect(values).toContain('weekly_veto');
    expect(values).toContain('exit_signal');
    fireEvent.change(kind, { target: { value: 'weekly_veto' } });
    expect(symbols().length).toBe(1);
    expect(symbols()[0]).toContain('ب');
    fireEvent.change(kind, { target: { value: 'exit_signal' } });
    expect(symbols().length).toBe(1);
    expect(symbols()[0]).toContain('ث');
  });

  it('نوع سیگنال، روند هفتگی و رأیِ FTS با هم AND می‌شوند', () => {
    renderSignals();
    fireEvent.change(screen.getByTestId('sidebar-fts-filter-kind'), { target: { value: 'jet' } });
    expect(symbols().length).toBe(1);
    expect(symbols()[0]).toContain('الف');
    fireEvent.change(screen.getByTestId('sidebar-fts-filter-weekly'), { target: { value: 'down' } });
    expect(symbols().length).toBe(0);
    expect(screen.getByTestId('sidebar-fts-empty').textContent).toContain('هیچ نمادی با این فیلترها نیست');
    expect(screen.getByTestId('sidebar-fts-count').textContent).toContain('۰ نماد');
    fireEvent.change(screen.getByTestId('sidebar-fts-filter-kind'), { target: { value: 'choch_bear' } });
    expect(symbols().length).toBe(0);
  });

  it('جستجو با فیلترها AND می‌شود و بازنشانی همه را برمی‌گرداند', () => {
    renderSignals();
    fireEvent.change(screen.getByTestId('sidebar-fts-filter-kind'), { target: { value: 'choch_bear' } });
    fireEvent.change(screen.getByTestId('sidebar-fts-search'), { target: { value: 'ب' } });
    expect(symbols().length).toBe(0);
    fireEvent.click(screen.getByTestId('sidebar-fts-reset'));
    expect(symbols().length).toBe(5);
    expect((screen.getByTestId('sidebar-fts-search') as HTMLInputElement).value).toBe('');
    expect((screen.getByTestId('sidebar-fts-filter-kind') as HTMLSelectElement).value).toBe(FTS_FILTERS_DEFAULT.kind);
  });
});

describe('fallback اولین screener', () => {
  it('واچ‌لیست غیرمردود مقدم است، سپس اولین غیرمردود، وگرنه null', () => {
    expect(firstScreenerSymbol([srow({ symbol: 'الف', excluded: true }), srow({ symbol: 'ب', watchlist: true })])).toBe('ب');
    expect(firstScreenerSymbol([srow({ symbol: 'ج' })])).toBe('ج');
    expect(firstScreenerSymbol([])).toBeNull();
  });
});
