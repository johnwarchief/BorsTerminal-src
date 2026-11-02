/**
 * frontend-v2/src/features/technical/model/__tests__/patternGlossary.test.ts
 *
 * آزمون‌های فرهنگ اصطلاحات و آموزش تعاملی معامله‌گر:
 * ۱. دربرگیری الگوهای کلیدی پرایس‌اکشن (شهاب ثاقب، چکش، پوشای صعودی/نزولی، دوجی)
 * ۲. تبیین شفاف مفهوم نرخ برد تاریخی ۱، ۳ و ۵ کندل آینده
 * ۳. تبیین مفهوم فاکتور سود و ریسک/ریوارد
 */

import { describe, it, expect } from 'vitest';
import {
  getPatternExplanation,
  STATISTICAL_EDGE_EDUCATION,
  PATTERN_EDUCATION_MAP,
} from '../patternGlossary';

describe('patternGlossary module', () => {
  it('provides detailed explanation and psychology for Shooting Star (شهاب ثاقب)', () => {
    const info = getPatternExplanation('Shooting Star');
    expect(info.nameFa).toBe('شهاب ثاقب');
    expect(info.typeFa).toContain('نزولی');
    expect(info.psychologyFa).toContain('فروشندگان');
    expect(info.adviceFa).toBeTruthy();
  });

  it('provides detailed explanation for Hammer (چکش صعودی)', () => {
    const info = getPatternExplanation('Hammer');
    expect(info.nameFa).toBe('چکش صعودی');
    expect(info.typeFa).toContain('صعودی');
    expect(info.psychologyFa).toContain('خریداران');
    expect(info.adviceFa).toBeTruthy();
  });

  it('provides detailed explanation for Bullish and Bearish Engulfing', () => {
    const bullish = getPatternExplanation('Bullish Engulfing');
    expect(bullish.nameFa).toBe('پوشای صعودی');
    expect(bullish.isBullish).toBe(true);

    const bearish = getPatternExplanation('Bearish Engulfing');
    expect(bearish.nameFa).toBe('پوشای نزولی');
    expect(bearish.isBullish).toBe(false);
  });

  it('falls back safely for unknown patterns without throwing', () => {
    const unknown = getPatternExplanation('Unknown Pattern X');
    expect(unknown.nameFa).toBe('Unknown Pattern X');
    expect(unknown.psychologyFa).toBeTruthy();
  });

  it('contains comprehensive statistical edge educational texts', () => {
    expect(Object.keys(PATTERN_EDUCATION_MAP).length).toBeGreaterThan(5);
    expect(STATISTICAL_EDGE_EDUCATION.winRateFa.titleFa).toContain('نرخ برد تاریخی');
    expect(STATISTICAL_EDGE_EDUCATION.winRateFa.explanationFa).toContain('کندل');
    expect(STATISTICAL_EDGE_EDUCATION.profitFactorFa.titleFa).toContain('فاکتور سود');
    expect(STATISTICAL_EDGE_EDUCATION.riskRewardFa.titleFa).toContain('سود به زیان');
  });
});
