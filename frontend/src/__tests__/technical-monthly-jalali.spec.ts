// Round 23: Rahavard's monthly bars are Jalali months, not Gregorian ones.
// 2026-09-23 is 1 Mehr 1405, 2026-10-22 is 30 Mehr, and 2026-10-23 is
// 1 Aban; the Gregorian bucket split Mehr at 2026-10-01.
import { describe, expect, it } from 'vitest';
import type { KLineData } from 'klinecharts';
import { aggregateCandles } from '@features/technical/nahayatnegar/lib/timeframe';
import { epochToJalali } from '@features/technical/lib/jalaliDate';

const t = (s: string) => Date.parse(`${s}T00:00:00Z`);
const bar = (s: string, o: number, h: number, l: number, c: number, v: number) =>
  ({ timestamp: t(s), open: o, high: h, low: l, close: c, volume: v }) as unknown as KLineData;

describe('monthly aggregation follows the Jalali calendar (Rahavard contract)', () => {
  it('confirms the boundary dates', () => {
    expect(epochToJalali(t('2026-09-23'))).toBe('1405/07/01');
    expect(epochToJalali(t('2026-10-22'))).toBe('1405/07/30');
    expect(epochToJalali(t('2026-10-23'))).toBe('1405/08/01');
  });

  it('keeps a whole Jalali month in one bar across a Gregorian month boundary', () => {
    const daily = [
      bar('2026-09-22', 100, 110, 90, 105, 10),
      bar('2026-09-23', 200, 220, 190, 210, 20),
      bar('2026-10-01', 300, 330, 280, 320, 30),
      bar('2026-10-22', 400, 450, 390, 440, 40),
      bar('2026-10-23', 500, 510, 490, 505, 50),
    ];
    const monthly = aggregateCandles(daily, 'M');
    expect(monthly).toHaveLength(3);
    const mehr = monthly[1];
    expect(new Date(mehr.timestamp).toISOString().slice(0, 10)).toBe('2026-10-22');
    expect(mehr.open).toBe(200);
    expect(mehr.high).toBe(450);
    expect(mehr.low).toBe(190);
    expect(mehr.close).toBe(440);
    expect(mehr.volume).toBe(90);
    expect(monthly[0].timestamp).toBe(t('2026-09-22'));
    expect(monthly[2].timestamp).toBe(t('2026-10-23'));
  });
});
