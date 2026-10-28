import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Num = z.number().nullish();
const Str = z.string().nullish();
const Bool = z.boolean().nullish();

const Axis1Schema = z.looseObject({
  monetary: z.looseObject({ monetary_pct: Num, threshold: Num, data_gap: Bool, reason: Str }).nullish(),
  volume: z.looseObject({ applicable: Bool }).nullish(),
}).nullish();

const Axis2Schema = z.looseObject({
  eps_series: z.array(z.number().nullable()).nullish(),
  years_available: Num,
  years_required: Num,
}).nullish();

const Axis3Schema = z.looseObject({
  margin_pct: Num,
  threshold: Num,
  band: Str,
  optimal: Bool,
}).nullish();

const Axis4Schema = z.looseObject({
  sales_to_mcap: Num,
  sales_threshold: Num,
  gap_cause: Str,
  available: Bool,
  data_gap: Bool,
  reason: Str,
}).nullish();

const Axis5Schema = z.looseObject({
  label: Str,
  regime_label: Str,
  sector: Str,
}).nullish();

export const FtsCardSchema = z.looseObject({
  status: z.literal('success'),
  symbol: z.string(),
  sector: Str,
  message: Str,
  passes: z.record(z.string(), Bool).nullish(),
  indicators: z.looseObject({
    '1': Axis1Schema,
    '2': Axis2Schema,
    '3': Axis3Schema,
    '4': Axis4Schema,
    '5': Axis5Schema,
  }).nullish(),
});

export type FtsCard = z.infer<typeof FtsCardSchema>;

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
