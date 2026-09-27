// تست استور تابلو: فیلترهای جدید جهت/زنده و بازنشانی
import { beforeEach, describe, expect, it } from 'vitest';
import { ASSET_TYPES } from '@features/market/lib/assetType';
import {
  ASSET_QUICK_PRESETS,
  DEFAULT_ASSET_TYPES,
  LIMIT_PCT,
  isDefaultAssetTypes,
  matchesDirection,
  sameAssetSets,
  useTapeStore,
} from '@features/market/stores/tapeStore';

describe('استور فیلترهای تابلو', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('فیلتر جهت مثبت فقط درصد مثبت را عبور می دهد', () => {
    useTapeStore.getState().setDirection('pos');
    const { direction } = useTapeStore.getState();
    expect(matchesDirection(2.1, direction)).toBe(true);
    expect(matchesDirection(-0.5, direction)).toBe(false);
    expect(matchesDirection(null, direction)).toBe(false);
  });

  it('فیلتر صف خرید آستانه 4.9 درصد را می شناسد', () => {
    expect(matchesDirection(LIMIT_PCT, 'limitUp')).toBe(true);
    expect(matchesDirection(4.5, 'limitUp')).toBe(false);
    expect(matchesDirection(-LIMIT_PCT, 'limitDown')).toBe(true);
  });

  it('حالت «همه» مقدار ناقص را هم عبور می دهد', () => {
    expect(matchesDirection(null, 'all')).toBe(true);
  });

  it('سوئیچ فقط زنده و بازنشانی کلی کار می کند', () => {
    const s = useTapeStore.getState();
    // #197: پیش‌فرض روشن است؛ سوئیچ باید خاموشش کند و بازنشانی روشنش
    s.setLiveOnly(false);
    s.setDirection('neg');
    s.setQuery('فول');
    s.setSector('فلزات');
    s.toggleQuickFilter('f_clock');
    const mid = useTapeStore.getState();
    expect(mid.liveOnly).toBe(false);
    expect(mid.direction).toBe('neg');
    expect(mid.query).toBe('فول');
    expect(mid.sector).toBe('فلزات');
    expect(mid.quickFilters).toContain('f_clock');
    mid.resetFilters();
    const after = useTapeStore.getState();
    // #197: پیش‌فرضِ جدول «فقط زنده» روشن است
    expect(after.liveOnly).toBe(true);
    expect(after.direction).toBe('all');
    expect(after.query).toBe('');
    expect(after.sector).toBe('');
    expect(after.quickFilters).toHaveLength(0);
    expect(after.assetTypes).toEqual(DEFAULT_ASSET_TYPES);
  });

  it('حالت پیش‌فرض نوع دارایی فقط پنج بازار استاندارد است (مشتقه/اوراق/تسهیلات خارج)', () => {
    expect(DEFAULT_ASSET_TYPES).toEqual(['stock', 'payeh', 'right', 'energy', 'fund']);
    expect(isDefaultAssetTypes(useTapeStore.getState().assetTypes)).toBe(true);
    for (const t of ['option', 'bond', 'teseh', 'tal', 'ati', 'kala'] as const) {
      expect(DEFAULT_ASSET_TYPES).not.toContain(t);
    }
  });

  it('آرایهٔ خالی دیگر «همه» نیست: ریست دقیقاً پنج نوع را برمی‌گرداند و toggle صریح کار می‌کند', () => {
    const s = useTapeStore.getState();
    s.toggleAssetType('stock');
    s.toggleAssetType('option');
    const mid = useTapeStore.getState();
    expect(mid.assetTypes).toEqual(['payeh', 'right', 'energy', 'fund', 'option']);
    expect(isDefaultAssetTypes(mid.assetTypes)).toBe(false);
    // غیرفعال کردن همه → آرایهٔ خالی = هیچ (نه «همه»)
    for (const t of mid.assetTypes) useTapeStore.getState().toggleAssetType(t);
    expect(useTapeStore.getState().assetTypes).toEqual([]);
    mid.resetFilters();
    expect(useTapeStore.getState().assetTypes).toEqual(DEFAULT_ASSET_TYPES);
  });

  it('setAllAssetTypes هر ۱۱ نوع را فعال و resetAssetTypes به پیش‌فرض برمی‌گردد', () => {
    useTapeStore.getState().setAllAssetTypes();
    expect(useTapeStore.getState().assetTypes).toEqual([...ASSET_TYPES]);
    useTapeStore.getState().resetAssetTypes();
    expect(useTapeStore.getState().assetTypes).toEqual(DEFAULT_ASSET_TYPES);
  });

  it('سوییچ‌های سریع تک‌کلیکه: پرست ست می‌شود و کلیک دوباره به پیش‌فرض برمی‌گردد', () => {
    expect(sameAssetSets(['payeh', 'stock'], ['stock', 'payeh'])).toBe(true);
    expect(sameAssetSets(['payeh'], ASSET_QUICK_PRESETS.bourse_stocks)).toBe(false);

    useTapeStore.getState().toggleAssetPreset('payeh_only');
    expect(useTapeStore.getState().assetTypes).toEqual(ASSET_QUICK_PRESETS.payeh_only);
    useTapeStore.getState().toggleAssetPreset('payeh_only');
    expect(isDefaultAssetTypes(useTapeStore.getState().assetTypes)).toBe(true);

    useTapeStore.getState().toggleAssetPreset('bourse_stocks');
    expect(useTapeStore.getState().assetTypes).toEqual(ASSET_QUICK_PRESETS.bourse_stocks);
    useTapeStore.getState().toggleAssetPreset('bourse_stocks');
    expect(isDefaultAssetTypes(useTapeStore.getState().assetTypes)).toBe(true);

    // از پرست دیگر، سوییچ سریع مستقیم عوض می‌شود (نه toggle روی مجموعه فعلی)
    useTapeStore.getState().toggleAssetPreset('bourse_stocks');
    useTapeStore.getState().toggleAssetPreset('payeh_only');
    expect(useTapeStore.getState().assetTypes).toEqual(['payeh']);
  });

  it('setAssetTypes مجموعه را کپی و صریح جایگزین می‌کند', () => {
    const src: ('stock' | 'fund')[] = ['stock', 'fund'];
    useTapeStore.getState().setAssetTypes(src);
    src.push('stock');
    expect(useTapeStore.getState().assetTypes).toEqual(['stock', 'fund']);
  });
});
