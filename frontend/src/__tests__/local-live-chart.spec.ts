// تست توابع خالص چارت زندهٔ موبایل (shared/api/local/live.ts) — همتای api/chart.py
//   parseTsetmcCsv       ← _parse_tsetmc_csv (هدرمحور v9.7 + ترمیم هندسه + LAST-CLAMP)
//   adjustEventsFromRows ← _adjust_events_from_rows (درِ لنگر ANCHOR_MIN + آستانهٔ ADJ_TOL)
import { describe, expect, it } from 'vitest';
import { adjustEventsFromRows, parseTsetmcCsv } from '../shared/api/local/live';

const HDR = '<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>';

function row(d: string, first: number, hi: number, lo: number, close: number,
             vol: number, base: number, last: number): string {
  return `فولاد,${d},${first},${hi},${lo},${close},0,${vol},0,D,${base},${last}`;
}

describe('parseTsetmcCsv', () => {
  it('کندل عادی: open از FIRST، حجم و رنگ درست', () => {
    const { candles, volumes, allRows } = parseTsetmcCsv(
      [HDR, row('20250101', 100, 110, 95, 105, 5000, 98, 104)].join('\n'),
    );
    expect(candles).toEqual([
      { time: '2025-01-01', open: 100, high: 110, low: 95, close: 105, last: 104 },
    ]);
    expect(volumes[0]).toEqual({ time: '2025-01-01', value: 5000, color: '#10b981' });
    expect(allRows).toEqual([{ time: '2025-01-01', base: 98, close: 105 }]);
  });

  it('FIRST=۰ → open از پایهٔ clampشده؛ روز بی‌معامله کندل نمی‌شود ولی در allRows می‌ماند', () => {
    const { candles, allRows } = parseTsetmcCsv(
      [HDR,
       row('20250101', 0, 1825, 1825, 1825, 10, 1756, 1825), // FIRST صفر ⇒ open=پایه داخل بازه
       row('20250102', 0, 0, 0, 1800, 0, 1825, 0),           // H=L=۰ ⇒ بدون کندل
      ].join('\n'),
    );
    expect(candles).toHaveLength(1);
    expect(candles[0].open).toBe(1825); // پایهٔ ۱۷۵۶ داخل [۱۸۲۵،۱۸۲۵] clamp شد
    expect(allRows).toHaveLength(2);    // تشخیص تعدیل هر دو روز را می‌خواهد
  });

  it('ترمیم هندسه: پایانی بیرون سایه ⇒ سایه گشاد می‌شود؛ LAST بیرون بازه clamp می‌شود', () => {
    const { candles } = parseTsetmcCsv(
      [HDR, row('20250101', 1950, 1973, 1973, 1917, 100, 1970, 5000)].join('\n'),
    );
    expect(candles[0].low).toBe(1917);   // low تا پایانی پایین آمد
    expect(candles[0].high).toBe(1973);
    expect(candles[0].last).toBe(1973);  // LAST معیوب ⇒ داخل [low,high]
  });
});

describe('adjustEventsFromRows', () => {
  const chain = (n: number, close: number) =>
    Array.from({ length: n }, (_, i) => ({
      time: `2025-01-${String(i + 1).padStart(2, '0')}`, base: close, close,
    }));

  it('شکست زنجیرهٔ base==close دیروز ⇒ رویداد با ratio درست', () => {
    // ۳ روز ۱۰۰۰؛ روز چهارم پایه ۵۰۰ (تعدیل ۵۰٪)
    const rows = [
      { time: '2025-01-01', base: 990, close: 1000 },
      { time: '2025-01-02', base: 1000, close: 1000 },
      { time: '2025-01-03', base: 1000, close: 1000 },
      { time: '2025-01-04', base: 500, close: 510 },
    ];
    expect(adjustEventsFromRows(rows)).toEqual([{ date: '2025-01-04', ratio: 0.5 }]);
  });

  it('نوسان زیر آستانه (ADJ_TOL) رویداد نمی‌سازد', () => {
    const rows = chain(5, 10000);
    rows[3] = { ...rows[3], base: 10005 }; // ۰٫۰۵٪ < ۰٫۱٪
    expect(adjustEventsFromRows(rows)).toEqual([]);
  });

  it('درِ لنگر: صندوق NAVمحور (base هرگز به پایانی زنجیر نیست) ⇒ هیچ رویدادی', () => {
    const rows = Array.from({ length: 30 }, (_, i) => ({
      time: `2025-01-${String(i + 1).padStart(2, '0')}`,
      base: 10000 + i * 7 + 3,   // همیشه ≠ پایانی دیروز
      close: 10000 + i * 7,
    }));
    expect(adjustEventsFromRows(rows)).toEqual([]);
  });

  it('سری کوتاه (<۲۰ جفت) از درِ لنگر معاف است و رویداد واقعی را می‌دهد', () => {
    const rows = [...chain(5, 2000), { time: '2025-01-06', base: 1000, close: 1010 }];
    expect(adjustEventsFromRows(rows)).toEqual([{ date: '2025-01-06', ratio: 0.5 }]);
  });
});
