import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const QuarterSchema = z.looseObject({
  period_end: z.string().nullish(),
  period_months: z.number().nullish(),
  revenue: z.number().nullish(),
  net_profit: z.number().nullish(),
  basic_eps: z.number().nullish(),
  title: z.string().nullish(),
});

const Payload = z.looseObject({
  status: z.string(),
  symbol: z.string().nullish(),
  count: z.number().nullish(),
  quarters: z.array(QuarterSchema).default([]),
});

export type Quarter = z.infer<typeof QuarterSchema>;

export function useQuarters(symbol: string | null | undefined) {
  return useQuery({
    queryKey: ['fundamental-quarters', symbol],
    queryFn: ({ signal }) => getJson(
      `/api/fundamental/${encodeURIComponent(String(symbol))}/quarters`, Payload, signal),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}
