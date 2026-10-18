// features/market/api/useMarketStatusFeed.ts -- خواننده‌های «وضعیت بازار»
//
// چرا جدا از useMarketPulse: نبض بازار رأیِ «ورود/صبر/مخالف» می‌سازد و یک‌جا
// بار می‌کند؛ صفحۀ «وضعیت بازار» همان بانک را در نقشِ پخش‌شده می‌خواهد (توزیع
// درصد، تفکیک مشتری، فازهای نشست، نظارت اصلی) و هر بلوک سنجشِ خودش را دارد.
// هیچ عددی اینجا ساخته نمی‌شود: هر خانۀ null «بی‌داده» می‌ماند.
import { useQuery, type QueryFunctionContext } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { toFaDigits } from '@shared/lib/fmt';
import { SNAPSHOT_POLL_MS } from '../lib/intradayCache';

const num = z.number().nullish();
const str = z.string().nullish();

/** لحظۀ اسنپ‌شاتِ خودِ موتور — برای «داده از کِی است» در هر بلوک */
export const AsOfSchema = z.object({
  d_even: num,
  h_even: num,
  client_d_even: num,
  client_lag_days: z.boolean().nullish(),
  depth: z.boolean().nullish(),
  top50: num,
  n: num,
});
export type AsOf = z.infer<typeof AsOfSchema>;

const bucket = z.object({
  key: z.string(),
  label: z.string(),
  color: z.string(),
  count: z.number(),
});

export const HistogramSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  group: str,
  basis: str,
  traded_only: z.boolean().nullish(),
  histo12: z.array(bucket).nullish(),
  histo7: z.array(bucket).nullish(),
  known: num,
  nodata: num,
  total: num,
  not_traded: num,
  source: str,
});
export type HistogramFeed = z.infer<typeof HistogramSchema>;

/** کلید + آدرس + قراردادِ هیستوگرام، یک‌جا (همان دلیلی که برایِ کارت‌های شاخص). */
export function histogramQueryOptions(group = 'all') {
  return {
    queryKey: ['mstat-histogram', group],
    queryFn: ({ signal }: QueryFunctionContext) =>
      http<HistogramFeed>(`/api/mstat/histogram?group=${encodeURIComponent(group)}`, {
        schema: HistogramSchema,
        signal,
      }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  };
}

export function useMstatHistogram(group = 'all') {
  return useQuery(histogramQueryOptions(group));
}

const side = z.object({
  buy_count: num,
  buy_b_toman: num,
  buy_pct: num,
  sell_count: num,
  sell_b_toman: num,
  sell_pct: num,
});

export const ClientSplitSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  tab: str,
  symbols: num,
  retail: side.nullish(),
  institutional: side.nullish(),
  pc_buy_m_toman: num,
  pc_sell_m_toman: num,
  power: num,
  money_flow_b_toman: num,
  source: str,
});
export type ClientSplitFeed = z.infer<typeof ClientSplitSchema>;

export function useMstatClientSplit(tab = 'all') {
  return useQuery({
    queryKey: ['mstat-clientsplit', tab],
    queryFn: ({ signal }) =>
      http<ClientSplitFeed>(`/api/mstat/clientsplit?tab=${encodeURIComponent(tab)}`, {
        schema: ClientSplitSchema,
        signal,
      }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

const phase = z.object({ key: z.string(), label: z.string(), count: z.number() });

export const PhasesSchema = z.object({
  status: z.string(),
  points: num,
  ready: z.boolean().nullish(),
  red: z.array(phase).nullish(),
  green: z.array(phase).nullish(),
  source: str,
});
export type PhasesFeed = z.infer<typeof PhasesSchema>;

export function useMstatPhases() {
  return useQuery({
    queryKey: ['mstat-phases'],
    queryFn: ({ signal }) =>
      http<PhasesFeed>('/api/mstat/phases', { schema: PhasesSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

// ── مرحلِ جلسه از وضعیتِ رسمیِ بازار (بند ۵ مأموریت، 1405-07-20) ─────────────
// هیچ حکمی اینجا ساخته نمی‌شود: `verdict_allowed` و فهرستِ «چه چیزی در این
// مرحل معنا ندارد» از خودِ `market_phase.py` می‌آید. `official=false` یعنی
// برنامه فقط تقویم را دیده است — رابط همین را صریح می‌نویسد.
export const SessionPhaseSchema = z.object({
  status: z.string(),
  phase: z.string(),
  label: z.string(),
  phase_source: str,
  official: z.boolean().nullish(),
  official_state: str,
  official_state_title: str,
  session_day: num,
  activity_h_even: num,
  is_live: z.boolean().nullish(),
  verdict_allowed: z.boolean().nullish(),
  computable: z.record(z.string(), z.boolean()).nullish(),
  not_computable: z.array(z.string()).nullish(),
  why_not: z.record(z.string(), z.string()).nullish(),
  data_updated_at: str,
  clock_now: str,
  session_start: str,
  session_end: str,
  source: str,
});
export type SessionPhaseFeed = z.infer<typeof SessionPhaseSchema>;

export function useMstatSessionPhase() {
  return useQuery({
    queryKey: ['mstat-session-phase'],
    queryFn: ({ signal }) =>
      http<SessionPhaseFeed>('/api/mstat/phase', { schema: SessionPhaseSchema, signal }),
    staleTime: 30_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

export const MainWatchRowSchema = z.object({
  symbol: z.string(),
  ins_code: str,
  name: str,
  industry: str,
  cls: str,
  kind: str,
  vol_b_shares: num,
  trades: num,
  val_b_toman: num,
  p_last: num,
  p_closing: num,
  /** بدنۀِ همین نشست برایِ ویجتِ «کندل روز» (`FormingCandle` درِ تبِّ تابلو)؛
   *  تهی یعنی اولینِ مبادله هنوز نیفتاده — کندلِ ساختگی ساخته نمی‌شود. */
  p_first: num,
  p_max: num,
  p_min: num,
  pct_last: num,
  pct_close: num,
  clock_pct: num,
  pc_buy: num,
  pc_sell: num,
  power: num,
  flow_b_toman: num,
  /** هفت پرچمِ تابلو، عیناً از `tape_flags.apply_tape_flags` (نه محاسبۀ دوم).
   *  null یعنی این نماد در فیدِ تابلو نبود؛ با «پرچمی ندارد» یکی نیست. */
  tape_flags: z
    .object({
      f_clock: z.boolean(), f_susp: z.boolean(), f_jet: z.boolean(), f_roobi: z.boolean(),
      f_noqteh: z.boolean(), f_smart: z.boolean(), f_legal: z.boolean(),
    })
    .nullish(),
});
export type MainWatchRow = z.infer<typeof MainWatchRowSchema>;

export const MainWatchSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  group: str,
  industry: str,
  sort: str,
  sort_col: str,
  desc: z.boolean().nullish(),
  total: num,
  clock_hits: num,
  clock_rule: z
    .object({ min_pct: num, min_trades: num, min_price: num })
    .nullish(),
  rows: z.array(MainWatchRowSchema).nullish(),
  /** 'api/market' = پرچم‌ها از فیدِ تابلو منتقل شده‌اند؛ 'unavailable' = منبع
   *  نرسید و جدول باید صریح بگوید «پرچم نرسید»، نه اینکه بج‌ها غیب شوند. */
  tape_flags_source: z.string().nullish(),
  source: str,
});
export type MainWatchFeed = z.infer<typeof MainWatchSchema>;

export function useMstatMainwatch(group = 'eq_all', industry = '') {
  return useQuery({
    queryKey: ['mstat-mainwatch', group, industry],
    queryFn: ({ signal }) =>
      http<MainWatchFeed>(
        `/api/mstat/mainwatch?group=${encodeURIComponent(group)}&industry=${encodeURIComponent(industry)}`,
        { schema: MainWatchSchema, signal },
      ),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
    refetchOnWindowFocus: false,
  });
}

/** «۱۰:۲۳» از h_even، خودِ پاسخ. تاریخِ d_even قالبِ ثابتی ندارد
 *  (همان قیدِ WatchOrderBookPanel)، پس فقط ساعت نشان داده می‌شود و بی‌asof هیچ
 *  ساعتی وعده داده نمی‌شود. */
export function asOfText(a: AsOf | null | undefined): string | null {
  const h = a?.h_even;
  if (typeof h !== 'number' || h <= 0) return null;
  const s = String(h).padStart(6, '0');
  return toFaDigits(`${s.slice(0, 2)}:${s.slice(2, 4)}`);
}
