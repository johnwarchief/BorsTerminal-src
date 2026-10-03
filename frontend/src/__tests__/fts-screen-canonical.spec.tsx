// src/__tests__/fts-screen-canonical.spec.tsx
// گاردِ همگامیِ جدول غربالگری با رأیِ خودِ بک‌اند (Card = Engine = API = Screener = Frontend)
//
// چرا این فایل هست: سنجشِ ۱۴۰۵-۰۷-۱۱ رویِ ۸۷۳ نمادِ زنده نشان داد جدول سه‌جا
// منطقِ مستقل دارد — (۱) «ب» رشد تولیدی را با regexِ نام/صنعت N/A می‌کرد و
// حکمِ واقعیِ موتور را می‌پوشاند (۲۵۱ ردیف) و درِ ۱۰۲ ردیفِ دیگر N/Aِ اشتباه
// می‌گذاشت، (۲) علتِ خالی‌بودنِ شاخص ۳/۴ هم از همان regex می‌آمد (واگرایی ۱۱۲
// و ۷۹ ردیف)، (۳) پری‌ست «سوپر بنیادی» آستانهٔ فرانتیِ `score>=4 && free` را
// می‌شمرد نه `verdict === 'STRONG'` (۹۶ در برابرِ ۵۱). فایلِ دانلودی هم «ب» را
// از `i2_pass` (محورِ EPS!) و رژیمِ صنعت را از کلیدِ `'regulated'` (بک‌اند
// `mandatory` می‌فرستد) می‌نوشت. هر کدام یک آزمونِ منفی/مثبت همین‌جا قفل می‌شود.
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable, displayScore, screenRowCells } from '@features/fundamental/ui/FtsScreenTable';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 14;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(opts.count, WINDOW) }, (_, i) => ({
          key: i, index: i, start: i * 46,
        })),
    }),
  };
});

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتي، كك و سوخت هسته اي',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_years_available: 3,
    eps_years_required: 3,
    gross_margin: 32.4,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: true,
    i1b_applicable: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
    verdict: 'WATCH',
    excluded: false,
    applicable: true,
    ...patch,
  } as FtsScreenRow;
}

const renderRows = (rows: FtsScreenRow[]) =>
  render(<FtsScreenTable rows={rows} onSelect={() => {}} thresholds={{}} />);

describe('حکمِ هر محور فقط از پرچمِ همان محور', () => {
  it('بانکِ «هلدینگ‌نما» با i1b_applicable=true: تیکِ موتور نمایش داده می‌شود، نه N/A', () => {
    // نام و صنعت عمداً همان الگویی‌اند که regexِ پیشین «مالی» می‌خواند؛
    // بک‌اند می‌گوید این محور قابل‌اعمال و مردود است ⇒ باید ✗ دید.
    renderRows([row({
      symbol: 'وبملت', name: 'بانك ملت (هلدینگ)', sector_name: 'بانكها و موسسات اعتباري',
      i1b_applicable: true, i1b_pass: false,
    })]);
    expect(screen.queryByTestId('fts-na-1b_volume_growth')).toBeNull();
    expect(screen.getByTestId('fts-mark-1b_volume_growth')).toBeTruthy();
  });

  it('i1b_applicable=false: همان‌جا N/A از اعلامِ موتور می‌نشیند', () => {
    renderRows([row({
      symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', sector_name: 'فلزات اساسي',
      i1b_applicable: false, i1b_pass: true,
    })]);
    expect(screen.getByTestId('fts-na-1b_volume_growth')).toBeTruthy();
    expect(screen.queryByTestId('fts-mark-1b_volume_growth')).toBeNull();
  });

  it('الف و ب دو حکمِ جدایند: i1a_pass=false با i1_pass=true باید ✗ بگوید', () => {
    renderRows([row({ i1_pass: true, i1a_pass: false, i1b_pass: true })]);
    expect(screen.getByTestId('fts-mark-1a_monetary_growth')).toBeTruthy();
    expect(screen.getByTestId('fts-mark-1a_monetary_growth').textContent).toContain('✗');
  });

  it('علتِ خالیِ شاخص ۳: na از `i3_na` می‌آید، نه از نام/صنعت', () => {
    renderRows([row({
      symbol: 'وبيaname', name: 'بانک سامان (هلدینگ)', sector_name: 'بانكها و موسسات اعتباري',
      i3_pass: null, i3_na: false, gross_margin: null,
    })]);
    expect(screen.queryByTestId('fts-na-3_gross_margin')).toBeNull();
    expect(screen.getByTestId('fts-gap-reason-3_gross_margin')).toBeTruthy();
  });

  it('شاخص ۴ با i4_na=true: برچسبِ N/A؛ با i4_na=false: علتِ شکافِ داده', () => {
    renderRows([
      row({ symbol: 'وغدير', name: 'گسترش سرمایه‌گذاری ایران‌خودرو', sector_name: 'سرمايه گذاريها',
            i4_pass: null, i4_na: true, sales_to_mcap: null }),
      row({ symbol: 'كيمازي', name: 'صيادKemiaz', sector_name: 'محصولات شيميايي',
            i4_pass: null, i4_na: false, sales_to_mcap: null }),
    ]);
    expect(screen.getByTestId('fts-na-4_sales_to_mcap')).toBeTruthy();
    expect(screen.getAllByTestId(/fts-gap-reason|fts-na-4/).length).toBeGreaterThanOrEqual(2);
  });
});

describe('پری‌ست «سوپر بنیادی» = رأیِ موتور', () => {
  it('شمارش و فیلتر از verdict === STRONG می‌آید، نه از score/pricing_mode', () => {
    const rows = [
      // قویِ واقعی: امتیازِ ۴ و سه بلاکر قبول
      row({ symbol: 'شپنا', score: 4, verdict: 'STRONG', pricing_mode: 'neutral' }),
      // امتیاز ۵ ولی بلاکرِ سوم مردود ⇒ بک‌اند آن را STRONG نمی‌خواند
      row({ symbol: 'خودرو', score: 5, verdict: 'WATCH', pricing_mode: 'free' }),
    ];
    renderRows(rows);
    const btn = screen.getByRole('button', { name: /سوپر بنیادی/ });
    expect(btn.textContent).toContain('۱');
    fireEvent.click(btn);
    expect(screen.queryByText('خودرو')).toBeNull();
    expect(screen.getByText('شپنا')).toBeTruthy();
  });
});

describe('ردیفِ «FTS ندارد» امتیاز FTS ندارد (مثلِ کارت)', () => {
  it('applicable=false ⇒ نه عدد در بجِ امتیاز، نه در فایلِ دانلودی', () => {
    // نمادی که فیلترِ قلمروِ جدول آن را «شرکت» می‌شناسد (دارایِ نامِ
    // «سرمایه‌گذاری» بدونِ واژۀ «صندوق/کارگزاری»، که خودِ فیلتر دور می‌انداختش)
    // ولی موتور برایش می‌گوید «FTS ندارد» — همان هشت ردیفِ سنجشِ زنده.
    const r = row({ symbol: 'ومدير', name: 'سرمایه گذاری توسعه صنعت و معدن',
                    sector_name: 'سرمايه گذاريها', applicable: false, score: 3,
                    verdict: 'FTS ندارد' });
    expect(displayScore(r)).toBeNull();
    render(<FtsScreenTable rows={[r]} onSelect={() => {}} />);
    const tr = screen.getByTestId('fts-screen-row');
    expect(within(tr).queryByText('۳')).toBeNull();
    // علتِ N/A رویِ همان بج می‌ماند (title) — نه حذفِ بی‌دلیلِ عدد
    expect(tr.querySelector('td:last-child span')?.getAttribute('title'))
      .toContain('خارج از پنج')
    expect(screenRowCells(r).at(-1)).not.toBe('۳');
  });

  it('applicable=true با امتیاز ۳ ⇒ همان عدد نمایش داده می‌شود', () => {
    const r = row({ applicable: true, score: 3 });
    expect(displayScore(r)).toBe(3);
    render(<FtsScreenTable rows={[r]} onSelect={() => {}} />);
    expect(within(screen.getByTestId('fts-screen-row')).getByText('۳')).toBeInTheDocument();
  });
});

describe('لایۀ ریاضیاتِ فصلی هیچ داوری FTS نمی‌سازد', () => {
  it('fundMath هیچ eval* یا PASS/score/verdict صادر نمی‌کند', async () => {
    const mod = await import('@features/fundamental/lib/fundMath');
    const names = Object.keys(mod);
    expect(names).toEqual(expect.arrayContaining(['deCumulateQuarters', 'profitYoY', 'sectorMedianPE']));
    expect(names.filter((n) => /^eval/.test(n))).toEqual([]);
    // هر خروجیِ داوری (pass/score/verdict) ممنوع — فقط عددِ نمایشی
    expect(names.filter((n) => /(Pass|Score|Verdict|Eval)/i.test(n))).toEqual([]);
  });
});

describe('فایلِ دانلودی با صفحه یکی است', () => {
  it('«الف» از i1a_pass، «ب» از i1b_pass (یا N/A)، و رژیمِ دستوری از mandatory', () => {
    const cells = screenRowCells(row({
      i1_pass: true, i1a_pass: false, i1b_pass: true, i1b_applicable: true,
      i2_pass: false, pricing_mode: 'mandatory',
    }));
    expect(cells[1]).toContain('الف: ✗');
    expect(cells[1]).toContain('ب: ✓');
    expect(cells[1]).not.toContain('الف: ✓');
    expect(cells[5]).toContain('دستوری');
  });

  it('«ب» وقتی موتور می‌گوید قابل‌اعمال نیست، N/A نوشته می‌شود', () => {
    const cells = screenRowCells(row({ i1b_applicable: false, i1b_pass: true }));
    expect(cells[1]).toContain('ب: N/A');
  });
});
