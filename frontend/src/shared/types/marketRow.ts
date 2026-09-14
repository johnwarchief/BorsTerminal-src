// shared/types/marketRow.ts -- شکل پاسخ /api/market
// فیلدها از کوئری api/market.py استخراج شده اند. عددها ممکن است null باشند.
import { z } from 'zod';

const num = z.number().nullish();
const flag = z.boolean().nullish();

export const MarketRowSchema = z.object({
  ins_code: z.string().nullish(),
  symbol: z.string().min(1),
  name: z.string().nullish(),
  sector_name: z.string().nullish(),
  board: z.union([z.number(), z.string()]).nullish(),
  p_closing: num,
  p_last: num,
  price_yesterday: num,
  percent_change: num,
  q_tot_tran: num,
  z_tot_tran: num,
  q_tot_cap: num,
  pe: num,
  eps: num,
  price_max: z.string().nullish(),
  price_min: z.string().nullish(),
  p_max: num,
  p_min: num,
  buy_i_vol: num,
  buy_n_vol: num,
  sell_i_vol: num,
  sell_n_vol: num,
  buy_count_i: num,
  sell_count_i: num,
  month_avg_vol: num,
  prev_day_vol: num,
  tvol: num,
  vol_ratio: num,
  vol_dod: num,
  vol_trend: z.string().nullish(),
  buyer_power: num,
  buy_power_i: num,
  sell_power_i: num,
  suspicious_vol: flag,
  f_roobi: flag,
  f_susp: flag,
  f_clock: flag,
  f_jet: flag,
  f_noqteh: flag,
  is_live: flag,
  d_even: num,
  h1_max: num,
  h5_max: num,
  h9_max: num,
  h19_max: num,
  h29_max: num,
  h39_max: num,
  h49_max: num,
  h59_max: num,
  min30_low: num,
  max30_high: num,
  d1_vol: num,
  dist_min30_pct: num,
});

export type MarketRow = z.infer<typeof MarketRowSchema>;

export const MarketMetaSchema = z.object({
  d_even: num,
  h_even: num,
  last_sync: z.string().nullish(),
});

export type MarketMeta = z.infer<typeof MarketMetaSchema>;

export const MarketFeedSchema = z.object({
  status: z.string(),
  count: z.number().nullish(),
  data: z.array(MarketRowSchema),
  meta: MarketMetaSchema.nullish(),
  live_count: z.number().nullish(),
  fossil_count: z.number().nullish(),
});

export type MarketFeed = z.infer<typeof MarketFeedSchema>;
