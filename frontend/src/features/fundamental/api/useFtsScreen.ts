// features/fundamental/api/useFtsScreen.ts -- دیده‌بان کلان ۵ شاخص FTS
// ماتریس مقایسه‌ای شرکت‌ها از /api/screener (bulk_scan) — همان پنج محور جزوه.
// ستون‌های nullable همه tolerant شدند: نبود گزارش فصلی «شکاف داده» است، نه خطا.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

/** ردیف غربالگری — همهٔ شاخص‌ها nullable تا شکاف داده کرش نزند */
export const FtsScreenRowSchema = z.object({
  symbol: z.string(),
  symbol_norm: z.string().nullish(),
  name: z.string().nullish(),
  sector_name: z.string().nullish(),
  pricing_mode: z.string().nullish(),
  /** شاخص ۱: رشد درآمد کدال (٪) — null یعنی مخرج YoY نبود */
  rev_growth: z.number().nullable().nullish(),
  /** شاخص ۲: روند EPS سه‌ساله — null یعنی سابقه ناقص */
  eps_series: z.array(z.number().nullable()).nullish(),
  eps_last: z.number().nullable().nullish(),
  eps_data_gap: z.boolean().nullish(),
  /** اگر بک‌اند در ردیف اسکنر هم تعداد سال‌های EPS را بدهد (هم‌شکل با
   *  indicators['2'] اندپوینت جزئیات)، جدول همان‌ها را مبنا می‌گیرد؛ وگرنه
   *  طول سری eps_series. هر دو اختیاری‌اند — نبودشان یعنی «داده نیست». */
  eps_years_available: z.number().nullish(),
  eps_years_required: z.number().nullish(),
  /** شاخص ۳: حاشیه سود ناخالص (٪) */
  gross_margin: z.number().nullable().nullish(),
  /** شاخص ۴: فروش سالانه ÷ ارزش بازار و پتانسیل سود ناخالص (٪) */
  sales_to_mcap: z.number().nullable().nullish(),
  profit_potential_pct: z.number().nullable().nullish(),
  annual_sales_bt: z.number().nullish(),
  mcap: z.number().nullish(),
  score: z.number().min(0).max(5),
  i1_pass: z.boolean().nullish(),
  i2_pass: z.boolean().nullish(),
  i3_pass: z.boolean().nullish(),
  i4_pass: z.boolean().nullish(),
  i5_pass: z.boolean().nullish(),
  excluded: z.boolean().nullish(),
  exclusion_reasons: z.string().nullish(),
  m141: z.boolean().nullish(),
  watchlist: z.boolean().nullish(),
  // FTS Technical Methodology Fields
  tech_trend_d: z.string().nullish(),
  tech_trend_w: z.string().nullish(),
  tech_trend_m: z.string().nullish(),
  tech_alignment: z.string().nullish(),
  tech_jet: z.boolean().nullish(),
  tech_choch_bull: z.boolean().nullish(),
  tech_choch_bear: z.boolean().nullish(),
  tech_double_bottom: z.boolean().nullish(),
  tech_range_break: z.boolean().nullish(),
  tech_fib_zone: z.string().nullable().nullish(),
  tech_exit_verdict: z.string().nullable().nullish(),
  tech_exit_signals: z.array(z.string()).nullish(),
  tech_matrix_decision: z.string().nullable().nullish(),
  tech_matrix_setup: z.string().nullable().nullish(),
  tech_matrix_desc: z.string().nullable().nullish(),
  tech_hourglass_active: z.boolean().nullish(),
  tech_hourglass_action: z.string().nullable().nullish(),
});
export type FtsScreenRow = z.infer<typeof FtsScreenRowSchema>;

const FtsScreenSchema = z.object({
  status: z.string(),
  count: z.number(),
  data: z.array(FtsScreenRowSchema),
  thresholds: z.record(z.string(), z.unknown()).nullish(),
  max_score: z.number().nullish(),
});
export type FtsScreen = z.infer<typeof FtsScreenSchema>;

export function useFtsScreen(limit = 60) {
  return useQuery({
    queryKey: ['fts-screen', limit],
    queryFn: ({ signal }) =>
      http<FtsScreen>(`/api/screener?limit=${limit}`, { schema: FtsScreenSchema, signal }),
    staleTime: 5 * 60_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
  });
}
