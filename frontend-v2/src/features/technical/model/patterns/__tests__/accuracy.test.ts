// model/patterns/__tests__/accuracy.test.ts
import { describe, expect, it } from 'vitest';
import { detectAllPatterns, PATTERN_TIER } from '../registry';
import { PATTERN_CONFIG } from '../config';
import { detectContinuation } from '../detectContinuation';
import { calculateAtr } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';
import type { PatternKind } from '../types';

/**
 * سازندهٔ مسیر قطعه‌خطی: بین نقاط عطف پیوت اضافی ساخته نمی‌شود. `end` فقط طول
 * سری را تعیین می‌کند؛ مقدار هر ایندکس مستقل از آن است، پس `series(n)` پیشوند
 * دقیق `series(m)` برای m > n می‌ماند.
 */
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

/** سری بدون نویز؛ هر کندل حول قیمت بسته ساخته می‌شود (مثل تست‌های A2/A3). */
function seriesFrom(values: number[]): EngineCandle[] {
  return values.map((v, i) => ({
    timestamp: i * 60_000,
    open: v,
    high: v + 0.4,
    low: v - 0.4,
    close: v,
  }));
}

function path(turns: ReadonlyArray<readonly [number, number]>, end: number): EngineCandle[] {
  return seriesFrom(pathValues(turns, end));
}

/** آینهٔ سری حول ۲۰۰؛ سقف/کف و جهت الگو برعکس می‌شود. */
function mirrored(values: number[]): EngineCandle[] {
  return seriesFrom(values.map((v) => 200 - v));
}

/**
 * سری ۳۰۰/۲۵۰ کندلیِ آزمون بدون نگاه به آینده: دوقلوی سقف در کندل‌های ۱۰..۵۰
 * (شکست در ~۸۳) و سپس یک رَمپ یکنوا تا انتها. فقط سری ۳۰۰ یک جزیرهٔ گپ‌دار
 * در دم (کندل‌های ۲۹۳..۲۹۵) دارد که ردهٔ دو را هم وارد خروجی می‌کند؛ لنگرش
 * ۲۹۵ است و در آزمون عدم‌نگاه‌به‌آینده (لنگر < ۲۵۰) دیده نمی‌شود.
 */
function series(n: number): EngineCandle[] {
  const values = pathValues(
    [[0, 96], [10, 100], [30, 94], [50, 100], [100, 90], [299, 130]],
    n - 1,
  );
  if (n >= 300) {
    values[290] = 129.4;
    values[291] = 129.6;
    values[292] = 130;
    values[293] = 131.5; // گپ ورود: ۱۳۱٫۱ − ۱۳۰٫۴ = ۰٫۷ ≥ islandGapAtr·ATR
    values[294] = 132;
    values[295] = 129.5; // گپ خروج در j − i = ۲
    values[296] = 129;
    values[297] = 128.5;
    values[298] = 128.2;
    values[299] = 128;
  }
  return seriesFrom(values);
}

/**
 * کاپ با لبه‌های نامتقارن: چپ ۱۰۰ و راست ۱۰۴؛ فاصلهٔ ۴ از
 * cup.rimToleranceAtr·ATR بزرگ‌تر است. عمق، پنجرهٔ کندلی و دستهٔ کم‌عمق
 * (۹۷ در برابر سقف ۳۳٪ از ۱۸) همه معتبرند، پس فقط قاعدهٔ لبه نقض می‌شود.
 */
function wideRimCup(): EngineCandle[] {
  return path([[0, 96], [10, 100], [50, 84], [90, 104], [100, 97], [110, 98]], 110);
}

function wideRimInverseCup(): EngineCandle[] {
  return mirrored(pathValues([[0, 96], [10, 100], [50, 84], [90, 104], [100, 97], [110, 98]], 110));
}

/**
 * کف V تیز: عمق/برجستگی/هم‌ترازی سرها معتبرند، اما فقط ۹ کندل از ۲۰ کندلِ
 * بخش میانی زیر خط لبه بسته می‌شوند (سهم ۰٫۴۵ < rounding.curvatureMin = ۰٫۵۵).
 * سکوی پایانی ۹۸ هم باعث می‌شود لبهٔ راست فقط ۲ واحد از چپ اختلاف داشته باشد
 * (زیر endSkewPct = ۵۰٪ عمق).
 */
function vBottom(): EngineCandle[] {
  return path([[0, 100], [25, 100], [30, 94], [35, 100], [40, 98], [59, 98]], 59);
}

function vTop(): EngineCandle[] {
  return mirrored(pathValues([[0, 100], [25, 100], [30, 94], [35, 100], [40, 98], [59, 98]], 59));
}

/**
 * پنج پیوتِ متناوب با مرزهای واگرا: سقف ۱۰۰→۱۱۰ و کف ۹۲→۹۰ (پنجرهٔ سقف)،
 * و سقف ۱۰۸→۱۱۰ و کف ۹۲→۹۰ (پنجرهٔ کف). عرض‌ها بزرگ می‌شوند، پس شرط
 * diamondConvergeMin (پایان ≤ ۰٫۷۵×شروع) نقض می‌شود؛ هر دو پنجره در عوض
 * پهن‌شوندهٔ معتبرند.
 */
function wideningFive(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 108], [70, 88], [90, 110], [110, 90], [119, 95]],
    119,
  );
}

/**
 * قرینهٔ `wideningFive`: پنج پیوتِ متناوب با مرزهای همگرا. عرض‌ها کوچک می‌شوند،
 * پس شرط broadeningMin (پایان ≥ ۱٫۲۵×شروع) نقض می‌شود؛ پنجرهٔ سقف در عوض
 * الماسِ معتبر است.
 */
function convergingFive(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 108], [70, 96], [90, 103], [110, 94], [119, 99]],
    119,
  );
}

/**
 * جزیرهٔ یک‌طرفه: گپ ورود در کندل ۱۵ بزرگ است (۱٫۲ ≥ islandGapAtr·ATR) اما
 * گپ خروج تا آخرین کندلِ پنجرهٔ بلوک (۱۹) هرگز به آستانه نمی‌رسد؛ فقط یکی از
 * دو گپ لازم نقض می‌شود.
 */
function oneSidedGap(): EngineCandle[] {
  return seriesFrom([
    99, 99.2, 99.4, 99.5, 99.6, 99.5, 99.4, 99.3, 99.2, 99.3, 99.4, 99.5, 99.6, 99.5, 99.4,
    102, 103, 103.5, 102, 101.5,
  ]);
}

/**
 * سه سقفِ ۱۰۰/۱۱۰/۱۰۱ و سه کفِ ۹۲/۸۸/۹۰: گسترهٔ هر سه‌گانه از
 * threePeaksToleranceAtr·ATR بزرگ‌تر است، پس هر دو گونه (سقف و کف) رد می‌شوند.
 */
function spreadPeaks(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 110], [70, 88], [90, 101], [110, 90], [119, 95]],
    119,
  );
}

/**
 * اولویت هم‌پوشانی: الماسِ سقف در لنگر ۲۳۰ و مثلثِ متقارن در همان لنگر ۲۳۰
 * (دتکتور ادامه‌دهنده واقعاً آن را می‌سازد)؛ بازگشتی باید ادامه‌دهنده را حذف
 * کند. دو ادامه‌دهندهٔ دور (مستطیل ۱۵۰) برای اثبات غیرتهی‌بودن آزمون هستند؛
 * لنگرها یکتا می‌مانند.
 */
function overlapSeries(): EngineCandle[] {
  return path([
    [0, 96], [10, 100], [30, 92], [50, 98], [70, 94],
    [100, 100], [120, 94], [150, 100],
    [170, 92], [190, 108], [210, 96], [230, 103], [239, 97],
  ], 239);
}

/** کاپ با لبه‌های هم‌تراز ۱۰۰ و دستهٔ کم‌عمق ۹۷٫۲۵؛ فقط برای اثبات ثبت. */
function alignedRimCup(): EngineCandle[] {
  return path([[0, 96], [10, 100], [50, 84], [90, 100], [100, 97.25], [110, 98]], 110);
}

function alignedRimInverseCup(): EngineCandle[] {
  return mirrored(pathValues([[0, 96], [10, 100], [50, 84], [90, 100], [100, 97.25], [110, 98]], 110));
}

/** کاسهٔ گرد ۴۵ کندلی: عمق ۳ و بیش از نیمی از بسته‌های میانی زیر لبه. */
function bowlCloses(): number[] {
  return [
    ...Array.from({ length: 15 }, (_, i) => 100 - i * (8 / 14)),
    ...Array.from({ length: 15 }, (_, i) => 89 + 3 * ((i - 7) / 7) ** 2),
    ...Array.from({ length: 15 }, (_, i) => 92 + i * (8 / 14)),
  ];
}

function bowl(): EngineCandle[] {
  return seriesFrom(bowlCloses());
}

function bowlTop(): EngineCandle[] {
  return mirrored(bowlCloses());
}

/** آینهٔ `convergingFive`: الماسِ معتبر پنجرهٔ کف (ردهٔ دو) را می‌سازد. */
function convergingFiveMirror(): EngineCandle[] {
  return mirrored(pathValues(
    [[0, 96], [10, 100], [30, 92], [50, 108], [70, 96], [90, 103], [110, 94], [119, 99]],
    119,
  ));
}

/** سه سقفِ ۱۰۰/۱۰۰٫۲/۱۰۰٫۱ (گستره ۰٫۲ ≤ threePeaksToleranceAtr·ATR). */
function levelPeaks(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 100.2], [70, 92.2], [90, 100.1], [110, 92], [119, 97]],
    119,
  );
}

describe('pattern accuracy', () => {
  it('assigns a tier to every emitted pattern', () => {
    const patterns = detectAllPatterns(series(300), PATTERN_CONFIG);
    expect(patterns.length).toBeGreaterThan(0);
    for (const p of patterns) expect(p.tier, p.id).toBe(PATTERN_TIER[p.kind]);
  });

  it('never changes an event when later bars are removed', () => {
    const full = detectAllPatterns(series(300), PATTERN_CONFIG)
      .filter((p) => p.anchor.index < 250);
    const cut = detectAllPatterns(series(250), PATTERN_CONFIG);
    for (const past of full) {
      const same = cut.find((p) => p.id === past.id);
      expect(same?.status, past.id).toBe(past.status);
    }
  });

  const negatives: Array<[PatternKind, string, EngineCandle[]]> = [
    ['CUP_HANDLE', 'the rim gap exceeds cup.rimToleranceAtr', wideRimCup()],
    ['INVERSE_CUP_HANDLE', 'the rim gap exceeds cup.rimToleranceAtr', wideRimInverseCup()],
    ['ROUNDING_BOTTOM', 'the V leaves fewer than rounding.curvatureMin closes beyond the rim', vBottom()],
    ['ROUNDING_TOP', 'the V leaves fewer than rounding.curvatureMin closes beyond the rim', vTop()],
    ['DIAMOND_TOP', 'the five-pivot boundaries widen instead of converging', wideningFive()],
    ['DIAMOND_BOTTOM', 'the five-pivot boundaries widen instead of converging', wideningFive()],
    ['BROADENING_TOP', 'the five-pivot boundaries converge instead of widening', convergingFive()],
    ['BROADENING_BOTTOM', 'the five-pivot boundaries converge instead of widening', convergingFive()],
    ['ISLAND_REVERSAL', 'only the entry gap reaches islandGapAtr, not the exit gap', oneSidedGap()],
    ['THREE_RISING_PEAKS', 'the trio spread exceeds threePeaksToleranceAtr', spreadPeaks()],
    ['THREE_FALLING_PEAKS', 'the trio spread exceeds threePeaksToleranceAtr', spreadPeaks()],
  ];

  it.each(negatives)('rejects %s when %s', (kind, rule, candles) => {
    const found = detectAllPatterns(candles, PATTERN_CONFIG);
    expect(found.some((p) => p.kind === kind), `${kind} emitted although ${rule}`).toBe(false);
  });

  /**
   * `THREE_FALLING_PEAKS` عمداً در جدول نیست: هر سه کفِ هم‌سطح که تلورانس
   * سه‌قلو را پاس می‌کند، همان پنجرهٔ TRIPLE_BOTTOM را هم می‌سازد و قاعدهٔ
   * اولویت بازگشتی (R-PAT-6) آن را حذف می‌کند؛ دتکتور مستقل در tier2.test.ts
   * با ردهٔ ۲ پوشش داده شده است.
   */
  const registered: Array<[PatternKind, 1 | 2, EngineCandle[]]> = [
    ['CUP_HANDLE', 1, alignedRimCup()],
    ['INVERSE_CUP_HANDLE', 1, alignedRimInverseCup()],
    ['ROUNDING_BOTTOM', 1, bowl()],
    ['ROUNDING_TOP', 1, bowlTop()],
    ['DIAMOND_TOP', 2, convergingFive()],
    ['DIAMOND_BOTTOM', 2, convergingFiveMirror()],
    ['BROADENING_TOP', 2, wideningFive()],
    ['BROADENING_BOTTOM', 2, wideningFive()],
    ['ISLAND_REVERSAL', 2, series(300)],
    ['THREE_RISING_PEAKS', 2, levelPeaks()],
  ];

  it.each(registered)('registers %s with tier %i through detectAllPatterns', (kind, tier, candles) => {
    const found = detectAllPatterns(candles, PATTERN_CONFIG).find((p) => p.kind === kind);
    expect(found, kind).toBeDefined();
    expect(found!.tier).toBe(tier);
    expect(found!.tier).toBe(PATTERN_TIER[kind]);
  });

  it('keeps the reversal when a continuation overlaps it', () => {
    const candles = overlapSeries();
    const atr = calculateAtr(candles, PATTERN_CONFIG.atrPeriod).at(-1) ?? 0;
    // غیرتهی‌بودن: دتکتور ادامه‌دهنده واقعاً یک الگو در همان لنگر می‌سازد...
    const raw = detectContinuation(candles, atr, PATTERN_CONFIG);
    const patterns = detectAllPatterns(candles, PATTERN_CONFIG);
    const anchors = patterns.map((p) => p.anchor.index);
    for (const p of patterns.filter((x) => x.family === 'continuation')) {
      expect(patterns.some((r) => r.family === 'reversal'
        && Math.abs(r.anchor.index - p.anchor.index) <= PATTERN_CONFIG.overlapWindowBars)).toBe(false);
    }
    expect(new Set(anchors).size).toBe(anchors.length);

    // ...و رجیستری همان نمونهٔ هم‌پوشان را به‌نفع بازگشتی حذف می‌کند.
    const reversal = patterns.find((p) => p.family === 'reversal' && p.kind === 'DIAMOND_TOP');
    expect(reversal).toBeDefined();
    const overlapping = raw.filter((p) => Math.abs(p.anchor.index - reversal!.anchor.index)
      <= PATTERN_CONFIG.overlapWindowBars);
    expect(overlapping.length).toBeGreaterThan(0);
    for (const p of overlapping) expect(patterns.some((x) => x.id === p.id)).toBe(false);
  });
});
