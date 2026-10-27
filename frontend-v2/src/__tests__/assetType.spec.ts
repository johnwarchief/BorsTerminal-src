import { describe, expect, it } from 'vitest';
import { classifyAssetType } from '@features/market/lib/assetType';

describe('asset type classification (port of the product rule)', () => {
  it('classifies funds', () => {
    expect(classifyAssetType({ symbol: 'دارا', name: 'صندوق سرمایه‌گذاری دارا' })).toBe('fund');
  });

  it('classifies bonds by prefix and sector', () => {
    expect(classifyAssetType({ symbol: 'اخزا3024', name: 'اوراق خزانه' })).toBe('bond');
    expect(classifyAssetType({ symbol: 'اراد3054', name: 'اوراق تامین مالی' })).toBe('bond');
  });

  it('classifies rights by trailing ح', () => {
    expect(classifyAssetType({ symbol: 'فولادح', name: 'حق تقدم فولاد' })).toBe('right');
  });

  it('classifies base market by board=2', () => {
    expect(classifyAssetType({ symbol: 'آباد', name: 'آبادگران', board: 2 })).toBe('payeh');
  });

  it('defaults ordinary symbols to stock', () => {
    expect(classifyAssetType({ symbol: 'فولاد', name: 'فولاد مبارکه', board: 1 })).toBe('stock');
  });
});
