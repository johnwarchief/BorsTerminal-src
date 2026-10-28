import { describe, expect, it } from 'vitest';
import {
  changePct,
  faNum,
  fmtInt,
  fmtMcap,
  fmtPct,
  fmtPe,
  fmtShare,
  fmtValue,
  fmtVolume,
  isOn,
  toFaDigits,
} from '@shared/lib/fa';
import { normalizeFa } from '@shared/lib/faSearch';
import { jalaliFromYmd } from '@shared/lib/jalali';

describe('fa digits and units', () => {
  it('converts ascii digits to persian', () => {
    expect(toFaDigits('0123456789')).toBe('۰۱۲۳۴۵۶۷۸۹');
  });

  it('groups integers with the persian thousands separator', () => {
    expect(fmtInt(1234567)).toBe('۱٬۲۳۴٬۵۶۷');
    expect(fmtInt(null)).toBe('—');
  });

  it('keeps the sign of a percent change without inventing decimals', () => {
    expect(fmtPct(1.234)).toBe('+۱٫۲۳٪');
    expect(fmtPct(-2)).toBe('−۲٪');
    expect(fmtPct(0)).toBe('۰٪');
    expect(fmtPct(undefined)).toBe('—');
  });

  it('formats trade value in milliard rial like the prototype', () => {
    expect(fmtValue(303174401184)).toBe('۳۰۳');
    expect(fmtValue(5e12)).toBe('۵٬۰۰۰');
    expect(fmtValue(2e9)).toBe('۲');
    expect(fmtValue(null)).toBe('—');
  });

  it('formats market cap in hemmat with one decimal', () => {
    expect(fmtMcap(2.5e13)).toBe('۲٫۵');
    expect(fmtMcap(null)).toBe('—');
  });

  it('formats volume with م and هـ suffixes', () => {
    expect(fmtVolume(217797702)).toBe('۲۱۸ م');
    expect(fmtVolume(1500)).toBe('۲ هـ');
    expect(fmtVolume(null)).toBe('—');
  });

  it('formats P/E and shares', () => {
    expect(fmtPe(8.4)).toBe('۸٫۴');
    expect(fmtPe(140.6)).toBe('۱۴۱');
    expect(fmtPe(null)).toBe('—');
    expect(fmtShare(42.1)).toBe('۴۲٫۱٪');
    expect(fmtShare(null)).toBe('—');
  });

  it('returns an em dash for a non-finite number', () => {
    expect(faNum(Number.NaN)).toBe('—');
    expect(faNum(Number.POSITIVE_INFINITY)).toBe('—');
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
    expect(jalaliFromYmd(20261014)).toBe('۱۴۰۵/۰۷/۲۲');
  });

  it('rejects a missing date', () => {
    expect(jalaliFromYmd(null)).toBe('—');
  });
});
