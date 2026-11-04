import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const Str = z.string().nullish();
const Bool = z.boolean().nullish();

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
});

export const ScreenerCoreSchema = z.looseObject({
  status: z.string(),
  count: z.number(),
  data: z.array(ScreenerCoreRowSchema),
  as_of: Str,
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
