import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { TapeFilterChips } from '@features/market/components/TapeFilterChips';

const row = {
  symbol: 'الف', ins_code: '10', is_live: true,
  f_smart: true, f_legal: false, f_susp: null,
} as MarketRow;

afterEach(cleanup);

describe('TapeFilterChips', () => {
  it('renders all seven canonical filters as display-only chips', () => {
    render(<TapeFilterChips row={row} />);
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('takes pass, fail and unevaluated straight from the canonical verdict', () => {
    render(<TapeFilterChips row={row} />);
    expect(screen.getByTestId('symbol-tape-f_smart').getAttribute('data-on')).toBe('true');
    expect(screen.getByTestId('symbol-tape-f_legal').getAttribute('data-on')).toBe('false');
    expect(screen.getByTestId('symbol-tape-f_susp').getAttribute('data-state')).toBe('unevaluated');
    expect(screen.getByTestId('symbol-tape-f_susp').getAttribute('title')).toContain('سنجش');
  });

  it('renders nothing without a row', () => {
    render(<TapeFilterChips row={null} />);
    expect(screen.queryByTestId('symbol-tapes')).toBeNull();
  });
});
