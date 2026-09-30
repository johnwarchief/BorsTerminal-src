// funnelCellValue باید آینهٔ دقیقِ همان سلولی باشد که Cell می‌کشد.
// اگر این دو از هم جدا بیفتند، فایلِ اکسل چیزی می‌گوید که رویِ صفحه نیست —
// بدترین نوعِ خطا، چون بی‌صدا است.
import { describe, expect, it } from 'vitest';
import { funnelCellValue } from '@features/master/ui/FtsFunnelStages';
import type { FunnelEntry } from '@features/master/lib/ftsFunnel';

const E = {
  symbol: 'فولاد',
  row: { p_last: 4520, percent_change: 3.14, vol_ratio: 2.5 },
  patterns: ['کف‌روبی', 'جت'],
  trendW: 'صعودی',
  trendD: 'خنثی',
  setups: 'پولبک',
  screen: { rev_growth: 55, eps_last: 900, gross_margin: 28, sales_to_mcap: 0.75, pricing_mode: 'free' },
  inds: ['ok', 'ok', 'ok', 'ok', 'ok'],
  score: 4,
} as unknown as FunnelEntry;

describe('خروجیِ اکسلِ قیف', () => {
  it('عددها خام‌اند، نه رقمِ فارسی و نه با ٪ و ×', () => {
    // رقمِ فارسی در اکسل متن است: جمع و مرتب‌سازی از کار می‌افتد.
    expect(funnelCellValue('last', E, null)).toBe(4520);
    expect(funnelCellValue('chg', E, null)).toBe(3.14);
    expect(funnelCellValue('vol', E, null)).toBe(2.5);
    expect(funnelCellValue('score', E, null)).toBe(4);
  });

  it('پنج شاخصِ بنیادی به ترتیبِ ستون‌ها می‌آیند', () => {
    expect(funnelCellValue('ind1', E, null)).toBe(55);
    expect(funnelCellValue('ind2', E, null)).toBe(900);
    expect(funnelCellValue('ind3', E, null)).toBe(28);
    expect(funnelCellValue('ind4', E, null)).toBe(0.75);
    expect(typeof funnelCellValue('ind5', E, null)).toBe('string');
  });

  it('متن‌ها همان چیزی‌اند که رویِ صفحه است', () => {
    expect(funnelCellValue('symbol', E, null)).toBe('فولاد');
    expect(funnelCellValue('pattern', E, null)).toBe('کف‌روبی + جت');
    expect(funnelCellValue('weekly', E, null)).toBe('صعودی');
    expect(funnelCellValue('setup', E, null)).toBe('پولبک');
  });

  it('ردیفِ تهی می‌شکند، نه صفرِ دروغین', () => {
    const empty = { symbol: 'x', row: null, patterns: [], inds: [] } as unknown as FunnelEntry;
    expect(funnelCellValue('last', empty, null)).toBeNull();
    expect(funnelCellValue('chg', empty, null)).toBeNull();
    expect(funnelCellValue('ind1', empty, null)).toBeNull();
    expect(funnelCellValue('pattern', empty, null)).toBeNull();
  });

  it('ستونِ «سبد» دکمه است، پس در فایل تهی می‌ماند', () => {
    expect(funnelCellValue('basket', E, null)).toBeNull();
  });
});
