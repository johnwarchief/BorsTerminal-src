// features/technical/api/useCandleFeed.ts -- کندل های روزانه با قالب klinecharts
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from '../../../vendor/klinecharts';

const HistorySchema = z.object({
  status: z.string(),
  candles: z
    .array(
      z.object({
        time: z.string(),
        open: z.number(),
        high: z.number(),
        low: z.number(),
        close: z.number(),
      }),
    )
    .nullish(),
  volumes: z.array(z.object({ time: z.string(), value: z.number() })).nullish(),
});

export function toKLineData(
  candles: { time: string; open: number; high: number; low: number; close: number }[],
  volumes: { time: string; value: number }[],
): KLineData[] {
  const volByTime = new Map(volumes.map((v) => [v.time, v.value]));
  const out: KLineData[] = [];
  for (const c of candles) {
    const ts = Date.parse(c.time + 'T00:00:00Z');
    if (!Number.isFinite(ts)) continue;
    if (![c.open, c.high, c.low, c.close].every((v) => Number.isFinite(v) && v > 0)) continue;
    out.push({ timestamp: ts, open: c.open, high: c.high, low: c.low, close: c.close, volume: volByTime.get(c.time) ?? 0 });
  }
  return out.sort((a, b) => a.timestamp - b.timestamp);
}

export function useCandleFeed(symbol: string) {
  const query = useQuery({
    queryKey: ['candles', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof HistorySchema>>(`/api/history/${encodeURIComponent(symbol)}`, { schema: HistorySchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
  const data = useMemo(
    () => toKLineData(query.data?.candles ?? [], query.data?.volumes ?? []),
    [query.data],
  );
  return { ...query, candles: data };
}
