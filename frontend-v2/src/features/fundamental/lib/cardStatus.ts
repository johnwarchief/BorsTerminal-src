import type { FtsCard } from '../api/useFtsCard';
import type { AxisKey, AxisStatus } from './axisMeta';
import { isBankCard, isHoldingCard } from './assetScope';

/** کلیدِ هر محور در `card.passes` و شمارهٔ آن در `card.indicators`/`card.details`. */
export const CARD_KEY = {
  growth: '1_growth',
  eps: '2_eps_trend',
  margin: '3_gross_margin',
  sales: '4_sales_to_mcap',
  industry: '5_industry',
} as const;

export const CARD_NUM = { growth: '1', eps: '2', margin: '3', sales: '4', industry: '5' } as const;

type CardIndicator = { na?: boolean | null; available?: boolean | null; data_gap?: boolean | null };

/**
 * تنها منبعِ وضعیتِ پنج محور برای پنل‌ها، کوینتت و روبانِ امتیاز.
 * R70: بی‌نظری و نبودِ داده بر pass/fail مقدم‌اند تا محورِ بدون داده «رد» دیده نشود.
 */
export function cardStatus(card: FtsCard, axis: AxisKey): AxisStatus {
  const pass = card.passes?.[CARD_KEY[axis]];
  const indicator = card.indicators?.[CARD_NUM[axis]] as unknown as CardIndicator | undefined;
  if (indicator?.na === true) return 'na';
  if (indicator?.available === false || indicator?.data_gap === true) return 'unknown';
  // R97: شکافِ دادهٔ ۱الف/۱ب پیش از حکمِ رشد، محور را «نامشخص» می‌کند.
  if (axis === 'growth') {
    const growth = card.indicators?.['1'];
    if (growth?.monetary?.data_gap === true || growth?.volume?.data_gap === true) return 'unknown';
  }
  // R-V1-1 (B-1): وتویِ طبقه در سطحِ نماد بر passِ محور ۵ مقدم است — بیمه با
  // indicators['5'].pass=true هم بیرونِ غربال است و «قبول» نباید بگوید.
  // R-V1-2 (M-1): برایِ هلدینگ/بانک نرخ‌گذاریِ محصول تعریف نشده، پس این محور
  // سنجیده نمی‌شود؛ «بی‌نظر» و بیرونِ شمارشِ امتیاز، نه «رد».
  if (axis === 'industry') {
    if (card.excluded === true) return 'fail';
    if (isHoldingCard(card) || isBankCard(card)) return 'na';
  }
  if (pass === true) return 'pass';
  if (pass === false) return 'fail';
  return 'unknown';
}
