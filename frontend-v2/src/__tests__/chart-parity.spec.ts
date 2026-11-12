import { describe, expect, it } from 'vitest';
import { toKlineBars } from '@features/chart/api/useChart';

// وغدير 1996-03-17 از captureِ پین‌شدهٔ Rahavard (bars-all.ndjson.gz،
// sha256 272336c0…): type0 چهار قیمت ۱۳۰۰ و حجم ۲٬۱۷۸٬۰۶۰؛ type7 هر چهار قیمت
// ۰٫۳۱۳۴۳۰۵۹۷۸۹۶۴۱۷۳ و همان حجم. قانونِ اندازه‌گیری‌شده: type7 = type0 × factor
// و حجم دست‌نخورده.
const REF = {
  time: '1996-03-17',
  open: 1300, high: 1300, low: 1300, close: 1300, volume: 2178060,
};
const FACTOR = 0.00024110045992032102;
const ADJUSTED = 0.3134305978964173;

describe('toKlineBars reference parity', () => {
  it('keeps the fractional adjusted price instead of rounding it to an integer', () => {
    const [bar] = toKlineBars([REF], [{ time: REF.time, factor: FACTOR }]);
    expect(bar!.open).toBe(ADJUSTED);
    expect(bar!.high).toBe(ADJUSTED);
    expect(bar!.low).toBe(ADJUSTED);
    expect(bar!.close).toBe(ADJUSTED);
  });

  it('serves the reference volume untouched, never divided by the factor', () => {
    const [bar] = toKlineBars([REF], [{ time: REF.time, factor: FACTOR }]);
    expect(bar!.volume).toBe(REF.volume);
  });
});