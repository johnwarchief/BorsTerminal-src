/**
 * lib/__tests__/telegramIndicatorCatalog.test.ts
 *
 * سه چیزی که این ماژول باید تضمین کند (همان باگِ tvIndicatorCatalog.ts):
 * ۱. ۶۴ ردیف است ۲. هر ردیف عکسِ واقعی دارد ۳. هر overlayId لینک‌شده در
 * رجیستری پیدا می‌شود. هیچ‌کدام با try/catch ساکت نمی‌شوند.
 */

import { describe, it, expect } from 'vitest';
import {
  TELEGRAM_CATALOG,
  TELEGRAM_OVERLAY_LINKS,
  UNLINKED_OVERLAYS,
  searchTelegramRows,
} from '../telegramIndicatorCatalog';
import { ADVANCED_INDICATORS_REGISTRY } from '../../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../../overlays/userIndicators';

describe('telegramIndicatorCatalog', () => {
  it('has exactly 64 rows', () => {
    expect(TELEGRAM_CATALOG).toHaveLength(64);
  });

  it('gives every row a resolved photo url', () => {
    const missing = TELEGRAM_CATALOG.filter((r) => !r.photoUrl).map((r) => r.id);
    expect(missing).toEqual([]);
  });

  it('ids are p01..p64 in order', () => {
    expect(TELEGRAM_CATALOG[0].id).toBe('p01');
    expect(TELEGRAM_CATALOG[63].id).toBe('p64');
  });

  it('every linked overlayId exists in one of the two registries', () => {
    const known = new Set([
      ...ADVANCED_INDICATORS_REGISTRY.map((i) => i.id),
      ...USER_INDICATORS_REGISTRY.map((i) => i.id),
    ]);
    const dead = Object.entries(TELEGRAM_OVERLAY_LINKS).filter(([, v]) => !known.has(v));
    expect(dead).toEqual([]);
  });

  it('links 7 distinct overlays across 9 rows and reports the 2 unresolved', () => {
    expect(new Set(Object.values(TELEGRAM_OVERLAY_LINKS)).size).toBe(7);
    expect(UNLINKED_OVERLAYS).toEqual(['MultiModeChannel', 'MultiVariantRSI']);
  });

  it('search matches title, caption and attachment names', () => {
    expect(searchTelegramRows('supertrend').length).toBeGreaterThan(0);
    // names measured from the delivered JSON: Indi 518.txt is only on p11, while
    // Indi 225.txt is on p14 and p42 (one attachment posted in two messages).
    expect(searchTelegramRows('Indi 518.txt').map((r) => r.id)).toContain('p11');
    expect(searchTelegramRows('Indi 225.txt').map((r) => r.id)).toEqual(['p14', 'p42']);
    expect(searchTelegramRows('zzzz-nothing')).toHaveLength(0);
  });

  it('leaves the three caption-less rows empty instead of inventing text', () => {
    const noTitle = TELEGRAM_CATALOG.filter((r) => r.titleEn === '').map((r) => r.id);
    expect(noTitle).toEqual(['p08', 'p09', 'p10']);
  });
});
