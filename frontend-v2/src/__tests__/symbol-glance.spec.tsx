import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { SymbolGlance } from '@app/shell/SymbolGlance';

afterEach(cleanup);

describe('SymbolGlance', () => {
  it('never turns a missing number into zero', () => {
    render(<SymbolGlance row={{ symbol: 'الف', ins_code: '10' } as MarketRow} />);
    expect(screen.getByTestId('symbol-price').textContent).toBe('—');
    expect(screen.getByTestId('symbol-stat-pe').textContent).toContain('—');
    expect(screen.getByTestId('symbol-stat-range').textContent).toContain('—');
    expect(screen.queryByTestId('symbol-pressure')).toBeNull();
  });

  it('shows a buy-pressure bar only for the percentages that exist', () => {
    const row = {
      symbol: 'الف', ins_code: '10', p_last: 112, p_closing: 110, percent_change: 1.8,
      retail_buy_pct: 62.4, legal_buy_pct: null,
    } as MarketRow;
    render(<SymbolGlance row={row} />);
    expect(screen.getByTestId('pressure-retail').textContent).toContain('۶۲٫۴');
    expect(screen.queryByTestId('pressure-legal')).toBeNull();
    expect(screen.getByTestId('symbol-pct').textContent).toContain('۱٫۸');
  });

  it('keeps the six key stats in one compact grid', () => {
    const row = {
      symbol: 'الف', ins_code: '10', p_last: 1030, p_closing: 1000, percent_change: 2,
      q_tot_cap: 4_000_000, q_tot_tran: 4000, z_tot_tran: 100,
      pe: 7.4, mcap: 1.2e12, p_min: 990, p_max: 1040,
    } as MarketRow;
    render(<SymbolGlance row={row} />);
    expect(screen.getAllByTestId(/^symbol-stat-/)).toHaveLength(6);
    expect(screen.getByTestId('symbol-stat-trades').textContent).toContain('۱۰۰');
    expect(screen.getByTestId('symbol-stat-pe').textContent).toContain('۷٫۴');
    expect(screen.getByTestId('symbol-stat-range').textContent).toContain('۹۹۰');
  });
});
