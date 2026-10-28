import type { MarketRow } from '@shared/types/market';

export const M_TUMAN_FROM_RIAL = 1e7;
export const FTS_VOL_RATIO_HOT = 3;

type PerCapitaRow = Partial<Pick<
  MarketRow,
  'buy_i_vol' | 'sell_i_vol' | 'buy_count_i' | 'sell_count_i'
  | 'q_tot_cap' | 'q_tot_tran' | 'p_closing' | 'p_last'
>>;

function vwapRial(r: PerCapitaRow): number {
  const cap = r.q_tot_cap;
  const vol = r.q_tot_tran;
  if (cap != null && vol != null && vol > 0) return cap / vol;
  return r.p_closing ?? r.p_last ?? 0;
}

export function buyPerCapitaMt(r: PerCapitaRow): number | null {
  const count = r.buy_count_i;
  const vol = r.buy_i_vol;
  if (count == null || count <= 0 || vol == null) return null;
  const price = vwapRial(r);
  if (!(price > 0)) return null;
  return ((vol / count) * price) / M_TUMAN_FROM_RIAL;
}

export function sellPerCapitaMt(r: PerCapitaRow): number | null {
  const count = r.sell_count_i;
  const vol = r.sell_i_vol;
  if (count == null || count <= 0 || vol == null) return null;
  const price = vwapRial(r);
  if (!(price > 0)) return null;
  return ((vol / count) * price) / M_TUMAN_FROM_RIAL;
}

export function buySellShare(buy: number | null, sell: number | null): number | null {
  if (buy == null || sell == null) return null;
  const total = buy + sell;
  if (!(total > 0)) return null;
  return Math.min(1, Math.max(0, buy / total));
}
