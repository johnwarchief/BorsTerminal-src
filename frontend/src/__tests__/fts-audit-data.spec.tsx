// F-10 — تست ممیزیِ داده‌ایِ جدول غربالگری:
// ۱) حکمِ موتور بر «مقدار غایب» مقدم است (برچسب «داده نیست» برای ردیفِ دارای حکم دروغ است)
// ۲) EPS بدون گِردکردن بی‌صدا (۴۵۴.۶۷ نباید ۴۵۵ شود)
// ۳) قالب درصد با جداکنندهٔ هزارگان + هشدار برای اعداد غیرمعقول (بدون حذف/دستکاری عدد)
// ۴) علت حذف ردیف سرریز نمی‌کند و متن کامل در tooltip می‌ماند
// ۵) علتِ کارت ممیزی وقتی مقدار نیست، همان حقیقت را می‌گوید («حکمِ موتور اعمال شده»)
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { cardAuditEvidence, screenAuditEvidence } from '@features/fundamental/lib/auditEvidence';
import { gapLabel, standardizeGap } from '@features/fundamental/lib/gapReason';
import { fmtPctGrouped, fmtRatioGrouped, isAbsurdPct } from '@features/fundamental/lib/numFmt';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

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

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'نماد',
    symbol_norm: 'نماد',
    name: 'شرکت نمونه',
    sector_name: 'مواد و محصولات دارویی',
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
    i5_pass: true,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

describe('F-10 — حکمِ موتور بر مقدار غایب مقدم است', () => {
  it('شاخص ۱: رشد null ولی حکم مردود ⇒ ✗ (نه برچسب «داده نیست»)', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'الف', rev_growth: null, i1_pass: false })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-mark-1a_monetary_growth');
    expect(cell.textContent).toContain('✗');
    expect(screen.queryByText(gapLabel('1a_monetary_growth'))).toBeNull();
    // عدد جای «—» با tooltip صادقانه
    const value = screen.getByText('—', { selector: 'span.num' });
    expect(value.getAttribute('title')).toContain('حکمِ موتور FTS');
  });

  it('شاخص ۳: حاشیهٔ null ولی حکم مردود ⇒ ✗', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'ب', gross_margin: null, i3_pass: false })]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-mark-3_gross_margin').textContent).toContain('✗');
    expect(screen.queryByText(gapLabel('3_gross_margin'))).toBeNull();
  });

  it('شاخص ۴: هر دو مقدار null ولی حکم قبول ⇒ ✓', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'ج', profit_potential_pct: null, sales_to_mcap: null, i4_pass: true })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId('fts-mark-4_sales_to_mcap').textContent).toContain('✓');
    expect(screen.queryByText(gapLabel('4_sales_to_mcap'))).toBeNull();
  });

  it('شاخص ۲: eps_data_gap ولی حکم موجود ⇒ حکم اعمال می‌شود (نه برچسب شکاف)', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'د', eps_data_gap: true, i2_pass: false, eps_series: [100, 120, 150] })]}
        onSelect={() => {}}
      />,
    );
    const cell = screen.getByTestId('fts-mark-2_eps_trend') ?? screen.getByTestId('eps-gap-reason');
    expect(cell.textContent).toContain('✗');
  });

  it('بدون پرچم (حالت نظری) هنوز «بدون داده» می‌آید — صادقانه', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'ه', i5_pass: null, pricing_mode: 'free' })]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-gap-reason-5_industry')).toBeInTheDocument();
  });
});

describe('F-10 — قالب‌بندی و دقت اعداد', () => {
  it('EPS اعشاری بدون گِردکردن بی‌صدا نمایش داده می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'فسوژ', eps_series: [454.67, 219, 330.67] })]}
        onSelect={() => {}}
      />,
    );
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۴۵۴.۶۷');
    expect(cell.textContent).toContain('۳۳۰.۶۷');
    expect(cell.textContent).not.toContain('۴۵۵');
  });

  it('درصد بزرگ با جداکنندهٔ هزارگان و نشان هشدار می‌آید (عدد حذف/کلیپ نمی‌شود)', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'شپديس', rev_growth: 3885990000, i1_pass: true })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۳٬۸۸۵٬۹۹۰٬۰۰۰٪');
    expect(cell.textContent).toContain('⚠');
  });

  it('حاشیهٔ منفیِ بزرگ هم گروه‌بندی و هشدار می‌گیرد', () => {
    render(<FtsScreenTable rows={[row({ symbol: 'فولاد', gross_margin: -1885.9, i3_pass: false })]} onSelect={() => {}} />);
    const cell = screen.getByTestId('fts-screen-row');
    expect(cell.textContent).toContain('۱٬۸۸۵.۹٪');
    expect(cell.textContent).toContain('⚠');
  });

  it('توابع قالب‌بندی: گروه‌بندی، نسبت و آستانهٔ غیرمعقول', () => {
    expect(fmtPctGrouped(3885990000)).toBe('۳٬۸۸۵٬۹۹۰٬۰۰۰٪');
    expect(fmtPctGrouped(45.2)).toBe('۴۵.۲٪');
    expect(fmtPctGrouped(null)).toBeNull();
    expect(fmtRatioGrouped(25618.03)).toBe('۲۵٬۶۱۸.۰۳×');
    expect(isAbsurdPct(1000)).toBe(true);
    expect(isAbsurdPct(999.9)).toBe(false);
  });

  it('ردیف‌های مشمول دروازه‌های سخت در دیده‌بان پنهان می‌مانند', () => {
    render(
      <FtsScreenTable
        rows={[row({ symbol: 'فولاد', excluded: true, exclusion_reasons: 'صنعت بیمه · نماد تعلیق · قیمت‌گذاری دستوری' })]}
        onSelect={() => {}}
      />,
    );
    expect(screen.queryByText('فولاد')).not.toBeInTheDocument();
  });

  it('شاهدِ ممیزی وقتی مقدار نیست، دلیلش را صادقانه می‌گوید', () => {
    const ev = screenAuditEvidence('1a_monetary_growth', row({ rev_growth: null }), { growth_min: 30 });
    expect(String(ev.reason)).toContain('حکمِ موتور');
    expect(String(ev.reason)).toContain('کارت نماد');
  });
});

// GAPS-1 — علتِ نبودِ داده باید علتِ *همان نماد* باشد، نه برچسبِ عمومیِ محور.
describe('GAPS-1 — قراردادِ تازهٔ standardizeGap', () => {
  it('نامِ محورِ ۱بِ بک‌اند (1b_physical_volume) به علتِ درستِ ۱ب می‌رسد، نه fallback', () => {
    expect(gapLabel('1b_physical_volume')).toBe(gapLabel('1b_volume_growth'));
    expect(gapLabel('1b_physical_volume')).not.toBe('گزارش کدال ناقص است');
  });

  it('علتِ خاصِّ بک‌اند بر متنِ عمومیِ محور پیش‌روی می‌کند', () => {
    const g = standardizeGap({
      layer: '۳', axis: '3_gross_margin',
      why: 'این نماد صندوق است؛ صندوق «فروش» و «بهای تمام‌شده» ندارد.',
      fix: 'برای صندوق‌ها شاخص ۳ سنجیده نمی‌شود.',
    });
    expect(g.why).toContain('صندوق');
    expect(g.why).not.toContain('سود ناخالصِ ثبت‌شده');
    expect(g.fix).toContain('سنجیده نمی‌شود');
  });

  it('متنِ سرشار از نامِ ستون/مسیر API به متنِ تمیزِ محور تبدیل می‌شود', () => {
    const g = standardizeGap({
      layer: '۱ب', axis: '1b_physical_volume',
      why: 'هیچ ستونِ حجم/تناژ فیزیکی در monthly_sales وجود ندارد.',
      fix: 'با POST /api/sync/codal?mode=backfill بسته می‌شود.',
    });
    expect(g.why).not.toContain('monthly_sales');
    expect(g.fix).not.toContain('/api/');
    // افتاد به متنِ محورِ ۱ب — همان چیزی که بدونِ فیلتر، «ستونِ فنی» را به کاربر می‌داد
    expect(g.why).toContain('ستون مقدار و حجم فیزیکی');
    expect(g.fix).toContain('تعدیل تورمی');
  });

  it('علتِ خالی ⇒ متنِ جانشینِ محور، و ارقام لاتین به فارسی تبدیل می‌شود', () => {
    const g = standardizeGap({
      layer: '3', axis: '3_gross_margin', why: '', fix: '',
    });
    expect(g.why).toContain('سود ناخالص');
    const d = standardizeGap({
      layer: '۳', axis: '3_gross_margin',
      why: 'در صورت سود و زیانِ سالِ مرجع (1403/12/30) سطر نبود.', fix: 'x',
    });
    expect(d.why).toContain('1403'.split('').map((c) => String.fromCharCode(0x06f0 + Number(c))).join(''));
    expect(d.why).not.toMatch(/[0-9]/);
  });
});

// ── FUND-TEXT: علتِ هر شاخص باید فقط «چه عددی در برابر چه کفی» باشد ──────────
// جمله‌های تفسیریِ علّی («قدرت انحصاری»، «ریسک حباب»، «تضمینِ پایداری») چیزی را
// می‌گفتند که موتور هرگز اندازه نگرفته بود؛ کاربر آن‌ها را دلیلِ رأی می‌خواند.
describe('متنِ علتِ شاخص‌ها — عدد و کف، بدون ادعای اندازه‌گیری‌نشده', () => {
  const BANNED = [
    'قدرت انحصاری', 'بهره‌وری عالی', 'تضمین', 'حباب', 'جهش عملیاتی',
    'تایید می‌شود', 'قدرت فروش', 'حاشیه امن', 'نیازمند دقت', 'انقباض فروش',
    'بی‌معنا', 'سرکوب', 'معاف می‌باشد',
  ];
  const CASES: Partial<FtsScreenRow>[] = [
    {},
    { rev_growth: -12, i1_pass: false },
    { gross_margin: 8.5, i3_pass: false },
    { gross_margin: null, i3_pass: null },
    { sales_to_mcap: 0.02, i4_pass: false },
    { sales_to_mcap: null, i4_pass: null },
    { pricing_mode: 'mandatory', i5_pass: false },
    { pricing_mode: null, i5_pass: null },
    { eps_series: [100, 120, 90], i2_pass: false },
  ];
  const AXES = [
    '1a_monetary_growth', '1b_volume_growth', '2_eps_trend',
    '3_gross_margin', '4_sales_to_mcap', '5_industry',
  ] as const;

  it('هیچ علتی واژۀ تفسیریِ علّی ندارد (همهٔ ترکیب‌های مقدار/حکم)', () => {
    for (const axis of AXES) {
      for (const patch of CASES) {
        const reason = String(screenAuditEvidence(axis, row(patch), null).reason ?? '');
        for (const word of BANNED) {
          expect(`${axis}/${patch}/${reason}`).not.toContain(word);
        }
      }
    }
  });

  it('ردِ شاخص ۳ هر دو عدد را می‌گوید: مقدارِ واقعی و کف', () => {
    const ev = screenAuditEvidence('3_gross_margin', row({ gross_margin: 8.5, i3_pass: false }), { margin_min: 20 });
    expect(String(ev.reason)).toContain('۸.۵');
    expect(String(ev.reason)).toContain('۲۰');
  });

  it('شاخص ۵ فقط رژیم را گزارش می‌کند، نه پیامدِ آن', () => {
    const ev = screenAuditEvidence('5_industry', row({ pricing_mode: 'mandatory', i5_pass: false }), null);
    expect(String(ev.reason)).toBe('رژیم قیمت‌گذاری: دستوری.');
  });

  // متنِ موتور (که بر متنِ جانشین اولویت دارد) رقمِ لاتین دارد — کارت باید
  // یکدست فارسی بخواند، وگرنه «افت سود در 1404» کنار «۲۲٫۰٪» کج می‌ایستد.
  it('دلیلِ ردِ ساختِ موتور با رقمِ فارسی به کاربر می‌رسد', () => {
    const card = {
      symbol: 'خودرو',
      sector: 'خودرو و ساخت قطعات',
      pricing_mode: 'mandatory',
      passes: {},
      indicators: {
        '1': {
          monetary: { monetary_pct: 52.2, threshold: 60, reason: 'رشد اسمی +52.2٪ کمتر از مبنای افزایش نرخ 60٪ است.' },
          volume: { real_pct: -5, reason: 'فروش مقداری کم شده؛ رشد ریالی فقط از افزایش نرخ آمده است.' },
        },
        '2': { reason: 'افت سود در 1404 (افت 22.0٪)' },
        '3': { margin_pct: 2.7, threshold: 20 },
        '4': { reason: 'قبولی با نسبت فروش/ارزش‌بازار' },
        '5': { outlook: 'قیمت‌گذاری دستوری — نرخ توسط دولت تعیین میشود.' },
      },
    } as unknown as Parameters<typeof cardAuditEvidence>[0];

    const ev = cardAuditEvidence(card);
    expect(String(ev['1a_monetary_growth']?.reason)).toContain('۵۲.۲');
    expect(String(ev['2_eps_trend']?.reason)).toContain('۱۴۰۴');
    for (const axis of ['1a_monetary_growth', '1b_volume_growth', '2_eps_trend',
                        '3_gross_margin', '4_sales_to_mcap', '5_industry'] as const) {
      const reason = String(ev[axis]?.reason ?? '');
      expect(reason).not.toMatch(/[0-9]/);
    }
  });

  // علت/راه‌حلِ پیش‌فرض هر محور must-read کاربر است، نه یادداشتِ توسعه:
  // واژگانی مثل «بک‌اند» یا نامِ ستونِ دیتابیس معنایی برایش ندارد.
  it('متن‌های پیش‌فرض شکاف، واژۀ فنیِ درون‌سازمانی ندارند', () => {
    const JARGON = ['بک‌اند', 'بک اند', 'backend', 'POST', 'GET', 'monthly_sales', 'annualize', 'fts_engine'];
    const axes = ['1a_monetary_growth', '1b_volume_growth', '2_eps_trend',
                  '3_gross_margin', '4_sales_to_mcap', '5_industry'] as const;
    for (const axis of axes) {
      const g = standardizeGap({ axis, layer: axis } as never);
      const text = `${g.label} ${g.why} ${g.fix}`;
      for (const w of JARGON) expect(`${axis}/${text}`).not.toContain(w);
    }
  });
});
