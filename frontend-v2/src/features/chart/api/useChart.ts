import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const CandleSchema = z.looseObject({
  time: z.union([z.string(), z.number()]),
  open: z.number(), high: z.number(), low: z.number(), close: z.number(),
  volume: z.number().nullish(),
});

export const ChartSchema = z.looseObject({
  status: z.string(),
  message: z.string().nullish(),
  candles: z.array(CandleSchema).default([]),
});

export type ChartPayload = z.infer<typeof ChartSchema>;

export function toKlineBars(candles: ChartPayload['candles']) {
  return [...candles]
    .sort((a, b) => String(a.time).localeCompare(String(b.time)))
    .map((candle) => ({
      timestamp: new Date(String(candle.time)).getTime(),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      volume: candle.volume ?? 0,
    }));
}

export function useChart(symbol: string, enabled = true) {
  return useQuery<ChartPayload>({
    queryKey: ['chart', symbol],
    queryFn: ({ signal }) => getJson(`/api/chart/${encodeURIComponent(symbol)}`, ChartSchema, signal),
    enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
