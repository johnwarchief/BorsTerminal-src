// __tests__/fts-screen-contract.spec.ts — قراردادِ ردیفِ غربالگری FTS
// پنج شاخصِ بنیادی، در یک دور، فیلدهای تازه‌ای به ردیفِ `/api/screener` دادند
// (Task 4 N/A، Task 5 شاهدِ EPS، Task 6 طبقهٔ حاشیه، Task 7 مسیرِ پذیرشِ ۴،
// Task 10B2a1 شکافِ دادهٔ ۱ب). آزمون‌های UI اگر ردیف را با `as unknown as
// FtsScreenRow` بسازند، ریختنِ اسکیما را نمی‌بینند؛ اینجا همان پاسخِ واقعیِ
// بک‌اند از `FtsScreenRowSchema` می‌گذرد و باید **همهٔ** فیلدهای تازه را
// دست‌نخورده برگرداند — نه حذفِ خاموش، نه تبدیلِ تهی به غایب.
import { describe, expect, it } from 'vitest';
import { FtsScreenRowSchema, type FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

/** ردیفِ واقع‌نما: همان کلیدهایی که `/api/screener` برایِ یک شرکتِ تولیدی
 *  می‌فرستد (شاملِ فیلدهای تازهٔ همین دور). */
function fullRow(): Record<string, unknown> {
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
    eps_years_available: 3,
    eps_years_required: 3,
    gross_margin: 32.5,
    margin_tier: 'good',
    sales_to_mcap: 1.2,
    profit_potential_pct: 42,
    annual_sales_bt: 90,
    mcap: 5e13,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: null,
    i1b_applicable: true,
    i1b_data_gap: true,
    i1_basis: 'fs_interim',
    i1_na: false,
    i1_reason: 'رشد تولیدی/تناژ در گزارش ماهانه ثبت نشده — ۱ب سنجیده نشد.',
    i1b_basis: 'unavailable',
    i2_pass: true,
    i2_na: false,
    eps_consolidated: false,
    eps_evidence_label: 'سالانهٔ حسابرسی‌شده',
    i3_pass: true,
    i3_na: false,
    i3_reason: '',
    i4_pass: true,
    i4_acceptance_path: 'profit_potential',
    annualize_label: 'سالانه‌شده از دورهٔ 6 ماهه',
    i4_na: false,
    i4_reason: 'مسیر دوم پذیرش: پتانسیل سود ناخالص ÷ ارزش بازار ≥ ۴۰٪',
    i5_pass: true,
    verdict: 'STRONG',
    excluded: false,
    applicable: true,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    weekly_veto: false,
    assembly_veto: false,
    assembly_date: null,
    assembly_days: null,
    tech_trend_d: 'up',
    tech_trend_w: 'up',
    tech_trend_m: 'neutral',
    tech_alignment: 'partial',
    tech_jet: false,
    tech_hourglass_active: false,
    tape_status: 'pass',
    technical_status: 'pass',
    fundamental_status: 'pass',
    technical_reason: '',
    gate_state: 'applied',
    funnel_candidate: true,
  };
}

/** فیلدهای تازهٔ همین دور که قراردادِ UI رویِ آن‌ها ایستاده است */
const NEW_FIELDS = [
  'i1b_data_gap',
  'i1_na',
  'i1_reason',
  'i3_reason',
  'i4_reason',
  'i4_acceptance_path',
  'annualize_label',
  'margin_tier',
  'eps_evidence_label',
] as const;

describe('قراردادِ ردیفِ غربالگری FTS — فیلدهای تازه نباید در parse گم شوند', () => {
  it('ردیفِ کاملِ واقع‌نما با همهٔ فیلدهای تازه parse می‌شود', () => {
    const parsed = FtsScreenRowSchema.safeParse(fullRow());
    expect(parsed.success, JSON.stringify(parsed.error?.issues)).toBe(true);
  });

  it('هر فیلدِ تازه با کلید و مقدارِ خودش در خروجیِ parse هست (حذفِ خاموش ممنوع)', () => {
    const payload = fullRow();
    const parsed = FtsScreenRowSchema.parse(payload);
    for (const key of NEW_FIELDS) {
      expect(Object.prototype.hasOwnProperty.call(parsed, key), `${key} از خروجی افتاد`).toBe(true);
      expect(parsed[key as keyof FtsScreenRow], `${key} عوض شد`).toEqual(payload[key]);
    }
    expect(parsed.i1b_data_gap).toBe(true);
    expect(parsed.i1_na).toBe(false);
    expect(parsed.i3_reason).toBe('');
    expect(parsed.i4_reason).toContain('مسیر دوم');
    expect(parsed.annualize_label).toBe('سالانه‌شده از دورهٔ 6 ماهه');
    expect(parsed.margin_tier).toBe('good');
    expect(parsed.eps_evidence_label).toBe('سالانهٔ حسابرسی‌شده');
  });

  it('هیچ کلیدی از پاسخِ بک‌اند بی‌صدا حذف نمی‌شود (کلیدها یکی‌به‌یکی)', () => {
    const payload = fullRow();
    const parsed = FtsScreenRowSchema.parse(payload);
    expect(Object.keys(parsed).sort()).toEqual(Object.keys(payload).sort());
  });

  it('`i4_acceptance_path` هر دو مسیر و null را می‌پذیرد و مقدارِ ناشناس را رد می‌کند', () => {
    const base = fullRow();
    for (const path of ['sales_to_mcap', 'profit_potential'] as const) {
      const parsed = FtsScreenRowSchema.parse({ ...base, i4_acceptance_path: path });
      expect(parsed.i4_acceptance_path).toBe(path);
    }
    const nullCase = FtsScreenRowSchema.parse({ ...base, i4_acceptance_path: null });
    expect(nullCase.i4_acceptance_path).toBeNull();
    // غایب هم مجاز است (ردیفِ قدیمی) — ولی مقدارِ بیرون از قرارداد نباید رد شود
    const { i4_acceptance_path: _omitted, ...withoutPath } = base;
    expect(FtsScreenRowSchema.parse(withoutPath).i4_acceptance_path).toBeUndefined();
    expect(FtsScreenRowSchema.safeParse({ ...base, i4_acceptance_path: 'both' }).success).toBe(false);
  });

  it('ردیفِ حداقلیِ قدیمی (بی‌هیچ فیلدِ تازه) parse می‌شود و فرمِ تهی نمی‌سازد', () => {
    const legacy = { symbol: 'شپنا', score: 3 };
    const parsed = FtsScreenRowSchema.parse(legacy);
    expect(parsed.symbol).toBe('شپنا');
    expect(parsed.score).toBe(3);
    for (const key of NEW_FIELDS) {
      expect(parsed[key as keyof FtsScreenRow], `${key} از ردیفِ قدیمی ساخته شد`).toBeUndefined();
    }
  });

  it('ردیفِ N/Aِ ماهیتی: دلیلِ i3/i4 و i1_na هم‌زمان می‌رسند (بدونِ تبدیل به false)', () => {
    const parsed = FtsScreenRowSchema.parse({
      ...fullRow(),
      i1_na: true,
      i1_pass: null,
      i3_pass: null,
      i3_na: true,
      i3_reason: 'ماهیت مالی (بانک/بیمه/هلدینگ) — حاشیهٔ ناخالص معنا ندارد.',
      i4_pass: null,
      i4_na: true,
      i4_reason: 'معاف از شرطِ فروش ÷ ارزش بازار (ind4_na).',
      margin_tier: null,
      eps_evidence_label: 'دادهٔ ناکافی',
    });
    expect(parsed.i1_na).toBe(true);
    expect(parsed.i3_na).toBe(true);
    expect(parsed.i3_reason).toContain('ماهیت مالی');
    expect(parsed.i4_na).toBe(true);
    expect(parsed.i4_reason).toContain('معاف');
    expect(parsed.margin_tier).toBeNull();
    expect(parsed.eps_evidence_label).toBe('دادهٔ ناکافی');
  });
});
