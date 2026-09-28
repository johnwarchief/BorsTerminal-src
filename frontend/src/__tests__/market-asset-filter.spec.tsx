// تست یکپارچه فیلتر نوع دارایی: خروج خودکار مشتقه‌ها از لیست‌های الگو در حالت پیش‌فرض ۵تایی
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { SuspiciousPanel } from '@features/market/components/SuspiciousPanel';
import { applyFilters } from '@features/market/routes/MarketPage';
import { countHiddenMatches, hiddenDoorOf } from '@features/market/components/MarketFilters';
import { ASSET_TYPES } from '@features/market/lib/assetType';
import { isNumericSuffixSymbol } from '@features/market/lib/tapeFts';
import { DEFAULT_ASSET_TYPES, useTapeStore } from '@features/market/stores/tapeStore';

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'فولاد',
    name: 'فولاد مبارکه',
    sector_name: 'فرآوری مواد معدنی',
    board: 1,
    percent_change: 2.5,
    tvol: 5_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 5,
    vol_ratio_file: 5,   // قیدِ پنلِ حجم مشکوک مبناءِ فایل است
    p_last: 1000,
    p_closing: 1030,
    price_yesterday: 1010,
    z_tot_tran: 120,
    is_live: true,
    f_clock: true,
    f_susp: true,
    ...patch,
  } as MarketRow;
}

const stock = row();
const option = row({ symbol: 'ضفولاد', name: 'اختیار فولاد', sector_name: 'اختیار' });
const bond = row({ symbol: 'اخزا001', name: 'اوراق اخزا', sector_name: 'اوراق تامين' });
const rows = [stock, option, bond];

describe('خروج مشتقه‌ها از لیست‌های تابلو با پیش‌فرض ۵تایی', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('applyFilters با پیش‌فرض استور فقط سهام/پایه/حق تقدم/انرژی/صندوق را نگه می‌دارد', () => {
    const state = useTapeStore.getState();
    expect(state.assetTypes).toEqual(DEFAULT_ASSET_TYPES);
    const kept = applyFilters(rows, '', state.assetTypes, [], '', false, 'all', false, 3, false);
    expect(kept.map((r) => r.symbol)).toEqual(['فولاد']);
  });

  it('آرایهٔ خالی یعنی «هیچ» (رفع semantics قدیمی «همه») و مجموعهٔ کامل یعنی همهٔ ۱۱ نماد', () => {
    expect(applyFilters(rows, '', [], [], '', false, 'all', false, 3, false)).toEqual([]);
    const all = applyFilters(rows, '', [...ASSET_TYPES], [], '', false, 'all', false, 3, false);
    expect(all.map((r) => r.symbol)).toEqual(['فولاد', 'ضفولاد', 'اخزا001']);
  });

  it('پنل الگوی ساعت/حجم مشکوک روی ردیف‌های فیلترشده، اختیار معامله را نشان نمی‌دهد', () => {
    const state = useTapeStore.getState();
    const filtered = applyFilters(rows, '', state.assetTypes, [], '', false, 'all', false, 3, false);
    render(<SuspiciousPanel rows={filtered} onSelect={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.some((b) => b.textContent?.includes('ضفولاد'))).toBe(false);
    expect(buttons.some((b) => b.textContent?.includes('اخزا'))).toBe(false);
    expect(buttons.some((b) => b.textContent?.includes('فولاد مبارکه'))).toBe(true);
  });

  it('بدون فیلتر نوع، همان پنل نماد اختیار را نشان می‌دهد (تطبیق منفی)', () => {
    render(<SuspiciousPanel rows={rows} onSelect={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.some((b) => b.textContent?.includes('ضفولاد'))).toBe(true);
  });
});

// #197: «فقط زنده» پیش‌فرضِ جدول شد و بالاخره دکمه گرفت
describe('بندِ «فقط زنده» در applyFilters', () => {
  const live = row({ symbol: 'خگلپا', name: 'خگلی پارس' });
  const fossil = row({ symbol: 'همتا', name: 'همتا', is_live: false });
  const set = [live, fossil];
  const types = [...DEFAULT_ASSET_TYPES];

  it('پیش‌فرضِ استور روشن است و ردیفِ بیرونِ تابلو را از جدول بیرون می‌گذارد', () => {
    expect(useTapeStore.getState().liveOnly).toBe(true);
    const kept = applyFilters(set, '', types, [], '', true, 'all', false, 3, false);
    expect(kept.map((r) => r.symbol)).toEqual(['خگلپا']);
  });

  it('جست‌وجویِ صریح از این بند معاف است — نمادِ خاموش هم پیدا می‌شود', () => {
    const kept = applyFilters(set, 'همتا', types, [], '', true, 'all', false, 3, false);
    expect(kept.map((r) => r.symbol)).toEqual(['همتا']);
  });

  it('خاموش‌کردنِ سوئیچ هر دو ردیف را برمی‌گرداند', () => {
    const kept = applyFilters(set, '', types, [], '', false, 'all', false, 3, false);
    expect(kept.map((r) => r.symbol)).toEqual(['خگلپا', 'همتا']);
  });
});

// #207: دلیلِ «چرا چیپ کمتر از فیلترنویسِ TSETMC است» باید از خودِ ردیف‌های
// پنهان بخواند، و هر ردیف فقط یک در بگیرد؛ فهرستِ ثابت رویِ فیدِ زنده دروغ می‌گفت.
describe('hiddenDoorOf/countHiddenMatches: هر ردیفِ پنهان یک در', () => {
  const types = [...DEFAULT_ASSET_TYPES];
  const ctx = { assetTypes: types, liveOnly: true, query: '', sector: '', dropSuffix: true };

  it('پسوندِ عددی اول می‌آید: ردیفی که قاعدۀ حذفِ مشتقه می‌برد به بازار نسبت داده نمی‌شود', () => {
    expect(hiddenDoorOf(row({ symbol: 'فولاد۳' }), ctx)).toBe('پسوندِ عددی');
    // اخزایِ پسونددار هم اختیار/اوراق ندارد: همان در، نه دو در
    expect(hiddenDoorOf(row({ symbol: 'اخزا۱' }), ctx)).toBe('پسوندِ عددی');
  });

  it('بی‌پسوند، درِ منوی بازارها نام برده می‌شود', () => {
    expect(hiddenDoorOf(option, ctx)).toBe('بازار/ابزارِ خاموش');
  });

  // تنظیمِ جدیدِ کاربر: اگر خودِ درِ «پسوندِ عددی» را باز گذاشته باشد، تولتیپ
  // نباید همان ردیف‌ها را به همان در نسبت بدهد.
  it('حذفِ پسوند خاموش ⇒ ردیف به درِ بعدی می‌رسد یا هیچ در نمی‌گیرد', () => {
    const off = { ...ctx, dropSuffix: false };
    // با ASCII هم همان قاعده است: /[0-9۰-۹]$/
    expect(isNumericSuffixSymbol('FOLAD1')).toBe(true);
    // بازارش در منوی پیش‌فرض خاموش است ⇒ درِ بعدی
    expect(hiddenDoorOf(row({ symbol: 'AKHZA1', name: 'اوراق اخزا', sector_name: 'اوراق تامين' }), off)).toBe(
      'بازار/ابزارِ خاموش',
    );
    // سهامِ پسونددار در بازارِ روشن: دیگر پنهان نیست، پس در ندارد
    expect(hiddenDoorOf(row({ symbol: 'FOLAD1' }), off)).toBe(null);
    // همان ردیف با درِ بسته: می‌شود پسوندِ عددی
    expect(hiddenDoorOf(row({ symbol: 'FOLAD1' }), ctx)).toBe('پسوندِ عددی');
  });

  it('نمادِ خاموش با جستجویِ فعال از جدول بیرون نمی‌رود، پس دلیلش هم نوشته نمی‌شود', () => {
    const dead = row({ symbol: 'همتا', is_live: false });
    expect(hiddenDoorOf(dead, ctx)).toBe('نمادِ خاموش');
    expect(hiddenDoorOf(dead, { ...ctx, liveOnly: false })).toBe(null);
    // نمادِ خاموشی که نامش با جستجو می‌خواند در جدول می‌ماند (همان بندِ #197)
    expect(hiddenDoorOf(dead, { ...ctx, query: 'فولاد' })).toBe(null);
  });

  it('جستجو و صنعتِ انتخابی هر کدام درِ خودشان را دارند و ردیفِ سالم هیچ در نمی‌گیرد', () => {
    expect(hiddenDoorOf(row(), ctx)).toBe(null);
    expect(hiddenDoorOf(row(), { ...ctx, query: 'پتروشیمی' })).toBe('جستجو');
    expect(hiddenDoorOf(row(), { ...ctx, sector: 'سیمان' })).toBe('صنعت');
  });

  it('شمارِ هر چیپ با جمعِ درهایش یکی است، و درِ بی‌سهم ثبت نمی‌شود', () => {
    // قالبِ ردیف f_clock و f_susp را روشن دارد؛ فقط f_roobi دستی است
    const hidden = [
      row({ symbol: 'فولاد۳', f_roobi: true }),
      row({ symbol: 'فولاد۴', f_roobi: true }),
      option,
    ];
    const got = countHiddenMatches(hidden, ctx);
    expect(got.f_roobi.count).toBe(2);
    expect(got.f_roobi.doors).toEqual({ 'پسوندِ عددی': 2 });
    expect(got.f_clock.count).toBe(3);
    expect(got.f_clock.doors).toEqual({ 'پسوندِ عددی': 2, 'بازار/ابزارِ خاموش': 1 });
    expect(got.f_jet.doors).toEqual({});
    // جمعِ درها هیچ‌وقت از شمارِ چیپ جلو نمی‌زند
    for (const f of Object.keys(got) as (keyof typeof got)[]) {
      const sum = Object.values(got[f].doors).reduce((a, b) => a + (b ?? 0), 0);
      expect(sum).toBeLessThanOrEqual(got[f].count);
    }
  });
});
