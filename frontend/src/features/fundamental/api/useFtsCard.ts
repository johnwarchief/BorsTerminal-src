// features/fundamental/api/useFtsCard.ts -- کارت پنج لایه FTS
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const GapSchema = z.object({
  layer: z.string().min(1),
  axis: z.string().nullish(),
  why: z.string().min(1),
  fix: z.string().min(1),
});

const HistoryRowSchema = z.object({
  period_end: z.string(),
  /** سال مالی را بک‌اند/کدال رشته می‌فرستد ("1404") — عدد هم بپذیرد.
   *  رگرسیون: z.number() خشک باعث می‌شد کل کارت FTS در parse بیفتد و صفحه
   *  به‌جای کارت، فقط «در دسترس نیست» نشان دهد (کارت خالی). */
  fiscal_year: z.coerce.number().nullish(),
  revenue: z.number().nullish(),
  gross_profit: z.number().nullish(),
  net_profit: z.number().nullish(),
  eps: z.number().nullish(),
  audited: z.unknown().nullish(),
  consolidated: z.unknown().nullish(),
});

/** لایه ۱الف — رشد ریالی با جزئیات YTD ماهانه (برای drill-down شاخص ۱) */
const Indicator1MonetarySchema = z
  .object({
    monetary_pct: z.number().nullish(),
    ytd_now_bt: z.number().nullish(),
    ytd_prev_bt: z.number().nullish(),
    ytd_now_mrl: z.number().nullish(),
    ytd_prev_mrl: z.number().nullish(),
    period: z.string().nullish(),
    months: z.number().nullish(),
    year: z.number().nullish(),
    threshold: z.number().nullish(),
    pass: z.boolean().nullish(),
    data_gap: z.boolean().nullish(),
    reason: z.string().nullish(),
    denominator_basis: z.string().nullish(),
  })
  .nullish();

/** لایه ۱ب — رشد فیزیکی/تناژ (قابل‌اعمال بودن + مبنا) */
const Indicator1VolumeSchema = z
  .object({
    quantity_verified: z.boolean().nullish(),
    basis: z.string().nullish(),
    confidence: z.string().nullish(),
    volume_pct: z.number().nullish(),
    real_pct: z.number().nullish(),
    implied_price_pct: z.number().nullish(),
    price_benchmark_pct: z.number().nullish(),
    /** کفِ رشد مقداری (volume_growth_min) — بک‌اند می‌فرستد؛ بدونِ این کلید
     *  zod آن را دور می‌ریخت و کارت مجبور بود عددِ ثابتِ خودش را بنویسد. */
    threshold: z.number().nullish(),
    applicable: z.boolean().nullish(),
    pass: z.boolean().nullish(),
    data_gap: z.boolean().nullish(),
    reason: z.string().nullish(),
    note: z.string().nullish(),
  })
  .nullish();

const Indicator1Schema = z
  .object({
    monetary: Indicator1MonetarySchema,
    volume: Indicator1VolumeSchema,
    pass: z.boolean().nullish(),
  })
  .nullish();

/** لایه ۲ — نردبان EPS سه‌ساله حسابرسی‌شده + میاندوره */
const Indicator2Schema = z
  .object({
    eps_series: z.array(z.number().nullable()).nullish(),
    net_profit_series: z.array(z.number().nullable()).nullish(),
    fiscal_years: z.array(z.string()).nullish(),
    period_ends: z.array(z.string()).nullish(),
    period_slots: z.array(z.string()).nullish(),
    years_required: z.number().nullish(),
    years_available: z.number().nullish(),
    consecutive_years: z.boolean().nullish(),
    strictly_rising: z.boolean().nullish(),
    all_profitable: z.boolean().nullish(),
    pass: z.boolean().nullish(),
    partial: z.boolean().nullish(),
    /** پرچم شکاف دادهٔ شاخص ۲ — بک‌اند آن را می‌فرستد ولی در جدول فیلدهای
     *  UI لازم است تا «ردِ گیت» از «نقص داده» تفکیک شود */
    data_gap: z.boolean().nullish(),
    reason: z.string().nullish(),
    evidence_tier: z.string().nullish(),
    interim: z
      .object({
        available: z.boolean().nullish(),
        period_end: z.string().nullish(),
        period_months: z.number().nullish(),
        eps_interim: z.number().nullish(),
        eps_projected_year: z.number().nullish(),
        interim_yoy_pct: z.number().nullish(),
        continues_trend: z.boolean().nullish(),
        annualize_label: z.string().nullish(),
      })
      .nullish(),
  })
  .nullish();

/** لایه ۳ — حاشیه سود ناخالص با فرمول شفاف */
const Indicator3Schema = z
  .object({
    margin_pct: z.number().nullish(),
    gross_profit_bt: z.number().nullish(),
    revenue_bt: z.number().nullish(),
    period_end: z.string().nullish(),
    basis: z.string().nullish(),
    formula: z.string().nullish(),
    pass: z.boolean().nullish(),
    optimal: z.boolean().nullish(),
    threshold: z.number().nullish(),
    optimal_threshold: z.number().nullish(),
    /** بک‌اند «ideal_threshold» می‌فرستد (margin_ideal)؛ optimal_threshold هیچ‌وقت
     *  نمی‌رسید، پس کارت همیشه به پیش‌فرض ۳۰٪ می‌افتاد. */
    ideal_threshold: z.number().nullish(),
    band: z.string().nullish(),
    na: z.boolean().nullish(),
    reason: z.string().nullish(),
  })
  .nullish();

/** لایه ۴ — سالانه‌سازی پویا ×۱۲÷م + نسبت‌های ارزش */
const Indicator4Schema = z
  .object({
    available: z.boolean().nullish(),
    mcap_ht: z.number().nullish(),
    annual_sales_bt: z.number().nullish(),
    months_used: z.number().nullish(),
    scale_factor: z.number().nullish(),
    annualize_basis: z.string().nullish(),
    sales_to_mcap: z.number().nullish(),
    sales_threshold: z.number().nullish(),
    sales_pass: z.boolean().nullish(),
    margin_used_pct: z.number().nullish(),
    margin_basis: z.string().nullish(),
    est_gross_profit_bt: z.number().nullish(),
    potential_pct: z.number().nullish(),
    potential_threshold: z.number().nullish(),
    potential_pass: z.boolean().nullish(),
    pass: z.boolean().nullish(),
    na: z.boolean().nullish(),
    exempt: z.boolean().nullish(),
    reason: z.string().nullish(),
    annual: z
      .object({
        annual_sales_mrl: z.number().nullish(),
        annual_sales_bt: z.number().nullish(),
        months_used: z.number().nullish(),
        scale_factor: z.number().nullish(),
        basis: z.string().nullish(),
        reconciled: z.boolean().nullish(),
        ytd_sales_bt: z.number().nullish(),
        scale_table: z.array(z.object({ months: z.number(), factor: z.number() })).nullish(),
      })
      .nullish(),
  })
  .nullish();

/** لایه ۵ — رژیم قیمت‌گذاری صنعت و چشم‌انداز */
const Indicator5Schema = z
  .object({
    verdict: z.string().nullish(),
    label: z.string().nullish(),
    sector: z.string().nullish(),
    matched_tokens: z.array(z.string()).nullish(),
    fts_top_industry: z.boolean().nullish(),
    pass: z.boolean().nullish(),
    market_share_pct: z.number().nullish(),
    outlook: z.string().nullish(),
    regime_label: z.string().nullish(),
  })
  .nullish();

const IndicatorsSchema = z
  .object({
    '1': Indicator1Schema,
    '2': Indicator2Schema,
    '3': Indicator3Schema,
    '4': Indicator4Schema,
    '5': Indicator5Schema,
  })
  .nullish();

/** طبقهٔ شرکت (تولیدی/خدماتی/مالی/صندوق/هلدینگ) — مبنای N/A هوشمند */
const ProfileSchema = z
  .object({
    kind: z.string().nullish(),
    label: z.string().nullish(),
    revenue_basis: z.string().nullish(),
    volume_applicable: z.boolean().nullish(),
    volume_note: z.string().nullish(),
    pricing_note: z.string().nullish(),
  })
  .nullish();

export const FtsCardSchema = z.object({
  status: z.string(),
  symbol: z.string(),
  sector: z.string().nullish(),
  score: z.number().nullish(),
  verdict: z.string().nullish(),
  /** false = شرکت عملیاتی نیست (صندوق)؛ FTS روی آن اعمال نمی‌شود */
  applicable: z.boolean().nullish(),
  pricing_mode: z.string().nullish(),
  /** سه‌حاله (رأیِ مالک ۱۴۰۵-۰۷-۰۳): null = «نظر نمی‌دهد». رکوردِ خشکِ boolean
   *  کل کارت را در parse می‌انداخت و صفحه به‌جای کارت «در دسترس نیست» می‌داد. */
  passes: z.record(z.string(), z.boolean().nullish()).nullish(),
  indicators: IndicatorsSchema,
  profile: ProfileSchema,
  metrics: z
    .object({
      eps_series: z.array(z.number().nullable()).nullish(),
      eps_slots: z.array(z.coerce.string()).nullish(),
      eps_available: z.number().nullish(),
      eps_required: z.number().nullish(),
      eps_partial: z.boolean().nullish(),
      gross_margin: z.number().nullish(),
      net_margin: z.number().nullish(),
      profit_potential_pct: z.number().nullish(),
      sales_to_mcap: z.number().nullish(),
      roe: z.number().nullish(),
      mcap_stale: z.boolean().nullish(),
      mcap: z.number().nullish(),
      mcap_hmt: z.number().nullish(),
      annual_sales_bt: z.number().nullish(),
      months_used: z.number().nullish(),
      scale_factor: z.number().nullish(),
      real_growth_pct: z.number().nullish(),
      monetary_growth_pct: z.number().nullish(),
      volume_growth_pct: z.number().nullish(),
      growth_pct: z.number().nullish(),
      eps_projected_year: z.number().nullish(),
    })
    .nullish(),
  data_gaps: z.array(GapSchema).nullish(),
  history: z.array(HistoryRowSchema).nullish(),
  fs_count: z.number().nullish(),
  excluded: z.boolean().nullish(),
  exclusion_reasons: z.array(z.string()).nullish(),
});

export type FtsCard = z.infer<typeof FtsCardSchema>;
export type FtsCardIndicators = NonNullable<NonNullable<FtsCard['indicators']>>;

export function useFtsCard(symbol: string) {
  return useQuery({
    queryKey: ['fts-card', symbol],
    queryFn: ({ signal }) =>
      http<FtsCard>(`/api/fundamental/${encodeURIComponent(symbol)}`, { schema: FtsCardSchema, signal }),
    enabled: symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
  });
}
