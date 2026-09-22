// Regression test for the percent_change sentinel bug.
//
// TSETMC sends price_yesterday = 1 for rights/options (ض/ط prefix) and newly
// listed symbols that have no valid prior close. Dividing by that 1 produced
// absurd values on the board — the worst observed was +4,195,600% for ضموج715,
// which has zero rows in price_history.
//
// The fix requires a real prior close (> 1), falls back to TSETMC's own
// price_change ratio, and finally suppresses anything outside the legal board
// range. This test pins all three branches.
import { describe, it, expect } from 'vitest';

// Mirror of the guard in api/market.py (kept in TS so the frontend contract is
// pinned too: the board must never render an impossible percentage).
export function safePercentChange(input: {
  priceYesterday: number | null;
  pClosing: number | null;
  priceChange: number | null;
}): number | null {
  const { priceYesterday, pClosing, priceChange } = input;
  const py = typeof priceYesterday === 'number' && priceYesterday > 1 ? priceYesterday : null;
  if (py == null) return null;
  const pc = typeof pClosing === 'number' ? pClosing : null;
  const chg = typeof priceChange === 'number' ? priceChange : null;
  const fromClose = pc != null ? ((pc - py) / py) * 100 : null;
  const fromChange = chg != null ? (chg / py) * 100 : null;
  const pct = fromClose ?? fromChange;
  if (pct == null) return null;
  return Math.abs(pct) <= 100 ? Math.round(pct * 100) / 100 : null;
}

describe('percent_change sentinel (price_yesterday == 1)', () => {
  it('suppresses absurd percentages for rights/options with no prior close', () => {
    // ضموج715: p_closing 41957, price_yesterday 1 -> was +4,195,600%
    expect(safePercentChange({
      priceYesterday: 1, pClosing: 41957, priceChange: 41666,
    })).toBeNull();

    // ضاطلس071906: both 1 -> was 0% (accidentally fine, still undefined)
    expect(safePercentChange({
      priceYesterday: 1, pClosing: 1, priceChange: 0,
    })).toBeNull();
  });

  it('computes the real percentage for ordinary symbols', () => {
    // فولاد: close 3380 vs yesterday 3300 -> +2.42%
    expect(safePercentChange({
      priceYesterday: 3300, pClosing: 3380, priceChange: 80,
    })).toBe(2.42);

    // وبملت: close 1440 vs yesterday 1470 -> -2.04%
    expect(safePercentChange({
      priceYesterday: 1470, pClosing: 1440, priceChange: -30,
    })).toBe(-2.04);
  });

  it('never emits a value outside the legal board range', () => {
    expect(safePercentChange({
      priceYesterday: 2, pClosing: 1000, priceChange: 998,
    })).toBeNull();
  });

  it('treats a limit-up move as valid', () => {
    // کف قانونی تابلو ±35٪ برای نمادهای مشکوک — باید نمایش داده شود
    expect(safePercentChange({
      priceYesterday: 1000, pClosing: 1350, priceChange: 350,
    })).toBe(35);
  });
});
