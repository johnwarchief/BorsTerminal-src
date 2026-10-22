// features/portfolio/api/usePortfolio.ts -- تصمیم های سبد و قیمت جاری تابلو
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { sessionPollMs } from '@shared/lib/marketHours';
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
    // #M3.2: وزن/تخصیصِ هدف/ارزشِ سبد از همین snapshot می‌آید و قیمتِ جاری از
    // فیدِ مشترک. بی‌این، deltaِ تخصیص و فاصله‌ها تا پایانِ نشست رویِ عددِ ورودِ
    // صفحه می‌ماند. ریتمِ نشست‌محور (۳۰s باز / ۵min بسته) — نه هر نفسِ تابلو.
    refetchInterval: () => sessionPollMs(30_000),
    refetchIntervalInBackground: false,
  });
}


/** قیمت پایانی جاری نمادها برای کنترل حد ضرر */
// صفحهٔ «مستر»، پرتفوی و نوارِ زنجیره فقط همین عدد را می‌خواستند، ولی از فیدِ
// کاملِ /api/market (۶٫۸MB خام) می‌خواندند. مسیرِ سبکِ /api/market/closes همان
// p_closingِ همان نشست را در ~۱۵۰KB می‌دهد و با ETag در پولینگِ بی‌تغییر ۳۰۴
// می‌شود؛ مپ و کلیدهایِ نرمال‌شده عیناً مثلِ قبل ساخته می‌شوند.
const MarketClosesSchema = z.object({
  status: z.string(),
  rev: z.number().nullish(),
  asof: z
    .object({ d_even: z.number().nullish(), h_even: z.number().nullish() })
    .nullish(),
  count: z.number().nullish(),
  closes: z.record(z.string(), z.number()),
});
export type MarketClosesFeed = z.infer<typeof MarketClosesSchema>;

let closesCache: { src: MarketClosesFeed['closes']; map: Map<string, number> } | null = null;

function selectMarketCloses(feed: MarketClosesFeed): Map<string, number> {
  if (closesCache && closesCache.src === feed.closes) return closesCache.map;
  const map = new Map<string, number>();
  for (const [symbol, close] of Object.entries(feed.closes)) {
    if (close != null) {
      map.set(symbol, close);
      map.set(normalizeFa(symbol), close);
    }
  }
  closesCache = { src: feed.closes, map };
  return map;
}

export function useMarketCloses() {
  return useQuery({
    queryKey: ['market-closes'],
    queryFn: ({ signal }) =>
      http<MarketClosesFeed>('/api/market/closes', { schema: MarketClosesSchema, signal }),
    staleTime: 60_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(60_000),
    refetchOnWindowFocus: false,
    select: selectMarketCloses,
  });
}
