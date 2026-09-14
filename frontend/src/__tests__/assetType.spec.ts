// تست طبقه بندی نوع دارایی: پورت منطق app.js
import { describe, expect, it } from 'vitest';
import { ASSET_LABELS, ASSET_TYPES, classifyAssetType } from '@features/market/lib/assetType';

describe('طبقه بندی دارایی', () => {
  it('یازده نوع با برچسب فارسی', () => {
    expect(ASSET_TYPES).toHaveLength(11);
    for (const t of ASSET_TYPES) expect(ASSET_LABELS[t].length).toBeGreaterThan(1);
  });

  it('سهام پیش فرض و پایه با board برابر 2', () => {
    expect(classifyAssetType({ symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات', board: 1 })).toBe('stock');
    expect(classifyAssetType({ symbol: 'نماد پایه', name: 'شرکت نمونه', sector_name: 'فرابورس', board: 2 })).toBe('payeh');
  });

  it('صندوق و اوراق و حق تقدم', () => {
    expect(classifyAssetType({ symbol: 'آگاس', name: 'صندوق آگاس', sector_name: 'صندوق', board: 1 })).toBe('fund');
    expect(classifyAssetType({ symbol: 'اخزا001', name: 'اخزا', sector_name: 'اوراق', board: 1 })).toBe('bond');
    expect(classifyAssetType({ symbol: 'فولادح', name: 'حق تقدم فولاد', sector_name: 'فلزات', board: 1 })).toBe('right');
  });

  it('تسهیلات و اختیار', () => {
    expect(classifyAssetType({ symbol: 'تسه9801', name: 'تسهیلات مسکن', sector_name: 'تسهیلات', board: 1 })).toBe('teseh');
    expect(classifyAssetType({ symbol: 'ضفولاد', name: 'اختیار فولاد', sector_name: 'اختیار', board: 1 })).toBe('option');
  });
});
