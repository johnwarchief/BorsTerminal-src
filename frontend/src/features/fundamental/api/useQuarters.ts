// features/fundamental/api/useQuarters.ts -- سری میاندوره ای خام برای روند فصلی
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

export const QuarterRowSchema = z.object({
  period_end: z.string(),
  period_months: z.number().nullish(),
  revenue: z.number().nullish(),
  operating_profit: z.number().nullish(),
  net_profit: z.number().nullish(),
  basic_eps: z.number().nullish(),
  publish_date: z.string().nullish(),
});

export type QuarterRow = z.infer<typeof QuarterRowSchema>;

const QuartersSchema = z.object({
  status: z.string(),
  symbol: z.string(),
  count: z.number().nullish(),
  quarters: z.array(QuarterRowSchema).nullish(),
});

export function useQuarters(symbol: string) {
  return useQuery({
    queryKey: ['fund-quarters', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof QuartersSchema>>(`/api/fundamental/${encodeURIComponent(symbol)}/quarters`, {
        schema: QuartersSchema,
        signal,
      }),
    enabled: symbol.length > 0,
    staleTime: 30 * 60_000,
    gcTime: 60 * 60_000,
  });
}
