import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { evaluateBoard, type BoardFilters } from '@features/market/lib/boardFilters';

const rows: MarketRow[] = [
  {
    ins_code: '1', symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات اساسی',
    is_live: true, percent_change: 5.2, vol_ratio: 4, f_clock: true, f_susp: true,
  },
  {
    ins_code: '2', symbol: 'خساپا', name: 'سایپا', sector_name: 'خودرو',
    is_live: true, percent_change: -1, vol_ratio: 2, f_clock: true, f_susp: false,
  },
  {
    ins_code: '3', symbol: 'وتجارت', name: 'سرمایه‌گذاری تجارت', sector_name: 'سرمایه‌گذاری',
    is_live: false, percent_change: 6, vol_ratio: 5, f_clock: true, f_susp: true,
  },
  {
    ins_code: '4', symbol: 'شپنا', name: 'پالایش اصفهان', sector_name: 'فرآورده‌های نفتی',
    is_live: true, percent_change: 0, vol_ratio: null, f_clock: null, f_susp: null,
  },
  {
    ins_code: '5', symbol: 'فولاد1', name: 'فولاد عمده', sector_name: 'فلزات اساسی',
    is_live: true, percent_change: 5.5, vol_ratio: 4.5, f_clock: true, f_susp: true,
  },
];

function filters(patch: Partial<BoardFilters> = {}): BoardFilters {
  return {
    query: '',
    assetTypes: ['stock'],
    quickFilters: [],
    quickLogic: 'and',
    sector: '',
    liveOnly: true,
    direction: 'all',
    volRatioOn: false,
    volRatioMin: 3,
    exitAccum: false,
    showNumericSuffix: false,
    filterConfig: DEFAULT_TAPE_FILTER_CONFIG,
    ...patch,
  };
}

describe('complete board filtering', () => {
  it('requires every selected tape in AND mode', () => {
    const result = evaluateBoard(rows, filters({ quickFilters: ['f_clock', 'f_susp'] }));
    expect(result.visible.map((row) => row.symbol)).toEqual(['فولاد']);
  });

  it('keeps the union in OR mode but never admits unevaluated rows', () => {
    const result = evaluateBoard(rows, filters({ quickFilters: ['f_clock', 'f_susp'], quickLogic: 'or' }));
    expect(result.visible.map((row) => row.symbol)).toEqual(['فولاد', 'خساپا']);
    expect(result.visible.some((row) => row.symbol === 'شپنا')).toBe(false);
  });

  it('counts a chip against the other selected chips and reports unevaluated separately', () => {
    const result = evaluateBoard(rows, filters({ quickFilters: ['f_clock'] }));
    expect(result.counts.f_susp).toBe(1);
    expect(result.unevaluated.f_susp).toBe(0);
    expect(result.counts.f_clock).toBe(2);
    expect(result.unevaluated.f_clock).toBe(1);
  });

  it('keeps hidden matches visible as counts with their exclusion door', () => {
    const result = evaluateBoard(rows, filters());
    expect(result.hiddenCounts.f_clock).toBe(1);
    expect(result.hiddenDoors.f_clock['پسوندِ عددی']).toBe(1);
  });

  it('applies sector, direction, volume ratio and exit-accumulation without treating missing as zero', () => {
    expect(evaluateBoard(rows, filters({ sector: 'خودرو' })).visible.map((row) => row.symbol)).toEqual(['خساپا']);
    expect(evaluateBoard(rows, filters({ direction: 'limitUp' })).visible.map((row) => row.symbol)).toEqual(['فولاد']);
    expect(evaluateBoard(rows, filters({ volRatioOn: true, volRatioMin: 3 })).visible.map((row) => row.symbol)).toEqual(['فولاد']);
    expect(evaluateBoard(rows, filters({ exitAccum: true })).visible.map((row) => row.symbol)).toEqual(['فولاد']);
  });

  it('allows an explicit search to find a non-live symbol', () => {
    const result = evaluateBoard(rows, filters({ query: 'وتجارت' }));
    expect(result.visible.map((row) => row.symbol)).toEqual(['وتجارت']);
  });

  it('reports the non-tape base count independently from the visible AND/OR result', () => {
    const result = evaluateBoard(rows, filters({ quickFilters: ['f_clock', 'f_susp'] }));
    expect(result.baseCount).toBe(3);
    expect(result.visible).toHaveLength(1);
  });
});
