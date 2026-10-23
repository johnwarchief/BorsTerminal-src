// تست موتور تعدیلِ چارت نهایت‌نگر (T-17): منبع واحد = ضریبِ هر کندل آن‌طور که **سرور** شمرده
// قدمِ ۵: `applyAdjustmentToCandles` دیگر از `adjustEvents` زنجیرۀِ دوم نمی‌سازد؛ ورودیِ
// مقیاس، `factors=[{time,factor}]`ِ همان پاسخِ `/api/chart` است (`AE.chain_factors`).
// دورِ ممیزیِ کلِ نمادها: رابط دو حالتِ سری دارد (خام / عملکردی). نمایِ شاخصِ ۱۰۰ که
// `performance` نام داشت حذف شد، پس همین فایل همان عددِ تاریخی را رویِ دو حالتِ باقی‌مانده
// و رویِ کوچکتِ تنظیمِ کهنه قفل می‌کند — نه اینکه ادعایِ قبلی را بی‌جایگزین پاک کند.
import { describe, expect, it } from 'vitest';
import {
  applyAdjustmentToCandles, DEFAULT_ADJUSTMENT_MODE, functionalGapNote, functionalStatusNote,
  getAdjustmentFactor,
  mapBackendAdjustEvents,
  migrateAdjustmentMode,
  adjustmentGapNote,
  readAdjustmentCapability,
  type AdjustFactor,
} from '@features/technical/nahayatnegar/lib/adjustments';
import type { KLineData } from 'klinecharts';
import { toFaDigits } from '@shared/lib/fmt';

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

  it('تعدیل ترکیبی ⇒ پیشِ رویداد در ضریب سرور ضرب، پس از رویداد خام — حجم دست‌نخورده', () => {
    const out = applyAdjustmentToCandles(candles, factors, 'combined');
    expect(out[0].close).toBe(50);       // 100 × 0.5
    expect(out[1].close).toBe(50);
    expect(out[2].close).toBe(50);       // کندلِ پس از رویداد دست‌نخورده
    // حجم تقسیم نمی‌شود: درِ مرجع (ره‌آورد) سریِ حجمِ خام و تعدیل‌شده در ۶۰۱ از ۶۰۱
    // تاریخِ مشترکِ فولاد یکسان بود (`_audit/ra365_ref_bars.json`، سنجشِ ۱۴۰۵-۰۷-۲۷).
    // این سطر پیش از آن «۱۰۰۰ ÷ ۰٫۵ = ۲۰۰۰» را قفل کرده بود — رفتارِ غلط، نه تستِ غلط.
    expect(out[0].volume).toBe(1000);
    expect(out[2].volume).toBe(2000);
  });

  it('هیچ حالتِ تعدیلی حجم را مقیاس نمی‌کند (قیمت نیست که ضریب بخورد)', () => {
    for (const mode of ['none', 'combined'] as const) {
      const out = applyAdjustmentToCandles(candles, factors, mode);
      expect(out.map((c) => c.volume)).toEqual([1000, 1000, 2000]);
    }
  });

  it('قیمتِ کهنۀ زیرِ واحد گم نمی‌شود: ۱۹۰۰ × ۰٫۰۰۱۶۷۴۸۹۷۸ = ۳٫۱۸۲۳، نه ۳', () => {
    // ضریبِ واقعیِ زنجیرهٔ فولاد درِ ۲۰۰۷-۰۳-۱۱ (پاسخِ زندهٔ /api/chart).
    // صحیح‌گردانیِ پیشین ۵٫۷٪ از آن قیمت می‌خورد و چون «نمایِ بازدهی» بر همان
    // عددِ گِرد تقسیم می‌کرد، کلِ محورِ صفحه ۶٪ جابه‌جا می‌شد.
    const old = [{ timestamp: t('2007-03-11'), open: 1900, high: 1938, low: 1900,
                   close: 1900, volume: 500 }] as unknown as KLineData[];
    const out = applyAdjustmentToCandles(old, [{ time: '2007-03-11', factor: 0.0016748978 }], 'combined');
    expect(out[0].close).toBeCloseTo(3.1823, 4);
    expect(out[0].high).toBeCloseTo(3.246, 3);
  });

  it('لنگرِ سری نمی‌کَد: ۴۴۱۰ ریال می‌ماند و ۱۴۷٬۰۰۰ هرگز ساخته نمی‌شود', () => {
    // ۱۴۷٬۰۰۰ عددی بود که کاربر رویِ محورِ فولاد می‌خواند: نمایِ شاخصِ ۱۰۰ بر ۳
    // (پایانیِ گِردشدۀِ ۲۰۰۷) تقسیم می‌کرد، در حالی که عددِ درست ۳٫۱۸۲۳ است و
    // محور باید ۱۳۸٬۵۷۸ را نشان می‌داد. با حذفِ آن نمای، این تست همان دام را درِ
    // حالتِ باقی‌مانده می‌بندد: سریِ عملکردی ریال است، پایانیِ تازه‌ترینِ کندل
    // دست‌نخورده (لنگرِ factor=1) و هیچ مقیاسِ ۱۰۰‌مبنایی رویِ آن نمی‌نشیند.
    const pair = [
      { timestamp: t('2007-03-11'), open: 1900, high: 1900, low: 1900, close: 1900, volume: 1 },
      { timestamp: t('2026-10-17'), open: 4410, high: 4410, low: 4410, close: 4410, volume: 1 },
    ] as unknown as KLineData[];
    const fs: AdjustFactor[] = [
      { time: '2007-03-11', factor: 0.0016748978 },
      { time: '2026-10-17', factor: 1 },
    ];
    const out = applyAdjustmentToCandles(pair, fs, 'combined');
    expect(out[0].close).toBeCloseTo(3.1823, 4);
    expect(out[1].close).toBe(4410);
    expect(out.map((c) => c.close)).not.toContain(147000);
    expect(out[1].close / out[0].close).toBeCloseTo(4410 / 3.1823, 2);
  });

  it('پیش‌فرضِ چارت محورِ ریالیِ تعدیل‌شده است، نه شاخصِ ۱۰۰ (رأیِ مالک #186)', () => {
    expect(DEFAULT_ADJUSTMENT_MODE).toBe('combined');
    // آخرینِ کندل درِ زنجیرۀِ سرور لنگر است (factor = ۱)، پس پیش‌فرضِ درست همان
    // ریالِ تابلو را می‌دهد؛ اگر حالتِ ۱۰۰‌مبنا برمی‌گشت، همین‌جا ۱۰۰ می‌شد.
    const out = applyAdjustmentToCandles(candles, factors, DEFAULT_ADJUSTMENT_MODE);
    expect(out[out.length - 1].close).toBe(50);
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

  // ── دو حالتِ سری + کوچکتِ تنظیمِ کهنه ──────────────────────────────────
  it('«عملکردی» رویِ سریِ تعدیل‌شده می‌نشیند، نه رویِ قیمتِ خام', () => {
    const out = applyAdjustmentToCandles(candles, factors, 'combined');
    expect(out.map((c) => c.close)).toEqual([50, 50, 50]);
    expect(out[0].timestamp).toBe(candles[0].timestamp);
  });

  it('«خام» بی‌ضریب برمی‌گرداند و حجم/گردش دست‌نخورده می‌مانند (قیمت نیستند)', () => {
    const out = applyAdjustmentToCandles(candles, [], 'none');
    expect(out.map((c) => c.close)).toEqual([100, 100, 50]);
    expect(out[2].volume).toBe(2000);
  });

  it('تنظیمِ کهنهٔ «performance» به همان سریِ ریالیِ تعدیل‌شده کوچکت می‌شود', () => {
    // قالب‌هایِ ذخیره‌شده و stateِ قدیمی این رشته را نگه داشته‌اند. اگر بی‌کوچکت
    // به `applyAdjustmentToCandles` برسد، یا حالتِ سوم زنده می‌ماند یا خام; اینجا
    // دقیقاً همان combined می‌شود — و هیچ حالتِ سومی درِ رابط نیست.
    expect(migrateAdjustmentMode('performance')).toBe('combined');
    expect(migrateAdjustmentMode('capital')).toBe('combined');
    expect(migrateAdjustmentMode('cash')).toBe('combined');
    expect(migrateAdjustmentMode('none')).toBe('none');
    expect(migrateAdjustmentMode('combined')).toBe('combined');
    const migrated = applyAdjustmentToCandles(candles, factors,
      migrateAdjustmentMode('performance')!);
    expect(migrated.map((c) => c.close)).toEqual([50, 50, 50]);
  });

  it('رشتهٔ ناشناخته حدس زده نمی‌شود: `null` می‌ماند تا پیش‌فرضِ جاری سرِ جایش بماند', () => {
    expect(migrateAdjustmentMode('شاخص-۱۰۰')).toBeNull();
    expect(migrateAdjustmentMode(undefined)).toBeNull();
    expect(migrateAdjustmentMode(null)).toBeNull();
    expect(migrateAdjustmentMode(7)).toBeNull();
  });

  it('هیچِ حالتِ سومی برایِ ضربِ دوباره باقی نمانده (دو ورودی، دو خروجی)', () => {
    // «auto» بودنِ اعشارِ محور درِ خودِ چارت آزمون می‌شود (`technical-nn-chart.spec.tsx`);
    // اینجا مسیرِ عددی قفل می‌ماند: دو حالتِ سری، دو جوابِ متفاوت، بی‌سوم.
    const raw = applyAdjustmentToCandles(candles, factors, 'none');
    const adj = applyAdjustmentToCandles(candles, factors, 'combined');
    expect(raw.map((c) => c.close)).toEqual([100, 100, 50]);
    expect(adj.map((c) => c.close)).toEqual([50, 50, 50]);
    expect(raw).not.toEqual(adj);
  });
});

// PHASE A (Round K) + قدمِ ۵: جداسازیِ معناییِ تعدیل — دو حالتِ سری، یکِ ضرب
describe("PHASE A — جداسازیِ معناییِ تعدیل", () => {
  it("تعدیلِ دوباره سری را عوض می‌کند ⇒ مصرف‌کننده باید خام بدهد", () => {
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
    expect(adjustmentGapNote("combined", unseen)).toContain("در دسترس نیست");
    const cached = readAdjustmentCapability({ adjustCapability: {
      source: "local-cache", combined_available: true, functional_available: false,
      functional_reason: "r", functional_blockers: ["event-type-unresolved:3"],
      chain_complete: true, coverage: { rows_total: 4 }, event_count: 3 } });
    expect(cached.combinedAvailable).toBe(true);
    expect(cached.chainComplete).toBe(true);
    expect(cached.coverage).toEqual({ rows_total: 4 });
    expect(adjustmentGapNote("combined", cached)).toBeNull();
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
    // هشدار دیدنی: خلاصه کوتاه فارسی با عددهای همان پاسخ؛ کدها فقط در جزئیات.
    const ui = functionalStatusNote(blocked);
    expect(ui).not.toBeNull();
    expect(ui?.summary).toContain(`${toFaDigits(9)} رویداد حل‌نشده`);
    expect(ui?.summary).not.toContain("event-type-unresolved");
    expect(ui?.details).toHaveLength(2);
    expect(ui?.details.join(" ")).toContain(`${toFaDigits(9)} رویداد با نوعِ حل‌نشده`);
    expect(ui?.details.join(" ")).toContain(`${toFaDigits(12)} ردیف دفتر بی‌تطبیق با سری قیمت`);
    const proven = readAdjustmentCapability({ adjustCapability: {
      source: "x", combined_available: true, functional_available: true,
      functional_blockers: [] } });
    expect(functionalGapNote(proven)).toBeNull();
    expect(functionalStatusNote(proven)).toBeNull();
    const noRows = readAdjustmentCapability({ adjustCapability: {
      source: "no-adjustment-event", combined_available: true,
      functional_available: false, functional_reason: "r",
      functional_blockers: ["no-official-rows-for-instrument:هیچ ردیفی نیست"] } });
    const noRowsNote = functionalStatusNote(noRows);
    expect(noRowsNote?.summary).toContain("هیچ ردیف رسمیِ تعدیل در بانک نیست");
    expect(noRowsNote?.summary).not.toContain("no-official-rows");

    const partial = readAdjustmentCapability({ adjustCapability: {
      source: "base-price-discontinuity", combined_available: true,
      functional_available: false, functional_status: "PARTIAL",
      functional_reason: "r",
      functional_blockers: ["candles-before-ledger-coverage:120"],
      availability: { status: "PARTIAL", requested_start: "2020-01-01",
        requested_end: "2026-01-01", covered_start: "2023-01-01",
        covered_end: "2026-01-01", window_start: "2023-01-01",
        valid_points: 400, incomplete_points: 120,
        source: "base-price-discontinuity", stale: false } } });
    expect(partial.functionalStatus).toBe("PARTIAL");
    expect(partial.availability).not.toBeNull();
    const partialNote = functionalStatusNote(partial);
    expect(partialNote?.summary).toContain("بخشی از تاریخچه");
    expect(partialNote?.details.join(" ")).toContain("نقاط معتبر");
    expect(partialNote?.details.join(" ")).toContain(`${toFaDigits(120)} کندل پیش از پوشش`);

    const stale = readAdjustmentCapability({ adjustCapability: {
      source: "local-cache", combined_available: true,
      functional_available: false, functional_status: "STALE",
      functional_reason: "r", functional_blockers: [] } });
    expect(functionalStatusNote(stale)?.summary).toContain("کهنه");

    const noEvent = readAdjustmentCapability({ adjustCapability: {
      source: "no-adjustment-event", combined_available: true,
      functional_available: true, functional_status: "AVAILABLE_NO_EVENTS",
      functional_reason: "r", functional_blockers: [] } });
    expect(functionalStatusNote(noEvent)).toBeNull();
  });

  it("هندسهٔ OHLC پس از هر دو حالت حفظ می‌شود", () => {
    for (const mode of ["none", "combined"] as const) {
      for (const c of applyAdjustmentToCandles(candles, factors, mode)) {
        expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
        expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
      }
    }
  });
});
