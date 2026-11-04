import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson, requestJson } from '@shared/api/http';

const Num = z.number().nullish();
const Str = z.string().nullish();
const Bool = z.boolean().nullish();

export const FtsConfigPayloadSchema = z.looseObject({
  growth_min: z.number(),
  eps_years: z.number(),
  margin_min: z.number(),
  margin_optimal: z.number(),
  sales_to_mcap_min: z.number(),
  profit_potential_min: z.number(),
  industry_mode: z.string(),
  watchlist_max: z.number(),
  mcap_min_hmt: z.number(),
  suspended_max_stale_sessions: z.number(),
  filter_m141: z.boolean(),
  min_trade_val: z.number(),
  mandatory_sectors: z.array(z.string()),
  free_sectors: z.array(z.string()),
  reject_insurance: Bool,
  include_industries: z.array(z.string()).nullish(),
  exclude_industries: z.array(z.string()).nullish(),
  v10_monetary_growth_min: Num,
  v10_volume_growth_min: Num,
  v10_volume_breadth_min: Num,
  v10_eps_years: Num,
  v10_margin_min: Num,
  v10_margin_ideal: Num,
  v10_sales_to_mcap_min: Num,
  v10_potential_min: Num,
  v10_inflation_basis: Num,
  hourglass_rsi_period: z.number(),
  hourglass_rsi_oversold: z.number(),
  hourglass_ma52_position: z.enum(['below', 'above', 'either']),
  holdings_sales_na: Bool,
  pharma_margin_exempt_min: Num,
  exclude_base_market: Bool,
  exclude_rejected_indicators: z.array(z.string()).nullish(),
});

export const FtsConfigResponseSchema = z.looseObject({
  status: z.string(),
  config: FtsConfigPayloadSchema.nullish(),
  message: Str,
  errors: z.record(z.string(), z.string()).nullish(),
});

export type FtsConfig = z.infer<typeof FtsConfigPayloadSchema>;
export type FtsConfigResponse = z.infer<typeof FtsConfigResponseSchema>;

/** پیش‌فرض‌های جزوهٔ FTS — فقط کلیدهای موجود؛ هیچ آستانهٔ تازه‌ای اینجا ساخته نمی‌شود. */
export const FTS_BASIC_DEFAULTS = {
  growth_min: 40,
  eps_years: 3,
  margin_min: 20,
  margin_optimal: 30,
  sales_to_mcap_min: 0.33,
  profit_potential_min: 40,
  industry_mode: 'Exclude_Mandatory_Pricing',
  watchlist_max: 50,
  mcap_min_hmt: 0,
  suspended_max_stale_sessions: 3,
  filter_m141: false,
  min_trade_val: 0,
  mandatory_sectors: ['خودرو', 'نیروگاه', 'لاستیک'],
  free_sectors: ['سیمان', 'پتروشیمی', 'شیمیایی', 'فلزات', 'کانی', 'کاشی', 'سرامیک', 'شیشه', 'کانه', 'معادن', 'نفت', 'محصولات فلزی'],
  reject_insurance: true,
  include_industries: [] as string[],
  exclude_industries: [] as string[],
  v10_monetary_growth_min: 60,
  v10_volume_growth_min: 0,
  v10_volume_breadth_min: 0.6,
  v10_eps_years: 3,
  v10_margin_min: 20,
  v10_margin_ideal: 30,
  v10_sales_to_mcap_min: 0.33,
  v10_potential_min: 40,
  v10_inflation_basis: 60,
  hourglass_rsi_period: 7,
  hourglass_rsi_oversold: 30,
  hourglass_ma52_position: 'below' as const,
  holdings_sales_na: true,
  pharma_margin_exempt_min: 0,
  exclude_base_market: true,
  exclude_rejected_indicators: [] as string[],
};

export interface FtsSettingsDraft {
  growth_min: number;
  v10_monetary_growth_min: number;
  v10_inflation_basis: number;
  margin_min: number;
  v10_sales_to_mcap_min: number;
  profit_potential_min: number;
  suspended_max_stale_sessions: number;
  volumeGate: boolean;
  epsGate: boolean;
  pricingGate: 'free_only' | 'all';
  insuranceGate: boolean;
  holdingsNa: boolean;
  pharmaExempt: boolean;
  baseMarketGate: boolean;
}

export function draftFromConfig(config: Partial<FtsConfig> | null | undefined): FtsSettingsDraft {
  const c = config ?? {};
  return {
    growth_min: c.growth_min ?? 40,
    v10_monetary_growth_min: c.v10_monetary_growth_min ?? 60,
    v10_inflation_basis: c.v10_inflation_basis ?? 60,
    margin_min: c.margin_min ?? 20,
    v10_sales_to_mcap_min: c.v10_sales_to_mcap_min ?? 0.33,
    profit_potential_min: c.profit_potential_min ?? 40,
    suspended_max_stale_sessions: c.suspended_max_stale_sessions ?? 3,
    volumeGate: (c.v10_volume_breadth_min ?? 0.6) > 0,
    epsGate: (c.v10_eps_years ?? 3) >= 3,
    pricingGate: c.industry_mode === 'Rank_Only' ? 'all' : 'free_only',
    insuranceGate: c.reject_insurance ?? true,
    holdingsNa: c.holdings_sales_na ?? true,
    pharmaExempt: (c.pharma_margin_exempt_min ?? 0) > 0,
    baseMarketGate: c.exclude_base_market ?? true,
  };
}

export function buildFtsPayload(base: Partial<FtsConfig>, draft: FtsSettingsDraft): Record<string, unknown> {
  const {
    volumeGate, epsGate, pricingGate, insuranceGate, holdingsNa,
    pharmaExempt, baseMarketGate, ...numbers
  } = draft;
  return {
    ...base,
    ...numbers,
    industry_mode: pricingGate === 'all' ? 'Rank_Only' : 'Exclude_Mandatory_Pricing',
    mandatory_sectors: [...FTS_BASIC_DEFAULTS.mandatory_sectors],
    reject_insurance: insuranceGate,
    v10_eps_years: epsGate ? 3 : 1,
    v10_volume_growth_min: 0,
    v10_volume_breadth_min: volumeGate ? 0.6 : 0,
    margin_optimal: Math.max(draft.margin_min, 30),
    // v10_thresholds اول v10_margin_min را probe می‌کند؛ اگر همگام نشود،
    // مقدار کهنهٔ فایل بر اسلایدر کاربر مقدم می‌شود.
    v10_margin_min: draft.margin_min,
    v10_margin_ideal: Math.max(draft.margin_min, 30),
    v10_potential_min: draft.profit_potential_min,
    holdings_sales_na: holdingsNa,
    pharma_margin_exempt_min: pharmaExempt ? 50 : 0,
    exclude_base_market: baseMarketGate,
  };
}

export function buildResetPayload(base: Partial<FtsConfig>): Record<string, unknown> {
  return {
    ...base,
    ...FTS_BASIC_DEFAULTS,
    mandatory_sectors: [...FTS_BASIC_DEFAULTS.mandatory_sectors],
    hourglass_rsi_period: base.hourglass_rsi_period ?? 7,
    hourglass_rsi_oversold: base.hourglass_rsi_oversold ?? 30,
    hourglass_ma52_position: base.hourglass_ma52_position ?? 'below',
  };
}

export function useFtsConfig() {
  return useQuery({
    queryKey: ['fts-config'],
    queryFn: ({ signal }) => getJson('/api/fts/config', FtsConfigResponseSchema, signal),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useSaveFtsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      requestJson('/api/fts/config', FtsConfigResponseSchema, { method: 'POST', body: payload }),
    onSuccess: (res) => {
      if (res.status !== 'success') return;
      qc.invalidateQueries({ queryKey: ['screener-core'] });
      qc.invalidateQueries({ queryKey: ['fts-card'] });
      qc.invalidateQueries({ queryKey: ['fts-config'] });
    },
  });
}
