// features/technical/api/useCandleFeed.ts -- کندل های روزانه با قالب klinecharts
// منبع اول: /api/chart/{symbol} (کندل تعدیل‌شدهٔ TSETMC؛ نرمال‌سازی عربی/فارسی و LAST).
// fallback: /api/history/{symbol} (DB محلی) وقتی منبع اول خطا/خالی برگرداند (بدون رگرسیون).
// علت: /api/history تطبیق نماد را دقیق می‌کند و برای نمادهای ذخیره‌شده با «ك» عربی خالی
// برمی‌گرداند، در حالی که /api/chart سالم است (نمونهٔ تأییدشده: کانسار).
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from '../../../vendor/klinecharts';

const RawCandle = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
});
const RawVolume = z.object({ time: z.string(), value: z.number() });

/** رویدادِ تعدیلِ خام — همان شکلی که mapBackendAdjustEvents می‌خواند */
export const RawAdjustEvent = z.object({
  date: z.string().nullish(),
  dateStr: z.string().nullish(),
  timestamp: z.number().nullish(),
  time: z.number().nullish(),
  ratio: z.number().nullish(),
});
export type RawAdjustEvent = z.infer<typeof RawAdjustEvent>;

/** رویدادِ شرکتیِ مبدأ (TSETMC) — فقط برایِ نشانه‌گذاری، بی‌هیچ ضریبِ تازه */
export const RawCorporateEvent = z.object({
  date: z.string().nullish(),
  type: z.string().nullish(),
  from: z.number().nullish(),
  to: z.number().nullish(),
  source: z.string().nullish(),
});
export type RawCorporateEvent = z.infer<typeof RawCorporateEvent>;

/** /api/chart/{symbol} — کندل تعدیل‌شده؛ خطا شکل {status:'error', message} دارد */
const ChartSchema = z.object({
  status: z.string(),
  candles: z.array(RawCandle).nullish(),
  volumes: z.array(RawVolume).nullish(),
  count: z.number().nullish(),
  adjustEvents: z.array(RawAdjustEvent).nullish(),
  corporateEvents: z.array(RawCorporateEvent).nullish(),
});

/** /api/history/{symbol} — تاریخچهٔ محلی */
const HistorySchema = z.object({
  status: z.string(),
  candles: z.array(RawCandle).nullish(),
  volumes: z.array(RawVolume).nullish(),
});

export type CandleSource = 'chart' | 'history';
export type CandleFeedResult = {
  status: string;
  source: CandleSource;
  candles: { time: string; open: number; high: number; low: number; close: number }[];
  volumes: { time: string; value: number }[];
  /**
   * رویدادهای تعدیلِ همان نماد. بدونِ این، سریِ دومِ همسنجی با مبنای سریِ اول
   * نمی‌آید و یک افزایشِ سرمایه وسطِ بازه، خطِ مقایسه را بی‌دلیل می‌شکند.
   */
  adjustEvents: RawAdjustEvent[];
  /** رویدادهایِ شرکتیِ مبدأ برایِ نشانگرِ چارت (نمایش؛ درِ زنجیرۀ تعدیل نمی‌نشیند) */
  corporateEvents: RawCorporateEvent[];
};

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

/**
 * زنجیرهٔ منبع داده: /api/chart (تعدیل‌شده) → در صورت خطا/خالی، /api/history (محلی).
 * خالص‌سازی‌شده از هوک تا در تست با fetch ماک قابل آزمون باشد.
 */
export async function fetchCandleFeed(symbol: string, signal?: AbortSignal): Promise<CandleFeedResult> {
  try {
    const chart = await http<z.infer<typeof ChartSchema>>(`/api/chart/${encodeURIComponent(symbol)}`, {
      schema: ChartSchema,
      signal,
    });
    if (chart.status === 'success' && (chart.candles?.length ?? 0) > 0) {
      return {
        status: 'success',
        source: 'chart',
        candles: chart.candles ?? [],
        volumes: chart.volumes ?? [],
        adjustEvents: chart.adjustEvents ?? [],
        corporateEvents: chart.corporateEvents ?? [],
      };
    }
  } catch {
    // منبع اول در دسترس نیست — به تاریخچهٔ محلی برمی‌گردیم
  }
  const history = await http<z.infer<typeof HistorySchema>>(`/api/history/${encodeURIComponent(symbol)}`, {
    schema: HistorySchema,
    signal,
  });
  return {
    status: history.status,
    source: 'history',
    candles: history.candles ?? [],
    volumes: history.volumes ?? [],
    adjustEvents: [],
    corporateEvents: [],
  };
}

export function useCandleFeed(symbol: string) {
  const query = useQuery({
    queryKey: ['candles', symbol],
    queryFn: ({ signal }) => fetchCandleFeed(symbol, signal),
    enabled: symbol.length > 0,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
  const data = useMemo(() => toKLineData(query.data?.candles ?? [], query.data?.volumes ?? []), [query.data]);
  return { ...query, candles: data, source: query.data?.source ?? null };
}
