import type { MarketRow } from '@shared/types/market';
import { normalizeFa } from '@shared/lib/faSearch';
import { classifyAssetType, type AssetType } from './assetType';
import { TAPES, type TapeKey } from './tapeFilters';
import {
  isLiveBoardRow,
  tapeFilterState,
  type TapeFilterConfig,
} from './tapeAlgorithms';

export type DirectionFilter = 'all' | 'pos' | 'neg' | 'limitUp' | 'limitDown';
export type HiddenDoor = 'پسوندِ عددی' | 'بازار/ابزارِ خاموش' | 'نمادِ خاموش' | 'صنعت' | 'جستجو';

export type BoardFilters = {
  query: string;
  assetTypes: AssetType[];
  quickFilters: TapeKey[];
  quickLogic: 'and' | 'or';
  sector: string;
  liveOnly: boolean;
  direction: DirectionFilter;
  volRatioOn: boolean;
  volRatioMin: number;
  exitAccum: boolean;
  showNumericSuffix: boolean;
  filterConfig: TapeFilterConfig;
};

export type BoardFilterValues = Pick<
  BoardFilters,
  'sector' | 'liveOnly' | 'direction' | 'volRatioOn' | 'volRatioMin' | 'exitAccum' | 'showNumericSuffix'
>;

export const DEFAULT_BOARD_FILTER_VALUES: BoardFilterValues = {
  sector: '',
  liveOnly: true,
  direction: 'all',
  volRatioOn: false,
  volRatioMin: 3,
  exitAccum: false,
  showNumericSuffix: false,
};

export type BoardEvaluation = {
  visible: MarketRow[];
  baseCount: number;
  counts: Record<TapeKey, number>;
  unevaluated: Record<TapeKey, number>;
  hiddenCounts: Record<TapeKey, number>;
  hiddenDoors: Record<TapeKey, Partial<Record<HiddenDoor, number>>>;
};

function rowState(row: MarketRow, key: TapeKey, filters: BoardFilters) {
  if (!isLiveBoardRow(row)) return 'unevaluated' as const;
  return tapeFilterState(row, key, filters.filterConfig);
}

function passesTape(row: MarketRow, key: TapeKey, filters: BoardFilters): boolean {
  return rowState(row, key, filters) === 'pass';
}

function matchesQuery(row: MarketRow, query: string): boolean {
  const needle = normalizeFa(query);
  if (!needle) return true;
  const words = needle.split(' ').filter(Boolean);
  return [row.symbol, row.name ?? ''].some((value) => {
    const haystack = normalizeFa(value);
    if (haystack.includes(needle)) return true;
    if (words.length > 1 && words.every((word) => haystack.includes(word))) return true;
    return haystack.replace(/\s+/g, '').includes(needle.replace(/\s+/g, ''));
  });
}

function matchesDirection(row: MarketRow, direction: DirectionFilter): boolean {
  if (direction === 'all') return true;
  const pct = row.percent_change;
  if (pct == null || !Number.isFinite(pct)) return false;
  if (direction === 'pos') return pct > 0;
  if (direction === 'neg') return pct < 0;
  if (direction === 'limitUp') return pct >= 4.9;
  return pct <= -4.9;
}

function matchesBase(row: MarketRow, filters: BoardFilters): boolean {
  const query = filters.query.trim();
  if (query && !matchesQuery(row, query)) return false;
  if (filters.sector && (row.sector_name ?? '') !== filters.sector) return false;
  if (!filters.assetTypes.includes(classifyAssetType(row))) return false;
  if (filters.liveOnly && !query && row.is_live === false) return false;
  if (!matchesDirection(row, filters.direction)) return false;
  if (filters.volRatioOn) {
    const ratio = row.vol_ratio;
    if (ratio == null || !Number.isFinite(ratio) || ratio < filters.volRatioMin) return false;
  }
  if (filters.exitAccum && !(passesTape(row, 'f_clock', filters) && passesTape(row, 'f_susp', filters))) return false;
  return true;
}

function hiddenDoorOf(row: MarketRow, filters: BoardFilters): HiddenDoor | null {
  const query = filters.query.trim();
  if (!filters.showNumericSuffix && /[0-9۰-۹]$/.test(row.symbol.trim())) return 'پسوندِ عددی';
  if (!filters.assetTypes.includes(classifyAssetType(row))) return 'بازار/ابزارِ خاموش';
  if (filters.liveOnly && !query && row.is_live === false) return 'نمادِ خاموش';
  if (filters.sector && (row.sector_name ?? '') !== filters.sector) return 'صنعت';
  if (query && !matchesQuery(row, query)) return 'جستجو';
  return null;
}

function zeroCounts(): Record<TapeKey, number> {
  return Object.fromEntries(TAPES.map((tape) => [tape.key, 0])) as Record<TapeKey, number>;
}

export function evaluateBoard(rows: MarketRow[], filters: BoardFilters): BoardEvaluation {
  const base = rows.filter((row) => matchesBase(row, filters));
  const filterBase = filters.showNumericSuffix
    ? base
    : base.filter((row) => !/[0-9۰-۹]$/.test(row.symbol.trim()));
  const shown = new Set(filterBase);
  const hidden = rows.filter((row) => !shown.has(row));

  const counts = zeroCounts();
  const unevaluated = zeroCounts();
  const hiddenCounts = zeroCounts();
  const hiddenDoors = Object.fromEntries(
    TAPES.map((tape) => [tape.key, {}]),
  ) as BoardEvaluation['hiddenDoors'];

  for (const tape of TAPES) {
    const others = filters.quickFilters.filter((key) => key !== tape.key);
    for (const row of filterBase) {
      const inCandidateBase = others.length === 0 || (filters.quickLogic === 'or'
        ? others.some((key) => passesTape(row, key, filters))
        : others.every((key) => passesTape(row, key, filters)));
      if (!inCandidateBase) continue;
      const state = rowState(row, tape.key, filters);
      if (state === 'pass') counts[tape.key] += 1;
      if (state === 'unevaluated') unevaluated[tape.key] += 1;
    }

    for (const row of hidden) {
      if (!passesTape(row, tape.key, filters)) continue;
      hiddenCounts[tape.key] += 1;
      const door = hiddenDoorOf(row, filters);
      if (door) hiddenDoors[tape.key][door] = (hiddenDoors[tape.key][door] ?? 0) + 1;
    }
  }

  const visible = filters.quickFilters.length === 0
    ? filterBase
    : filterBase.filter((row) => filters.quickLogic === 'or'
      ? filters.quickFilters.some((key) => passesTape(row, key, filters))
      : filters.quickFilters.every((key) => passesTape(row, key, filters)));

  return { visible, baseCount: filterBase.length, counts, unevaluated, hiddenCounts, hiddenDoors };
}
