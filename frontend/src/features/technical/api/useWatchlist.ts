// features/technical/api/useWatchlist.ts -- دیده‌بان سایدبار راست (تب ۱)
// از اندپوینت /api/market با اسکیمای مشترک shared/types/marketRow (مرز B1 حفظ است:
// فقط shared و contracts). بازهٔ بازخوانی از shared/stores/marketStore می‌آید.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed, type MarketRow } from '@shared/types/marketRow';
import { useMarketStore } from '@shared/stores/marketStore';
import { matchFa } from '@shared/lib/normalizeFa';
import { effectivePollMs } from '@shared/lib/marketHours';

/** کفِ بازهٔ بازخوانی دیده‌بان — سبک‌تر از تابلو تا سایدبار سنگین نشود */
const MIN_INTERVAL_MS = 30_000;
const DEFAULT_LIMIT = 60;

export function useWatchlistFeed() {
  const refetchIntervalMs = useMarketStore((s) => s.refetchIntervalMs);
  const paused = useMarketStore((s) => s.paused);
  return useQuery({
    queryKey: ['technical-watchlist'],
    queryFn: ({ signal }) => http<MarketFeed>('/api/market', { schema: MarketFeedSchema, signal }),
    refetchInterval: paused ? false : () => effectivePollMs(Math.max(MIN_INTERVAL_MS, refetchIntervalMs)),
    staleTime: 10_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/** ارزش معاملهٔ روز ≈ آخرین قیمت × حجم — مبنای مرتب‌سازی دیده‌بان */
export function tradingValue(r: MarketRow): number {
  const price = r.p_last ?? r.p_closing ?? 0;
  const vol = r.q_tot_tran ?? 0;
  return Number.isFinite(price * vol) ? price * vol : 0;
}

/** فیلتر/جستجو/مرتب‌سازی خالص — فقط ردیف‌های زنده، بر اساس ارزش معامله */
export function filterWatchlist(rows: MarketRow[], q: string, limit = DEFAULT_LIMIT): MarketRow[] {
  const term = q.trim();
  const out = rows.filter((r) => {
    if (r.is_live === false) return false;
    if (!r.symbol) return false;
    if (!term) return true;
    return matchFa(r.symbol, term) || matchFa(r.name, term);
  });
  return out.sort((a, b) => tradingValue(b) - tradingValue(a)).slice(0, limit);
}
