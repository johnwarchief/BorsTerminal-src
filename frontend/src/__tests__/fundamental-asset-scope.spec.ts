import { describe, expect, it } from 'vitest';
import { financialClassLabel, isBankLike } from '@features/fundamental/lib/assetScope';

// بانک نباید با هلدینگ/سرمایه‌گذاری یکی خوانده شود؛ این تفکیک فقط نمایشی است
// (برچسبِ سرصفحه و متنِ پنلِ N/A) و به حکم/امتیاز دست نمی‌زند.
describe('طبقهٔ نمایشیِ مالی در کارت بنیادی', () => {
  it('بانک/مؤسسهٔ اعتباری: برچسبِ بانک، نه هلدینگ', () => {
    const bank = { name: 'بانک ملت', sector_name: 'بانكها و موسسات اعتباري' };
    expect(isBankLike(bank)).toBe(true);
    expect(financialClassLabel(bank)).toBe('بانک / مؤسسهٔ اعتباری');
  });

  it('هلدینگ/سرمایه‌گذاری: برچسبِ هلدینگ', () => {
    const hold = { name: 'شرکت سرمایه گذاری الف', sector_name: 'سرمايه گذاريها' };
    expect(isBankLike(hold)).toBe(false);
    expect(financialClassLabel(hold)).toBe('هلدینگ / سرمایه‌گذاری');
  });

  it('شرکت تولیدی: هیچ برچسبِ مالی ندارد', () => {
    const prod = { name: 'فولاد مبارکه', sector_name: 'فلزات اساسي' };
    expect(isBankLike(prod)).toBe(false);
    expect(financialClassLabel(prod)).toBeNull();
  });
});
