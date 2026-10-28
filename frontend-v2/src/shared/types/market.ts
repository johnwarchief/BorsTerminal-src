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
  percent_last: num,
  q_tot_tran: num,
  q_tot_cap: num,
  z_tot_tran: num,
  tvol: num,
  month_avg_vol: num,
  vol_ratio: num,
  vol_ratio_file: num,
  prior30_vol: num,
  vol_dod: num,
  hist_sessions: num,
  min_low_29: num,
  min30_low: num,
  buyer_power: num,
  buyer_power_raw: num,
  buy_power_i: num,
  sell_power_i: num,
  buy_i_vol: num,
  sell_i_vol: num,
  buy_count_i: num,
  sell_count_i: num,
  buy_q1_vol: num,
  buy_q1_cnt: num,
  tmin: num,
  is5: num,
  is6: num,
  h2_max: num,
  h5_max: num,
  h9_max: num,
  h19_max: num,
  h29_max: num,
  h39_max: num,
  h49_max: num,
  h59_max: num,
  pe: num,
  mcap: num,
  p_max: num,
  p_min: num,
  retail_buy_pct: num,
  retail_sell_pct: num,
  legal_buy_pct: num,
  legal_sell_pct: num,
  stop_state: z.string().nullish(),
  stop_reasons: z.string().nullish(),
  stop_since: z.string().nullish(),
  sup_flag: flag,
  sup_reason_count: num,
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

const deltaCounts = {
  count: z.number().nullish(),
  live_count: z.number().nullish(),
  fossil_count: z.number().nullish(),
};

export const MarketDeltaSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('unchanged'), rev: z.number(), meta: MarketMetaSchema.nullish(), ...deltaCounts }),
  z.object({
    status: z.literal('delta'), rev: z.number(), rows: z.array(MarketRowSchema),
    meta: MarketMetaSchema.nullish(), ...deltaCounts,
  }),
  z.object({ status: z.literal('full'), rev: z.number().nullish(), reason: z.string().nullish() }),
]);
export type MarketDelta = z.infer<typeof MarketDeltaSchema>;
