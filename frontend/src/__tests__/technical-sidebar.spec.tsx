// تست سایدبار راست تکنیکال (فاز ۲) — چهار تب، فیلترهای خالص و ترازهای نماد فعال
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { TechnicalSidebar } from '@features/technical/components/TechnicalSidebar';
import { SidebarActiveLevels, type ActiveLevelsView } from '@features/technical/components/SidebarActiveLevels';
import { filterWatchlist, tradingValue } from '@features/technical/api/useWatchlist';
import { filterFtsSignals, ftsSignalTags, type ScreenerRow } from '@features/technical/api/useScreener';
import { computeTradeLevels, lastSwingLow } from '@features/technical/lib/levels';
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

const ACTIVE: ActiveLevelsView = {
  symbol: 'فولاد',
  zone3340: { lo: 2739, hi: 2839 },
  zone61870: { lo: 2346, hi: 2447 },
  baseLevel: 2010,
  ma100: 2300,
  swingLow: 2100,
  stop5pct: 1995,
  keyLevels: [{ type: 'resistance', price: 2820 }],
  stopLoss: 2573,
  lastClose: 2967,
  setups: ['breakout'],
  direction: 'bullish',
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
    expect(tags.map((t) => t.label)).toEqual(['جت', 'CHoCH نزولی', 'نقطه‌زنی فیبو']);
  });

  it('نماد بی‌سیگنال حذف می‌شود', () => {
    const rows = [srow({ symbol: 'الف', tech_jet: true }), srow({ symbol: 'ب' })];
    expect(filterFtsSignals(rows, '').map((r) => r.symbol)).toEqual(['الف']);
  });
});

describe('ترازها و حد ضرر', () => {
  it('آخرین کف پیوت و حد ضرر ۵٪ زیر آن', () => {
    const lows = [10, 9, 8, 9, 10, 11, 10, 9, 8.5, 9, 10, 11, 12];
    const sw = lastSwingLow(lows, 2);
    expect(sw).not.toBeNull();
    const { stop5pct } = computeTradeLevels(lows, 2);
    expect(stop5pct).toBeCloseTo((sw as number) * 0.95);
  });

  it('در نبود پیوت، آخرین کف موجود', () => {
    expect(lastSwingLow([5, 4, 3], 3)).toBe(3);
  });
});

describe('پنل ترازها', () => {
  it('بدون نماد پیام راهنما می‌دهد', () => {
    render(<SidebarActiveLevels active={{ ...ACTIVE, symbol: '' }} />);
    expect(screen.getByTestId('sidebar-levels-empty')).toBeInTheDocument();
  });

  it('با نماد فعال، زون‌ها و حد ضرر رندر می‌شوند', () => {
    render(<SidebarActiveLevels active={ACTIVE} />);
    const panel = screen.getByTestId('sidebar-levels');
    expect(panel.textContent).toContain('فولاد');
    expect(panel.textContent).toContain('کمربند طلایی');
    expect(panel.textContent).toContain('حد ضرر نوسان‌گیر');
    expect(panel.textContent).toContain('MA(100)');
    expect(panel.textContent).toContain('جت (شکست سقف)');
  });
});

describe('شل سایدبار و تب‌ها', () => {
  it('چهار تب و بدنهٔ پیش‌فرض دیده‌بان', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} onSelect={() => undefined} />);
    expect(screen.getByTestId('technical-sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-watch')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-fts')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-tab-macro')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-watchlist')).toBeInTheDocument();
  });

  it('کلیک روی تب ترازها پنل نماد فعال را نشان می‌دهد', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} onSelect={() => undefined} />);
    fireEvent.click(screen.getByTestId('sidebar-tab-levels'));
    expect(screen.getByTestId('sidebar-levels')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-levels').textContent).toContain('فولاد');
  });

  it('کلیک روی تب نبض کلان پنل macro را نشان می‌دهد', () => {
    withQuery(<TechnicalSidebar active={ACTIVE} onSelect={() => undefined} />);
    fireEvent.click(screen.getByTestId('sidebar-tab-macro'));
    expect(screen.getByTestId('sidebar-macro')).toBeInTheDocument();
  });
});
