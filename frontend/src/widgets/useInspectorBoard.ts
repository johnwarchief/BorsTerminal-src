// widgets/useInspectorBoard.ts -- ردیف تابلوی نماد انتخابی با کش بلند
// دیتای خام نماد (نام/صنعت/قیمت/درصد) از همان خوراک تابلو می آید؛ یک کش
// سراسری سبک تا سایدبار در هر صفحه دوباره fetch نزند.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';

export type BoardRow = {
  symbol: string;
  name: string;
  sector: string;
  pLast: number | null;
  pClosing: number | null;
  percentChange: number | null;
  buyerPower: number | null;
  fClock: boolean;
  fSusp: boolean;
};

export function useInspectorBoard(): BoardRow | null {
  const symbol = useSymbolStore((s) => s.symbol);
  const { data } = useQuery({
    queryKey: ['inspector-board'],
    queryFn: ({ signal }) =>
      http<MarketFeed>('/api/market', { schema: MarketFeedSchema, signal }).then((feed) => {
        const map = new Map<string, BoardRow>();
        for (const r of feed.data) {
          map.set(r.symbol, {
            symbol: r.symbol,
            name: r.name ?? '',
            sector: r.sector_name ?? '',
            pLast: r.p_last ?? null,
            pClosing: r.p_closing ?? null,
            percentChange: r.percent_change ?? null,
            buyerPower: r.buyer_power ?? null,
            fClock: r.f_clock === true,
            fSusp: r.f_susp === true,
          });
        }
        return map;
      }),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  return (symbol && data?.get(symbol)) || null;
}
