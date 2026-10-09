// تست دیده‌بان کلان بنیادی: ماتریس ۵ شاخص + سورت + علت‌دار بودن بی‌داده + انتخاب نماد
// + دروازه‌های سخت (excluded) + regression سورت پیش‌فرض امتیاز (نزولی)
// + فیلتر نوع نماد (Asset Type): صندوق/کارگزاری/اختیار حذف می‌شوند
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { isFundamentalCompany, isPhysicalGrowthApplicable } from '@features/fundamental/lib/assetScope';
import { jalaliOf, todayIsoInTehran } from '@features/fundamental/lib/assemblyEvent';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می‌کنیم (الگوی tape-patterns)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  /** jsdom اندازه ندارد؛ پنجرهٔ ۱۲ ردیفی مثل پنجرهٔ مرورگر (۷۰vh/۴۶px) شبیه‌سازی می‌شود */
  const WINDOW = 12;
  let lastVirtualOptions: { count: number; overscan?: number; estimateSize?: (i: number) => number } | null = null;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number; overscan?: number; estimateSize?: (i: number) => number }) => {
      lastVirtualOptions = opts;
      const { count } = opts;
      return {
        getTotalSize: () => count * 46,
        getVirtualItems: () =>
          Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
      };
    },
    __virtualOptions: () => lastVirtualOptions,
  };
});


function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا',
    symbol_norm: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    gross_margin: 32.5,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    annual_sales_bt: 90.0,
    mcap: 5e13,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: true,
    i1b_applicable: true,
    i3_na: false,
    i4_na: false,
    verdict: 'WATCH',
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: false,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

describe('دیده‌بان کلان بنیادی (ماتریس FTS)', () => {
  it('پنج شاخص و امتیاز را رندر می کند', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    expect(screen.getByText('شپنا')).toBeInTheDocument();
    expect(screen.getByText('۱ — رشد فروش (الف/ب)')).toBeInTheDocument(); // عنوانِ بالای جدول عمداً حذف شد؛ هدرِ ستون‌ها می‌ماند
    // toFaDigits فقط ارقام را عوض می‌کند؛ ممیز لاتین می‌ماند: ۴۵.۲٪
    expect(screen.getByText('۴۵.۲٪')).toBeInTheDocument();
    expect(screen.getAllByText('✓').length).toBeGreaterThanOrEqual(4);
  });

  it('شمارهٔ هر شاخص در هدر با «—» از نامش جدا شده', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    for (const label of ['۱ —', '۲ —', '۳ —', '۴ —', '۵ —']) {
      expect(screen.getAllByText(new RegExp(`^${label}`)).length).toBeGreaterThanOrEqual(1);
    }
  });

  it('تیکِ حکم در لبهٔ راستِ هر سلول است (RTL: فرزندِ اولِ ظرف سلول) و عدد بعد از آن می‌آید', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const tds = screen.getAllByTestId('fts-screen-row')[0].querySelectorAll('td');
    // [۰]=نماد [۱]=شاخص۱ [۲]=شاخص۲ [۳]=شاخص۳ [۴]=شاخص۴ [۵]=شاخص۵
    for (const idx of [1, 2, 3, 4, 5]) {
      const box = tds[idx].firstElementChild;
      expect(box, `سلول ${idx} ظرفِ چیدمان ندارد`).not.toBeNull();
      expect(box!.children.length, `سلول ${idx} دو بخش ندارد`).toBeGreaterThanOrEqual(2);
      const first = box!.firstElementChild as HTMLElement;
      expect(
        first.querySelector('[data-testid*="fts-mark"],[data-testid*="fts-gap"],[data-testid*="fts-na"],[data-testid="eps-partial-rejected"],[data-testid="eps-gap-reason"]') ??
          (first.getAttribute('data-testid') ? first : null),
        `سلول ${idx}: تیکِ حکم اولین عنصر نیست`,
      ).not.toBeNull();
      // «justify-between» عدد را به لبهٔ مقابلِ ستون می‌انداخت — رویِ نمایشگرِ ۲۵۶۰
      // که ستونِ EPS ۶۴۷px است، رقم ۵۴۶px زیرِ عنوانِ خودش فاصله می‌گرفت و کاربر
      // آن را متعلق به ستونِ کناری می‌خواند. گروه باید از لبهٔ start شروع کند.
      expect(box!.className, `سلول ${idx}: چیدمان از لبهٔ start نیست`).toContain('justify-start');
      expect(box!.className).not.toContain('justify-between');
    }
  });

  it('ستون امتیاز: هدر و مقدار هم‌راستاوند (نه عنوانِ راست و عددِ وسطِ ستون)', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const ths = screen.getAllByRole('columnheader');
    const scoreTh = ths[ths.length - 1];
    const scoreTd = screen.getAllByTestId('fts-screen-row')[0].querySelectorAll('td')[6];
    expect(scoreTh.className).toContain('text-start');
    expect(scoreTh.className).not.toContain('text-center');
    expect(scoreTd.className).toContain('text-start');
    expect(scoreTd.className).not.toContain('text-center');
  });

  it('سورت امتیاز از بیشترین به کمترین', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'کف', score: 1 }), row({ symbol: 'الف', score: 5 })]}
        onSelect={() => {}}
      />,
    );
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells[0].textContent).toContain('الف');
    expect(cells[1].textContent).toContain('کف');
  });

  it('regression: سورت پیش‌فرض امتیاز نزولی است (۵ → ۰) بدون تعامل کاربر', () => {
    // ردیف‌ها با امتیاز نامرتب وارد می‌شوند — جدول باید خودش ۵→۰ مرتب کند
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'متوسط', score: 3 }),
          row({ symbol: 'کمینه', score: 0 }),
          row({ symbol: 'بیشینه', score: 5 }),
          row({ symbol: 'میانه', score: 2 }),
          row({ symbol: 'خوب', score: 4 }),
          row({ symbol: 'نحیف', score: 1 }),
        ]}
        onSelect={() => {}}
      />,
    );
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells.map((c) => c.textContent)).toEqual([
      expect.stringContaining('بیشینه'),
      expect.stringContaining('خوب'),
      expect.stringContaining('متوسط'),
      expect.stringContaining('میانه'),
      expect.stringContaining('نحیف'),
      expect.stringContaining('کمینه'),
    ]);
    // نشانگر ستون امتیاز در حالت پیش‌فرض ↓ (نزولی) است
    expect(screen.getByRole('button', { name: /امتیاز ↓/ })).toBeInTheDocument();
  });

  it('کلیک سطر نماد را برمی گرداند', () => {
    const onSelect = vi.fn();
    render(<FtsScreenTable rows={[row()]} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('شپنا'));
    expect(onSelect).toHaveBeenCalledWith('شپنا');
  });

  it('بدون داده علامت می خورد نه کرش — سطر حذف نمی شود (با علت هر شاخص)', () => {
    render(
      <FtsScreenTable
        rows={[
          row({
            symbol: 'ناقص',
            rev_growth: null,
            i1_pass: null,
            i1a_pass: null,
            i1b_pass: null,
            i1b_applicable: true,
            gross_margin: null,
            i3_pass: null,
            eps_series: null,
            eps_data_gap: true,
            sales_to_mcap: null,
            profit_potential_pct: null,
            i4_pass: null,
            score: 0,
          }),
        ]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('ناقص')).toBeInTheDocument();
    // جای برچسب عمومی «شکاف داده»، علتِ همان شاخص نمایش داده میشود
    expect(screen.getAllByText('گزارش ماهانهٔ کدال نیست').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('سابقهٔ EPS سالانه ثبت نشده').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('سود ناخالص در کدال نیست').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('سالانه‌سازی فروش کدال ناقص').length).toBeGreaterThanOrEqual(1);
    // برچسب عمومی حذف شده — هیچجا «شکاف داده» نداریم
    expect(screen.queryByText('شکاف داده')).not.toBeInTheDocument();
  });

  it('سلول بی‌داده tooltip علت + راه‌حل دارد (بازشوی ممیزی AuditBadge)', () => {
    render(<FtsScreenTable rows={[row({ rev_growth: null, i1_pass: null, i1a_pass: null })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-gap-reason-1a_monetary_growth');
    // از F-06: خودِ برچسبِ علت یک بج ممیزی است و متن tooltip کوتاه روی همان بج می‌ماند
    const title = cell.getAttribute('title') ?? '';
    expect(title).toContain('گزارش ماهانه');
    expect(title).toContain('مشابه');
    expect(title).toContain('راه‌حل');
  });

  it('ردیف بدون سابقه EPS: برچسب علت‌دار «سابقهٔ EPS سالانه ثبت نشده» نه «مردود»', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'تازه‌وارد', eps_series: null, eps_last: null, eps_data_gap: true, i2_pass: false })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText('تازه‌وارد')).toBeInTheDocument();
    expect(screen.getAllByText('سابقهٔ EPS سالانه ثبت نشده').length).toBeGreaterThanOrEqual(1);
  });

  it('۲ سال EPS: سری دو ساله نمایش + برچسب یکسانِ «مردود در شاخص ۲ — سابقهٔ ناقص» با علت در title', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'دوساله', eps_series: [100, 150, null], eps_data_gap: true, i2_pass: false })]}
        onSelect={() => {}}
      />,
    );
    // همان دو سالِ موجود رندر می‌شود (سال غایب «—»)
    expect(screen.getByTitle('۱۰۰ ← ۱۵۰ ← —')).toBeInTheDocument();
    const label = screen.getByTestId('eps-partial-rejected');
    // برچسب عیناً همان نردبان EPS و drill-down است (منبع واحد: lib/epsHistory)
    expect(label.textContent).toContain('مردود در شاخص ۲ — سابقهٔ ناقص');
    expect(label.textContent).toContain('۲ از ۳ سال');
    // علت شکاف با hover ظاهر می‌شود
    expect(label.getAttribute('title')).toContain('فقط ۲ سال از ۳ سال');
    // ردِ منطقی همان قبلی است — i2_pass تغییری نکرده
    expect(label.textContent).not.toContain('قبول');
  });

  it('۱ سال EPS: برچسب علت‌دار «سابقهٔ EPS کمتر از ۲ سال» — برچسب سابقهٔ ناقص نمی‌آید', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'یک‌ساله', eps_series: [50], eps_data_gap: true, i2_pass: null })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.queryByTestId('eps-partial-rejected')).not.toBeInTheDocument();
    expect(screen.getAllByText('سابقهٔ EPS کمتر از ۲ سال').length).toBeGreaterThanOrEqual(1);
  });

  it('جدول خالی حالت خالی تمیز دارد', () => {
    render(<FtsScreenTable rows={[]} onSelect={() => {}} />);
    expect(screen.getByText('ردیفی از غربالگری FTS نیامد')).toBeInTheDocument();
  });
});

describe('دروازه‌های سخت (Hard Gates) در دیده‌بان', () => {
  const mandatoryRow = row({
    symbol: 'خودرو',
    pricing_mode: 'mandatory',
    excluded: true,
    exclusion_reasons: 'صنعت با قیمت‌گذاری دستوری',
    score: 3,
  });
  const suspendedRow = row({
    symbol: 'معلق',
    excluded: true,
    exclusion_reasons: 'نماد تعلیق‌شده به علت ۳ نشست عقب‌مانده',
    score: 2,
  });
  const healthyRows = [row({ symbol: 'سالم۱', score: 5 }), row({ symbol: 'سالم۲', score: 4 })];

  it('ردیف‌های excluded (قیمت‌گذاری دستوری/تعلیق) پیش‌فرض از جدول حذف می‌شوند', () => {
    render(
      <FtsScreenTable rows={[...healthyRows, mandatoryRow, suspendedRow]} onSelect={() => {}} />,
    );
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells).toHaveLength(2);
    expect(cells[0].textContent).toContain('سالم۱');
    expect(cells[1].textContent).toContain('سالم۲');
    expect(screen.queryByText('خودرو')).not.toBeInTheDocument();
    expect(screen.queryByText('معلق')).not.toBeInTheDocument();
  });

  it('شمارنده شرکت‌ها ردیف‌های حذف‌شده را کم می‌کند و اطلاع در پانوشت می‌آید', () => {
    render(
      <FtsScreenTable rows={[...healthyRows, mandatoryRow, suspendedRow]} onSelect={() => {}} />,
    );
    expect(screen.getByText('۲ شرکت از ۴')).toBeInTheDocument();
    expect(screen.getByText(/۲ ردیفِ مشمول دروازه‌های سخت پنهان شد/)).toBeInTheDocument();
  });

  it('دکمهٔ «نمایش ردیف‌های حذف‌شده» حذف شده و ردیف‌های مشمول دروازه همواره پنهان هستند', () => {
    const onSelect = vi.fn();
    render(
      <FtsScreenTable rows={[...healthyRows, mandatoryRow, suspendedRow]} onSelect={onSelect} />,
    );
    expect(screen.queryByRole('button', { name: /ردیف‌های حذف‌شده/ })).not.toBeInTheDocument();
    expect(screen.queryByText('خودرو')).not.toBeInTheDocument();
    expect(screen.queryByText('معلق')).not.toBeInTheDocument();
  });
});

describe('فیلتر نوع نماد (Asset Type) در دیده‌بان بنیادی', () => {
  it('صندوق‌ها (ETF/سهامی/درآمد ثابت/طلا/اهرمی) پیش‌فرض حذف می‌شوند', () => {
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'سالم' }),
          row({ symbol: 'ديبا', name: 'صندوق س اوراق دولتي صبا-ثابت', sector_name: 'صندوق سرمايه گذاري قابل معامله' }),
          row({ symbol: 'عيار', name: 'صندوق طلاي عيار مفيد', sector_name: 'صندوق سرمايه گذاري قابل معامله' }),
          row({ symbol: 'وصندوق', name: 'سرمايه‌گذاري‌صندوق‌بازنشستگي' }),
        ]}
        onSelect={() => {}}
      />,
    );
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells).toHaveLength(1);
    expect(screen.getByText('سالم')).toBeInTheDocument();
    expect(screen.queryByText('ديبا')).not.toBeInTheDocument();
    expect(screen.queryByText('عيار')).not.toBeInTheDocument();
    expect(screen.queryByText('وصندوق')).not.toBeInTheDocument();
  });

  it('کارگزاری‌ها حذف می‌شوند اما سهم رفاهی کارگزاران (گپارس) می‌ماند', () => {
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'گپارس', name: 'امور رفاهي كارگزاران پارس', sector_name: 'هتل و رستوران' }),
          row({ symbol: 'کارگزاری سینا', name: 'کارگزاری سینا' }),
        ]}
        onSelect={() => {}}
      />,
    );
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells).toHaveLength(1);
    expect(screen.getByText('گپارس')).toBeInTheDocument();
    expect(screen.queryByText('کارگزاری سینا')).not.toBeInTheDocument();
  });

  it('اوراق (اخزا/اوراق تامين مالي) و اختیار معامله حذف می‌شوند', () => {
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'اخزا92', name: 'اوراق اخزا' }),
          row({ symbol: 'ضمان', name: 'اختیار معامله ضمان' }),
          row({ symbol: 'وگام', name: 'اوراق گام' }),
        ]}
        onSelect={() => {}}
      />,
    );
    expect(screen.queryByTestId('fts-screen-row')).not.toBeInTheDocument();
  });

  it('شمار صندوق/کارگزاری حذف‌شده در پانوشت اعلام می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'سالم' }), row({ symbol: 'ديبا', name: 'صندوق س اوراق دولتي صبا-ثابت' })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText(/۱ صندوق\/کارگزاری\/اوراق با فیلتر نوع نماد حذف شد/)).toBeInTheDocument();
  });

  it('isFundamentalCompany: شرکت تولیدی/خدماتی عادی می‌ماند', () => {
    expect(isFundamentalCompany({ symbol: 'شپنا', name: 'پالایش نفت', sector_name: 'فراورده‌هاي نفتي' })).toBe(true);
    expect(isFundamentalCompany({ symbol: 'همراه', name: 'ارتباطات سيار', sector_name: 'مخابرات' })).toBe(true);
    expect(isFundamentalCompany({ symbol: 'وصندوق', name: 'سرمايه‌گذاري‌صندوق‌بازنشستگي', sector_name: 'x' })).toBe(false);
  });
});

describe('N/A رشد فیزیکی برای شرکت‌های غیرتولیدی', () => {
  it('هلدینگ/سرمایه‌گذاری/بانک/خدماتی → رشد فیزیکی غیرقابل اعمال (N/A)', () => {
    expect(isPhysicalGrowthApplicable({ name: 'سرمايه‌گذاري‌غدير(هلدينگ', sector_name: 'سایر' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'سرمايه گذاري سينا', sector_name: 'سرمايه گذاريها' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'بانک سینا', sector_name: 'بانكها و موسسات اعتباري' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'ارتباطات سيار', sector_name: 'مخابرات' })).toBe(false);
    expect(isPhysicalGrowthApplicable({ name: 'بیمه دانا', sector_name: 'بيمه وصندوق بازنشستگي' })).toBe(false);
  });

  it('تولیدی/خدماتی صرفاً در گروه‌های نامرتبط → رشد فیزیکی قابل اعمال', () => {
    expect(isPhysicalGrowthApplicable({ name: 'پالایش نفت اصفهان', sector_name: 'فراورده‌هاي نفتي' })).toBe(true);
    expect(isPhysicalGrowthApplicable({ name: 'فولاد مبارکه', sector_name: 'فلزات اساسي' })).toBe(true);
  });
});


// ---------------------------------------------------------------------------
// F-08 — کارایی: جدول مجازی می‌شود (فقط پنجرهٔ در دید رندر می‌شود) و سلول‌ها ارزان‌اند
// ---------------------------------------------------------------------------
describe('کارایی جدول غربالگری (F-08)', () => {
  function bigRows(n: number): FtsScreenRow[] {
    return Array.from({ length: n }, (_, i) => row({ symbol: 'نماد' + String(i), name: 'شرکت نمونه ' + String(i) }));
  }

  it('با ۸۶۵ ردیف فقط پنجرهٔ مجازی رندر می‌شود (نه همهٔ ردیف‌ها)', () => {
    render(<FtsScreenTable rows={bigRows(865)} onSelect={() => {}} thresholds={{ growth_min: 30 }} />);
    const rendered = screen.getAllByTestId('fts-screen-row');
    expect(rendered.length).toBe(12); // پنجرهٔ mock = همان چیزی که virtualizer در دید نگه می‌دارد
    expect(rendered.length).toBeLessThan(865);
    // هزینهٔ DOM به پنجره گره خورده، نه به داده
    expect(document.querySelectorAll('*').length).toBeLessThan(1000);
  });

  it('virtualizer با تعداد ردیف‌های نمایان، ارتفاع ثابت ردیف و overscan پیکربندی شده است', async () => {
    render(<FtsScreenTable rows={bigRows(200)} onSelect={() => {}} thresholds={null} />);
    const rv = (await import('@tanstack/react-virtual')) as unknown as {
      __virtualOptions?: () => { count: number; overscan?: number; estimateSize?: (i: number) => number } | null;
    };
    const opts = rv.__virtualOptions?.();
    expect(opts).toBeTruthy();
    expect(opts!.count).toBe(200);
    // ارتفاعِ ردیف با فونتِ درشتِ جدول بالا رفت (46 → 52)؛ سنجشِ زنده
    // offsetHeightِ واقعی را همین ۵۲ اندازه گرفت، پس پین، پینِ عددِ تازه است.
    expect(opts!.estimateSize?.(0)).toBe(52);
    expect(opts!.overscan).toBe(8);
  });

  // ── جستجوی درونِ جدول (FUND-SEARCH) ─────────────────────────────────────
  it('جستجو فقط همین جدول را تنگ می‌کند: «فولاد» یک ردیف می‌گذارد', () => {
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', sector_name: 'فلزات اساسي' }),
          row({ symbol: 'ذوب', name: 'ذوب آهن اصفهان', sector_name: 'فلزات اساسي' }),
          row({ symbol: 'شپنا', name: 'پالایش نفت اصفهان', sector_name: 'محصولات نفتي' }),
        ]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(3);
    fireEvent.change(screen.getByTestId('fts-search'), { target: { value: 'فولاد' } });
    const rows = screen.getAllByTestId('fts-screen-row');
    expect(rows).toHaveLength(1);
    expect(rows[0].textContent).toContain('فولاد');
    expect(rows[0].textContent).not.toContain('ذوب');
  });

  it('جستجو با نوشتارِ عربی هم تطبیق می‌کند و با × پاک می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[
          row({ symbol: 'فولاد', name: 'فولاد مبارکه اصفهان' }),
          row({ symbol: 'شپنا', name: 'پالايش نفت اصفهان' }),
        ]}
        onSelect={() => {}}
      />,
    );
    fireEvent.change(screen.getByTestId('fts-search'), { target: { value: 'پالايش نفت' } });
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(1);
    fireEvent.click(screen.getByTestId('fts-search-clear'));
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(2);
  });

  it('نتیجهٔ بی‌مورد: صفر ردیف و صفرِ شمارنده، نه پیامِ خطا', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'فولاد' }), row({ symbol: 'شپنا' })]} onSelect={() => {}} />);
    fireEvent.change(screen.getByTestId('fts-search'), { target: { value: 'نیست' } });
    expect(screen.queryAllByTestId('fts-screen-row')).toHaveLength(0);
    expect(screen.getByText(/۰ شرکت از ۲/)).toBeInTheDocument();
  });

  it('کانتینر اسکرول با ارتفاع محدود و هدر چسبان آماده است', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const scroll = screen.getByTestId('fts-screen-scroll');
    expect(scroll.className).toMatch(/h-\[calc\(100dvh-200px\)\]/); // ارتفاع کشسانِ متناسب با ویوپورت (بدون فضای خالی پایین)
    expect(scroll.className).toContain('overflow-auto');
    const thead = document.querySelector('thead');
    expect(thead?.className).toContain('sticky');
    expect(thead?.className).toContain('top-0');
  });
});

/**
 * برچسب و وتوی مجمع در ردیفِ جدول — رأیِ مالک: «بغل نماد برچسب داده بشه که
 * … مجمع عمومی داره هشدار داده بشه و اینکه وتو بخوره».
 * دو نقشِ جدا: برچسبِ هشدار (زرد/آبی) از `assemblyEvents` ساخته می‌شود و
 * وتو (قرمز) از پرچمِ بک‌اند `assembly_veto`. دومی باید بر اولی بچربد، وگرنه
 * دو برچسبِ متناقض کنارِ هم می‌نشینند.
 */
describe('برچسب و وتوی مجمعِ ردیف', () => {
  const plusDays = (base: string, n: number) => {
    const d = new Date(`${base}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const TODAY = todayIsoInTehran();
  const IN3 = plusDays(TODAY, 3);
  const IN40 = plusDays(TODAY, 40);

  const events = (date: string, cat = 'assembly') => ({
    // «آگهی دعوت به مجمع…» تاریخِ جلسه را در عنوان دارد ⇒ منشأ title. بی‌این
    // میدان (§۲۴ِ رأی) برچسب شمارشِ معکوس نمی‌سازد.
    شپنا: [{ date, cat, title: 'آگهی دعوت به مجمع عمومی عادی سالیانه',
             date_source: 'title' as const }],
  });

  const badge = () => screen.queryByTestId('row-assembly-veto-badge');
  const near = () => screen.queryByTestId('row-assembly-near-badge');

  it('وتو ⇒ برچسبِ قرمز با تاریخِ جلالی، و برچسبِ هشدار تکرار نمی‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: true, assembly_date: IN3, assembly_days: 3, watchlist: false })]}
        onSelect={() => {}}
        assemblyEvents={events(IN3)}
      />,
    );
    const b = badge();
    expect(b).not.toBeNull();
    expect(b?.textContent).toContain('وتوی مجمع');
    expect(b?.textContent).toBe(`وتوی مجمع ${jalaliOf(IN3)}`);
    // هشدارِ زرد زیرِ وتو پنهان می‌شود — یک برچسب، یک رأی
    expect(near()).toBeNull();
    const title = b?.getAttribute('title') ?? '';
    expect(title).toContain('ورود وتو شد');
    expect(title).toContain('۳ روز دیگر');
  });

  it('کنترلِ منفی: بی‌وتو همان برچسبِ هشدارِ قبلی است', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: false })]}
        onSelect={() => {}}
        assemblyEvents={events(IN3)}
      />,
    );
    expect(badge()).toBeNull();
    expect(near()).not.toBeNull();
    expect(near()?.textContent).toContain('مجمع');
  });

  // §۲۴ِ رأی: اگر عنوانِ اطلاعیه تاریخِ جلسه را نمی‌گفت، عددِ تقویم فقط تاریخِ
  // انتشار است ⇒ نه شمارشِ معکوس، نه وتو. برچسبِ «اطلاعیه» می‌ماند.
  it('بی‌تاریخِ جلسه در عنوان ⇒ برچسبِ «اطلاعیه» با تاریخِ انتشار، بی‌«چند روز دیگر»', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: false })]}
        onSelect={() => {}}
        assemblyEvents={{ شپنا: [{ date: IN3, cat: 'assembly', date_source: 'publication_fallback' as const,
                                   title: 'تصمیمات مجمع عمومی عادی سالیانه' }] }}
      />,
    );
    expect(badge()).toBeNull();          // وتو نمی‌شود
    const n = screen.queryByTestId('row-assembly-notice-badge');
    expect(n).not.toBeNull();
    expect(near()).toBeNull();           // برچسبِ «مجمعِ نزدیک» هم نمی‌گیرد
    expect(n?.textContent).toContain('اطلاعیه');
    expect(n?.textContent).not.toMatch(/روز دیگر|فردا|امروز/);
  });

  it('لغو/تعویق برچسبِ تغییر می‌گیرد و وتو نمی‌شود (تاریخِ نامعلوم، وتوی ساختگی است)', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: false })]}
        onSelect={() => {}}
        assemblyEvents={events(IN3, 'assemblyChange')}
      />,
    );
    expect(badge()).toBeNull();
    expect(screen.queryByTestId('row-assembly-change-badge')).not.toBeNull();
  });

  it('مجمعِ بیرونِ پنجره هیچ برچسبی نمی‌سازد', () => {
    render(
      <FtsScreenTable rows={[row()]} onSelect={() => {}} assemblyEvents={events(IN40)} />,
    );
    expect(badge()).toBeNull();
    expect(near()).toBeNull();
  });

  it('وتوی بی‌تاریخ هم وتو می‌ماند — فقط تاریخ از برچسب می‌افتد، نه رأی', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: true, watchlist: false })]}
        onSelect={() => {}}
      />,
    );
    expect(badge()?.textContent).toBe('وتوی مجمع');
  });

  it('وتو ردیف را خاکستری نمی‌کند: مجمع ضعفِ بنیادی نیست، زمان‌بندیِ ورود است', () => {
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: true, assembly_date: IN3, assembly_days: 3, watchlist: false })]}
        onSelect={() => {}}
      />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    expect(tr.className).not.toContain('opacity-');
    expect(tr.className).not.toContain('cursor-not-allowed');
    // نمرۀ پنج‌شاخصه دست‌نخورده نشان داده می‌شود
    expect(tr.textContent).toContain('۴');
  });
});


/**
 * برچسب «افزایش سرمایه» (#59) — رأیِ pilot: فقط هشدارِ تاریخ، هیچ وتویی از آن
 * نمی‌سازد و ردیف را خاکستری نمی‌کند؛ کنارِ بجِ مجمع می‌نشیند نه به‌جای آن.
 */
describe('برچسب «افزایش سرمایه» در ردیف', () => {
  const plusDays = (base: string, n: number) => {
    const d = new Date(`${base}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const TODAY = todayIsoInTehran();
  const cap = (date: string) => ({
    شپنا: [{ date, cat: 'capitalIncrease', title: 'اطلاعیه افزایش سرمایه از محل سود انباشته' }],
  });

  it('رویدادِ پیش‌رو ⇒ برچسب با تاریخِ جلالی، بی‌هیچ وتویی', () => {
    render(
      <FtsScreenTable rows={[row()]} onSelect={() => {}} capitalEvents={cap(plusDays(TODAY, 5))} />,
    );
    const b = screen.getByTestId('row-capital-increase-badge');
    expect(b.textContent).toContain('افزایش سرمایه');
    expect(b.textContent).toContain(jalaliOf(plusDays(TODAY, 5)).split('-').slice(-2).join('/'));
    expect(b.getAttribute('title')).toContain('وتو نیست');
    expect(screen.queryByTestId('row-assembly-veto-badge')).toBeNull();
  });

  it('با وتوی مجمع هم‌زمان می‌نشیند و جایِ آن را نمی‌گیرد', () => {
    const d = plusDays(TODAY, 4);
    render(
      <FtsScreenTable
        rows={[row({ assembly_veto: true, assembly_date: d, assembly_days: 4 })]}
        onSelect={() => {}}
        assemblyEvents={{ شپنا: [{ date: d, cat: 'assembly', date_source: 'title' as const, title: 'آگهی دعوت به مجمع' }] }}
        capitalEvents={cap(d)}
      />,
    );
    expect(screen.queryByTestId('row-assembly-veto-badge')).not.toBeNull();
    expect(screen.queryByTestId('row-capital-increase-badge')).not.toBeNull();
  });

  it('بیرونِ افقِ «نزدیک» هیچ برچسبی نیست — تاریخِ دور ساخته نمی‌شود', () => {
    render(
      <FtsScreenTable rows={[row()]} onSelect={() => {}} capitalEvents={cap(plusDays(TODAY, 40))} />,
    );
    expect(screen.queryByTestId('row-capital-increase-badge')).toBeNull();
  });

  it('ردیفِ برچسب‌خورده خاکستری یا بی‌مصرف نمی‌شود', () => {
    render(
      <FtsScreenTable rows={[row()]} onSelect={() => {}} capitalEvents={cap(plusDays(TODAY, 2))} />,
    );
    const tr = screen.getByTestId('fts-screen-row');
    expect(tr.className).not.toContain('opacity-');
    expect(tr.className).not.toContain('cursor-not-allowed');
  });
});
