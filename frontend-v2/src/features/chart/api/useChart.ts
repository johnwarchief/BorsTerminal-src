import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const CandleSchema = z.looseObject({
  time: z.union([z.string(), z.number()]),
  open: z.number(), high: z.number(), low: z.number(), close: z.number(),
  volume: z.number().nullish(),
});

export const CorporateEventSchema = z.looseObject({
  date: z.string(),
  type: z.string(),
  from: z.any().nullish(),
  to: z.any().nullish(),
  source: z.string().nullish(),
});

export const FactorSchema = z.looseObject({
  time: z.string(),
  factor: z.number(),
});

export const ChartSchema = z.looseObject({
  status: z.string(),
  message: z.string().nullish(),
  candles: z.array(CandleSchema).default([]),
  factors: z.array(FactorSchema).default([]),
  corporateEvents: z.array(CorporateEventSchema).default([]),
  adjustment: z.number().nullish(),
});

export type ChartPayload = z.infer<typeof ChartSchema>;

export function toKlineBars(
  candles: ChartPayload['candles'],
  factors?: ChartPayload['factors'],
  adjustment = 3
) {
  const factorMap = new Map<string, number>();
  if (factors && factors.length > 0 && adjustment !== 0) {
    for (const f of factors) {
      if (typeof f.factor === 'number' && f.factor > 0) {
        factorMap.set(String(f.time).slice(0, 10), f.factor);
      }
    }
  }

  return [...candles]
    .sort((a, b) => String(a.time).localeCompare(String(b.time)))
    .map((candle) => {
      const timeKey = String(candle.time).slice(0, 10);
      const factor = (adjustment !== 0 && factorMap.size > 0 ? factorMap.get(timeKey) : undefined) ?? 1.0;
      // Rahavard: type7 = type0 × factor برای هر چهار قیمت، و حجمِ type7 عیناً
      // برابرِ type0 است (۸۴٬۴۵۲ ردیفِ اندازه‌گیری‌شده، صفر استثنا).
      return {
        timestamp: new Date(String(candle.time)).getTime(),
        open: candle.open * factor,
        high: candle.high * factor,
        low: candle.low * factor,
        close: candle.close * factor,
        volume: candle.volume ?? 0,
      };
    });
}

export function useChart(symbol: string, enabled = true, adjustment = 3) {
  return useQuery<ChartPayload>({
    queryKey: ['chart', symbol, adjustment],
    queryFn: ({ signal }) =>
      getJson(`/api/chart-db/${encodeURIComponent(symbol)}?adjustment=${adjustment}`, ChartSchema, signal),
    enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
