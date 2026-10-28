import { describe, expect, it } from 'vitest';
import { parseSnapshot } from '@features/market/api/useMarketSnapshot';

const good = {
  status: 'ok',
  asof: { d_even: 20261028 },
  index: { d_even: 20261028, last: 8_069_789, change: 12_000, pct: 1.5,
    ew_last: 2_229_587, ew_change: 500, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 8_000_000, change: 0, pct: 0,
    ew_last: 2_220_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 700_000, q_tot_cap: 4e14, q_tot_tran: 9e9 },
  market: { trade_value_hemat: 40.0, volume: 1e10, trades: 800_000, market_value_hemat: 8123.4 },
  retail: { value_hemat: 45.6, state: 'good', label: 'مساعد', good_min: 20,
    bad_max: 10, excellent_min: 50, basis: 'x', cause: null },
};

describe('market snapshot schema', () => {
  it('parses a good payload', () => {
    const snap = parseSnapshot(good);
    expect(snap.index?.last).toBe(8_069_789);
    expect(snap.market?.trades).toBe(800_000);
    expect(snap.retail?.bad_max).toBe(10);
  });

  it('accepts a null previous session', () => {
    expect(parseSnapshot({ ...good, prev: null }).prev).toBeNull();
  });

  it('rejects an error envelope', () => {
    expect(() => parseSnapshot({ status: 'error', message: 'x' })).toThrow();
  });

  it('rejects NaN-ish strings instead of coercing', () => {
    expect(() => parseSnapshot({ ...good, index: { ...good.index, last: '8.0' } })).toThrow();
  });
});
