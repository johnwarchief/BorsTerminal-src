// تست موتور تعدیلِ چارت نهایت‌نگر (T-17): منبع واحد = نسبت گسست قیمت پایهٔ سرور ({date,ratio})
import { describe, expect, it } from 'vitest';
import {
  applyAdjustmentToCandles,
  getAdjustmentFactor,
  mapBackendAdjustEvents,
  pricePrecisionFor,
  adjustmentGapNote,
  readAdjustmentCapability,
  toIndexedSeries,
} from '@features/technical/nahayatnegar/lib/adjustments';
import type { KLineData } from 'klinecharts';

const t = (s: string) => Date.parse(`${s}T00:00:00Z`);

const candles = [
  { timestamp: t('2020-01-08'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-09'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-12'), open: 50, high: 55, low: 48, close: 50, volume: 2000 },
] as unknown as KLineData[];

const events = mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0.5 }]);

describe('تعدیل چارت نهایت‌نگر (نسبت سرور)', () => {
  it('«بدون تعدیل» ⇒ قیمت خام دست‌نخورده', () => {
    const out = applyAdjustmentToCandles(candles, events, 'none');
    expect(out[0].close).toBe(100);
    expect(out[2].close).toBe(50);
  });

  it('تعدیل ترکیبی ⇒ کندل‌های پیش از رویداد در نسبت ضرب، حجم تقسیم، پس از رویداد خام', () => {
    const out = applyAdjustmentToCandles(candles, events, 'combined');
    expect(out[0].close).toBe(50);       // 100 × 0.5
    expect(out[1].close).toBe(50);
    expect(out[0].volume).toBe(2000);    // 1000 ÷ 0.5
    expect(out[2].close).toBe(50);       // کندلِ پس از رویداد دست‌نخورده
    expect(out[2].volume).toBe(2000);
  });

  it('نگاشت رویدادِ سرور نسبت را حفظ می‌کند و timestamp درست می‌سازد', () => {
    expect(events).toHaveLength(1);
    expect(events[0].ratio).toBe(0.5);
    expect(events[0].timestamp).toBe(t('2020-01-11'));
  });

  it('بدون رویداد ⇒ همان سری (بدون تغییر)', () => {
    const out = applyAdjustmentToCandles(candles, [], 'combined');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
  });

  it('رویدادِ بی‌تاریخ یا نسبتِ نامعقول حذف می‌شود — نه «امروز»', () => {
    // با timestamp=امروز، هر کندلِ موجود زیرِ رویداد می‌افتاد و کل سری مقیاس می‌شد
    expect(mapBackendAdjustEvents([{ date: null, ratio: 0.5 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: 'not-a-date', ratio: 0.5 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 1e-9 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 900 }])).toEqual([]);
    const series = applyAdjustmentToCandles(candles, mapBackendAdjustEvents([{ date: null, ratio: 0.5 }]), 'combined');
    expect(series.map((c) => c.close)).toEqual([100, 100, 50]);
  });

  it('نسبتِ سالم می‌ماند و فاکتورِ اعمال‌شده همان چیزی است که نشانگر نشان می‌دهد', () => {
    const [a] = mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0.5 }]);
    expect(getAdjustmentFactor(a)).toBe(0.5);
    expect(getAdjustmentFactor({ ...a, ratio: 0.00005 })).toBe(0.0001);   // clamp پایین
    expect(getAdjustmentFactor({ ...a, ratio: 500 })).toBe(50);        // clamp بالا
  });

  // ── تعدیل عملکردی (نمایِ بازدهی) ───────────────────────────────────────
  it('«عملکردی» رویِ سریِ تعدیل‌شده می‌نشیند، نه رویِ قیمتِ خام', () => {
    // ترکیبی: [50,50,50] — سهمِ افزایش سرمایه در قیمتِ پایه خنثی شده
    // عملکردی: همان سری ÷ ۵۰ × ۱۰۰ ⇒ [۱۰۰،۱۰۰،۱۰۰]
    const out = applyAdjustmentToCandles(candles, events, 'performance');
    expect(out.map((c) => c.close)).toEqual([100, 100, 100]);
    expect(out[0].timestamp).toBe(candles[0].timestamp);
  });

  it('«عملکردی» بی‌رویداد ⇒ بازدهیِ خام، و حجم/گردش دست‌نخورده (قیمت نیستند)', () => {
    const out = applyAdjustmentToCandles(candles, [], 'performance');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
    expect(out[2].volume).toBe(2000);
  });

  it('پایهٔ صفر یا تهی ⇒ سری بی‌تغییر برمی‌گردد، نه صفرِ جعلی یا بی‌نهایت', () => {
    const zero = [{ timestamp: t('2020-01-08'), open: 0, high: 0, low: 0, close: 0 }] as unknown as KLineData[];
    expect(toIndexedSeries(zero)[0].close).toBe(0);
    expect(toIndexedSeries([])).toEqual([]);
  });

  it('بازدهی دو رقمِ ممیز دارد — گردکردنِ صحیح یعنی ۱۰۰٫۴٪ بشود ۱۰۰٪', () => {
    const mild = [{ timestamp: t('2020-01-08'), open: 1000, high: 1000, low: 1000, close: 1000 },
                  { timestamp: t('2020-01-09'), open: 1004, high: 1004, low: 1004, close: 1004 }] as unknown as KLineData[];
    const out = applyAdjustmentToCandles(mild, [], 'performance');
    expect(out[1].close).toBe(100.4);
  });

  it('دقتِ محور با حالت عوض می‌شود (عملکردی ۲ رقم، بقیه صحیح)', () => {
    expect(pricePrecisionFor('performance')).toBe(2);
    expect(pricePrecisionFor('combined')).toBe(0);
    expect(pricePrecisionFor('none')).toBe(0);
  });
});

// PHASE A (Round K): جداسازیِ معناییِ تعدیل — چهار مفهوم، یک ضرب
describe("PHASE A — جداسازیِ معناییِ تعدیل", () => {
  it("«نمایِ بازدهی» فقط شاخصِ نخستینِ پایانی نیست: با رویداد ≠ شاخصِ خام", () => {
    const perf = applyAdjustmentToCandles(candles, events, "performance");
    const indexedRaw = toIndexedSeries(candles);
    expect(perf.map((c) => c.close)).not.toEqual(indexedRaw.map((c) => c.close));
  });

  it("combined ≠ indexed: indexed همان combined ÷ پایانیِ اول × ۱۰۰ است، نه سرمایه‌گذاریِ دوبارهٔ سود", () => {
    const comb = applyAdjustmentToCandles(candles, events, "combined");
    const perf = applyAdjustmentToCandles(candles, events, "performance");
    const k = 100 / comb[0].close;
    perf.forEach((c, i) => expect(c.close).toBeCloseTo(comb[i].close * k, 2));
  });

  it("تعدیلِ دوباره سری را عوض می‌کند ⇒ مصرف‌کننده باید خام بدهد؛ «none» بی‌تغییر برمی‌گرداند", () => {
    const once = applyAdjustmentToCandles(candles, events, "combined");
    const twice = applyAdjustmentToCandles(once, events, "combined");
    expect(twice[0].close).not.toBe(once[0].close);
    expect(applyAdjustmentToCandles(candles, events, "none").map((c) => c.close))
      .toEqual(candles.map((c) => c.close));
  });

  it("فال‌بکِ بی‌بلوکِ توانایی، combined را «هست» جا نمی‌زند و هشدار می‌دهد", () => {
    const unseen = readAdjustmentCapability({ adjustEvents: [] });
    expect(unseen.combinedAvailable).toBe(false);
    expect(unseen.functionalAvailable).toBe(false);
    expect(adjustmentGapNote("performance", unseen)).toContain("در دسترس نیست");
    const cached = readAdjustmentCapability({ adjustCapability: {
      source: "local-cache", combined_available: true, functional_available: false,
      functional_reason: "r", event_count: 3 } });
    expect(cached.combinedAvailable).toBe(true);
    expect(adjustmentGapNote("performance", cached)).toBeNull();
    expect(adjustmentGapNote("none", unseen)).toBeNull();
  });

  it("ترتیبِ رویداد در ورودی، داوری را عوض نمی‌کند", () => {
    const two = mapBackendAdjustEvents([{ date: "2020-01-11", ratio: 0.5 },
                                        { date: "2020-01-13", ratio: 0.8 }]);
    const rev = [...two].reverse();
    expect(applyAdjustmentToCandles(candles, two, "combined").map((c) => c.close))
      .toEqual(applyAdjustmentToCandles(candles, rev, "combined").map((c) => c.close));
  });

  it("هندسهٔ OHLC پس از هر دو حالت حفظ می‌شود", () => {
    for (const mode of ["combined", "performance"] as const) {
      for (const c of applyAdjustmentToCandles(candles, events, mode)) {
        expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
        expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
      }
    }
  });
});
