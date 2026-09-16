// nahayatnegar/lib/useNnData.ts -- وصل‌کردن دادهٔ واقعی ما به چارت پورت‌شدهٔ جمینای
// منبع: /api/chart/{symbol} (کندل + adjustEvents) و /api/index/tedpix (نمای کل بورس).
// رویدادهای تعدیل به CorporateAction نگاشت می‌شوند تا lib/adjustments.ts کار کند؛
// شکل ناشناخته ⇒ آرایهٔ خالی (صادقانه، بدون دادهٔ ساختگی).
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from 'klinecharts';
import type { CorporateAction } from './adjustments';

const CandleSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
});

const EventSchema = z.object({
  time: z.string().nullish(),
  dateStr: z.string().nullish(),
  timestamp: z.number().nullish(),
  type: z.string().nullish(),
  dpsAmount: z.number().nullish(),
  bonusPercent: z.number().nullish(),
  cashPercent: z.number().nullish(),
  preMeetingPrice: z.number().nullish(),
  postMeetingPrice: z.number().nullish(),
});
type RawEvent = z.infer<typeof EventSchema>;

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

const VALID_TYPES = new Set(['dps', 'capital_bonus', 'capital_cash', 'combined']);

/** نگاشت tolerant رویدادهای تعدیل؛ موارد ناقص حذف می‌شوند */
export function toCorporateActions(events: RawEvent[] | null | undefined): CorporateAction[] {
  if (!events) return [];
  const out: CorporateAction[] = [];
  for (const e of events) {
    const ts = typeof e.timestamp === 'number' ? e.timestamp : e.time ? Date.parse(`${e.time}T00:00:00Z`) : Number.NaN;
    const type = (e.type ?? '').trim();
    if (!Number.isFinite(ts) || !VALID_TYPES.has(type)) continue;
    out.push({
      timestamp: ts,
      dateStr: e.dateStr ?? e.time ?? '',
      type: type as CorporateAction['type'],
      dpsAmount: e.dpsAmount ?? undefined,
      bonusPercent: e.bonusPercent ?? undefined,
      cashPercent: e.cashPercent ?? undefined,
      preMeetingPrice: e.preMeetingPrice ?? 0,
      postMeetingPrice: e.postMeetingPrice ?? 0,
    });
  }
  return out;
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
  const actions = useMemo(() => toCorporateActions(q.data?.adjustEvents), [q.data]);
  return { data, actions, isLoading: q.isLoading, isError: q.isError, status: q.data?.status ?? null };
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
