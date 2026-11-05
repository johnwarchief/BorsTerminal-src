// model/patterns/__tests__/tier2.test.ts
import { describe, expect, it } from 'vitest';
import { detectTier2 } from '../detectTier2';
import { lineValue } from '../geometry';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/** سری مصنوعی بدون نویز؛ مثل تست A2، فقط پنجرهٔ پیوت در تست کوچک می‌شود. */
function seriesFrom(values: number[]): EngineCandle[] {
  return values.map((v, i) => ({
    timestamp: i * 60_000,
    open: v,
    high: v + 0.4,
    low: v - 0.4,
    close: v,
  }));
}

/** آینهٔ سری حول ۲۰۰؛ سقف‌ها/کف‌ها و جهت الگو برعکس می‌شوند. */
function mirrored(values: number[]): EngineCandle[] {
  return seriesFrom(values.map((v) => 200 - v));
}

/** مسیرِ خطی بین نقاطِ عطف (index، value)؛ بینِ عطف‌ها پیوتِ اضافی ساخته نمی‌شود. */
function pathValues(turns: ReadonlyArray<readonly [number, number]>, end: number): number[] {
  return Array.from({ length: end + 1 }, (_, i) => {
    let k = 0;
    while (k + 2 < turns.length && i > turns[k + 1]![0]) k++;
    const [x0, y0] = turns[k]!;
    const [x1, y1] = turns[k + 1] ?? turns[k]!;
    const t = x1 === x0 ? 0 : Math.min(1, Math.max(0, (i - x0) / (x1 - x0)));
    return y0 + (y1 - y0) * t;
  });
}

const FIXTURE_CONFIG = { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 };
const ATR = 2;

/**
 * الماسِ سقف (همگرا): پنج پیوتِ متناوب سقف ۱۰۰ (کندل ۴) → کف ۹۲ (۱۰) →
 * سقف ۱۰۸ (۱۶) → کف ۹۶ (۲۲) → سقف ۱۰۳ (۲۸). خطِ سقف ۱۰۰→۱۰۳ و خطِ کف
 * ۹۲→۹۶؛ عرض در سه نقطه: ۱۰ → ۷٫۵ → ۵ و ۵ ≤ ۰٫۷۵×۱۰.
 */
const DIAMOND_CLOSES = [
  96, 97.2, 98.4, 99.2, 99.6, // 0..4 → سقف ۱۰۰
  98.4, 96.8, 95.2, 93.6, 92.8, 92.4, // 5..10 → کف ۹۲
  95, 99, 102, 105, 106.8, 107.6, // 11..16 → سقف ۱۰۸
  105, 102, 99.5, 97.5, 96.8, 96.4, // 17..22 → کف ۹۶
  98, 99.5, 100.8, 101.6, 102.2, 102.6, // 23..28 → سقف ۱۰۳
  101, 99.5, 98, 96.5, 95, 93.5, // 29..34 → ریزش و تأیید
];

/**
 * همان پنج پیوت با سقفِ آخر ۱۰۶: عرض ۱۰ → ۹ → ۸؛ شرطِ همگرایی
 * «۸ ≤ ۰٫۷۵×۱۰ = ۷٫۵» نقض می‌شود، پس نه الماس است نه پهن‌شونده.
 */
const DIAMOND_SHALLOW_CLOSES = [
  96, 97.2, 98.4, 99.2, 99.6, // 0..4
  98.4, 96.8, 95.2, 93.6, 92.8, 92.4, // 5..10
  95, 99, 102, 105, 106.8, 107.6, // 11..16
  105, 102, 99.5, 97.5, 96.8, 96.4, // 17..22
  97.5, 99, 100.5, 102, 104, 105.6, // 23..28 → سقف ۱۰۶
  104, 102, 100, 98, 96, 94, // 29..34
];

/**
 * پهن‌شوندهٔ سقف: سقف ۱۰۰ (۴) → ۱۰۸ (۱۶) → ۱۰۶ (۲۸) و کف ۹۲ (۱۰) → ۹۰ (۲۲).
 * عرض ۷ → ۱۲ → ۱۷ و ۱۷ ≥ ۱٫۲۵×۷؛ مرزها واگرا می‌شوند.
 */
const BROADENING_CLOSES = [
  96, 97.2, 98.4, 99.2, 99.6, // 0..4 → سقف ۱۰۰
  98, 96.5, 95, 93.5, 92.8, 92.4, // 5..10 → کف ۹۲
  95, 99, 102, 105, 106.8, 107.6, // 11..16 → سقف ۱۰۸
  104, 101, 98.5, 95, 91.5, 90.4, // 17..22 → کف ۹۰
  93, 96, 99, 102, 104.5, 105.6, // 23..28 → سقف ۱۰۶
  104, 102, 100, 98, 96, 94, // 29..34
];

/**
 * نزدیک به پهن‌شونده اما زیرِ تلورانس: کفِ آخر ۹۱٫۵ و سقفِ آخر ۱۰۰٫۵؛
 * عرض ۷٫۷۵ → ۸٫۵ → ۹٫۲۵ و ۹٫۲۵ < ۱٫۲۵×۷٫۷۵ = ۹٫۶۸۷۵؛ پس واگرایی کافی نیست.
 */
const BROADENING_NARROW_CLOSES = [
  96, 97.2, 98.4, 99.2, 99.6, // 0..4 → سقف ۱۰۰
  98, 96.5, 95, 93.5, 92.8, 92.4, // 5..10 → کف ۹۲
  95, 99, 102, 105, 106.8, 107.6, // 11..16 → سقف ۱۰۸
  103, 100, 97, 94.5, 92.5, 91.9, // 17..22 → کف ۹۱٫۵
  93, 95, 96.8, 98.4, 99.6, 100.1, // 23..28 → سقف ۱۰۰٫۵
  99, 97, 95, 93, 91, 89, // 29..34
];

/**
 * جزیرهٔ گپ‌بالا: گپِ ورود در کندل ۵ (۱٫۶ قیمت = ۰٫۸×ATR > islandGapAtr·ATR)،
 * جزیرهٔ ۳ کندلی ۵..۷ و گپِ خروج در ۷ (فاصلهٔ ۲ کندل)؛ سپس ریزش.
 */
const ISLAND_CLOSES = [
  99, 99.2, 99.4, 99.5, 99.6, // 0..4
  102, 103, 99, // 5..7 → گپ بالا، جزیره، گپ پایین
  98.5, 98, 97.5, 97, 96.5, 96, // 8..13
];

/** همان ورود، اما گپِ خروج فقط ۰٫۵ قیمت (< islandGapAtr·ATR = ۱). */
const ISLAND_SMALL_EXIT_CLOSES = [
  99, 99.2, 99.4, 99.5, 99.6, // 0..4
  102, 103, 100.7, // 5..7 → گپ خروج ناکافی
  100.5, 100.4, 100.3, 99, 98, 97, 96, 95, // 8..15
];

/** گپِ ورود فقط ۰٫۶ قیمت (< ۱)؛ گپِ خروج بزرگ اما بدون ورودِ معتبر. */
const ISLAND_SMALL_ENTRY_CLOSES = [
  99, 99.2, 99.4, 99.5, 99.6, // 0..4
  101, 102, 99, // 5..7 → ورود ناکافی، خروج بزرگ
  98, 97, 96, 95.5, 95, // 8..12
];

/** گپِ خروج در فاصلهٔ ۵ کندل از ورود: با islandMaxBlockBars=5 مجاز، با ۴ رد. */
const ISLAND_LONG_CLOSES = [
  99, 99.2, 99.4, 99.5, 99.6, // 0..4
  102, 103, 103.5, 103.2, 102.8, 99, // 5..10 → گپ خروج در j−i=5
  98, 97, 96, 95.5, 95, 94.5, // 11..16
];

/**
 * سه سقفِ ۱۰۰ (۴)، ۱۰۰٫۳ (۱۰)، ۱۰۰٫۶ (۱۶) با دو کفِ بالاروندهٔ ۹۷ (۷) و
 * ۹۸ (۱۳)؛ گسترهٔ max−min = ۰٫۶ ≤ threePeaksToleranceAtr·ATR = ۱.
 */
const RISING_CLOSES = [
  97, 98, 98.8, 99.2, 99.6, // 0..4 → سقف ۱۰۰
  99, 98.2, 97.4, // 5..7 → کف ۹۷
  98.2, 99.2, 99.9, // 8..10 → سقف ۱۰۰٫۳
  99.4, 98.8, 98.4, // 11..13 → کف ۹۸
  99.2, 99.9, 100.2, // 14..16 → سقف ۱۰۰٫۶
  99, 97.5, 96, 95, 94.5, 94, // 17..22
];

/** همان سه قله با سقفِ سوم ۱۰۱٫۲: گسترهٔ ۱٫۲ > ۱؛ تلورانس نقض می‌شود. */
const RISING_SPREAD_CLOSES = [
  97, 98, 98.8, 99.2, 99.6, // 0..4
  99, 98.2, 97.4, // 5..7
  98.2, 99.2, 99.9, // 8..10
  99.4, 98.8, 98.4, // 11..13
  99.2, 100, 100.8, // 14..16 → سقف ۱۰۱٫۲
  99.5, 98, 96.5, 95.5, 95, 94.5, // 17..22
];

/**
 * الماسِ کف: آینهٔ DIAMOND_CLOSES با دُمِ داخلِ شکل (بدون شکست). پیوت‌ها
 * کف ۱۰۰ (۴) → سقف ۱۰۸ (۱۰) → کف ۹۲ (۱۶) → سقف ۱۰۴ (۲۲) → کف ۹۷ (۲۸)؛
 * قیمت پس از لنگر زیرِ خطِ سقف‌ها (۱۰۱٫۶۷ در ۲۹ تا ۱۰۰ در ۳۴) می‌ماند.
 */
const DIAMOND_BOTTOM_INSIDE_CLOSES = [
  104, 102.8, 101.6, 100.8, 100.4, // 0..4 → کف ۱۰۰
  101.6, 103.2, 104.8, 106.4, 107.2, 107.6, // 5..10 → سقف ۱۰۸
  105, 101, 98, 95, 93.2, 92.4, // 11..16 → کف ۹۲
  95, 98, 100.5, 102.5, 103.2, 103.6, // 17..22 → سقف ۱۰۴
  102, 100.5, 99.2, 98.4, 97.8, 97.4, // 23..28 → کف ۹۷
  98, 98.8, 99.2, 99.4, 99.5, 99.6, // 29..34 → داخلِ شکل
];

/**
 * پهن‌شوندهٔ کف (آینهٔ BROADENING_CLOSES): سقف‌های ۱۰۸ (۱۰) و ۱۱۰ (۲۲)،
 * کف‌های ۱۰۰ (۴)، ۹۲ (۱۶) و ۹۴ (۲۸)؛ عرض ۷ → ۱۲ → ۱۷. دُمِ صعودی ۱۰۹،
 * ۱۱۲، ۱۱۵ در ۳۵..۳۷ فقط در ۳۷ از خطِ سقف‌ها (۱۱۲٫۵) می‌گذرد.
 */
const BROADENING_BOTTOM_CLOSES = [
  104, 102.8, 101.6, 100.8, 100.4, // 0..4 → کف ۱۰۰
  102, 103.5, 105, 106.5, 107.2, 107.6, // 5..10 → سقف ۱۰۸
  105, 101, 98, 95, 93.2, 92.4, // 11..16 → کف ۹۲
  96, 99, 101.5, 105, 108.5, 109.6, // 17..22 → سقف ۱۱۰
  107, 104, 101, 98, 95.5, 94.4, // 23..28 → کف ۹۴
  96, 98, 100, 102, 104, 106, 109, 112, 115, // 29..37 → شکستِ سقف
];

/**
 * گُوهِ باریک‌شوندهٔ یکنوا: سقف ۱۰۶ (۴) → کف ۹۲ (۱۰) → سقف ۱۰۴ (۱۶) →
 * کف ۹۶ (۲۲) → سقف ۱۰۰ (۲۸). عرض ۱۶ → ۹ → ۲ پیوسته کم می‌شود، اما پیوتِ
 * میانی از سقفِ آغازین بالاتر نمی‌رود؛ پس الماس نیست (R-PA-11).
 */
const WEDGE_CLOSES = [
  100, 101.4, 102.8, 104.2, 105.6, // 0..4 → سقف ۱۰۶
  103.4, 101.2, 99, 96.8, 94.6, 92.4, // 5..10 → کف ۹۲
  94.27, 96.13, 98, 99.87, 101.73, 103.6, // 11..16 → سقف ۱۰۴
  101.5, 100.4, 99.3, 98.2, 97.1, 96.4, // 17..22 → کف ۹۶
  98, 98.32, 98.64, 98.96, 99.28, 99.6, // 23..28 → سقف ۱۰۰
  99.2, // 29
];

/**
 * جزیرهٔ گپ‌بالا با کفِ داخلیِ پایین‌تر: گپِ ورود در ۵ (۱٫۶ ≥ ۱)، کندلِ ۶ کفِ
 * بلوک را به ۱۰۰٫۱ می‌برد و کندلِ ۷ با سقفِ ۹۹٫۹ فقط از کفِ کندلِ ورود
 * (۱۰۱٫۶ − ۱ = ۱۰۰٫۶) می‌گذرد، نه از کفِ جاریِ بلوک (۱۰۰٫۱ − ۱ = ۹۹٫۱).
 */
const ISLAND_SPIKE_INSIDE_CLOSES = [
  99, 99.2, 99.4, 99.5, 99.6, // 0..4
  102, 100.5, 99.5, 98.5, // 5..8 → ورود، کفِ داخلی، گپِ ساختگی
];

/**
 * سه سقفِ هم‌سطح با فاصلهٔ ۷۰ کندل (گسترهٔ سه‌گانه ۱۴۰ > hs.maxBars=120)؛
 * هر سه در تلورانس‌اند و دو کفِ میانی دارند، پس فقط دروازهٔ گستره رد می‌کند.
 */
const THREE_PEAKS_LONG_CLOSES = pathValues(
  [[0, 99], [4, 99.6], [9, 91.4], [74, 99.9], [79, 91.8], [144, 100.2], [149, 92]],
  149,
);

/**
 * همان سه قله با گسترهٔ ۷۰ (≤ ۱۲۰) اما آخرین سقف در ۷۴ و سری تا ۱۹۹ ادامه
 * دارد؛ الگو چند کندل بعد تأیید می‌شود و پیش‌فیلترِ تازگی باید آن را براند.
 */
const THREE_PEAKS_STALE_CLOSES = pathValues(
  [[0, 95], [4, 99.6], [12, 91.4], [40, 99.9], [52, 91.8], [74, 100.2], [80, 90.4], [199, 88]],
  199,
);

const has = (patterns: { kind: string }[], kind: string) => patterns.some((p) => p.kind === kind);

describe('detectTier2', () => {
  it('detects a converging DIAMOND_TOP and rejects one that stops short of diamondConvergeMin', () => {
    const result = detectTier2(seriesFrom(DIAMOND_CLOSES), ATR, FIXTURE_CONFIG);
    const diamond = result.find((p) => p.kind === 'DIAMOND_TOP');
    expect(diamond).toBeDefined();
    expect(diamond?.status).toBe('confirmed');
    expect(diamond?.direction).toBe('bearish');
    expect(diamond?.family).toBe('reversal');
    expect(diamond?.tier).toBe(2);
    // R-PA-10: در سقف، خطِ بالا از سقف‌ها (w[0]، w[4]) و خطِ پایین از کف‌ها (w[1]، w[3]).
    expect(diamond?.upper.from.index).toBe(4);
    expect(diamond?.upper.to.index).toBe(28);
    expect(diamond?.lower.from.index).toBe(10);
    expect(diamond?.lower.to.index).toBe(22);
    expect(diamond?.upper.from.price).toBeCloseTo(100, 6);
    expect(diamond?.upper.to.price).toBeCloseTo(103, 6);
    expect(diamond?.lower.from.price).toBeCloseTo(92, 6);
    expect(diamond?.lower.to.price).toBeCloseTo(96, 6);
    expect(result.every((p) => p.tier === 2)).toBe(true);
    expect(has(detectTier2(seriesFrom(DIAMOND_SHALLOW_CLOSES), ATR, FIXTURE_CONFIG), 'DIAMOND_TOP')).toBe(false);
  });

  it('detects the mirrored DIAMOND_BOTTOM and rejects its too-shallow twin', () => {
    const result = detectTier2(mirrored(DIAMOND_CLOSES), ATR, FIXTURE_CONFIG);
    const diamond = result.find((p) => p.kind === 'DIAMOND_BOTTOM');
    expect(diamond).toBeDefined();
    expect(diamond?.status).toBe('confirmed');
    expect(diamond?.direction).toBe('bullish');
    expect(diamond?.family).toBe('reversal');
    expect(diamond?.tier).toBe(2);
    // R-PA-10: در کف، خطِ بالا از سقف‌ها (w[1]، w[3]) و خطِ پایین از کف‌ها (w[0]، w[4]).
    expect(diamond?.upper.from.index).toBe(10);
    expect(diamond?.upper.to.index).toBe(22);
    expect(diamond?.lower.from.index).toBe(4);
    expect(diamond?.lower.to.index).toBe(28);
    expect(diamond?.upper.from.price).toBeCloseTo(108, 6);
    expect(diamond?.upper.to.price).toBeCloseTo(104, 6);
    expect(diamond?.lower.from.price).toBeCloseTo(100, 6);
    expect(diamond?.lower.to.price).toBeCloseTo(97, 6);
    expect(has(detectTier2(mirrored(DIAMOND_SHALLOW_CLOSES), ATR, FIXTURE_CONFIG), 'DIAMOND_BOTTOM')).toBe(false);
  });

  it('keeps bottom shapes forming inside the highs line and confirms only above it', () => {
    const diamondInside = detectTier2(seriesFrom(DIAMOND_BOTTOM_INSIDE_CLOSES), ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'DIAMOND_BOTTOM');
    expect(diamondInside?.status).toBe('forming');

    const diamondCandles = mirrored(DIAMOND_CLOSES);
    const diamond = detectTier2(diamondCandles, ATR, FIXTURE_CONFIG).find((p) => p.kind === 'DIAMOND_BOTTOM');
    expect(diamond?.status).toBe('confirmed');
    expect(diamond?.breakoutIndex).toBe(31);
    expect(diamondCandles[diamond!.breakoutIndex!]!.close)
      .toBeGreaterThan(lineValue(diamond!.upper, diamond!.breakoutIndex!));

    const broadeningInside = detectTier2(mirrored(BROADENING_CLOSES), ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'BROADENING_BOTTOM');
    expect(broadeningInside?.status).toBe('forming');
    expect(broadeningInside?.upper.from.index).toBe(10);
    expect(broadeningInside?.upper.to.index).toBe(22);
    expect(broadeningInside?.lower.from.index).toBe(4);
    expect(broadeningInside?.lower.to.index).toBe(28);

    const broadeningCandles = seriesFrom(BROADENING_BOTTOM_CLOSES);
    const broadening = detectTier2(broadeningCandles, ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'BROADENING_BOTTOM');
    expect(broadening?.status).toBe('confirmed');
    expect(broadening?.breakoutIndex).toBe(37);
    expect(broadeningCandles[broadening!.breakoutIndex!]!.close)
      .toBeGreaterThan(lineValue(broadening!.upper, broadening!.breakoutIndex!));
  });

  it('rejects a monotone narrowing wedge as a diamond (mid > start)', () => {
    expect(has(detectTier2(seriesFrom(WEDGE_CLOSES), ATR, FIXTURE_CONFIG), 'DIAMOND_TOP')).toBe(false);
  });

  it('rejects a non-finite ATR', () => {
    expect(detectTier2(seriesFrom(DIAMOND_CLOSES), Number.POSITIVE_INFINITY, FIXTURE_CONFIG)).toEqual([]);
  });

  it('detects a diverging BROADENING_TOP and rejects near-parallel and converging boundaries', () => {
    const result = detectTier2(seriesFrom(BROADENING_CLOSES), ATR, FIXTURE_CONFIG);
    const broadening = result.find((p) => p.kind === 'BROADENING_TOP');
    expect(broadening).toBeDefined();
    expect(broadening?.direction).toBe('bearish');
    expect(broadening?.family).toBe('reversal');
    expect(broadening?.tier).toBe(2);
    expect(result.every((p) => p.tier === 2)).toBe(true);
    expect(has(detectTier2(seriesFrom(BROADENING_NARROW_CLOSES), ATR, FIXTURE_CONFIG), 'BROADENING_TOP')).toBe(false);
    expect(has(detectTier2(seriesFrom(DIAMOND_CLOSES), ATR, FIXTURE_CONFIG), 'BROADENING_TOP')).toBe(false);
  });

  it('detects the mirrored BROADENING_BOTTOM and rejects its near-parallel twin', () => {
    const result = detectTier2(mirrored(BROADENING_CLOSES), ATR, FIXTURE_CONFIG);
    const broadening = result.find((p) => p.kind === 'BROADENING_BOTTOM');
    expect(broadening).toBeDefined();
    expect(broadening?.direction).toBe('bullish');
    expect(broadening?.family).toBe('reversal');
    expect(broadening?.tier).toBe(2);
    expect(has(detectTier2(mirrored(BROADENING_NARROW_CLOSES), ATR, FIXTURE_CONFIG), 'BROADENING_BOTTOM')).toBe(false);
  });

  it('detects ISLAND_REVERSAL only when both gaps exceed islandGapAtr', () => {
    const result = detectTier2(seriesFrom(ISLAND_CLOSES), ATR, FIXTURE_CONFIG);
    const island = result.find((p) => p.kind === 'ISLAND_REVERSAL');
    expect(island).toBeDefined();
    expect(island?.status).toBe('confirmed');
    expect(island?.direction).toBe('bearish');
    expect(island?.family).toBe('reversal');
    expect(island?.tier).toBe(2);
    expect(island?.anchor.index).toBe(7);
    expect(island?.points).toHaveLength(1);
    expect(has(detectTier2(seriesFrom(ISLAND_SMALL_EXIT_CLOSES), ATR, FIXTURE_CONFIG), 'ISLAND_REVERSAL')).toBe(false);
    expect(has(detectTier2(seriesFrom(ISLAND_SMALL_ENTRY_CLOSES), ATR, FIXTURE_CONFIG), 'ISLAND_REVERSAL')).toBe(false);
    const down = detectTier2(mirrored(ISLAND_CLOSES), ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'ISLAND_REVERSAL');
    expect(down?.direction).toBe('bullish');
    expect(down?.tier).toBe(2);
  });

  it('consumes islandMaxBlockBars as the exit-gap window', () => {
    const candles = seriesFrom(ISLAND_LONG_CLOSES);
    expect(has(detectTier2(candles, ATR, FIXTURE_CONFIG), 'ISLAND_REVERSAL')).toBe(true);
    const strict = {
      ...FIXTURE_CONFIG,
      tier2: { ...FIXTURE_CONFIG.tier2, islandMaxBlockBars: 4 },
    };
    expect(has(detectTier2(candles, ATR, strict), 'ISLAND_REVERSAL')).toBe(false);
  });

  it('measures the island exit gap against the running block extreme, not the entry candle', () => {
    expect(has(detectTier2(seriesFrom(ISLAND_SPIKE_INSIDE_CLOSES), ATR, FIXTURE_CONFIG), 'ISLAND_REVERSAL'))
      .toBe(false);
  });

  it('detects THREE_RISING_PEAKS within threePeaksToleranceAtr and rejects a wider spread', () => {
    const result = detectTier2(seriesFrom(RISING_CLOSES), ATR, FIXTURE_CONFIG);
    const peaks = result.find((p) => p.kind === 'THREE_RISING_PEAKS');
    expect(peaks).toBeDefined();
    expect(peaks?.direction).toBe('bearish');
    expect(peaks?.family).toBe('reversal');
    expect(peaks?.tier).toBe(2);
    expect(peaks?.points).toHaveLength(3);
    expect(result.every((p) => p.tier === 2)).toBe(true);
    expect(has(detectTier2(seriesFrom(RISING_SPREAD_CLOSES), ATR, FIXTURE_CONFIG), 'THREE_RISING_PEAKS')).toBe(false);
  });

  it('detects THREE_FALLING_PEAKS at a bottom as a continuation within tolerance', () => {
    const result = detectTier2(mirrored(RISING_CLOSES), ATR, FIXTURE_CONFIG);
    const peaks = result.find((p) => p.kind === 'THREE_FALLING_PEAKS');
    expect(peaks).toBeDefined();
    expect(peaks?.direction).toBe('bullish');
    expect(peaks?.family).toBe('continuation');
    expect(peaks?.tier).toBe(2);
    expect(peaks?.points).toHaveLength(3);
    expect(result.every((p) => p.tier === 2)).toBe(true);
    expect(has(detectTier2(mirrored(RISING_SPREAD_CLOSES), ATR, FIXTURE_CONFIG), 'THREE_FALLING_PEAKS')).toBe(false);
  });

  it('rejects a three-peaks trio whose span exceeds hs.maxBars', () => {
    expect(has(detectTier2(seriesFrom(THREE_PEAKS_LONG_CLOSES), ATR, FIXTURE_CONFIG), 'THREE_RISING_PEAKS'))
      .toBe(false);
  });

  it('rejects a trio older than the hs.maxBars recency window', () => {
    expect(has(detectTier2(seriesFrom(THREE_PEAKS_STALE_CLOSES), ATR, FIXTURE_CONFIG), 'THREE_RISING_PEAKS'))
      .toBe(false);
  });
});
