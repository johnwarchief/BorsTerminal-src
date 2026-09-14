// تست تبدیل جلالی
import { describe, expect, it } from 'vitest';
import { jalaaliToGregorian, jalToEpochMs, statementAgeDays } from '@shared/lib/jalaali';

describe('تبدیل جلالی', () => {
  it('نوروز 1404 برابر 21 مارس 2025 است', () => {
    expect(jalaaliToGregorian(1404, 1, 1)).toEqual([2025, 3, 21]);
    expect(jalToEpochMs('1404/01/01')).toBe(Date.UTC(2025, 2, 21));
  });

  it('اسفند کبیسه 1403', () => {
    expect(jalaaliToGregorian(1403, 12, 30)).toEqual([2025, 3, 20]);
    expect(jalaaliToGregorian(1402, 12, 29)).toEqual([2024, 3, 19]);
  });

  it('ورودی نامعتبر null می دهد', () => {
    expect(jalaaliToGregorian(1404, 13, 1)).toBeNull();
    expect(jalToEpochMs('not-a-date')).toBeNull();
    expect(jalToEpochMs(null)).toBeNull();
    expect(statementAgeDays(null)).toBeNull();
  });

  it('سن صورت مالی به روز', () => {
    const now = Date.UTC(2025, 5, 1);
    const age = statementAgeDays('1404/01/01', now);
    expect(age).toBe(Math.floor((now - Date.UTC(2025, 2, 21)) / 86_400_000));
  });
});
