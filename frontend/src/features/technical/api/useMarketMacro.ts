// features/technical/api/useMarketMacro.ts -- نمای کلان «کل بورس» برای تب تکنیکال بدون نماد
// اسکیمای بومیِ همین فیچر (مرز B1): از فیچر market چیزی import نمی‌شود؛ فقط
// اندپوینت‌های /api/mstat/* مصرف می‌شوند. هر اندپوینت به‌تنهایی می‌میرد و نبودِ
// داده «بدون داده» می‌شود، نه صفر ساختگی (Circuit Breaker).
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import type { KLineData } from '../../../vendor/klinecharts';
import { toKLineData } from './useCandleFeed';

const num = z.number().nullish();
const cell = z.union([z.number(), z.string(), z.null()]);
const arrCell = z.array(cell).nullish();

/** سری کلان درون‌روزی — تنها سری زمانی موجودِ کل بازار در بک‌اند */
export const MacroTimelineSchema = z.object({
  status: z.string(),
  mode: z.string().nullish(),
  ready: z.boolean().nullish(),
  points: z.number().nullish(),
  day: z.number().nullish(),
  series: z
    .object({
      val_bt: arrCell,
      flow_eq_bt: arrCell,
      flow_fixed_bt: arrCell,
      pos: arrCell,
      neg: arrCell,
      bq_bt: arrCell,
      sq_bt: arrCell,
      t: z.array(z.union([z.string(), z.number(), z.null()])).nullish(),
    })
    .nullish(),
  session_open: z.string().nullish(),
  session_close: z.string().nullish(),
  note: z.string().nullish(),
  source: z.string().nullish(),
});
export type MacroTimeline = z.infer<typeof MacroTimelineSchema>;

export const MacroSummarySchema = z.object({
  status: z.string(),
  asof: z.object({ d_even: num }).nullish(),
  rows: z
    .array(
      z.object({
        key: z.string(),
        label: z.string().nullish(),
        symbols: num,
        traded: num,
        pc_buy_m_toman: num,
        pc_sell_m_toman: num,
        buy_power: num,
        money_flow_b_toman: num,
      }),
    )
    .nullish(),
});
export type MacroSummary = z.infer<typeof MacroSummarySchema>;

export const MacroThermometerSchema = z.object({
  status: z.string(),
  positive: num,
  negative: num,
  zero: num,
  nodata: num,
  positive_pct: num,
  negative_pct: num,
  entry_opportunity: z.boolean().nullish(),
  entry_rule_pct: num,
});
export type MacroThermometer = z.infer<typeof MacroThermometerSchema>;

export const MacroDepthSchema = z.object({
  status: z.string(),
  depth_available: z.boolean().nullish(),
  symbols_with_depth: num,
  buy_queue_b_toman: num,
  sell_queue_b_toman: num,
  ratio: num,
  buy_queue_count: num,
  sell_queue_count: num,
});
export type MacroDepth = z.infer<typeof MacroDepthSchema>;

export const MacroSmartMoneySchema = z.object({
  status: z.string(),
  macro: z
    .object({
      value_hemat: num,
      state: z.string().nullish(),
      label: z.string().nullish(),
      trade_value_all_market_hemat: num,
      market_value_hemat: num,
      market_value_source: z.string().nullish(),
    })
    .nullish(),
  flow: z
    .object({
      eq_flow_b_toman: num,
      fixed_flow_b_toman: num,
      eq_inflow: z.boolean().nullish(),
      fixed_outflow: z.boolean().nullish(),
    })
    .nullish(),
});
export type MacroSmartMoney = z.infer<typeof MacroSmartMoneySchema>;

export type MarketMacroData = {
  timeline: MacroTimeline | null;
  summary: MacroSummary | null;
  thermometer: MacroThermometer | null;
  depth: MacroDepth | null;
  smartMoney: MacroSmartMoney | null;
};

/** ردیف «سهام، حق تقدم و ص.سهامی» از جدول خلاصه — سرانهٔ حقیقی و قدرت خرید */
export function macroEqRow(summary: MacroSummary | null | undefined) {
  return summary?.rows?.find((r) => r.key === 'eq_all') ?? null;
}

/** ارزش معاملات خرد (همت) و برچسب وضعیت از پول هوشمند */
export function macroHemat(sm: MacroSmartMoney | null | undefined): { value: number | null; state: string | null } {
  const value = sm?.macro?.value_hemat;
  return {
    value: typeof value === 'number' && Number.isFinite(value) ? value : null,
    state: sm?.macro?.state ?? null,
  };
}

export function useMarketMacro(enabled = true) {
  return useQuery({
    queryKey: ['technical-market-macro'],
    queryFn: async ({ signal }): Promise<MarketMacroData> => {
      const [timeline, summary, thermometer, depth, smartMoney] = await Promise.all([
        http<MacroTimeline>('/api/mstat/timeline?mode=cum', { schema: MacroTimelineSchema, signal }).catch(() => null),
        http<MacroSummary>('/api/mstat/summary', { schema: MacroSummarySchema, signal }).catch(() => null),
        http<MacroThermometer>('/api/mstat/thermometer', { schema: MacroThermometerSchema, signal }).catch(() => null),
        http<MacroDepth>('/api/mstat/depth', { schema: MacroDepthSchema, signal }).catch(() => null),
        http<MacroSmartMoney>('/api/mstat/smart-money', { schema: MacroSmartMoneySchema, signal }).catch(() => null),
      ]);
      return { timeline, summary, thermometer, depth, smartMoney };
    },
    enabled,
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

// ============================================================================
// لایهٔ دادهٔ واحد «کل بورس» — اولویت: شاخص کل واقعی (TEDPIX)، fallback: سری کلان
// ============================================================================

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

/** سری کلان (fallback) — همان /api/mstat/timeline */
export function useMarketSeries() {
  const q = useMarketMacro();
  const data = useMemo(() => buildMarketSeries(q.data?.timeline), [q.data]);
  return { data, isLoading: q.isLoading, isError: q.isError };
}

/** اسکیمای پاسخ /api/index/tedpix — خطا ۵۰۲ با candles خالی */
export const TedpixSchema = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  has_volume: z.boolean().nullish(),
  candles: z
    .array(z.object({ time: z.string(), open: z.number(), high: z.number(), low: z.number(), close: z.number() }))
    .nullish(),
});
export type TedpixFeed = z.infer<typeof TedpixSchema>;

/** خالص-آزمون‌پذیر: یک درخواست شاخص کل (برای تست با fetch ماک) */
export async function fetchTedipx(signal?: AbortSignal): Promise<TedpixFeed> {
  return http<TedpixFeed>('/api/index/tedpix?limit=0', { schema: TedpixSchema, signal });
}

/** سری روزانهٔ واقعی شاخص کل — بدون حجم */
export function useTedipxIndex() {
  return useQuery({
    queryKey: ['technical-tedpix'],
    queryFn: ({ signal }) => fetchTedipx(signal),
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/** نتیجهٔ لایهٔ واحد: کندل شاخص واقعی، یا سری کلان، یا هیچ */
export type WholeMarket =
  | { kind: 'candles'; source: string; title: string; candles: KLineData[] }
  | { kind: 'macro'; source: string; title: string; unit: string; points: MarketSeriesPoint[]; note: string | null }
  | { kind: 'none'; source: string; title: string };

/** خالص: انتخاب منبع با اولویت شاخص واقعی (کندل → سری کلان → هیچ) */
export function buildWholeMarket(tedipxCandles: KLineData[], macro: MarketSeries | null): WholeMarket {
  if (tedipxCandles.length >= 2) {
    return { kind: 'candles', source: TEDPIX_SOURCE, title: TEDPIX_TITLE, candles: tedipxCandles };
  }
  if (macro) {
    return { kind: 'macro', source: macro.source, title: macro.title, unit: macro.unit, points: macro.points, note: macro.note };
  }
  return { kind: 'none', source: TEDPIX_SOURCE, title: TEDPIX_TITLE };
}

/** هوک مصرفی: شاخص کل موفق → چارت کندل؛ در غیر این صورت fallback صادقانه به سری کلان */
export function useWholeMarket() {
  const tedpix = useTedipxIndex();
  const macro = useMarketSeries();
  const data = useMemo(() => {
    const ok = tedpix.data?.status === 'success';
    const candles = ok ? toKLineData(tedpix.data?.candles ?? [], []) : [];
    return buildWholeMarket(candles, macro.data);
  }, [tedpix.data, macro.data]);
  return { data, isLoading: tedpix.isLoading || macro.isLoading };
}
