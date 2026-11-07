import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Str = z.string().nullish();
const Bool = z.boolean().nullish();
const Num = z.number().nullish();

const Thresholds = z.looseObject({
  growth_min: Num,
  margin_min: Num,
  margin_optimal: Num,
  v10_sales_to_mcap_min: Num,
  profit_potential_min: Num,
  v10_eps_years: Num,
}).nullish();

export const ScreenerCoreRowSchema = z.looseObject({
  symbol: z.string(),
  symbol_norm: Str,
  name: Str,
  sector_name: Str,
  score: z.number().nullish(),
  verdict: Str,
  excluded: Bool,
  i1_pass: Bool,
  i2_pass: Bool,
  i3_pass: Bool,
  i4_pass: Bool,
  i5_pass: Bool,
  i1_na: Bool,
  i2_na: Bool,
  i3_na: Bool,
  i4_na: Bool,
  i5_na: Bool,
  i1_reason: Str,
  i2_reason: Str,
  i3_reason: Str,
  i4_reason: Str,
  i5_reason: Str,
  eps_data_gap: Bool,
  rev_growth: Num,
  eps_series: z.array(z.number().nullable()).nullish(),
  eps_years_required: Num,
  eps_years_available: Num,
  gross_margin: Num,
  profit_potential_pct: Num,
  sales_to_mcap: Num,
  pricing_mode: Str,
  margin_tier: Str,
  i1a_pass: Bool,
  i1b_applicable: Bool,
  i1b_pass: Bool,
  i1b_data_gap: Bool,
  i4a_pass: Bool,
  i4b_pass: Bool,
});

export const ScreenerCoreSchema = z.looseObject({
  status: z.string(),
  count: z.number(),
  data: z.array(ScreenerCoreRowSchema),
  thresholds: Thresholds,
  as_of: z.union([z.string(), z.number()]).nullish(),
});

export type ScreenerCoreRow = z.infer<typeof ScreenerCoreRowSchema>;
export type ScreenerCore = z.infer<typeof ScreenerCoreSchema>;

export function useScreenerCore() {
  return useQuery<ScreenerCore>({
    queryKey: ['screener-core'],
    queryFn: ({ signal }) => getJson('/api/screener', ScreenerCoreSchema, signal),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
