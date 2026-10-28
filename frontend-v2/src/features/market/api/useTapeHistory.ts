import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const TapeDayCellSchema = z.object({
  active: z.boolean(),
  first_at: z.string().nullish(),
  last_at: z.string().nullish(),
  passes: z.number(),
  evidence: z.record(z.string(), z.unknown()).default({}),
});

const TapeFlagSeriesSchema = z.object({
  days: z.record(z.string(), TapeDayCellSchema).default({}),
  total: z.number().default(0),
  last_seen_at: z.string().nullish(),
});

const TapeHistorySchema = z.looseObject({
  status: z.string(),
  days: z.array(z.number()).default([]),
  reliable_from: z.number().nullish(),
  by_symbol: z.record(z.string(), z.record(z.string(), TapeFlagSeriesSchema)).default({}),
  flags: z.array(z.string()).default([]),
  write_error: z.string().nullish(),
  message: z.string().nullish(),
});

export type TapeDayCell = z.infer<typeof TapeDayCellSchema>;
export type TapeFlagSeries = z.infer<typeof TapeFlagSeriesSchema>;
export type TapeHistoryPayload = z.infer<typeof TapeHistorySchema>;

export function useTapeHistory(insCode: string | null | undefined, days = 6) {
  const code = String(insCode ?? '').trim();
  return useQuery({
    queryKey: ['tape-history', code, days],
    queryFn: ({ signal }) => getJson(
      `/api/tape-history?codes=${encodeURIComponent(code)}&days=${days}`,
      TapeHistorySchema,
      signal,
    ),
    enabled: code.length > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function seriesFor(
  payload: TapeHistoryPayload | undefined,
  insCode: string | null | undefined,
): Record<string, TapeFlagSeries> {
  return payload?.by_symbol[String(insCode ?? '').trim()] ?? {};
}
