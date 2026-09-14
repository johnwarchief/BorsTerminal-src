// تست ریاضیات بنیادی: تفکیک فصلی و میانه صنعت و رشد سالانه
import { describe, expect, it } from 'vitest';
import { deCumulateQuarters, peBonus, profitYoY, sectorMedianPE, yoyBonus } from '@features/fundamental/lib/fundMath';
import type { QuarterRow } from '@features/fundamental/api/useQuarters';

function q(period_end: string, period_months: number, revenue: number | null, net: number | null): QuarterRow {
  return { period_end, period_months, revenue, operating_profit: null, net_profit: net, basic_eps: null, publish_date: null };
}

describe('تفکیک فصلی', () => {
  const rows = [
    q('1404/03/31', 3, 100, 10),
    q('1404/06/31', 6, 250, 30),
    q('1404/09/30', 9, 400, 60),
    q('1404/12/29', 12, 600, 100),
  ];

  it('گزارش تجمعی به فصل خالص تبدیل می شود', () => {
    const out = deCumulateQuarters(rows);
    expect(out.map((x) => x.netProfit)).toEqual([10, 20, 30, 40]);
    expect(out.map((x) => x.revenue)).toEqual([100, 150, 150, 200]);
    expect(out[0].margin).toBeCloseTo(10, 4);
    expect(out.map((x) => x.key)).toEqual(['1404-Q1', '1404-Q2', '1404-Q3', '1404-Q4']);
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
      q('1403/03/31', 3, 100, 10),
      q('1403/06/31', 6, 200, 20),
      q('1403/09/30', 9, 300, 30),
      q('1403/12/29', 12, 400, 40),
      q('1404/03/31', 3, 120, 13),
      q('1404/06/31', 6, 260, 26),
    ]);
    expect(profitYoY(qs)).toBeCloseTo(30, 4);
  });

  it('مبنای منفی یا کمبود فصل یعنی null', () => {
    const qs = deCumulateQuarters([
      q('1403/03/31', 3, 100, 10),
      q('1403/06/31', 6, 150, 5),
      q('1403/09/30', 9, 300, 30),
      q('1403/12/29', 12, 400, 40),
      q('1404/03/31', 3, 120, 12),
      q('1404/06/31', 6, 260, 20),
    ]);
    // فصل مشابه پارسال (سه ماهه دوم 1403) زیان ده بود پس رشد معنادار نیست
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
