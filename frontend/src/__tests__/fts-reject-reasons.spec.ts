// #205 — «تصمیم استراتژیک» در حالتِ رد باید همان شاخصِ مردود را با عددِ موتور
// نام ببرد، نه «ضعف در سودسازی یا حاشیۀ پایین یا قیمت‌گذاری دستوری»ی حدسی.
// تابع خالصِ لایۀ نمایش است: هیچ پرچمی را خودش داوری نمی‌کند.
import { describe, expect, it } from 'vitest';
import { rejectReasons, rejectLineText } from '@features/fundamental/lib/rejectReasons';

const IND = {
  '1': {
    monetary: { monetary_pct: 12, threshold: 40 },
    volume: { real_pct: -6, threshold: 8, price_benchmark_pct: 45 },
  },
  '2': { years_available: 2, years_required: 3 },
  '3': { margin_pct: 12.4, threshold: 20 },
  '4': { sales_to_mcap: 0.31, sales_threshold: 0.33, potential_pct: 21, potential_threshold: 40 },
  '5': {},
} as never;

describe('علتِ دقیقِ رد (#205)', () => {
  it('هر محورِ مردود با عدد و آستانۀ خودش نام برده می‌شود', () => {
    const lines = rejectReasons(
      {
        '1a_monetary_growth': false,
        '1b_volume_growth': false,
        '2_eps_trend': false,
        '3_gross_margin': false,
        '4a_sales_to_mcap': false,
        '4b_profit_potential': false,
        '5_industry': true,
      },
      IND,
    );
    const text = lines.map(rejectLineText).join('\n');
    expect(text).toContain('+۱۲٫۰٪');
    expect(text).toContain('کف ۴۰٫۰٪');
    expect(text).toContain('−۶٫۰٪');
    expect(text).toContain('مبنای تورم ۴۵٫۰٪');
    expect(text).toContain('۲ از ۳ سال');
    expect(text).toContain('حاشیۀ ناخالص ۱۲٫۴٪ — کف ۲۰٫۰٪');
    expect(text).toContain('۰٫۳۱×');
    expect(text).toContain('پتانسیل سود ۲۱٫۰٪ — کف ۴۰٫۰٪');
    // شاخص ۵ قبول است ⇒ نباید در علتِ رد Comes
    expect(text).not.toContain('رژیم قیمت‌گذاری صنعت دستوری');
    // دو زیرِشرطِ یک شاخص در یک سطر می‌نشینند، نه دو سطرِ هم‌نام
    expect(lines).toHaveLength(4);
    expect(text.split('۱. رشد فروش کدال').length - 1).toBe(1);
    expect(text.split('۴. پتانسیل سود تا آخر سال').length - 1).toBe(1);
    expect(text).toContain('؛');
  });

  it('هیچ داوریِ تازه‌ای ساخته نمی‌شود: همه‌چیز true ⇒ فهرست خالی', () => {
    const all = {
      '1a_monetary_growth': true,
      '1b_volume_growth': true,
      '2_eps_trend': true,
      '3_gross_margin': true,
      '4a_sales_to_mcap': true,
      '4b_profit_potential': true,
      '5_industry': true,
    };
    expect(rejectReasons(all, IND)).toEqual([]);
  });

  it('«نظر نمی‌دهد» با «رد» قاطی نمی‌شود — پرچمِ null علتِ بی‌داده می‌گیرد', () => {
    const lines = rejectReasons({ '3_gross_margin': null }, IND);
    expect(lines).toHaveLength(1);
    expect(lines[0].missing).toBe(true);
    expect(rejectLineText(lines[0])).toContain('حاشیۀ ناخالص سنجیده نشد');
  });

  it('«۵ از ۳ سال» بی‌معناست — سالِ اضافی علتِ رد نمی‌شود (#217)', () => {
    const lines = rejectReasons({ '2_eps_trend': false }, { '2': { years_available: 5, years_required: 3 } } as never);
    const text = rejectLineText(lines[0]);
    expect(text).toContain('صعودیِ متوالی نیست');
    expect(text).not.toContain('از');
  });

  // #217 — علتِ رد باید همان چیزی باشد که موتور می‌داند، نه شمارشِ سال‌ها.
  it('علتِ خودِ موتور مقدم است: «۳ از ۳ سال» جای «تلفیقی» را نمی‌گیرد', () => {
    const lines = rejectReasons(
      { '2_eps_trend': false },
      {
        '2': {
          years_available: 3,
          years_required: 3,
          reason: 'سابقهٔ سه‌ساله فقط از صورت‌های مالی تلفیقی است — جزوه تلفیقی را مبنای داوری نمی‌داند.',
        },
      } as never,
    );
    const text = rejectLineText(lines[0]);
    expect(text).toContain('تلفیقی');
    expect(text).not.toContain('از ۳ سال');
    // رقمِ لاتینِ درونِ متنِ بک‌اند به فارسیِ رابط می‌رسد
    expect(lines[1]).toBeUndefined();
  });

  it('بی‌عدد ⇒ «سنجیده نشد»، نه ادعای «زیرِ کف» (#217)', () => {
    const lines = rejectReasons(
      { '3_gross_margin': false, '4a_sales_to_mcap': false, '4b_profit_potential': false },
      {
        '3': { reason: 'در صورت سود و زیانِ سالِ مرجع سطر سود ناخالص نیامده است.' },
        '4': { reason: 'دادهٔ ارزش بازار یا فروش سالانه برای محاسبه نسبت در دسترس نیست.' },
      } as never,
    );
    const text = lines.map(rejectLineText).join('\n');
    expect(text).toContain('سود ناخالص نیامده');
    expect(text).toContain('ارزش بازار');
    expect(text).not.toContain('زیرِ کف');
    // یک علتِ مشترک برای دو زیرِشرطِ شاخص ۴ یک‌بار نوشته می‌شود
    expect((text.match(/ارزش بازار/g) ?? []).length).toBe(1);
  });

  it('عددِ نبود ⇒ حدس نمی‌زند؛ متنِ علت می‌ماند بدونِ رقمِ ساختگی', () => {
    const lines = rejectReasons({ '3_gross_margin': false }, { '3': {} } as never);
    expect(rejectLineText(lines[0])).toBe('۳. حاشیه سود ناخالص — حاشیۀ سود ناخالص زیرِ کف است');
  });
});
