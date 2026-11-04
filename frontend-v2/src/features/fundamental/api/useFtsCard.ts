import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Num = z.number().nullish();
const Str = z.string().nullish();
const Bool = z.boolean().nullish();
// R82: در payloadِ زنده شواهدِ محور ۲ گاه رشته است و گاه آرایهٔ رشته‌ها.
const StrOrStrArray = z.union([z.string(), z.array(z.string())]).nullish();

const Axis1Schema = z.looseObject({
  monetary: z.looseObject({
    monetary_pct: Num,
    threshold: Num,
    // R97: آستانهٔ هدفِ گیتِ S4b (۶۰ در پاسخِ زنده) جدا از threshold آمده است.
    target_threshold: Num,
    pass: Bool,
    data_gap: Bool,
    reason: Str,
    // R-P1-1: فروشِ دورهٔ جاری/قبل (میلیارد تومان) برای ردیف‌ها و نمودارِ جفتِ فروش.
    ytd_now_bt: Num,
    ytd_prev_bt: Num,
  }).nullish(),
  volume: z.looseObject({
    applicable: Bool,
    real_pct: Num,
    volume_pct: Num,
    pass: Bool,
    threshold: Num,
    note: Str,
    // R106: دلیلِ شکستِ ۱ب جدا از یادداشتِ روش می‌آید.
    reason: Str,
    data_gap: Bool,
    basis: Str,
  }).nullish(),
}).nullish();

const Axis2Schema = z.looseObject({
  eps_series: z.array(z.number().nullable()).nullish(),
  net_profit_series: z.array(z.number().nullable()).nullish(),
  period_ends: z.array(Str).nullish(),
  years_available: Num,
  years_required: Num,
  evidence: StrOrStrArray,
  consolidated_used: Bool,
  audited_only: Bool,
  // R101: دلیل/شکافِ دادهٔ محور ۲ برای نمایشِ آشکار در پنل.
  reason: Str,
  data_gap: Bool,
}).nullish();

const Axis3Schema = z.looseObject({
  margin_pct: Num,
  threshold: Num,
  band: Str,
  optimal: Bool,
  na: Bool,
  margin_class: Str,
  gross_profit_bt: Num,
  revenue_bt: Num,
  optimal_threshold: Num,
  reason: Str,
}).nullish();

const Axis4Schema = z.looseObject({
  sales_to_mcap: Num,
  sales_threshold: Num,
  gap_cause: Str,
  available: Bool,
  data_gap: Bool,
  reason: Str,
  na: Bool,
  exempt: Bool,
  potential_pct: Num,
  potential_threshold: Num,
  annual_sales_bt: Num,
  months_used: Num,
  annualize_basis: Str,
}).nullish();

const Axis5Schema = z.looseObject({
  label: Str,
  regime_label: Str,
  sector: Str,
  verdict: Str,
  market_share_pct: Num,
  outlook: Str,
  rule_ref: Str,
  pass: Bool,
}).nullish();

const FreshnessAxisSchema = z.looseObject({
  as_of: Str,
  source: Str,
  tracing_no: Num,
  period_end: Str,
  state: z.enum(['fresh', 'stale', 'missing', 'quarantined']).nullish(),
  reason: Str,
});

const FreshnessSchema = z.looseObject({
  as_of: Str,
  axes: z.record(z.string(), FreshnessAxisSchema).nullish(),
});

const DetailSubcheckSchema = z.looseObject({
  key: Str,
  label: Str,
  state: Str,
  value: Str,
  threshold: Str,
  detail: Str,
  verified: Bool,
  confidence: Str,
});

const DetailSchema = z.looseObject({
  title: Str,
  formula: Str,
  source: Str,
  calc: Str,
  what: Str,
  subchecks: z.array(DetailSubcheckSchema).nullish(),
});

const HistoryRowSchema = z.looseObject({
  period_end: Str,
  fiscal_year: Str,
  revenue: Num,
  gross_profit: Num,
  net_profit: Num,
  eps: Num,
  audited: Bool,
  consolidated: Bool,
});

const MetricsSchema = z.looseObject({
  mcap: Num,
  annual_sales_bt: Num,
  revenue: Num,
  sales_to_mcap: Num,
  ps: Num,
  gross_margin: Num,
  net_margin: Num,
  growth_pct: Num,
});

export const FtsCardSchema = z.looseObject({
  status: z.literal('success'),
  symbol: z.string(),
  sector: Str,
  score: Num,
  verdict: Str,
  applicable: Bool,
  // R99: تنظیمِ گیتِ EPS از ریشهٔ کارت (loose) خوانده می‌شود تا آستانهٔ ۳سال سخت‌کد نشود.
  thresholds: z.looseObject({
    growth_min: Num,
    margin_min: Num,
    v10_eps_years: Num,
  }).nullish(),
  history: z.array(HistoryRowSchema).nullish(),
  metrics: MetricsSchema.nullish(),
  details: z.record(z.string(), DetailSchema).nullish(),
  freshness: FreshnessSchema.nullish(),
  message: Str,
  passes: z.record(z.string(), Bool).nullish(),
  profile: z.looseObject({
    kind: Str,
    margin_class: Str,
    label: Str,
    volume_applicable: Bool,
  }).nullish(),
  indicators: z.looseObject({
    '1': Axis1Schema,
    '2': Axis2Schema,
    '3': Axis3Schema,
    '4': Axis4Schema,
    '5': Axis5Schema,
  }).nullish(),
});

export type FtsCard = z.infer<typeof FtsCardSchema>;
export type FtsDetail = z.infer<typeof DetailSchema>;
export type FtsDetailSubcheck = z.infer<typeof DetailSubcheckSchema>;

export function useFtsCard(symbol: string | null | undefined) {
  return useQuery<FtsCard>({
    queryKey: ['fts-card', symbol],
    queryFn: ({ signal }) => getJson(`/api/fundamental/${encodeURIComponent(String(symbol))}`, FtsCardSchema, signal),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}
