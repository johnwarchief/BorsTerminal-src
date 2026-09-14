// features/technical/api/useMarketSeries.ts -- لایهٔ دادهٔ واحد برای سری «کل بورس»
// اولویت: سری واقعی شاخص کل (TEDPIX) از /api/index/tedpix → چارت کندل کل بازار.
// fallback: سری کلان /api/mstat/timeline → چارت خطی (صادقانه، تا وقتی شاخص نرسیده).
// مصرف‌کننده (MarketOverview) فقط WholeMarket را می‌بیند؛ افزودن منبع جدید بدون refactor.
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from '../../../vendor/klinecharts';
import { toKLineData } from './useCandleFeed';
import { useMarketMacro, type MacroTimeline } from './useMarketMacro';

/** منبع سری کلان (fallback) */
export const WHOLE_MARKET_SERIES_SOURCE = 'local:mstat-timeline';
/** منبع سری واقعی شاخص کل */
export const TEDPIX_SOURCE = 'tsetmc:tedpix';
export const TEDPIX_TITLE = 'شاخص کل بورس (TEDPIX)';

export type MarketSeriesPoint = { label: string | number | null; value: number };

export type MarketSeries = {
  key: 'whole-market';
  title: string;
  unit: string;
  source: string;
  ready: boolean;
  points: MarketSeriesPoint[];
  note: string | null;
  day: number | null;
};

/** خالص: ساخت سری کلان از پاسخ تایم‌لاین (fallback) */
export function buildMarketSeries(timeline: MacroTimeline | null | undefined): MarketSeries | null {
  if (!timeline) return null;
  const raw = timeline.series?.val_bt ?? [];
  const labels = timeline.series?.t ?? [];
  const points: MarketSeriesPoint[] = [];
  raw.forEach((v, i) => {
    const n = typeof v === 'string' ? Number(v) : v;
    if (typeof n === 'number' && Number.isFinite(n)) points.push({ label: labels[i] ?? null, value: n });
  });
  return {
    key: 'whole-market',
    title: 'ارزش معاملات خرد (سری تجمعی درون‌روزی)',
    unit: 'سری کلان',
    source: timeline.source ?? WHOLE_MARKET_SERIES_SOURCE,
    ready: timeline.ready === true && points.length >= 2,
    points,
    note: timeline.note ?? null,
    day: timeline.day ?? null,
  };
}

/** نتیجهٔ لایهٔ واحد: کندل شاخص واقعی، یا سری کلان، یا هیچ */
export type WholeMarket =
  | { kind: 'candles'; source: string; title: string; candles: KLineData[] }
  | { kind: 'macro'; source: string; title: string; series: MarketSeries }
  | { kind: 'none'; source: string; title: string };

/** خالص و آزمون‌پذیر: انتخاب منبع با اولویت شاخص واقعی */
export function buildWholeMarket(tedipxCandles: KLineData[], macro: MarketSeries | null): WholeMarket {
  if (tedipxCandles.length >= 2) {
    return { kind: 'candles', source: TEDPIX_SOURCE, title: TEDPIX_TITLE, candles: tedipxCandles };
  }
  if (macro) {
    return { kind: 'macro', source: macro.source, title: macro.title, series: macro };
  }
  return { kind: 'none', source: TEDPIX_SOURCE, title: TEDPIX_TITLE };
}

const TedpixSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  has_volume: z.boolean().nullish(),
  candles: z
    .array(z.object({ time: z.string(), open: z.number(), high: z.number(), low: z.number(), close: z.number() }))
    .nullish(),
});

export type TedpixFeed = z.infer<typeof TedpixSchema>;

/** سری روزانهٔ واقعی شاخص کل — بدون حجم (has_volume=false) */
export function useTedipxIndex() {
  return useQuery({
    queryKey: ['technical-tedpix'],
    queryFn: ({ signal }) => http<TedpixFeed>('/api/index/tedpix?limit=0', { schema: TedpixSchema, signal }),
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/** هوک مصرفی: سری «کل بورس» پشت یک انتزاع (کندل شاخص → سری کلان) */
export function useWholeMarket() {
  const tedpix = useTedipxIndex();
  const macro = useMarketSeries();
  const data = useMemo(
    () => buildWholeMarket(toKLineData(tedpix.data?.candles ?? [], []), macro.data),
    [tedpix.data, macro.data],
  );
  return { data, isLoading: tedpix.isLoading || macro.isLoading };
}

/** هوک سری کلان (fallback) — همان /api/mstat/timeline */
export function useMarketSeries() {
  const q = useMarketMacro();
  const data = useMemo(() => buildMarketSeries(q.data?.timeline), [q.data]);
  return { data, isLoading: q.isLoading, isError: q.isError };
}
