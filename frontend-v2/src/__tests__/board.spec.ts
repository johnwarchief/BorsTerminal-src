import { describe, expect, it } from 'vitest';
import { MarketFeedSchema } from '@shared/types/market';
import {
  COLUMNS,
  defaultColumns,
  gridTemplate,
  sortRows,
} from '@features/market/lib/columns';
import { matchTape, rowTapes, tapeCounts } from '@features/market/lib/tapeFilters';

const payload = {
  status: 'success',
  count: 3,
  live_count: 2,
  fossil_count: 1,
  rev: 10,
  rev_at: 1,
  meta: { d_even: 20261014, h_even: 183235, last_sync: '2026-10-14 19:26:09' },
  data: [
    {
      ins_code: '1',
      symbol: 'آباد',
      name: 'توریستی ورفاهی آبادگران ایران',
      sector_name: 'هتل و رستوران',
      p_last: 1392,
      p_closing: 1392,
      price_yesterday: 1352,
      price_change: 40,
      percent_change: null,
      q_tot_tran: 217797702,
      q_tot_cap: 303174401184,
      retail_buy_pct: 55.2,
      f_smart: 1,
      f_jet: 0,
    },
    {
      ins_code: '2',
      symbol: 'فولاد',
      name: 'فولاد مبارکه اصفهان',
      sector_name: 'فلزات اساسی',
      p_last: 5000,
      p_closing: 4980,
      price_yesterday: 5000,
      price_change: -20,
      percent_change: -0.4,
      q_tot_tran: 1_000_000_000,
      q_tot_cap: 5e12,
      retail_buy_pct: 31,
      f_smart: 0,
      f_jet: true,
    },
    {
      ins_code: '3',
      symbol: 'خساپا',
      name: 'سایپا',
      sector_name: 'خودرو',
      p_last: null,
      p_closing: 2100,
      price_yesterday: 2100,
      price_change: 0,
      percent_change: 0,
      q_tot_tran: null,
      q_tot_cap: null,
    },
  ],
};

describe('market feed schema', () => {
  it('parses the live payload shape and keeps unknown fields', () => {
    const feed = MarketFeedSchema.parse({ ...payload, extra_journal: 'x' });
    expect(feed.data).toHaveLength(3);
    expect(feed.count).toBe(3);
    expect((feed as Record<string, unknown>).extra_journal).toBe('x');
  });

  it('accepts boolean and numeric flags side by side', () => {
    const feed = MarketFeedSchema.parse(payload);
    expect(feed.data[0]?.f_smart).toBe(1);
    expect(feed.data[1]?.f_jet).toBe(true);
  });
});

describe('tape filters (single select)', () => {
  const feed = MarketFeedSchema.parse(payload);

  it('counts each tape over the given base', () => {
    const counts = tapeCounts(feed.data);
    expect(counts.f_smart).toBe(1);
    expect(counts.f_jet).toBe(1);
    expect(counts.f_roobi).toBe(0);
  });

  it('matches only the picked tape, and everything when none is picked', () => {
    const first = feed.data[0]!;
    expect(matchTape(first, 'f_smart')).toBe(true);
    expect(matchTape(first, 'f_jet')).toBe(false);
    expect(matchTape(first, null)).toBe(true);
    expect(rowTapes(first)).toEqual(['f_smart']);
  });
});

describe('board columns and sorting', () => {
  const feed = MarketFeedSchema.parse(payload);

  it('keeps unreachable columns out of the default profile', () => {
    expect(defaultColumns('general')).not.toContain('eps');
    expect(defaultColumns('general')).not.toContain('tech');
    expect(defaultColumns('general')).toContain('mcap');
    expect(defaultColumns('technical')).toEqual(['symbol', 'last', 'pct_close', 'volume']);
    expect(COLUMNS.eps.available).toBe(false);
    expect(COLUMNS.tech.available).toBe(false);
  });

  it('builds the grid template from the prototype widths', () => {
    expect(gridTemplate(['symbol', 'last'])).toBe('minmax(154px, var(--sym-max)) minmax(62px, 1fr)');
  });

  it('sorts by trade value descending with missing values last', () => {
    const rows = sortRows(feed.data, 'value', 'desc');
    expect(rows.map((r) => r.symbol)).toEqual(['فولاد', 'آباد', 'خساپا']);
  });

  it('keeps missing values last in ascending order too', () => {
    const rows = sortRows(feed.data, 'value', 'asc');
    expect(rows.map((r) => r.symbol)).toEqual(['آباد', 'فولاد', 'خساپا']);
  });

  it('derives the change percent when the server field is missing', () => {
    const rows = sortRows(feed.data, 'pct_close', 'desc');
    expect(rows[0]?.symbol).toBe('آباد');
    expect(rows.at(-1)?.symbol).toBe('فولاد');
  });

  it('sorts symbols with the persian collator', () => {
    const rows = sortRows(feed.data, 'symbol', 'asc');
    expect(rows.map((r) => r.symbol)).toEqual(
      [...feed.data].map((r) => r.symbol).sort((a, b) => a.localeCompare(b, 'fa')),
    );
  });
});
