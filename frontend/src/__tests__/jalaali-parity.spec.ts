// __tests__/jalaali-parity.spec.ts — دو تبدیلِ جلالی نباید از هم جدا افتند
// `shared/lib/jalaali` و `features/technical/lib/jalaliDate` هر دو الگوریتم
// jalaali-js را دارند؛ اگر روزی یکی عوض شود، برچسبِ تاریخِ Master و محورِ چارت
// دو روزِ متفاوت از یک نشست نشان می‌دهند. این تست همان برابری را می‌سنجد.
import { describe, expect, it } from 'vitest';
import { gregorianToJalaali as g2jShared, isoToJalali } from '@shared/lib/jalaali';
import { gregorianToJalaali as g2jChart } from '@features/technical/lib/jalaliDate';

const DAYS = [
  [2025, 3, 20], [2025, 3, 21], [2026, 1, 1], [2026, 10, 4],
  [2024, 2, 29], [2027, 12, 31], [2023, 6, 15], [2026, 3, 20], [2026, 3, 21],
];

describe('تبدیلِ جلالی — یک حقیقت', () => {
  it('shared و محورِ چارت برایِ هر نه روزِ نمونه یک روز را می‌دهند', () => {
    for (const [gy, gm, gd] of DAYS) {
      expect(g2jShared(gy, gm, gd)).toEqual(g2jChart(gy, gm, gd));
    }
  });

  it('نوروزِ ۱۴۰۴ همان ۲۰۲۵-۰۳-۲۱ است و روزِ قبلش ۱۴۰۳/۱۲/۳۰ (اسفندِ کبیسه ۳۰ روزه)', () => {
    expect(g2jShared(2025, 3, 21)).toEqual({ jy: 1404, jm: 1, jd: 1 });
    expect(g2jShared(2025, 3, 20)).toEqual({ jy: 1403, jm: 12, jd: 30 });
  });

  it('برچسبِ متنیِ Master از همان رشته می‌آید؛ رشتهٔ بی‌اعتبار null است نه ۰۰۰۰', () => {
    expect(isoToJalali('2026-10-04')).toBe('1405/07/12');
    expect(isoToJalali('2026-10-4')).toBe('1405/07/12');
    expect(isoToJalali('')).toBeNull();
    expect(isoToJalali('1405/07/12')).toBeNull();
    expect(isoToJalali('2026-13-01')).toBeNull();
    expect(isoToJalali(null)).toBeNull();
  });
});
