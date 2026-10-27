import { changePct } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';

export type SortKey = 'symbol' | 'last' | 'change' | 'value' | 'volume';
export type SortDir = 'asc' | 'desc';

export const SORT_LABEL: Record<SortKey, string> = {
  symbol: 'نماد',
  last: 'آخرین',
  change: 'تغییر٪',
  value: 'ارزش',
  volume: 'حجم',
};

export function sortValue(row: MarketRow, key: SortKey): number | string {
  switch (key) {
    case 'symbol':
      return row.symbol;
    case 'last':
      return row.p_last ?? row.p_closing ?? -Infinity;
    case 'change':
      return changePct(row.percent_change, row.price_change, row.price_yesterday) ?? -Infinity;
    case 'value':
      return row.q_tot_cap ?? -Infinity;
    case 'volume':
      return row.q_tot_tran ?? -Infinity;
  }
}

export function sortRows(rows: readonly MarketRow[], key: SortKey, dir: SortDir): MarketRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    if (typeof va === 'string' || typeof vb === 'string') {
      return String(va).localeCompare(String(vb), 'fa') * sign;
    }
    if (va === vb) return a.symbol.localeCompare(b.symbol, 'fa');
    return (va < vb ? -1 : 1) * sign;
  });
}
