import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { CARD_ORDER, CARD_REGISTRY } from '@features/market/components/cards/registry';
import type { MarketSnapshot } from '@features/market/api/useMarketSnapshot';

const rows = [
  { symbol: 'الف', ins_code: '10', price_yesterday: 100, p_closing: 110, percent_change: 10,
    q_tot_cap: 6_000_000_000, q_tot_tran: 2_000_000, pe: 7, mcap: 1e12 },
  { symbol: 'ب', ins_code: '20', price_yesterday: 200, p_closing: 180, percent_change: -10,
    q_tot_cap: 4_000_000_000, q_tot_tran: 1_000_000, pe: null, mcap: 2e12 },
] as MarketRow[];

const snapshot = {
  status: 'ok',
  index: { d_even: 20261028, last: 8_000_000, change: 80_000, pct: 1.0,
    ew_last: 2_200_000, ew_change: 4_400, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 7_920_000, change: 0, pct: 0,
    ew_last: 2_100_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 600_000, q_tot_cap: 4e14, q_tot_tran: 8e9 },
  market: { trade_value_hemat: 40, volume: 1e10, trades: 800_000, market_value_hemat: 8000 },
  retail: { value_hemat: 45, state: 'good', label: 'مساعد', good_min: 20, bad_max: 10,
    excellent_min: 50, basis: 'b', cause: null },
} as MarketSnapshot;

const ctx = { rows, snapshot };

describe('card registry', () => {
  it('has every card in the order', () => {
    expect(CARD_ORDER.sort()).toEqual(Object.keys(CARD_REGISTRY).sort());
  });

  it('reads the index and withholds delta without a previous session', () => {
    expect(CARD_REGISTRY.tedpix.value(ctx)).toContain('۸');
    const noPrev = { ...ctx, snapshot: { ...snapshot, prev: null } };
    expect(CARD_REGISTRY.tedpix.delta(noPrev)).toBeNull();
    expect(CARD_REGISTRY.tedpix.preview(noPrev)[0]!.note).toContain('نشست');
  });

  it('marks board cards with the board basis and never mixes retail', () => {
    const value = CARD_REGISTRY.boardValueComposition;
    expect(value.basis).toBe('board');
    expect(value.value(ctx)).not.toBeNull();
    expect(value.preview(ctx).some((row) => row.label === 'سهام')).toBe(true);
  });

  it('shows a dash when the snapshot is missing', () => {
    expect(CARD_REGISTRY.retailValue.value({ rows })).toBeNull();
    expect(CARD_REGISTRY.marketTrades.value({ rows })).toBeNull();
  });

  it('counts breadth from rows', () => {
    expect(CARD_REGISTRY.breadth.value(ctx)).toContain('۱');
  });
});
