import { changePct, faNum, fmtInt, fmtMcap, fmtPct, fmtPe, fmtPrice, fmtValue, fmtVolume, toFaDigits } from '@shared/lib/fa';
import { toExportTable, type ExportCell, type ExportTable } from '@shared/lib/tableExport';
import type { MarketRow } from '@shared/types/market';
import { COLUMNS, type ColumnKey } from './columns';
import type { TapeFilterConfig } from './tapeAlgorithms';
import { patternBadges } from './tapeBadges';
import { buyPerCapitaMt, sellPerCapitaMt } from './tapeFts';
import { lastCloseDiff } from './tapePatterns';

export function boardExportCell(
  row: MarketRow,
  key: ColumnKey,
  filterConfig: TapeFilterConfig,
): ExportCell {
  switch (key) {
    case 'symbol':
      return row.name ? `${row.symbol} — ${row.name}` : row.symbol;
    case 'last':
      return fmtPrice(row.p_last ?? row.p_closing);
    case 'close':
      return fmtPrice(row.p_closing);
    case 'last_vs_close': {
      const diff = lastCloseDiff(row);
      return fmtPct(diff == null ? null : diff * 100);
    }
    case 'pct_close':
      return fmtPct(changePct(row.percent_change, row.price_change, row.price_yesterday));
    case 'pct_last':
      return fmtPct(row.percent_last);
    case 'volume':
      return fmtVolume(row.q_tot_tran);
    case 'value':
      return fmtValue(row.q_tot_cap);
    case 'trades':
      return fmtInt(row.z_tot_tran);
    case 'vol_ratio':
      return row.vol_ratio == null ? '—' : `${faNum(row.vol_ratio, 1)}×`;
    case 'buy_sell': {
      const buy = buyPerCapitaMt(row);
      const sell = sellPerCapitaMt(row);
      const cells = [
        buy == null ? null : `خرید ${faNum(buy, 1)} م.ت`,
        sell == null ? null : `فروش ${faNum(sell, 1)} م.ت`,
        row.buyer_power == null ? null : `قدرت ${toFaDigits(row.buyer_power.toFixed(2))}×`,
      ].filter((value): value is string => value != null);
      return cells.length ? cells.join(' / ') : '—';
    }
    case 'patterns': {
      const badges = patternBadges(row, filterConfig).map((badge) => badge.label);
      return badges.length ? badges.join(' / ') : '—';
    }
    case 'pe':
      return fmtPe(row.pe);
    case 'mcap':
      return fmtMcap(row.mcap);
    case 'eps':
    case 'tech':
      return '—';
  }
}

export function boardExportTable(
  rows: readonly MarketRow[],
  columns: readonly ColumnKey[],
  filterConfig: TapeFilterConfig,
): ExportTable {
  return toExportTable(
    columns.map((key) => COLUMNS[key].label),
    rows,
    (row) => columns.map((key) => boardExportCell(row, key, filterConfig)),
  );
}
