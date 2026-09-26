// features/portfolio/api/usePortfolio.ts -- تصمیم های سبد و قیمت جاری تابلو
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { PortfolioDecisionSchema } from '../model/portfolioSignals';

const PortfolioFeedSchema = z.object({
  status: z.string(),
  decisions: z.array(PortfolioDecisionSchema).nullish(),
  portfolio: z.array(PortfolioDecisionSchema).nullish(),
  monitor: z.array(PortfolioDecisionSchema).nullish(),
  counts: z.record(z.string(), z.number()).nullish(),
  limits: z
    .object({
      min: z.number().nullish(),
      max: z.number().nullish(),
      weight_cap_pct: z.number().nullish(),
      equal_weight_pct: z.number().nullish(),
      sum_weight_pct: z.number().nullish(),
      // #106: منشأِ وزن و ارزشِ ریالیِ سبد — «۷۰٪ از سبد» باید بداند مخرجش چیست
      weight_source: z.enum(['value', 'manual', 'equal']).nullish(),
      portfolio_value_toman: z.number().nullable().nullish(),
      value_missing_count: z.number().nullish(),
      /** درصد هر طبقهٔ دارایی از سبد (کلید: gold/silver/fixed/equity/stock/…) */
      class_mix_pct: z.record(z.string(), z.number()).nullish(),
      class_missing_count: z.number().nullish(),
    })
    .nullish(),
});

export type PortfolioFeed = z.infer<typeof PortfolioFeedSchema>;

// جدول پرتفوی این کلید را می‌خواند و فید تصمیم‌ها کلیدی جدا دارد؛ هر دو همان
// /api/selection/portfolio هستند. نوشتن روی یکی بی‌اعتبار کردن دیگری را لازم
// می‌کند، وگرنه ردیفِ تازه‌ثبت‌شده در جدول نمی‌نشیند.
export const PORTFOLIO_QUERY_KEY = ['portfolio'] as const;

export function usePortfolio() {
  return useQuery({
    queryKey: PORTFOLIO_QUERY_KEY,
    queryFn: ({ signal }) =>
      http<PortfolioFeed>('/api/selection/portfolio', { schema: PortfolioFeedSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}

const ClosesSchema = z.object({
  status: z.string(),
  data: z.array(z.object({ symbol: z.string().min(1), p_closing: z.number().nullish() })).nullish(),
});

/** قیمت پایانی جاری نمادها برای کنترل حد ضرر */
export function useMarketCloses() {
  return useQuery({
    queryKey: ['portfolio-closes'],
    queryFn: ({ signal }) =>
      http<z.infer<typeof ClosesSchema>>('/api/market', { schema: ClosesSchema, signal }).then((feed) => {
        const map = new Map<string, number>();
        for (const r of feed.data ?? []) {
          if (r.p_closing != null) {
            map.set(r.symbol, r.p_closing);
            map.set(normalizeFa(r.symbol), r.p_closing);
          }
        }
        return map;
      }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}
