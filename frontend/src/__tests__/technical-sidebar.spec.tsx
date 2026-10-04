// تست سایدبار راست تکنیکال (فاز ۲) — سه تب، فیلترهای خالص و ترازهای نماد فعال
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { TechnicalSidebar } from '@features/technical/components/TechnicalSidebar';
import { SidebarActiveLevels, type ActiveLevelsView } from '@features/technical/components/SidebarActiveLevels';
import { filterWatchlist, tradingValue } from '@features/technical/api/useWatchlist';
import { filterFtsSignals, firstScreenerSymbol, ftsSignalTags, type ScreenerRow } from '@features/technical/api/useScreener';
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

  it('نماد بی‌سیگنال حذف می‌شود؛ «فقط زمینه» هم سیگنال نیست', () => {
    const rows = [srow({ symbol: 'الف', tech_jet: true }), srow({ symbol: 'ب' }),
                  srow({ symbol: 'پ', tech_fib_zone: '33-40' })];
    expect(filterFtsSignals(rows, '').map((r) => r.symbol)).toEqual(['الف']);
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
    expect(panel.textContent).toContain('کمربند طلایی');
    expect(panel.textContent).toContain('MA(100)');
    expect(panel.textContent).toContain('جت (شکست سقف)');
    expect(panel.textContent).toContain('۲,۴۴۷');
    // «بدون داده» برای محوری که سرور نگفته — نه صفرِ ساختگی
    render(<SidebarActiveLevels active={{ ...ACTIVE, fts: null }} />);
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
  });
});

describe('شل سایدبار و تب‌ها', () => {
  it('سه تب هست و پیش‌فرض، سیگنال‌های FTS است (#184)', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} symbol="فولاد" onSelect={() => undefined} />);
    expect(screen.getByTestId('technical-sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-watch')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-fts')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-book')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-fts')).toBeInTheDocument();
    // دیده‌بان حذف نشده، فقط پیش‌فرض نیست
    fireEvent.click(screen.getByTestId('sidebar-tab-watch'));
    expect(screen.getByTestId('sidebar-watchlist')).toBeInTheDocument();
  });

  it('کلیک روی تب ترازها پنل نماد فعال را نشان می‌دهد', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} symbol="فولاد" onSelect={() => undefined} />);
    fireEvent.click(screen.getByTestId('sidebar-tab-levels'));
    expect(screen.getByTestId('sidebar-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-levels').textContent).toContain('فولاد');
  });

  it('تب «نبض کلان» حذف شده است', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} symbol="فولاد" onSelect={() => undefined} />);
    expect(screen.queryByTestId('sidebar-tab-macro')).toBeNull();
    expect(screen.queryByText('نبض کلان')).toBeNull();
  });
});

describe('fallback اولین screener', () => {
  it('واچ‌لیست غیرمردود مقدم است، سپس اولین غیرمردود، وگرنه null', () => {
    expect(firstScreenerSymbol([srow({ symbol: 'الف', excluded: true }), srow({ symbol: 'ب', watchlist: true })])).toBe('ب');
    expect(firstScreenerSymbol([srow({ symbol: 'ج' })])).toBe('ج');
    expect(firstScreenerSymbol([])).toBeNull();
  });
});
