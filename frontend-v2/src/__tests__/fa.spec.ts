import { describe, expect, it } from 'vitest';
import { changePct, fmtHemmat, fmtInt, fmtPct, fmtShare, isOn, toFaDigits } from '@shared/lib/fa';
import { normalizeFa } from '@shared/lib/faSearch';
import { jalaliFromYmd } from '@shared/lib/jalali';

describe('fa digits and units', () => {
  it('converts ascii digits to persian', () => {
    expect(toFaDigits('0123456789')).toBe('۰۱۲۳۴۵۶۷۸۹');
  });

  it('groups integers with persian digits', () => {
    expect(fmtInt(1234567)).toBe('۱,۲۳۴,۵۶۷');
    expect(fmtInt(null)).toBe('—');
  });

  it('keeps the sign of a percent change', () => {
    expect(fmtPct(1.234)).toBe('+۱.۲۳٪');
    expect(fmtPct(-2)).toBe('−۲.۰۰٪');
    expect(fmtPct(0)).toBe('۰.۰۰٪');
  });

  it('formats hemmat without inventing zeros', () => {
    expect(fmtHemmat(2.5e13)).toBe('۲.۵۰');
    expect(fmtHemmat(undefined)).toBe('—');
  });

  it('formats a share percent', () => {
    expect(fmtShare(42.15)).toBe('۴۲.۱٪');
    expect(fmtShare(null)).toBe('—');
  });
});

describe('changePct fallback', () => {
  it('prefers the explicit percent', () => {
    expect(changePct(3.2, 99, 100)).toBe(3.2);
  });

  it('derives from yesterday when the explicit field is missing', () => {
    expect(changePct(null, 40, 1352)).toBeCloseTo(2.9586, 3);
  });

  it('returns null instead of a fabricated zero', () => {
    expect(changePct(null, 40, 0)).toBeNull();
    expect(changePct(null, null, 100)).toBeNull();
  });
});

describe('flag coercion', () => {
  it('accepts boolean, number and string truthy forms', () => {
    expect(isOn(true)).toBe(true);
    expect(isOn(1)).toBe(true);
    expect(isOn('1')).toBe(true);
    expect(isOn(0)).toBe(false);
    expect(isOn(null)).toBe(false);
  });
});

describe('fa search normalisation', () => {
  it('unifies arabic letters and zwnj', () => {
    expect(normalizeFa('كشتاوري')).toBe('کشتاوری');
    expect(normalizeFa('آ س  پ')).toBe('آ س پ');
  });
});

describe('jalali date from board ymd', () => {
  it('formats 20261014 as a persian calendar date', () => {
    const out = jalaliFromYmd(20261014);
    expect(out).toContain('۱۴۰۵');
  });

  it('rejects a missing date', () => {
    expect(jalaliFromYmd(null)).toBe('—');
  });
});
