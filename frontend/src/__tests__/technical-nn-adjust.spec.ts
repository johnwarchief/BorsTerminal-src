// تست موتور تعدیلِ چارت نهایت‌نگر (T-17): منبع واحد = ضریبِ هر کندل آن‌طور که **سرور** شمرده
// قدمِ ۵: `applyAdjustmentToCandles` دیگر از `adjustEvents` زنجیرۀِ دوم نمی‌سازد؛ ورودیِ
// مقیاس، `factors=[{time,factor}]`ِ همان پاسخِ `/api/chart` است (`AE.chain_factors`).
import { describe, expect, it } from 'vitest';
import {
  applyAdjustmentToCandles,
  functionalGapNote,
  getAdjustmentFactor,
  mapBackendAdjustEvents,
  pricePrecisionFor,
  adjustmentGapNote,
  readAdjustmentCapability,
  toIndexedSeries,
  type AdjustFactor,
} from '@features/technical/nahayatnegar/lib/adjustments';
import type { KLineData } from 'klinecharts';

const t = (s: string) => Date.parse(`${s}T00:00:00Z`);

const candles = [
  { timestamp: t('2020-01-08'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-09'), open: 100, high: 110, low: 95, close: 100, volume: 1000 },
  { timestamp: t('2020-01-12'), open: 50, high: 55, low: 48, close: 50, volume: 2000 },
] as unknown as KLineData[];

// رویدادِ ۲۰۲۰-۰۱-۱۱ با نسبتِ ۰٫۵ ⇒ ضریبِ تجمعیِ سرور: کندل‌هایِ پیشِ رویداد ۰٫۵،
// روزِ رویداد و بعدش دقیقاً ۱ (لنگر: factor(t)=∏ ratio برایِ date > t).
const factors: AdjustFactor[] = [
  { time: '2020-01-08', factor: 0.5 },
  { time: '2020-01-09', factor: 0.5 },
  { time: '2020-01-12', factor: 1 },
];

// همان رویداد به‌شکلِ نشانگر (این مسیر درِ قدمِ ۵ **نمایش** است، نه محاسبه)
const events = mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0.5 }]);

describe('تعدیل چارت نهایت‌نگر (ضریبِ سرور)', () => {
  it('«بدون تعدیل» ⇒ قیمت خام دست‌نخورده', () => {
    const out = applyAdjustmentToCandles(candles, factors, 'none');
    expect(out[0].close).toBe(100);
    expect(out[2].close).toBe(50);
  });

  it('تعدیل ترکیبی ⇒ پیشِ رویداد در ضریب سرور ضرب، حجم تقسیم، پس از رویداد خام', () => {
    const out = applyAdjustmentToCandles(candles, factors, 'combined');
    expect(out[0].close).toBe(50);       // 100 × 0.5
    expect(out[1].close).toBe(50);
    expect(out[0].volume).toBe(2000);    // 1000 ÷ 0.5
    expect(out[2].close).toBe(50);       // کندلِ پس از رویداد دست‌نخورده
    expect(out[2].volume).toBe(2000);
  });

  it('نگاشت رویدادِ سرور نسبت را برایِ نشانگر حفظ می‌کند و timestamp درست می‌سازد', () => {
    expect(events).toHaveLength(1);
    expect(events[0].ratio).toBe(0.5);
    expect(events[0].timestamp).toBe(t('2020-01-11'));
  });

  it('بی‌ضریب (سریِ محلیِ بی‌factors) ⇒ همان سری، نه سریِ صفرشده', () => {
    const out = applyAdjustmentToCandles(candles, [], 'combined');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
  });

  it('کندلی که سرور برایش ضریبی نفرستاده ⇒ ۱، نه حذف و نه عددِ ساخته‌شده', () => {
    const withGap = [...candles, { timestamp: t('2020-01-13'), open: 51, high: 56, low: 49,
                                   close: 51, volume: 10 }] as unknown as KLineData[];
    const out = applyAdjustmentToCandles(withGap, factors, 'combined');
    expect(out[3].close).toBe(51);
    expect(out[3].timestamp).toBe(t('2020-01-13'));
  });

  it('ضریبِ بی‌تاریخ/نامعقول نادیده می‌شود — نه اینکه کلِ سری را مقیاس کند', () => {
    const junk: AdjustFactor[] = [
      { time: '', factor: 0.5 },
      { time: '2020-01-08', factor: Number.NaN },
      { time: '2020-01-09', factor: -1 },
      { time: '2020-01-12', factor: 0 },
    ];
    const out = applyAdjustmentToCandles(candles, junk, 'combined');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
  });

  it('رویدادِ بی‌تاریخ یا نسبتِ نامعقول از نشانگر حذف می‌شود — نه «امروز»', () => {
    // با timestamp=امروز، هر کندلِ موجود زیرِ رویداد می‌افتاد و کل سری مقیاس می‌شد
    expect(mapBackendAdjustEvents([{ date: null, ratio: 0.5 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: 'not-a-date', ratio: 0.5 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 1e-9 }])).toEqual([]);
    expect(mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 900 }])).toEqual([]);
  });

  it('نسبتِ سالم می‌ماند و فاکتورِ نشانگر همان چیزی است که کاربر می‌خواند', () => {
    const [a] = mapBackendAdjustEvents([{ date: '2020-01-11', ratio: 0.5 }]);
    expect(getAdjustmentFactor(a)).toBe(0.5);
    expect(getAdjustmentFactor({ ...a, ratio: 0.00005 })).toBe(0.0001);   // clamp پایین
    expect(getAdjustmentFactor({ ...a, ratio: 500 })).toBe(50);        // clamp بالا
  });

  // ── تعدیل عملکردی (نمایِ بازدهی) ───────────────────────────────────────
  it('«عملکردی» رویِ سریِ تعدیل‌شده می‌نشیند، نه رویِ قیمتِ خام', () => {
    // ترکیبی: [50,50,50] — سهمِ افزایش سرمایه در قیمتِ پایه خنثی شده
    // عملکردی: همان سری ÷ ۵۰ × ۱۰۰ ⇒ [۱۰۰،۱۰۰،۱۰۰]
    const out = applyAdjustmentToCandles(candles, factors, 'performance');
    expect(out.map((c) => c.close)).toEqual([100, 100, 100]);
    expect(out[0].timestamp).toBe(candles[0].timestamp);
  });

  it('«عملکردی» بی‌ضریب ⇒ بازدهیِ خام، و حجم/گردش دست‌نخورده (قیمت نیستند)', () => {
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

// PHASE A (Round K) + قدمِ ۵: جداسازیِ معناییِ تعدیل — چهار مفهوم، یک ضرب
describe("PHASE A — جداسازیِ معناییِ تعدیل", () => {
  it("«نمایِ بازدهی» فقط شاخصِ نخستینِ پایانی نیست: با ضریب ≠ شاخصِ خام", () => {
    const perf = applyAdjustmentToCandles(candles, factors, "performance");
    const indexedRaw = toIndexedSeries(candles);
    expect(perf.map((c) => c.close)).not.toEqual(indexedRaw.map((c) => c.close));
  });

  it("combined ≠ indexed: indexed همان combined ÷ پایانیِ اول × ۱۰۰ است، نه سرمایه‌گذاریِ دوبارهٔ سود", () => {
    const comb = applyAdjustmentToCandles(candles, factors, "combined");
    const perf = applyAdjustmentToCandles(candles, factors, "performance");
    const k = 100 / comb[0].close;
    perf.forEach((c, i) => expect(c.close).toBeCloseTo(comb[i].close * k, 2));
  });

  it("تعدیلِ دوباره سری را عوض می‌کند ⇒ مصرف‌کننده باید خام بدهد؛ «none» بی‌تغییر برمی‌گرداند", () => {
    const once = applyAdjustmentToCandles(candles, factors, "combined");
    const twice = applyAdjustmentToCandles(once, factors, "combined");
    expect(twice[0].close).not.toBe(once[0].close);
    expect(applyAdjustmentToCandles(candles, factors, "none").map((c) => c.close))
      .toEqual(candles.map((c) => c.close));
  });

  it("ترتیبِ ضریب درِ ورودی داوری را عوض نمی‌کند (تطبیق با تاریخِ کندل، نه با اندیس)", () => {
    const rev = [...factors].reverse();
    expect(applyAdjustmentToCandles(candles, rev, "combined").map((c) => c.close))
      .toEqual(applyAdjustmentToCandles(candles, factors, "combined").map((c) => c.close));
  });

  it("فال‌بکِ بی‌بلوکِ توانایی، combined را «هست» جا نمی‌زند و هشدار می‌دهد", () => {
    const unseen = readAdjustmentCapability({ adjustEvents: [] });
    expect(unseen.combinedAvailable).toBe(false);
    expect(unseen.functionalAvailable).toBe(false);
    expect(unseen.chainComplete).toBeNull();
    expect(unseen.functionalBlockers.length).toBeGreaterThan(0);
    expect(adjustmentGapNote("performance", unseen)).toContain("در دسترس نیست");
    const cached = readAdjustmentCapability({ adjustCapability: {
      source: "local-cache", combined_available: true, functional_available: false,
      functional_reason: "r", functional_blockers: ["event-type-unresolved:3"],
      chain_complete: true, coverage: { rows_total: 4 }, event_count: 3 } });
    expect(cached.combinedAvailable).toBe(true);
    expect(cached.chainComplete).toBe(true);
    expect(cached.coverage).toEqual({ rows_total: 4 });
    expect(adjustmentGapNote("performance", cached)).toBeNull();
    expect(adjustmentGapNote("none", unseen)).toBeNull();
  });

  it("مانعِ تعدیلِ عملکردی با همان شمارۀِ سرور به کاربر گفته می‌شود (قدمِ ۵: UI صادق)", () => {
    const blocked = readAdjustmentCapability({ adjustCapability: {
      source: "ledger+base-price-discontinuity", combined_available: true,
      functional_available: false, functional_reason: "r",
      functional_blockers: ["event-type-unresolved:9", "ledger-rows-unmatched-by-price-series:12"] } });
    const note = functionalGapNote(blocked);
    expect(note).toContain("event-type-unresolved:9");
    expect(note).toContain("ledger-rows-unmatched-by-price-series:12");
    expect(note).toContain("ترکیبی");
    const proven = readAdjustmentCapability({ adjustCapability: {
      source: "x", combined_available: true, functional_available: true,
      functional_blockers: [] } });
    expect(functionalGapNote(proven)).toBeNull();
  });

  it("هندسهٔ OHLC پس از هر دو حالت حفظ می‌شود", () => {
    for (const mode of ["combined", "performance"] as const) {
      for (const c of applyAdjustmentToCandles(candles, factors, mode)) {
        expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
        expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
      }
    }
  });
});
