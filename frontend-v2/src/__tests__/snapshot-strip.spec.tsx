import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import type { MarketSnapshot } from '@features/market/api/useMarketSnapshot';
import { SnapshotStrip } from '@features/market/components/SnapshotStrip';
import { DEFAULT_SLOTS, useWorkspace } from '@shared/workspace/store';

const rows = [
  { symbol: 'الف', ins_code: '10', price_yesterday: 100, p_closing: 110, percent_change: 10,
    q_tot_cap: 6e9, q_tot_tran: 2e6 },
] as MarketRow[];

const snapshot = {
  status: 'ok',
  index: { d_even: 20261028, last: 8_000_000, change: 1, pct: 1.2,
    ew_last: 2_200_000, ew_change: 1, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 7_900_000, change: 0, pct: 0,
    ew_last: 2_100_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 600_000, q_tot_cap: 4e14, q_tot_tran: 8e9 },
  market: { trade_value_hemat: 40, volume: 1e10, trades: 800_000, market_value_hemat: 8000 },
  retail: { value_hemat: 45, state: 'good', label: 'مساعد', good_min: 20, bad_max: 10,
    excellent_min: 50, basis: 'b', cause: null },
} as MarketSnapshot;

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

afterEach(cleanup);

describe('SnapshotStrip', () => {
  it('renders the four default cards', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    expect(screen.getByTestId('snapshot-strip')).toBeTruthy();
    expect(screen.getAllByTestId(/^card-[a-zA-Z]+$/)).toHaveLength(4);
  });

  it('opens the preview on hover and labels the basis', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.mouseEnter(screen.getByTestId('card-tedpix'));
    const preview = screen.getByTestId('preview-tedpix');
    expect(preview.textContent).toContain('تعداد معاملات');
    expect(preview.textContent).toContain('کل بازار');
  });

  it('shows a dash, not zero, when the snapshot is missing', () => {
    render(<SnapshotStrip rows={rows} />);
    expect(screen.getByTestId('card-retailValue').textContent).toContain('—');
  });

  it('reorders cards and persists the new slots', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.click(screen.getByTestId('card-move-left-tedpix'));
    expect(useWorkspace.getState().workspaces[0].slots[0]).toBe(DEFAULT_SLOTS[1]);
  });

  it('changes a slot from the catalog', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.click(screen.getByTestId('card-pick-tedpix'));
    fireEvent.click(screen.getByTestId('card-option-tedpix-marketTrades'));
    expect(useWorkspace.getState().workspaces[0].slots).toContain('marketTrades');
  });
});
