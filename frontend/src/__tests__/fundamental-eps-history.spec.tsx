// تست شاخص ۲ (سابقهٔ ۳ سالهٔ EPS) — منبع واحدِ lib/epsHistory + سازگاری سه نما.
// باگ گزارش‌شدهٔ کاربر: نمادی که فقط ۲ سال سابقهٔ EPS دارد، در «جدول غربالگری»
// باید همان ۲ سال را نشان دهد و روشن باشد که به‌خاطر سابقهٔ ناقص (۲ از ۳ سال)
// مردود است — نه اینکه برچسب شکاف بخورد. شکاف فقط برای <۲ سال.
// دادهٔ واقعیِ مرجع: /api/fundamental/احيا → years_available=2، series=[null,590,990]
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';

// jsdom اندازه ندارد -- virtualizer به رندر کامل پنجره وادار می‌شود (الگوی tape-patterns/F-08)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 12;
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});
import { EpsLadder } from '@features/fundamental/components/EpsLadder';
import { FtsDrillDown } from '@features/fundamental/components/FtsDrillDown';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import {
  EPS_MIN_SHOWN_YEARS,
  EPS_PARTIAL_TESTID,
  EPS_REQUIRED_YEARS,
  epsHistory,
  epsPartialRejectLabel,
  epsRealYears,
  epsSeriesText,
} from '@features/fundamental/lib/epsHistory';

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'احيا',
    symbol_norm: 'احيا',
    name: 'احيا استيل فولاد بافت',
    sector_name: 'فلزات اساسي',
    pricing_mode: 'free',
    rev_growth: 41.2,
    eps_series: [null, 590, 990],
    eps_last: 990,
    eps_data_gap: true,
    gross_margin: 25.5,
    sales_to_mcap: 1.1,
    profit_potential_pct: 35.0,
    annual_sales_bt: 20.0,
    mcap: 1e13,
    score: 3,
    i1_pass: true,
    i2_pass: false,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

function card2year(): FtsCard {
  return {
    status: 'success',
    symbol: 'احيا',
    indicators: {
      '2': {
        eps_series: [null, 590, 990],
        period_slots: ['1403', '1404', '1405'],
        fiscal_years: ['1403', '1404', '1405'],
        years_required: 3,
        years_available: 2,
        partial: true,
        strictly_rising: null,
        pass: false,
      },
    },
    metrics: { eps_series: [null, 590, 990], eps_available: 2, eps_required: 3, eps_partial: true },
  };
}

describe('lib/epsHistory — شمارش و وضعیت سابقهٔ EPS', () => {
  it('سال‌های واقعی سری شمرده می‌شوند (null = سال غایب)', () => {
    expect(epsRealYears([null, 590, 990])).toBe(2);
    expect(epsRealYears([91, 96, 202])).toBe(3);
    expect(epsRealYears([null, null, null])).toBe(0);
    expect(epsRealYears(null)).toBe(0);
    // NaN/undefined داده نیستند
    expect(epsRealYears([100, Number.NaN, null])).toBe(1);
  });

  it('متن سری: سال غایب «—» و ارقام فارسی', () => {
    expect(epsSeriesText([null, 590, 990])).toBe('— ← ۵۹۰ ← ۹۹۰');
    expect(epsSeriesText([])).toBeNull();
  });

  it('وضعیت‌ها: کامل / سابقهٔ ناقص / ناکافی', () => {
    expect(epsHistory([91, 96, 202]).state).toBe('complete');
    expect(epsHistory([null, 590, 990]).state).toBe('partial');
    expect(epsHistory([null, 590, 990]).realYears).toBe(2);
    expect(epsHistory([590, null, null]).state).toBe('insufficient');
    expect(epsHistory([null, null, null]).state).toBe('insufficient');
    // کفِ نمایش از یک منبع می‌آید
    expect(EPS_MIN_SHOWN_YEARS).toBe(2);
    expect(EPS_REQUIRED_YEARS).toBe(3);
  });

  it('برچسب یکسان «۲ از ۳ سال»', () => {
    expect(epsHistory([null, 590, 990]).label).toBe('مردود در شاخص ۲ — سابقهٔ ناقص (۲ از ۳ سال)');
    expect(epsPartialRejectLabel(2, 3)).toContain('۲ از ۳ سال');
  });

  it('تعداد سال‌های اعلامیِ بک‌اند تنها وقتی سری خالی است به کار می‌آید و به سابقهٔ لازم کلمپ می‌شود', () => {
    // سری نیامده ولی بک‌اند می‌گوید ۲ سال → همان برچسب سابقهٔ ناقص
    expect(epsHistory(null, 3, 2).state).toBe('partial');
    expect(epsHistory(null, 3, 2).realYears).toBe(2);
    // عدد بزرگ‌تر از سابقهٔ لازم هرگز «۴ از ۳ سال» نمی‌سازد
    expect(epsHistory(null, 3, 4).realYears).toBe(3);
    expect(epsHistory(null, 3, 4).state).toBe('complete');
    // سری موجود بر تعداد اعلامی مقدم است
    expect(epsHistory([null, 590, 990], 3, 0).realYears).toBe(2);
    // عدد منفی/بی‌معنا نادیده
    expect(epsHistory(null, 3, -5).state).toBe('insufficient');
  });
});

describe('جدول غربالگری — شاخص ۲ با ۲ سال سابقه', () => {
  it('۲ سال: همان دو سال نمایش + برچسب «مردود — سابقهٔ ناقص (۲ از ۳ سال)» — نه برچسب شکاف', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    // همان دو سالِ موجود (۱۴۰۴ و ۱۴۰۵) دیده می‌شود
    expect(within(tr).getByText('— ← ۵۹۰ ← ۹۹۰')).toBeInTheDocument();
    const label = within(tr).getByTestId(EPS_PARTIAL_TESTID);
    expect(label.textContent).toContain('مردود در شاخص ۲ — سابقهٔ ناقص');
    expect(label.textContent).toContain('۲ از ۳ سال');
    // سلول شاخص ۲ برچسب علت‌دارِ سابقهٔ ناکافی نمی‌گیرد (پانوشت جدول بیرون از ردیف است)
    expect(within(tr).queryByText('سابقهٔ EPS کمتر از ۲ سال')).not.toBeInTheDocument();
    // سطر حذف نشده و امتیاز خودش را دارد
    expect(within(tr).getByText('احيا')).toBeInTheDocument();
  });

  it('۳ سال کامل و قبول → ✓ (بدون برچسب سابقهٔ ناقص)', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'شفارس', eps_series: [91, 96, 202], eps_data_gap: false, i2_pass: true })]}
        onSelect={() => {}}
      />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByTestId(EPS_PARTIAL_TESTID)).not.toBeInTheDocument();
    // هر پنج شاخص قبول ⇒ پنج ✓ در همان ردیف
    expect(within(tr).getAllByText('✓')).toHaveLength(5);
    expect(within(tr).getByText('۹۱ ← ۹۶ ← ۲۰۲')).toBeInTheDocument();
  });

  it('۳ سال کامل ولی غیرصعودی → ✗ (مردودِ واقعی، نه سابقهٔ ناقص)', () => {
    render(
      <FtsScreenTable
        rows={[row({ eps_series: [990, 590, 100], eps_data_gap: false, i2_pass: false })]}
        onSelect={() => {}}
      />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByTestId(EPS_PARTIAL_TESTID)).not.toBeInTheDocument();
    expect(within(tr).getByText('✗')).toBeInTheDocument();
  });

  it('۱ سال: برچسب علت‌دار «سابقهٔ EPS کمتر از ۲ سال» (داده برای قضاوت نیست)', () => {
    render(
      <FtsScreenTable rows={[row({ symbol: 'یک‌ساله', eps_series: [50, null, null] })]} onSelect={() => {}} />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByTestId(EPS_PARTIAL_TESTID)).not.toBeInTheDocument();
    expect(within(tr).getByText('سابقهٔ EPS کمتر از ۲ سال')).toBeInTheDocument();
  });

  it('۰ سال (سری تهی/null): «سابقهٔ EPS سالانه ثبت نشده» — سطر حذف نمی‌شود', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'بی‌داده', eps_series: null, eps_last: null })]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByTestId(EPS_PARTIAL_TESTID)).not.toBeInTheDocument();
    expect(within(tr).getByText('سابقهٔ EPS سالانه ثبت نشده')).toBeInTheDocument();
    expect(within(tr).getByText('بی‌داده')).toBeInTheDocument();
  });

  it('ردیف اسکنر اگر تعداد سال را بفرستد (eps_years_available) هم سابقهٔ ناقص تشخیص داده می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'ماديرا', eps_series: null, eps_last: null, eps_years_available: 2, eps_years_required: 3 })]}
        onSelect={() => {}}
      />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    const label = within(tr).getByTestId(EPS_PARTIAL_TESTID);
    expect(label.textContent).toContain('۲ از ۳ سال');
    expect(within(tr).queryByText('سابقهٔ EPS کمتر از ۲ سال')).not.toBeInTheDocument();
  });
});

describe('سازگاری برچسب بین جدول، نردبان EPS و drill-down (برچسب و منطق یکی)', () => {
  it('هر سه نما برای همان «۲ از ۳ سال» یک متن برچسب می‌دهند', () => {
    const expected = 'مردود در شاخص ۲ — سابقهٔ ناقص (۲ از ۳ سال)';
    // نرمال‌سازی: حذف نشانگر ⓘ و فاصله‌های اضافی
    const norm = (t: string | null) => (t ?? '').replace(/ⓘ/g, '').replace(/\s+/g, ' ').trim();

    render(
      <>
        <FtsScreenTable rows={[row()]} onSelect={() => {}} />
        <EpsLadder slots={['1403', '1404', '1405']} series={[null, 590, 990]} partial requiredYears={3} />
        <FtsDrillDown card={card2year()} active="2" quarters={[]} physicalApplicable />
      </>,
    );
    const labels = screen.getAllByTestId(EPS_PARTIAL_TESTID).map((el) => norm(el.textContent));
    expect(labels).toHaveLength(3);
    for (const l of labels) expect(l).toBe(expected);
  });

  it('هر سه نما با ۱ سال سابقه، برچسب سابقهٔ ناقص نمی‌زنند', () => {
    render(
      <>
        <FtsScreenTable rows={[row({ eps_series: [50, null, null] })]} onSelect={() => {}} />
        <EpsLadder slots={['1405']} series={[50]} partial requiredYears={3} />
      </>,
    );
    expect(screen.queryByTestId(EPS_PARTIAL_TESTID)).not.toBeInTheDocument();
  });
});
