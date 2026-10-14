// features/market/api/useMarketPanels.ts -- خواننده‌های پنل‌های «وضعیت بازار»
//
// هر بلوکِ صفحۀ بازسازی‌شدۀ «وضعیت بازار» (مرجع: Binder1.pdf) از یک اندپوینتِ
// مستقلِ mstat می‌آید. چرا جدا از `useMarketStatusFeed`: آن فایل قراردادهایِ
// نبضِ پیشین را قفل کرده و تست‌هایش رویِ همان کلیدها هستند؛ افزودنِ هفت قرارداد
// تازه به آن، یک فایلِ ۲۵۰ سطری را به ۷۰۰ سطر می‌برد و مرزِ «چه چیزی قبلاً
// تضمین شده» را گم می‌کرد.
//
// سه قاعده که همه‌جا رعایت شده:
// ۱) هیچ عددی درِ رابط ساخته نمی‌شود. هر خانۀ nullable واقعاً null می‌ماند و
//    کامپوننت «بی‌داده» نشان می‌دهد، نه صفر.
// ۲) یکا و مبنا از خودِ پاسخ می‌آیند (`unit`, `basis`, `formula`) — پس دو
//    جایِ صفحه دو خوانشِ متفاوت از یک مفهوم ندارند.
// ۳) `no_source` / `blockers` بخشی از قراردادند، نه خطا: منبعِ نرسیده با علت
//    می‌آید و رابط همان علت را می‌نویسد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { SNAPSHOT_POLL_MS } from '../lib/intradayCache';
import { AsOfSchema, type AsOf } from './useMarketStatusFeed';

const num = z.number().nullish();
const str = z.string().nullish();

/** علتِ نیامدنِ داده — همان چیزی که پنل باید روِ بنویسد، نه اینکه صفر بگذارد */
export const ReasonSchema = z.object({
  key: z.string(),
  label: z.string(),
  why: z.string(),
  needed: str,
  official_attribution_available: z.boolean().nullish(),
});
export type PanelReason = z.infer<typeof ReasonSchema>;

/** ردیفِ مشترکِ پنل‌های رتبه‌بندی‌شده: هر مقدار + طولِ میله‌اش از خودِ مقدار */
export const RankedRowSchema = z.object({
  rank: num,
  symbol: z.string(),
  ins_code: str,
  name: str,
  industry: str,
  bar_pct: num,
  tone: z.enum(['pos', 'neg', 'zero', 'nodata']),
  pct: num,
  p_closing: num,
});
export type RankedRow = z.infer<typeof RankedRowSchema>;

export const RankedPanelSchema = z.object({
  key: z.string(),
  title: z.string(),
  unit: str,
  formula: str,
  value_field: str,
  candidates: num,
  note: str,
  rows: z.array(RankedRowSchema.passthrough()).nullish(),
});
export type RankedPanel = z.infer<typeof RankedPanelSchema>;

const poll = {
  staleTime: 60_000,
  gcTime: 10 * 60_000,
  refetchInterval: () => sessionPollMs(SNAPSHOT_POLL_MS),
  refetchOnWindowFocus: false,
};

// ═══════════════════════════════════════════════════════ نقشۀ بازار (صفحۀ ۲/۱۲)
export const TreemapNodeSchema = z.object({
  symbol: z.string(),
  ins_code: str,
  name: str,
  industry: str,
  cls: str,
  kind: str,
  pct: num,
  tone: z.enum(['pos', 'neg', 'zero', 'nodata']),
  /** سطحِ مستطیل — از معیارِ انتخابی می‌آید، نه از عددِ ثابت */
  size: z.number(),
  size_field: str,
  unit: str,
  share_pct: num,
  p_closing: num,
  value_b_toman: num,
  volume_m_share: num,
  market_cap_b_toman: num,
  trades: num,
});
export type TreemapNode = z.infer<typeof TreemapNodeSchema>;

export const TreemapGroupSchema = z.object({
  industry: z.string(),
  symbols: z.number(),
  size: z.number(),
  share_pct: num,
  pos: z.number(),
  neg: z.number(),
  nodata: z.number(),
});
export type TreemapGroup = z.infer<typeof TreemapGroupSchema>;

export const TreemapSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  computed_at: str,
  group: str,
  group_label: str,
  industry: str,
  metric: z.string(),
  metric_label: str,
  metric_unit: str,
  basis: str,
  formula: z.record(z.string(), z.string()).nullish(),
  total_nodes: num,
  shown: num,
  skipped_nodata: num,
  total_size: num,
  rows: z.array(TreemapNodeSchema).nullish(),
  groups: z.array(TreemapGroupSchema).nullish(),
  no_source: z.array(ReasonSchema).nullish(),
  source: str,
});
export type TreemapFeed = z.infer<typeof TreemapSchema>;

export type TreemapMetric = 'value' | 'volume' | 'cap' | 'trades';

export function useMstatTreemap(group = 'eq_all', industry = '', metric: TreemapMetric = 'value') {
  return useQuery({
    queryKey: ['mstat-treemap', group, industry, metric],
    queryFn: ({ signal }) =>
      http<TreemapFeed>(
        `/api/mstat/treemap?group=${encodeURIComponent(group)}` +
          `&industry=${encodeURIComponent(industry)}&metric=${encodeURIComponent(metric)}`,
        { schema: TreemapSchema, signal },
      ),
    ...poll,
  });
}

// ═══════════════════════════════════════════════════ برترین‌ها (صفحۀ ۸)
export const TopsIndexSchema = z.object({
  d_even: num,
  last: num,
  change: num,
  pct: num,
  ew_last: num,
  ew_change: num,
  ew_pct: num,
});
export type TopsIndex = z.infer<typeof TopsIndexSchema>;

export const TopsSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  computed_at: str,
  group: str,
  group_label: str,
  panels: z.array(RankedPanelSchema).nullish(),
  index: TopsIndexSchema.nullish(),
  market_total_source: str,
  reconciliation: z
    .object({
      sum_of_impacts: num,
      official_index_change: num,
      rel_diff_pct: num,
      meaning: str,
    })
    .nullish(),
  blockers: z.array(ReasonSchema).nullish(),
  traded_only: z.boolean().nullish(),
  source: str,
});
export type TopsFeed = z.infer<typeof TopsSchema>;

export function useMstatTops(group = 'eq_all') {
  return useQuery({
    queryKey: ['mstat-tops', group],
    queryFn: ({ signal }) =>
      http<TopsFeed>(`/api/mstat/tops?group=${encodeURIComponent(group)}`, {
        schema: TopsSchema,
        signal,
      }),
    ...poll,
  });
}

// ════════════════════════════════════════ سفارش‌ها و تغییرِ مالکیت (صفحۀ ۹)
export const OrderFlowRowSchema = RankedRowSchema.extend({
  buy_order_m_share: num,
  sell_order_m_share: num,
  imbalance_m_share: num,
  imbalance_pct_of_traded: num,
  executed_m_share: num,
  buy_queue_b_toman: num,
  sell_queue_b_toman: num,
  queue: str,
});
export type OrderFlowRow = z.infer<typeof OrderFlowRowSchema>;

export const OrderFlowsSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  computed_at: str,
  group: str,
  orders_available: z.boolean().nullish(),
  symbols_with_orders: num,
  symbols_in_scope: num,
  unit: str,
  basis: str,
  formula: z.record(z.string(), z.string()).nullish(),
  totals: z
    .object({
      buy_order_m_share: num,
      sell_order_m_share: num,
      net_order_m_share: num,
      executed_m_share: num,
      buy_sell_ratio: num,
      order_vs_executed_note: str,
    })
    .nullish(),
  buy_panels: RankedPanelSchema.nullish(),
  sell_panels: RankedPanelSchema.nullish(),
  no_source: z.array(ReasonSchema).nullish(),
  source: str,
});
export type OrderFlowsFeed = z.infer<typeof OrderFlowsSchema>;

export function useMstatOrderFlows(group = 'all') {
  return useQuery({
    queryKey: ['mstat-orderflows', group],
    queryFn: ({ signal }) =>
      http<OrderFlowsFeed>(`/api/mstat/orderflows?group=${encodeURIComponent(group)}`, {
        schema: OrderFlowsSchema,
        signal,
      }),
    ...poll,
  });
}

export const OwnershipRowSchema = RankedRowSchema.extend({
  legal_net_share: num,
  real_net_share: num,
  legal_net_m_share: num,
  real_net_m_share: num,
  legal_net_pct_of_capital: num,
  legal_buy_pct_of_volume: num,
  legal_sell_pct_of_volume: num,
  executed_m_share: num,
  value_source: str,
});
export type OwnershipRow = z.infer<typeof OwnershipRowSchema>;

export const OwnershipSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  computed_at: str,
  group: str,
  symbols_with_client_data: num,
  unit: str,
  basis: str,
  formula: z.record(z.string(), z.string()).nullish(),
  client_data_lags_session: z.boolean().nullish(),
  totals: z.object({ legal_net_m_share: num, real_net_m_share: num }).nullish(),
  to_legal_panel: RankedPanelSchema.nullish(),
  to_real_panel: RankedPanelSchema.nullish(),
  no_source: z.array(ReasonSchema).nullish(),
  source: str,
});
export type OwnershipFeed = z.infer<typeof OwnershipSchema>;

export function useMstatOwnership(group = 'all') {
  return useQuery({
    queryKey: ['mstat-ownership', group],
    queryFn: ({ signal }) =>
      http<OwnershipFeed>(`/api/mstat/ownership?group=${encodeURIComponent(group)}`, {
        schema: OwnershipSchema,
        signal,
      }),
    ...poll,
  });
}

// ════════════════════════════════════════════ کارت‌های شاخص (صفحۀ ۶/۷)
export const IndexCardSchema = z.object({
  key: z.string(),
  label: z.string(),
  available: z.boolean(),
  value: num,
  change: num,
  pct: num,
  unit: str,
  tone: z.enum(['pos', 'neg', 'zero', 'nodata']),
  spark: z.array(z.number().nullish()).nullish(),
  formula: str,
  asof_d_even: num,
});
export type IndexCard = z.infer<typeof IndexCardSchema>;

export const IndexCardsSchema = z.object({
  status: z.string(),
  computed_at: str,
  cards: z.array(IndexCardSchema).nullish(),
  source: str,
  history_points: num,
  history_days: z.array(z.number()).nullish(),
  trades: num,
  market_total_b_toman: num,
  market_total_source: str,
  note: str,
  blockers: z.array(ReasonSchema).nullish(),
});
export type IndexCardsFeed = z.infer<typeof IndexCardsSchema>;

export function useMstatIndexCards(days = 30) {
  return useQuery({
    queryKey: ['mstat-indexcards', days],
    queryFn: ({ signal }) =>
      http<IndexCardsFeed>(`/api/mstat/indexcards?days=${days}`, {
        schema: IndexCardsSchema,
        signal,
      }),
    ...poll,
  });
}

// ═══════════════════════════════════ طلا، سکه و صندوق‌های طلا (صفحۀ ۱/۳/۱۰/۱۱/۱۲)
export const GoldSymbolSchema = z.object({
  symbol: z.string(),
  ins_code: str,
  name: str,
  cls: str,
  kind: str,
  p_closing: num,
  p_last: num,
  p_yesterday: num,
  pct: num,
  tone: z.enum(['pos', 'neg', 'zero', 'nodata']),
  value_b_toman: num,
  volume_m_share: num,
  market_cap_b_toman: num,
  trades: num,
  value_share_pct: num,
  spark: z.array(z.object({ d: str, v: num })).nullish(),
});
export type GoldSymbol = z.infer<typeof GoldSymbolSchema>;

export const GoldMarketSchema = z.object({
  status: z.string(),
  asof: AsOfSchema.nullish(),
  computed_at: str,
  unit: z.record(z.string(), z.string()).nullish(),
  basis: str,
  symbols: z.array(GoldSymbolSchema).nullish(),
  symbols_count: num,
  total_value_b_toman: num,
  history_days: num,
  history_source: str,
  no_source: z.array(ReasonSchema).nullish(),
  access_limits: z.array(ReasonSchema).nullish(),
  source: str,
});
export type GoldMarketFeed = z.infer<typeof GoldMarketSchema>;

export function useMstatGold(historyDays = 60) {
  return useQuery({
    queryKey: ['mstat-gold', historyDays],
    queryFn: ({ signal }) =>
      http<GoldMarketFeed>(`/api/mstat/gold?history_days=${historyDays}`, {
        schema: GoldMarketSchema,
        signal,
      }),
    ...poll,
  });
}

export const SymbolHistorySchema = z.object({
  status: z.string(),
  symbol: str,
  computed_at: str,
  available: z.boolean(),
  points: num,
  days: num,
  unit: str,
  basis: str,
  series: z.array(z.object({ d: str, v: num })).nullish(),
  peak: z.object({ value: num, at: str }).nullish(),
  note: str,
});
export type SymbolHistoryFeed = z.infer<typeof SymbolHistorySchema>;

export function useMstatSymbolHistory(symbol: string | null, days = 250) {
  return useQuery({
    queryKey: ['mstat-goldhistory', symbol, days],
    enabled: !!symbol,
    queryFn: ({ signal }) =>
      http<SymbolHistoryFeed>(
        `/api/mstat/goldhistory?symbol=${encodeURIComponent(symbol ?? '')}&days=${days}`,
        { schema: SymbolHistorySchema, signal },
      ),
    ...poll,
  });
}

export type { AsOf };
