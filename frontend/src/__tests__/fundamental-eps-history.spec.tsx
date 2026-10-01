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
import { FtsCard as EpsCardPanel } from '@features/fundamental/components/FtsCard';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import {
  EPS_GROWTH_NO_BASE,
  EPS_GROWTH_NO_DATA,
  EPS_MIN_SHOWN_YEARS,
  EPS_PARTIAL_TESTID,
  EPS_REQUIRED_YEARS,
  epsChangePct,
  epsChangeText,
  epsChanges,
  epsGrowthReason,
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
  it('۲ سال: همان دو سال نمایش + برچسبِ کوتاهِ «سابقهٔ ناقص» — نه برچسب شکاف', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    // همان دو سالِ موجود (۱۴۰۴ و ۱۴۰۵) دیده می‌شود
    expect(within(tr).getByTitle('— ← ۵۹۰ ← ۹۹۰')).toBeInTheDocument();
    const label = within(tr).getByTestId(EPS_PARTIAL_TESTID);
    // در جدول شکلِ کوتاه می‌آید (سرستون خودش «۲ — روند EPS» است)
    expect(label.textContent).toContain('سابقهٔ ناقص');
    expect(label.textContent).not.toContain('مردود در شاخص ۲');
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
    expect(within(tr).getByTitle('۹۱ ← ۹۶ ← ۲۰۲')).toBeInTheDocument();
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
  it('هر سه نما یک *حکم* می‌دهند؛ جدول شکلِ کوتاهش را', () => {
    // قراردادِ تازه (۱٫۰٫۶۶): منبع هنوز یکی است، ولی رندر به متن وابسته
    // است. در جدول سرستونْ خودش «۲ — روند EPS» است، پس «مردود در شاخص ۲»
    // همان را دوباره می‌گفت و فقط عرض می‌خورد؛ متنِ کامل آنجا در title
    // می‌ماند. در نردبان و drill-down که ستونی در کار نیست، شکلِ کامل.
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
    const els = screen.getAllByTestId(EPS_PARTIAL_TESTID);
    expect(els).toHaveLength(3);
    // همهٔ نماها همان عددِ «۲ از ۳ سال» را می‌گویند — حکم یکی است
    for (const el of els) expect(norm(el.textContent)).toContain('۲ از ۳ سال');
    // دستِ‌کم دو نما شکلِ کامل دارند (نردبان و drill-down)
    const full = els.filter((el) => norm(el.textContent) === expected);
    expect(full.length).toBeGreaterThanOrEqual(2);
    // نمایِ کوتاه (جدول) علتِ شکاف را در title دارد — همان چیزی که کاربر
    // با hover می‌خواهد بداند، و از تکرارِ نامِ ستون مفیدتر است.
    const short = els.filter((el) => norm(el.textContent) !== expected);
    expect(short).toHaveLength(1);
    expect(norm(short[0].getAttribute('title'))).toContain('۲ سال از ۳ سال');
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

// ─────────────────────────────────────────────────────────────────────────────
//  #101 — «کارت eps: درصدها نوشته بشه بدونیم چقدر رشد داشته»
//  درصدِ رشد نمایشی است (هیچ داوری‌ای را عوض نمی‌کند) و قاعدهٔ سختش این است:
//  «نبودِ داده هیچ‌وقت صفر نیست» — نه ۰٪، نه ۱۰۰٪ِ جعلی، نه فلشِ سبز/سرخ.
// ─────────────────────────────────────────────────────────────────────────────
describe('#101 lib/epsHistory — درصد رشد سال‌به‌سال', () => {
  it('درصد از مبنای مثبت درست حساب می‌شود', () => {
    expect(epsChangePct(100, 130)).toBeCloseTo(30, 6);
    expect(epsChangePct(96, 202)).toBeCloseTo(110.4166667, 4);
    // افت هم منفی می‌آید، نه صفر
    expect(epsChangePct(200, 150)).toBeCloseTo(-25, 6);
    // برابر ⇒ ۰٪ واقعی (این تنها جایِ مجازِ صفر است: داده هست و تغییر ندارد)
    expect(epsChangePct(100, 100)).toBe(0);
  });

  it('مبنای صفر/زیان و سالِ غایب هیچ‌وقت درصد جعلی نمی‌سازند', () => {
    expect(epsChangePct(null, 590)).toBeNull();
    expect(epsChangePct(undefined, 590)).toBeNull();
    expect(epsChangePct(0, 590)).toBeNull(); // ← پیش از این +۱۰۰٪ جعلی می‌داد
    expect(epsChangePct(0, 0)).toBeNull(); //                    و ۰٪ جعلی
    expect(epsChangePct(0, -5)).toBeNull(); //                   و −۱۰۰٪ جعلی
    expect(epsChangePct(-8, 100)).toBeNull(); // مبنای زیان: درصد بی‌معنا
    expect(epsChangePct(100, null)).toBeNull();
    expect(epsChangePct(100, Number.NaN)).toBeNull();
  });

  it('سری به همان بلندای ورودی برمی‌گردد و سالِ نخست null است', () => {
    expect(epsChanges([91, 96, 202])).toEqual([null, expect.closeTo(5.4945, 4), expect.closeTo(110.4167, 3)]);
    // سالِ غایب بین دو سال ⇒ آن فاصله هم null (جهشِ دو‌ساله به حساب نمی‌آید)
    expect(epsChanges([null, 590, 990])).toEqual([null, null, expect.closeTo(67.7966, 4)]);
    expect(epsChanges(null)).toEqual([]);
    expect(epsChanges([])).toEqual([]);
  });

  it('عددِ فرستاده‌شدهٔ بک‌اند (eps_yoy_pct) مقدم است و دوباره حک نمی‌شود', () => {
    expect(epsChanges([91, 96, 202], [null, 5.5, 110.4])).toEqual([null, 5.5, 110.4]);
    // طولِ ناهمسان = پاسخِ معتبر نیست → از سری حساب می‌شود
    expect(epsChanges([91, 96, 202], [null, 5.5])).not.toEqual([null, 5.5]);
    expect(epsChanges([91, 96, 202], [null, null, null])).toEqual([null, null, null]);
  });

  it('درصد با رقمِ فارسی و ٪ نوشته می‌شود؛ نبودِ درصد یعنی null', () => {
    expect(epsChangeText(110.4166667)).toBe('+۱۱۰.۴٪');
    expect(epsChangeText(-25)).toBe('-۲۵.۰٪');
    expect(epsChangeText(0)).toBe('۰.۰٪');
    expect(epsChangeText(null)).toBeNull();
    expect(epsChangeText(Number.NaN)).toBeNull();
    // هیچ رقمِ لاتینی در متنِ نمایشی نمی‌ماند
    expect(epsChangeText(110.4166667)).not.toMatch(/[0-9]/);
  });

  it('دلیلِ نداشتنِ درصد بین «داده نداریم» و «مبنای زیان» را تفکیک می‌کند', () => {
    expect(epsGrowthReason([])).toBe(EPS_GROWTH_NO_DATA);
    expect(epsGrowthReason([150])).toBe(EPS_GROWTH_NO_DATA);
    expect(epsGrowthReason([null, null, null])).toBe(EPS_GROWTH_NO_DATA);
    expect(epsGrowthReason([-8, 100])).toBe(EPS_GROWTH_NO_BASE);
    expect(EPS_GROWTH_NO_DATA).toBe('داده نداریم');
  });
});

describe('#101 کارت EPS (شاخص ۲) — درصدها کنارِ عدد', () => {
  function cardWith(patch: Record<string, unknown>) {
    return {
      status: 'success' as const,
      symbol: 'شفارس',
      indicators: { '2': { eps_years_required: 3, years_required: 3, years_available: 3, ...patch } },
    } as unknown as FtsCard;
  }

  function renderCard(patch: Record<string, unknown>) {
    render(
      <EpsCardPanel
        score={4}
        passes={{ '2_eps_trend': true }}
        indicators={cardWith(patch).indicators ?? null}
      />,
    );
    return screen.getByTestId('fts-card-cell-2_eps_trend');
  }

  it('سریِ سه‌ساله: هر دو درصد رشد نوشته می‌شود (+۵.۵٪ و +۱۱۰.۴٪)', () => {
    const cell = renderCard({ eps_series: [91, 96, 202] });
    const growth = within(cell).getByTestId('fts-card-eps-growth');
    expect(growth.textContent).toContain('+۵.۵٪');
    expect(growth.textContent).toContain('+۱۱۰.۴٪');
    expect(within(cell).queryByTestId('fts-card-eps-growth-nodata')).not.toBeInTheDocument();
  });

  it('سریِ صعودیِ کاملِ بدون درصدِ لاتین', () => {
    const growth = within(renderCard({ eps_series: [100, 150, 300] })).getByTestId('fts-card-eps-growth');
    expect(growth.textContent).toContain('+۵۰.۰٪');
    expect(growth.textContent).toContain('+۱۰۰.۰٪');
    expect(growth.textContent).not.toMatch(/[0-9]/);
  });

  it('سریِ افت‌کرده: درصدِ منفی با همان منبع نمایش داده می‌شود', () => {
    const growth = within(renderCard({ eps_series: [200, 150, 100] })).getByTestId('fts-card-eps-growth');
    expect(growth.textContent).toContain('-۲۵.۰٪');
    expect(growth.textContent).toContain('-۳۳.۳٪');
  });

  it('یک نقطه داده ⇒ «داده نداریم»، نه ۰٪ و نه فلش', () => {
    const cell = renderCard({ eps_series: [50] });
    expect(within(cell).getByTestId('fts-card-eps-growth-nodata').textContent).toContain(EPS_GROWTH_NO_DATA);
    expect(within(cell).getByTestId('fts-card-eps-growth').textContent).not.toContain('٪');
    expect(within(cell).getByTestId('fts-card-eps-growth').textContent).not.toMatch(/[▲✓↑]/);
  });

  it('بدون سری (indicators خالی) ⇒ همان «داده نداریم»', () => {
    const cell = renderCard({ eps_series: null });
    expect(within(cell).getByTestId('fts-card-eps-growth-nodata').textContent).toContain(EPS_GROWTH_NO_DATA);
  });

  it('سریِ آلوده به زیان: درصد جعلی نمی‌شود، دلیل نوشته می‌شود', () => {
    const cell = renderCard({ eps_series: [-8, 100, null] });
    const line = within(cell).getByTestId('fts-card-eps-growth');
    expect(within(cell).getByTestId('fts-card-eps-growth-nodata').textContent).toContain(EPS_GROWTH_NO_BASE);
    expect(line.textContent).not.toContain('۱۰۰.۰٪');
  });

  it('درصدِ خودِ بک‌اند (eps_yoy_pct) بر محاسبهٔ UI مقدم است', () => {
    const growth = within(
      renderCard({ eps_series: [91, 96, 202], eps_yoy_pct: [null, 5.49, 110.42] }),
    ).getByTestId('fts-card-eps-growth');
    expect(growth.textContent).toContain('+۵.۵٪');
    expect(growth.textContent).toContain('+۱۱۰.۴٪');
  });
});

describe('#101 نردبان EPS و دریل‌دان — همان درصدها، یک منبع', () => {
  it('نردبان: درصدِ هر سال زیرِ همان سال نوشته می‌شود و سالِ نخست «—» است', () => {
    render(<EpsLadder slots={['1403', '1404', '1405']} series={[100, 150, 300]} partial={false} />);
    const ladder = screen.getByTestId('eps-ladder');
    expect(ladder.textContent).toContain('+۵۰.۰٪');
    expect(ladder.textContent).toContain('+۱۰۰.۰٪');
    expect(within(ladder).getByTestId('eps-cell-change-0').textContent).toBe('—');
  });

  it('نردبان با سالِ غایب: هیچ درصد و هیچ رنگی برای آن فاصله نیست', () => {
    render(<EpsLadder slots={['1403', '1404', '1405']} series={[null, 590, 990]} partial requiredYears={3} />);
    const ladder = screen.getByTestId('eps-ladder');
    // ۵۹۰ ← ۹۹۰ = ۶۷.۸٪ هست، ولی ۱۴۰۳ مبنای ندارد
    expect(ladder.textContent).toContain('+۶۷.۸٪');
    expect(within(ladder).getByTestId('eps-cell-change-1').textContent).toBe('—');
  });

  it('دریل‌دان شاخص ۲: زیرِ هر میله درصد رشد نوشته می‌شود', () => {
    const card = {
      status: 'success',
      symbol: 'شفارس',
      indicators: {
        '2': {
          eps_series: [91, 96, 202],
          period_slots: ['1402', '1403', '1404'],
          years_required: 3,
          years_available: 3,
          strictly_rising: true,
          all_profitable: true,
          pass: true,
        },
      },
      metrics: {},
    } as unknown as FtsCard;
    render(<FtsDrillDown card={card} active="2" quarters={[]} physicalApplicable />);
    expect(screen.getByTestId('drilldown-eps-change-0').textContent).toBe('—');
    expect(screen.getByTestId('drilldown-eps-change-1').textContent).toBe('+۵.۵٪');
    expect(screen.getByTestId('drilldown-eps-change-2').textContent).toBe('+۱۱۰.۴٪');
  });
});

describe('#101 جدول غربالگری — EpsFlow دیگر درصد جعلی نمی‌سازد', () => {
  it('سریِ نرمال: درصدها میانِ عددها نوشته می‌شود', () => {
    render(<FtsScreenTable rows={[row({ eps_series: [100, 150, 300] })]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).getByText('+۵۰.۰٪')).toBeInTheDocument();
    expect(within(tr).getByText('+۱۰۰.۰٪')).toBeInTheDocument();
  });

  it('مبنای صفر: به‌جای +۱۰۰٪ یا ۰٪ جعلی فقط خط تیره می‌آید', () => {
    render(<FtsScreenTable rows={[row({ eps_series: [0, 590, 990] })]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    // هیچ درصدِ جعلیِ مبنای-صفر در ردیف نیست (±۱۰۰٪ و ۰٪)
    expect(within(tr).queryByText('۱۰۰٪')).toBeNull();
    expect(within(tr).queryByText('+۱۰۰.۰٪')).toBeNull();
    expect(within(tr).queryByText('-۱۰۰.۰٪')).toBeNull();
    expect(within(tr).queryByText('۰.۰٪')).toBeNull();
    // تنها درصدِ ستون EPS همان ۵۹۰ ← ۹۹۰ است؛ فاصلهٔ از صفر درصدی نمی‌گیرد
    expect(within(tr).getByText('+۶۷.۸٪')).toBeInTheDocument();
    expect(within(tr).getAllByText('—').length).toBeGreaterThanOrEqual(1);
  });
});

