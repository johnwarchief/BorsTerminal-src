// nahayatnegar/lib/useNnData.ts -- وصل‌کردن دادهٔ واقعی ما به چارت پورت‌شدهٔ جمینای
// منبع: /api/chart/{symbol} (کندل + adjustEvents) و /api/index/tedpix (نمای کل بورس).
// رویدادهای تعدیل به CorporateAction نگاشت می‌شوند تا lib/adjustments.ts کار کند؛
// شکل ناشناخته ⇒ آرایهٔ خالی (صادقانه، بدون دادهٔ ساختگی).
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from 'klinecharts';
import { mapBackendAdjustEvents } from './adjustments';

const CandleSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
});

const EventSchema = z.object({
  date: z.string().nullish(),
  ratio: z.number().nullish(),
});

const VolSchema = z.object({ time: z.string(), value: z.number() });

const ChartSchema = z.object({
  status: z.string(),
  candles: z.array(CandleSchema).nullish(),
  volumes: z.array(VolSchema).nullish(),
  adjustEvents: z.array(EventSchema).nullish(),
});

const TedpixSchema = z.object({
  status: z.string(),
  candles: z.array(CandleSchema).nullish(),
  volumes: z.array(VolSchema).nullish(),
});

/** کندل‌های API (رشته تاریخ) → KLineData (میلی‌ثانیه) */
export function toKLine(candles: { time: string; open: number; high: number; low: number; close: number }[], volByTime: Record<string, number> = {}): KLineData[] {
  const out: KLineData[] = [];
  for (const c of candles) {
    const ts = Date.parse(`${c.time}T00:00:00Z`);
    if (!Number.isFinite(ts)) continue;
    if (![c.open, c.high, c.low, c.close].every((v) => Number.isFinite(v) && v > 0)) continue;
    out.push({ timestamp: ts, open: c.open, high: c.high, low: c.low, close: c.close, volume: volByTime[c.time] ?? 0 } as unknown as KLineData);
  }
  return out.sort((a, b) => a.timestamp - b.timestamp);
}

export function useNnChartData(symbol: string, enabled = true) {
  const q = useQuery({
    queryKey: ['nn-chart', symbol],
    queryFn: ({ signal }) => http<z.infer<typeof ChartSchema>>(`/api/chart/${encodeURIComponent(symbol)}`, { schema: ChartSchema, signal }),
    enabled: enabled && symbol.length > 0,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
  const volMap = useMemo(() => {
    const m: Record<string, number> = {};
    for (const v of q.data?.volumes ?? []) m[v.time] = v.value;
    return m;
  }, [q.data]);
  const data = useMemo(() => toKLine(q.data?.candles ?? [], volMap), [q.data, volMap]);
  const actions = useMemo(() => mapBackendAdjustEvents(q.data?.adjustEvents ?? []), [q.data]);
  return { data, actions, isLoading: q.isLoading, isError: q.isError, refetch: q.refetch, status: q.data?.status ?? null };
}

/** نمای کل بورس (شاخص کل) */
export function useNnTedipx() {
  const q = useQuery({
    queryKey: ['nn-tedipx'],
    queryFn: ({ signal }) => http<z.infer<typeof TedpixSchema>>('/api/index/tedpix?limit=0', { schema: TedpixSchema, signal }),
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
  const volMap = useMemo(() => {
    const m: Record<string, number> = {};
    for (const v of q.data?.volumes ?? []) m[v.time] = v.value;
    return m;
  }, [q.data]);
  const data = useMemo(() => toKLine(q.data?.candles ?? [], volMap), [q.data, volMap]);
  return { data, isLoading: q.isLoading };
}
