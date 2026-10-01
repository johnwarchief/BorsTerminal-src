// __tests__/technical-range-replay-v1066.spec.ts — دو کنترلِ مردهٔ تب تکنیکال
// ۱) دکمه‌های «بازه زمانی» فقط برچسبِ فعال را جابه‌جا می‌کردند و چارت زوم نمی‌شد.
// ۲) «بازپخش» مکان‌نما را جلو می‌برد ولی هیچ‌کس سری را نمی‌برید، پس هیچ کندلی
//    پنهان نمی‌شد. هر دو از همان تابعِ خالصِ این‌جا حساب می‌شوند — تستِ بدونِ DOM.
// ۳) سطحِ ۰٫۵ فیبو در جزوه هست («۰ و ۰.۳۳ و ۰.۴ و ۰.۵ و ۰.۶۱۸ و ۰.۷ و ۱») ولی
//    در رسمِ فرانت جا افتاده بود؛ فهرستِ فرانت باید با بک‌اند یکی بماند.
import { describe, expect, it } from 'vitest';
import { rangeVisibleBars, VIEW_RANGES } from '@features/technical/nahayatnegar/lib/timeframe';
import { FTS_FIB_LEVELS } from '@features/technical/lib/ftsOverlays';
import { replaySlice } from '@features/technical/lib/replay';

const DAY = 86_400_000;
const t0 = Date.UTC(2025, 0, 1);
const series = (n: number) => Array.from({ length: n }, (_, i) => ({ timestamp: t0 + i * DAY }));

describe('دکمه‌های بازۀ زمانی', () => {
  const bars = series(400);

  it('«All» تمامِ سری را می‌خواهد و فهرستِ کلیدها همان دکمه‌های نوارند', () => {
    expect(rangeVisibleBars('All', bars)).toBe(400);
    expect(VIEW_RANGES).toEqual(['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'All']);
  });

  it('شمارش تقویمی است: ۳M روی سریِ روزانه حدودِ نود‌وسه کندلِ آخر', () => {
    const n = rangeVisibleBars('3M', bars);
    expect(n).toBeGreaterThanOrEqual(90);
    expect(n).toBeLessThanOrEqual(93);
  });

  it('کلیدِ ناشناخته سری را کوتاه نمی‌کند (فول‌دید، نه صفر)', () => {
    expect(rangeVisibleBars('??', bars)).toBe(400);
    expect(rangeVisibleBars('All', [])).toBe(0);
  });

  it('روی سریِ روزانه «۱ روز» تک‌کندل نمی‌شود — حداقلِ دیدِ خوانا می‌ماند', () => {
    expect(rangeVisibleBars('1D', bars)).toBe(5);
    expect(rangeVisibleBars('1D', series(3))).toBe(3);
  });

  it('YTD فقط سالِ جلالیِ کندلِ آخر را می‌شمارد', () => {
    // ۱۴۰۵/۰۱/۰۱ = ۲۰۲۶-۰۳-۲۱؛ دو کندل قبل از آن به سالِ قبل تعلق دارند
    const ytd = series(10).map((_, i) => ({ timestamp: Date.UTC(2026, 2, 19) + i * DAY }));
    expect(rangeVisibleBars('YTD', ytd)).toBe(8);
  });
});

describe('برشِ بازپخش', () => {
  it('کندل‌هایِ بعد از مکان‌نما پنهان می‌شوند و خودِ مکان‌نما می‌ماند', () => {
    const rows = series(20);
    expect(replaySlice(rows, 4).length).toBe(5);
    expect(replaySlice(rows, 4).at(-1)).toBe(rows[4]);
    expect(replaySlice(rows, 999).length).toBe(20);
    expect(replaySlice(rows, -1).length).toBe(1);
  });
});

describe('سطوحِ فیبوی FTS', () => {
  it('عینِ جزوه: صفر، ۰٫۳۳، ۰٫۴، ۰٫۵، ۰٫۶۱۸، ۰٫۷، یک', () => {
    expect([...FTS_FIB_LEVELS]).toEqual([0, 0.33, 0.4, 0.5, 0.618, 0.7, 1]);
  });
});
