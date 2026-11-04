import type { FtsCard } from '../api/useFtsCard';
import type { AxisKey, AxisStatus } from './axisMeta';

/** کلیدِ هر محور در `card.passes` و شمارهٔ آن در `card.indicators`/`card.details`. */
export const CARD_KEY = {
  growth: '1_growth',
  eps: '2_eps_trend',
  margin: '3_gross_margin',
  sales: '4_sales_to_mcap',
  industry: '5_industry',
} as const;

export const CARD_NUM = { growth: '1', eps: '2', margin: '3', sales: '4', industry: '5' } as const;

type CardIndicator = { na?: boolean | null; data_gap?: boolean | null };

/** تنها منبعِ وضعیتِ پنج محور برای پنل‌ها، کوینتت و روبانِ امتیاز. */
export function cardStatus(card: FtsCard, axis: AxisKey): AxisStatus {
  const pass = card.passes?.[CARD_KEY[axis]];
  const indicator = card.indicators?.[CARD_NUM[axis]] as unknown as CardIndicator | undefined;
  if (pass === true) return 'pass';
  if (pass === false) return 'fail';
  if (indicator?.na === true) return 'na';
  return 'unknown';
}
