import { z } from 'zod';

/** فقط فیلدهایی که این اپ می‌خواند؛ بقیهٔ پیلود با looseObject حفظ می‌شود. */
const num = z.number().nullish();
const flag = z.union([z.boolean(), z.number(), z.string(), z.null()]).optional();

export const MarketRowSchema = z.looseObject({
  ins_code: z.string().nullish(),
  symbol: z.string(),
  name: z.string().nullish(),
  sector_name: z.string().nullish(),
  board: z.union([z.number(), z.string()]).nullish(),
  p_last: num,
  p_closing: num,
  price_yesterday: num,
  price_change: num,
  percent_change: num,
  q_tot_tran: num,
  q_tot_cap: num,
  z_tot_tran: num,
  retail_buy_pct: num,
  retail_sell_pct: num,
  legal_buy_pct: num,
  legal_sell_pct: num,
  is_live: flag,
  pct_is_current: flag,
  f_smart: flag,
  f_legal: flag,
  f_roobi: flag,
  f_susp: flag,
  f_clock: flag,
  f_noqteh: flag,
  f_jet: flag,
});
export type MarketRow = z.infer<typeof MarketRowSchema>;

export const MarketMetaSchema = z.looseObject({
  d_even: num,
  h_even: num,
  last_sync: z.string().nullish(),
});

export const MarketFeedSchema = z.looseObject({
  status: z.string(),
  data: z.array(MarketRowSchema),
  count: num,
  live_count: num,
  fossil_count: num,
  rev: num,
  rev_at: num,
  meta: MarketMetaSchema.nullish(),
});
export type MarketFeed = z.infer<typeof MarketFeedSchema>;
