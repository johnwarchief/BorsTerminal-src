// features/technical/api/useMarketMacro.ts -- نمای کلان «کل بورس» برای تب تکنیکال بدون نماد
// اسکیمای بومیِ همین فیچر (مرز B1): از فیچر market چیزی import نمی‌شود؛ فقط
// اندپوینت‌های /api/mstat/* مصرف می‌شوند. هر اندپوینت به‌تنهایی می‌میرد و نبودِ
// داده «بدون داده» می‌شود، نه صفر ساختگی (Circuit Breaker).
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

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
      value_hemat_all_market: num,
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
