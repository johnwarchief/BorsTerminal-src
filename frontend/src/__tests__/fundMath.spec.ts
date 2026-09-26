// تست ریاضیات بنیادی: تفکیک فصلی و میانه صنعت و رشد
// #102 (رأیِ جزوه): روند فصلیِ درآمد باید با سود **ناخالص** سنجیده شود نه سود
// خالص؛ نبودِ سود ناخالص «صفر» نیست و جایگزینِ سود خالص هم ندارد.
import { describe, expect, it } from 'vitest';
import { deCumulateQuarters, peBonus, profitYoY, sectorMedianPE, yoyBonus } from '@features/fundamental/lib/fundMath';
import type { QuarterRow } from '@features/fundamental/api/useQuarters';

function q(
  period_end: string,
  period_months: number,
  revenue: number | null,
  net: number | null,
  gross: number | null = null,
): QuarterRow {
  return {
    period_end,
    period_months,
    revenue,
    gross_profit: gross,
    operating_profit: null,
    net_profit: net,
    basic_eps: null,
    publish_date: null,
  };
}

describe('تفکیک فصلی', () => {
  const rows = [
    q('1404/03/31', 3, 100, 10, 40),
    q('1404/06/31', 6, 250, 30, 100),
    q('1404/09/30', 9, 400, 60, 160),
    q('1404/12/29', 12, 600, 100, 240),
  ];

  it('گزارش تجمعی به فصل خالص تبدیل می شود', () => {
    const out = deCumulateQuarters(rows);
    expect(out.map((x) => x.netProfit)).toEqual([10, 20, 30, 40]);
    expect(out.map((x) => x.revenue)).toEqual([100, 150, 150, 200]);
    // #102: حاشیه = سود ناخالص ÷ درآمد (۴۰÷۱۰۰ = ۴۰٪) — نه سود خالص (۱۰٪)
    expect(out.map((x) => x.grossProfit)).toEqual([40, 60, 60, 80]);
    expect(out[0].margin).toBeCloseTo(40, 4);
    expect(out.map((x) => x.key)).toEqual(['1404-Q1', '1404-Q2', '1404-Q3', '1404-Q4']);
  });

  it('#102 — حاشیهٔ فصلی هرگز از سود خالص ساخته نمی‌شود', () => {
    // درآمد ۱۰۰ و سود خالص ۱۰ هست، ولی سود ناخالص ثبت نشده ⇒ N/A نه ۱۰٪
    const out = deCumulateQuarters([q('1404/03/31', 3, 100, 10, null)]);
    expect(out[0].netProfit).toBe(10);
    expect(out[0].grossProfit).toBeNull();
    expect(out[0].margin).toBeNull();
  });

  it('#102 — NULL با صفرِ واقعی یکی نیست', () => {
    const noGross = deCumulateQuarters([q('1404/03/31', 3, 100, 10, null)]);
    expect(noGross[0].margin).toBeNull();
    const zeroGross = deCumulateQuarters([q('1404/03/31', 3, 100, 10, 0)]);
    expect(zeroGross[0].margin).toBe(0);
  });

  it('#102 — گزارشِ بی‌سودِ ناخالص، پایهٔ تفاضلِ فصل‌های بعد نمی‌شود', () => {
    const out = deCumulateQuarters([
      q('1404/03/31', 3, 100, 10, 40),
      // ۶ماهه سود ناخالص ندارد ⇒ فصل دوم مجهول است و فصل سوم هم پایهٔ درست ندارد
      q('1404/06/31', 6, 250, 30, null),
      q('1404/09/30', 9, 400, 60, 160),
    ]);
    expect(out.map((x) => x.grossProfit)).toEqual([40, null, null]);
    expect(out.map((x) => x.margin)).toEqual([40, null, null]);
  });

  it('فقط 8 فصل آخر نگه داشته می شود', () => {
    const doubled = [...rows.map((r) => ({ ...r, period_end: '1403' + r.period_end.slice(4) })), ...rows];
    expect(deCumulateQuarters(doubled, 8)).toHaveLength(8);
  });

  it('دوره جاافتاده با آخرین تجمعی معلوم تفاضل می گیرد', () => {
    const out = deCumulateQuarters([rows[0], rows[2], rows[3]]);
    expect(out.map((x) => x.netProfit)).toEqual([10, 50, 40]);
  });
});

describe('میانه صنعت و رشد', () => {
  it('میانه P/E مثبت ها', () => {
    const rows = [
      { sector_name: 'الف', pe: 5 },
      { sector_name: 'الف', pe: 7 },
      { sector_name: 'الف', pe: -3 },
      { sector_name: 'الف', pe: null },
      { sector_name: 'ب', pe: 100 },
    ];
    expect(sectorMedianPE(rows, 'الف')).toBe(6);
    expect(sectorMedianPE(rows, 'ج')).toBeNull();
  });

  it('رشد سالانه فصل مشابه', () => {
    const qs = deCumulateQuarters([
      q('1403/03/31', 3, 100, 10, 10),
      q('1403/06/31', 6, 200, 20, 30),
      q('1403/09/30', 9, 300, 30, 45),
      q('1403/12/29', 12, 400, 40, 60),
      q('1404/03/31', 3, 120, 13, 13),
      q('1404/06/31', 6, 260, 26, 39),
    ]);
    // تابستان ۱۴۰۳ = ۳۰-۱۰ = ۲۰ ← تابستان ۱۴۰۴ = ۳۹-۱۳ = ۲۶ ⇒ ۳۰٪ (مبنای ناخالص)
    expect(qs[1].grossProfit).toBe(20);
    expect(qs[5].grossProfit).toBe(26);
    expect(profitYoY(qs)).toBeCloseTo(30, 4);
  });

  it('#102 — داوریِ روند از سود ناخالص خوانده می‌شود، نه سود خالص', () => {
    // سود خالصِ بهار دو سال: ۱۰ ← ۱۰ (هیچ تغییری). سود ناخالص: ۲۰ ← ۳۳ (+۶۵٪).
    // اگر مبنای مقایسه سود خالص مانده باشد، جواب ۰٪ (یا null) می‌شد.
    const qs = deCumulateQuarters([
      q('1403/03/31', 3, 100, 10, 20),
      q('1403/06/31', 6, 200, 20, 40),
      q('1403/09/30', 9, 300, 30, 60),
      q('1403/12/29', 12, 400, 40, 80),
      q('1404/03/31', 3, 120, 10, 33),
      q('1404/06/31', 6, 260, 20, 66),
    ]);
    expect(qs[0].netProfit).toBe(10);
    expect(qs[4].netProfit).toBe(10);
    expect(profitYoY(qs)).toBeCloseTo(65, 4);
  });

  it('#102 — سود ناخالصِ NULL یعنی داوریِ روند null (با سود خالصِ موجود)', () => {
    const qs = deCumulateQuarters([
      q('1403/03/31', 3, 100, 10, null),
      q('1403/06/31', 6, 200, 20, null),
      q('1403/09/30', 9, 300, 30, null),
      q('1403/12/29', 12, 400, 40, null),
      q('1404/03/31', 3, 120, 13, null),
      q('1404/06/31', 6, 260, 26, null),
    ]);
    // سود خالص هر دو فصل هست و ۳۰٪ می‌داد؛ مبنای ناخالص ⇒ هیچ داوری‌ای صادر نمی‌شود
    expect(qs.every((x) => x.netProfit != null)).toBe(true);
    expect(profitYoY(qs)).toBeNull();
  });

  it('مبنای منفی یا کمبود فصل یعنی null', () => {
    const qs = deCumulateQuarters([
      q('1403/03/31', 3, 100, 10, 100),
      q('1403/06/31', 6, 150, 5, -20),
      q('1403/09/30', 9, 300, 30, 60),
      q('1403/12/29', 12, 400, 40, 80),
      q('1404/03/31', 3, 120, 12, 30),
      q('1404/06/31', 6, 260, 20, 66),
    ]);
    // تابستانِ پارسال (فصلِ مشابه) زیان‌ده بود ⇒ رشدِ ناخالص معنادار نیست
    expect(qs[1].grossProfit).toBe(-120);
    expect(profitYoY(qs)).toBeNull();
    expect(profitYoY(qs.slice(0, 4))).toBeNull();
  });

  it('بونوس ها در بازه می مانند', () => {
    expect(peBonus(3.5, 7)).toBe(15);
    expect(peBonus(7, 7)).toBe(0);
    expect(peBonus(null, 7)).toBe(0);
    expect(peBonus(-2, 7)).toBe(0);
    expect(yoyBonus(50)).toBe(15);
    expect(yoyBonus(-100)).toBe(-15);
    expect(yoyBonus(null)).toBe(0);
  });
});
