// features/portfolio/api/useWatchCandles.ts -- کندل‌هایِ روزانه برایِ چارت کوچکِ دیده‌بان
//
// منبع: `GET /api/chart/{symbol}` (کندل تعدیل‌شدۀِ TSETMC — همان قراردادی که
// `features/technical/api/useCandleFeed.ts` می‌خواند؛ اینجا فقط نسخۀِ فشرده‌اش
// برایِ پنلِ «دیده‌بان بازار» است، چون importِ بینِ featureها ممنوع است).
// خطایِ API ≠ نتیجهٔ خالی: queryKey با نماد، بی‌placeholderData، پس با عوض
// شدنِ انتخاب، کندلِ نمادِ قبلی زیرِ نمادِ جدید نمایش داده نمی‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const CandleSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
});

const VolumeSchema = z.object({
  time: z.string(),
  value: z.number(),
});

const ChartSchema = z.object({
  status: z.string(),
  candles: z.array(CandleSchema).nullish(),
  volumes: z.array(VolumeSchema).nullish(),
  count: z.number().nullish(),
});

export type WatchCandle = z.infer<typeof CandleSchema>;
export type WatchCandlesResult = { candles: WatchCandle[]; volumes: { time: string; value: number }[] };

/** حداکثرِ سطوحِ دیدیِ چارت کوچک — بیشترش درِ ۳۰۰px خوانا نیست */
export const WATCH_CHART_LAST = 40;

function pickRecent(chart: z.infer<typeof ChartSchema>): WatchCandlesResult {
  const sorted = [...(chart.candles ?? [])].sort((a, b) => (a.time < b.time ? -1 : 1));
  const candles = sorted.filter((c) =>
    [c.open, c.high, c.low, c.close].every((v) => Number.isFinite(v) && v > 0),
  ).slice(-WATCH_CHART_LAST);
  const keep = new Set(candles.map((c) => c.time));
  return { candles, volumes: (chart.volumes ?? []).filter((v) => keep.has(v.time)) };
}

export function useWatchCandles(symbol: string) {
  return useQuery({
    queryKey: ['watch-candles', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof ChartSchema>>(`/api/chart/${encodeURIComponent(symbol)}`, { schema: ChartSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    select: pickRecent,
  });
}
