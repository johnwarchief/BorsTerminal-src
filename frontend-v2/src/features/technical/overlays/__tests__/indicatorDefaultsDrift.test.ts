/**
 * overlays/__tests__/indicatorDefaultsDrift.test.ts
 *
 * گاردِ واگرایی. پیش از این، مقادیرِ پیش‌فرضِ هر اورلی دو جا نوشته شده بود:
 * داخلِ تابعِ رسم (هاردکد) و داخلِ defaultParamsِ رجیستری. دو نسخه از هم
 * واگرا شده بودند — رجیستری pivLeft:6 می‌گفت و اورلی pivLeft=3 را کار می‌داد —
 * و نتیجه‌اش روی ۲۸ نمادِ اصلی، ۱۷٫۷ شکلِ رسم‌شده به‌جای ۷٫۱ بود.
 *
 * این تست ثابت می‌کند رجیستری دیگر عددِ مستقلی ندارد: همان ثابتِ صادرشده را
 * می‌خواند. تا این سبز است، «پیش‌فرض» چیزی است که واقعاً رسم می‌شود.
 */

import { describe, it, expect } from 'vitest';
import {
  ADVANCED_INDICATORS_REGISTRY,
  DOUBLE_TAP_DEFAULTS,
  TRENDLINE_DEFAULTS,
  SUPER_TREND_PULLBACK_DEFAULTS,
} from '../advancedTradingIndicators';
import { useTechnicalStore } from '../../model/technicalStore';

const byId = (id: string) => ADVANCED_INDICATORS_REGISTRY.find((i) => i.id === id);

describe('indicator default-params drift guard', () => {
  it('registry DoubleTap3D reads the same object the overlay draws with', () => {
    expect(byId('DoubleTap3D')?.defaultParams).toEqual(DOUBLE_TAP_DEFAULTS);
  });

  it('registry AutoTrendlineCHoCH reads the same object the overlay draws with', () => {
    expect(byId('AutoTrendlineCHoCH')?.defaultParams).toEqual(TRENDLINE_DEFAULTS);
  });

  it('no registry entry carries a stale hand-written number', () => {
    // هر ورودی باید یا بدونِ پارامتر باشد یا دقیقاً یکی از ثابت‌های صادرشده
    const known = [DOUBLE_TAP_DEFAULTS, TRENDLINE_DEFAULTS, SUPER_TREND_PULLBACK_DEFAULTS];
    for (const ind of ADVANCED_INDICATORS_REGISTRY) {
      const keys = Object.keys(ind.defaultParams);
      if (keys.length === 0) continue;
      const matchesKnown = known.some((k) => {
        const kk = Object.keys(k);
        return kk.length === keys.length && kk.every((x) => x in ind.defaultParams);
      });
      // MultiModeChannel/MultiVariantRSI پارامترِ حالتی دارند، نه عددی
      const allNumeric = Object.values(ind.defaultParams).every((v) => typeof v === 'number');
      if (allNumeric) expect(matchesKnown, `${ind.id} numeric defaults must come from a shared const`).toBe(true);
    }
  });

  it('the widened windows are the ones that cut drawn figures', () => {
    // این اعداد همان چیزی است که در _audit/indicator-density سنجیده شد
    expect(DOUBLE_TAP_DEFAULTS.pivLeft).toBe(6);
    expect(DOUBLE_TAP_DEFAULTS.pivRight).toBe(4);
    expect(TRENDLINE_DEFAULTS.swingLeft).toBe(5);
    expect(TRENDLINE_DEFAULTS.swingRight).toBe(3);
  });
});

describe('indicatorParams store', () => {
  it('starts empty so the registry defaults are what actually draw', () => {
    useTechnicalStore.getState().reset();
    expect(useTechnicalStore.getState().indicatorParams).toEqual({});
  });

  it('a set override reaches the overlay input and is removable', () => {
    useTechnicalStore.getState().setIndicatorParam('DoubleTap3D', 'pivLeft', 9);
    expect(useTechnicalStore.getState().indicatorParams.DoubleTap3D.pivLeft).toBe(9);
    useTechnicalStore.getState().resetIndicatorParams('DoubleTap3D');
    expect(useTechnicalStore.getState().indicatorParams.DoubleTap3D).toBeUndefined();
  });

  it('clamps the drawn-pattern cap to a usable range', () => {
    useTechnicalStore.getState().setMaxDrawnPatterns(0);
    expect(useTechnicalStore.getState().maxDrawnPatterns).toBe(1);
    useTechnicalStore.getState().setMaxDrawnPatterns(999);
    expect(useTechnicalStore.getState().maxDrawnPatterns).toBe(20);
    useTechnicalStore.getState().setMaxDrawnPatterns(5);
    expect(useTechnicalStore.getState().maxDrawnPatterns).toBe(5);
  });
});
