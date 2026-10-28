import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { BoardTable } from '@features/market/components/BoardTable';
import { BoardToolbar } from '@features/market/components/BoardToolbar';
import { DEFAULT_BOARD_FILTER_VALUES } from '@features/market/lib/boardFilters';
import { defaultColumns, sortRows } from '@features/market/lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '@features/market/lib/tapeAlgorithms';
import { patternBadges } from '@features/market/lib/tapeBadges';
import { buyPerCapitaMt, buySellShare } from '@features/market/lib/tapeFts';
import { useMarketPrefs } from '@features/market/stores/prefs';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 30,
      getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ key: index, index, start: index * 30 })),
      measure: noop,
    }),
  };
});

const noop = () => undefined;

const row = (patch: Partial<MarketRow>): MarketRow => ({
  ins_code: patch.symbol,
  symbol: patch.symbol ?? 'نماد',
  ...patch,
});

beforeEach(() => {
  localStorage.clear();
  useMarketPrefs.persist.clearStorage();
  useMarketPrefs.setState(useMarketPrefs.getInitialState(), true);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('real tape columns', () => {
  it('offers the twelve reference tape columns in the trading profile', () => {
    expect(defaultColumns('trading')).toEqual([
      'symbol', 'last', 'close', 'last_vs_close', 'pct_close', 'pct_last',
      'volume', 'trades', 'value', 'vol_ratio', 'buy_sell', 'patterns',
    ]);
    expect(defaultColumns('general')).toContain('patterns');
  });

  it('sorts the new numeric fields without turning missing values into zero', () => {
    const rows = [
      row({ symbol: 'الف', p_last: 102, p_closing: 100, percent_last: 1, vol_ratio: 2, buyer_power: 1 }),
      row({ symbol: 'ب', p_last: 101, p_closing: 100, percent_last: 3, vol_ratio: 4, buyer_power: 2 }),
      row({ symbol: 'ج', p_last: null, p_closing: 100, percent_last: null, vol_ratio: null, buyer_power: null }),
    ];
    expect(sortRows(rows, 'last_vs_close', 'desc').map((r) => r.symbol)).toEqual(['الف', 'ب', 'ج']);
    expect(sortRows(rows, 'pct_last', 'desc').map((r) => r.symbol)).toEqual(['ب', 'الف', 'ج']);
    expect(sortRows(rows, 'vol_ratio', 'desc').map((r) => r.symbol)).toEqual(['ب', 'الف', 'ج']);
    expect(sortRows(rows, 'buy_sell', 'desc').map((r) => r.symbol)).toEqual(['ب', 'الف', 'ج']);
  });
});

describe('canonical tape badges and buy/sell metrics', () => {
  it('uses the canonical verdict instead of a contradictory raw flag', () => {
    const rawOnly = row({ symbol: 'خام', f_clock: true });
    const formulaRejected = row({
      symbol: 'رد', p_last: 100, p_closing: 100, hist_sessions: 30,
      prior30_vol: 1_000, min_low_29: 90, vol_ratio_file: 4, z_tot_tran: 100,
      f_clock: true,
    });
    expect(patternBadges(rawOnly, DEFAULT_TAPE_FILTER_CONFIG).some((b) => b.pattern === 'clock')).toBe(true);
    expect(patternBadges(formulaRejected, DEFAULT_TAPE_FILTER_CONFIG).some((b) => b.pattern === 'clock')).toBe(false);
  });

  it('derives per-capita buy value and refuses a one-sided share bar', () => {
    const value = buyPerCapitaMt({
      buy_i_vol: 1_000,
      buy_count_i: 10,
      q_tot_cap: 2_000_000,
      q_tot_tran: 1_000,
      p_closing: 2_000,
    });
    expect(value).toBeCloseTo(0.02);
    expect(buySellShare(value, null)).toBeNull();
  });
});

describe('column selection and table wiring', () => {
  it('persists column toggles and resets the selection with the profile', () => {
    const initial = useMarketPrefs.getState().visibleColumns;
    useMarketPrefs.getState().toggleColumn('patterns');
    expect(useMarketPrefs.getState().visibleColumns).not.toEqual(initial);
    useMarketPrefs.getState().setProfile('trading');
    expect(useMarketPrefs.getState().visibleColumns).toEqual(defaultColumns('trading'));
  });

  it('emits a column toggle from the toolbar', () => {
    const onToggleColumn = vi.fn();
    render(
      <BoardToolbar
        query=""
        onQuery={noop}
        profile="general"
        onProfile={noop}
        density="compact"
        onDensity={noop}
        columns={['symbol', 'last']}
        onToggleColumn={onToggleColumn}
        assetTypes={['stock']}
        onAssetTypes={noop}
        filters={DEFAULT_BOARD_FILTER_VALUES}
        onFilters={noop}
        sectors={[]}
        pollMs={5_000}
        onPollMs={noop}
      />,
    );
    fireEvent.click(screen.getByTestId('columns-btn'));
    fireEvent.click(screen.getByTestId('column-patterns'));
    expect(onToggleColumn).toHaveBeenCalledWith('patterns');
  });

  it('renders the tape headers and canonical pattern cell without the interim active tape prop', () => {
    render(
      <BoardTable
        rows={[row({ symbol: 'خام', f_clock: true }), row({ symbol: 'رد', f_clock: false })]}
        columns={['symbol', 'last_vs_close', 'pct_last', 'vol_ratio', 'buy_sell', 'patterns']}
        sortKey="vol_ratio"
        sortDir="desc"
        density="compact"
        filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
        selectedKey={null}
        resetKey="test"
        onSort={noop}
        onSelect={noop}
      />,
    );
    expect(screen.getByText('اختلاف٪')).toBeTruthy();
    expect(screen.getByText('آخرین٪')).toBeTruthy();
    expect(screen.getByText('حجم/ماه')).toBeTruthy();
    expect(screen.getByText('خرید / فروش')).toBeTruthy();
    expect(screen.getByText('الگو')).toBeTruthy();
    expect(screen.getAllByTestId('badge-clock')).toHaveLength(1);
  });
});
