// تست دیده‌بان کلان بنیادی: ماتریس ۵ شاخص + سورت + علت‌دار بودن بی‌داده + انتخاب نماد
// + دروازه‌های سخت (excluded) + regression سورت پیش‌فرض امتیاز (نزولی)
// + فیلتر نوع نماد (Asset Type): صندوق/کارگزاری/اختیار حذف می‌شوند
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { isFundamentalCompany, isPhysicalGrowthApplicable } from '@features/fundamental/lib/assetScope';
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
    expect(screen.getByText('دیده‌بان کلان بنیادی — ماتریس ۵ شاخص FTS')).toBeInTheDocument();
    // toFaDigits فقط ارقام را عوض می‌کند؛ ممیز لاتین می‌ماند: ۴۵.۲٪
    expect(screen.getByText('۴۵.۲٪')).toBeInTheDocument();
    expect(screen.getAllByText('✓').length).toBeGreaterThanOrEqual(4);
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
    render(<FtsScreenTable rows={[row({ rev_growth: null, i1_pass: null })]} onSelect={() => {}} />);
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
    expect(screen.getByText('۱۰۰ ← ۱۵۰ ← —')).toBeInTheDocument();
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

  it('سوییچ «نمایش ردیف‌های حذف‌شده» ردیف‌های excluded را با ظاهر محو برمی‌گرداند', () => {
    render(
      <FtsScreenTable rows={[...healthyRows, mandatoryRow, suspendedRow]} onSelect={() => {}} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'نمایش ردیف‌های حذف‌شده' }));
    const cells = screen.getAllByTestId('fts-screen-row');
    expect(cells).toHaveLength(4);
    expect(screen.getByText('خودرو')).toBeInTheDocument();
    expect(screen.getByText('معلق')).toBeInTheDocument();
    expect(screen.getByText('۴ شرکت از ۴')).toBeInTheDocument();
    // ردیف excluded محو و خط‌خورده است
    const excludedCell = cells.find((c) => (c.textContent ?? '').includes('خودرو'));
    expect(excludedCell?.className).toContain('opacity-55');
    // دکمه به حالت «پنهان‌سازی» برمی‌گردد
    expect(screen.getByRole('button', { name: 'پنهان‌سازی ردیف‌های حذف‌شده' })).toBeInTheDocument();
  });

  it('کلیک روی ردیف excluded نماد را فعال نمی‌کند', () => {
    const onSelect = vi.fn();
    render(
      <FtsScreenTable rows={[...healthyRows, mandatoryRow]} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'نمایش ردیف‌های حذف‌شده' }));
    fireEvent.click(screen.getByText('خودرو'));
    expect(onSelect).not.toHaveBeenCalledWith('خودرو');
  });

  it('بدون ردیف excluded سوییچ نمایش رندر نمی‌شود', () => {
    render(<FtsScreenTable rows={healthyRows} onSelect={() => {}} />);
    expect(screen.queryByRole('button', { name: 'نمایش ردیف‌های حذف‌شده' })).not.toBeInTheDocument();
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
    expect(opts!.estimateSize?.(0)).toBe(46);
    expect(opts!.overscan).toBe(8);
  });

  it('کانتینر اسکرول با ارتفاع محدود و هدر چسبان آماده است', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const scroll = screen.getByTestId('fts-screen-scroll');
    expect(scroll.className).toContain('max-h-[70vh]');
    expect(scroll.className).toContain('overflow-auto');
    const thead = document.querySelector('thead');
    expect(thead?.className).toContain('sticky');
    expect(thead?.className).toContain('top-0');
  });
});
