// widgets/useInspectorBoard.ts -- ردیف تابلوی نماد انتخابی با کش بلند
// دیتای خام نماد (نام/صنعت/قیمت/درصد) از همان خوراک تابلو می آید؛ یک کش
// سراسری سبک تا سایدبار در هر صفحه دوباره fetch نزند.
import { useMemo } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketRow, marketRowOf } from '@features/market/api/useMarketRow';
import type { MarketRow } from '@shared/types/marketRow';

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

/** ردیفِ خامِ تابلو — همان چیزی که قواعدِ درِ تابلو (`tapeFilterVerdict`) و
 *  `symbolStageProgress` رویِ خودش اجرا می‌شوند. تطبیقِ نماد از `findBoardRow`
 *  است (نوشتارِ عربی/فارسی + فاصله)، نه از مقایسهٔ خام. */
export function useInspectorRawRow(opts: { enabled?: boolean } = {}): MarketRow | null {
  const symbol = useSymbolStore((s) => s.symbol);
  const q = useMarketRow(symbol, opts.enabled ?? true);
  return marketRowOf(q);
}

export function useInspectorBoard(opts: { enabled?: boolean } = {}): BoardRow | null {
  const r = useInspectorRawRow(opts);
  return useMemo(() => {
    if (!r) return null;
    return {
      symbol: r.symbol,
      name: r.name ?? '',
      sector: r.sector_name ?? '',
      pLast: r.p_last ?? null,
      pClosing: r.p_closing ?? null,
      percentChange: r.percent_change ?? null,
      buyerPower: r.buyer_power ?? null,
      fClock: r.f_clock === true,
      fSusp: r.f_susp === true,
    };
  }, [r]);
}
