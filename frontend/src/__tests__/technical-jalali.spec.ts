// تست تاریخ جلالی چارت تکنیکال (پورت jalaali-js)
import { describe, expect, it } from 'vitest';
import { epochToJalali, gregorianToJalaali } from '@features/technical/lib/jalaliDate';

describe('تبدیل میلادی به جلالی', () => {
  it('نوروز 1404 برابر 21 مارس 2025 است', () => {
    const j = gregorianToJalaali(2025, 3, 21);
    expect([j.jy, j.jm, j.jd]).toEqual([1404, 1, 1]);
  });

  it('اول ژانویه در دی ماه است', () => {
    const j = gregorianToJalaali(2026, 1, 1);
    expect(j.jy).toBe(1404);
    expect(j.jm).toBe(10);
    expect(j.jd).toBe(11);
  });

  it('اسفند سال کبیسه 1403 سی روزه است', () => {
    // 20 مارس 2025 = 30 اسفند 1403
    const j = gregorianToJalaali(2025, 3, 20);
    expect([j.jm, j.jd]).toEqual([12, 30]);
    // روز بعد نوروز است
    const j2 = gregorianToJalaali(2025, 3, 21);
    expect([j2.jy, j2.jm, j2.jd]).toEqual([1404, 1, 1]);
  });

  it('سال نوده و نه و روزهای مرزی', () => {
    // 1 فروردین 1399 = 20 مارس 2020
    const j = gregorianToJalaali(2020, 3, 20);
    expect([j.jy, j.jm, j.jd]).toEqual([1399, 1, 1]);
    // 19 مارس 2020 = 29 اسفند 1398
    const j2 = gregorianToJalaali(2020, 3, 19);
    expect([j2.jm, j2.jd]).toEqual([12, 29]);
  });

  it('epoch به رشته YYYY/MM/DD', () => {
    // ظهر UTC 21 مارس 2025
    expect(epochToJalali(Date.UTC(2025, 2, 21, 12))).toBe('1404/01/01');
    // نامعتبر
    expect(epochToJalali(Number.NaN)).toBe('');
  });
});
