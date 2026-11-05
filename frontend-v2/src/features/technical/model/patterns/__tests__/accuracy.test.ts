// model/patterns/__tests__/accuracy.test.ts
import { describe, expect, it } from 'vitest';
import { detectAllPatterns, PATTERN_TIER } from '../registry';
import { PATTERN_CONFIG, type PatternConfig } from '../config';
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

/** پیکربندی با یک کلیدِ رده‌دو که آگاهانه شل شده است؛ بقیهٔ کلیدها دست‌نخورده. */
function relaxedTier2(patch: Partial<PatternConfig['tier2']>): PatternConfig {
  return { ...PATTERN_CONFIG, tier2: { ...PATTERN_CONFIG.tier2, ...patch } };
}

/**
 * سری ۳۰۰/۲۵۰ کندلیِ آزمون رده‌بندی: دوقلوی سقف در کندل‌های ۱۰..۵۰ (شکست در
 * ~۸۳) و سپس یک رَمپ یکنوا تا انتها. فقط سری ۳۰۰ یک جزیرهٔ گپ‌دار در دم
 * (کندل‌های ۲۹۳..۲۹۵) دارد که ردهٔ دو را هم وارد خروجی می‌کند؛ لنگرش ۲۹۵ است.
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

/** پیوتِ پنجمِ پهن‌شوندهٔ `lookAheadSeries`، دقیقاً سه کندل پیش از برشِ ۱۰۰. */
const NEAR_CUT_PIVOT = 97;
/** برش‌های آزمونِ عدم‌نگاه‌به‌آینده. */
const CUTS = [100, 120, 160, 250] as const;

/**
 * سریِ آزمونِ عدم‌نگاه‌به‌آینده: دوقلوی سقف (۱۰..۵۰)، سپس یک پهن‌شوندهٔ سقف با
 * پنج پیوتِ ۶۵/۷۳/۸۱/۸۹/۹۷ — لنگرش ۹۷ است، یعنی سه کندل پیش از برشِ ۱۰۰ —
 * و در انتها یک رَمپ تا ۲۹۹ (به‌علاوهٔ جزیرهٔ دم، مانند `series`).
 * مقدار هر ایندکس مستقل از طول سری است، پس `lookAheadSeries(cut)` پیشوندِ
 * دقیق `lookAheadSeries(300)` است.
 */
function lookAheadSeries(n: number): EngineCandle[] {
  const values = pathValues(
    [[0, 96], [10, 100], [30, 94], [50, 100], [60, 90],
      [65, 100], [73, 96], [81, 104], [89, 93], [97, 106],
      [108, 88], [200, 96], [299, 104]],
    n - 1,
  );
  if (n >= 300) {
    values[290] = 103.4;
    values[291] = 103.6;
    values[292] = 104;
    values[293] = 105.5; // گپ ورود
    values[294] = 106;
    values[295] = 103.5; // گپ خروج
    values[296] = 103;
    values[297] = 102.5;
    values[298] = 102.2;
    values[299] = 102;
  }
  return seriesFrom(values);
}

/**
 * کاپ با لبه‌های نامتقارن: چپ ۱۰۰٫۴ و راست ۱۰۴٫۴؛ فاصلهٔ ۴ از
 * cup.rimToleranceAtr·ATR = ۰٫۴۴ بزرگ‌تر است. عمق ۱۸٫۸، پنجرهٔ کندلی ۸۰ و
 * دستهٔ کم‌عمق ۵٫۸ (در برابر سقف ۳۳٪ × ۱۸٫۸ = ۶٫۲) معتبرند، پس فقط قاعدهٔ
 * لبه نقض می‌شود.
 */
function wideRimCup(): EngineCandle[] {
  return path([[0, 96], [10, 100], [50, 84], [90, 104], [100, 97], [110, 98]], 110);
}

function wideRimInverseCup(): EngineCandle[] {
  return mirrored(pathValues([[0, 96], [10, 100], [50, 84], [90, 104], [100, 97], [110, 98]], 110));
}

/**
 * کف V تیز: عمق ۵ (≥ minDepthAtr·ATR = ۰٫۸)، برجستگی و هم‌ترازی سرها معتبر
 * (اختلاف لبه‌ها ۲ ≤ ۵۰٪ × ۵)، اما فقط ۸ کندل از ۲۰ کندلِ بخش میانی زیر خط
 * لبه بسته می‌شوند (سهم ۰٫۴ < rounding.curvatureMin = ۰٫۵۵).
 */
function vBottom(): EngineCandle[] {
  return path([[0, 100], [25, 100], [30, 94], [35, 100], [40, 98], [59, 98]], 59);
}

function vTop(): EngineCandle[] {
  return mirrored(pathValues([[0, 100], [25, 100], [30, 94], [35, 100], [40, 98], [59, 98]], 59));
}

/**
 * پنج پیوتِ متناوب با مرزهای واگرا: سقف ۱۰۰٫۴→۱۱۰٫۴ و کف ۹۱٫۶→۸۹٫۶ (پنجرهٔ
 * سقف)، و سقف ۱۰۸٫۴→۱۱۰٫۴ و کف ۸۷٫۶→۸۹٫۶ (پنجرهٔ کف). عرض‌ها بزرگ می‌شوند
 * (۶٫۸ → ۲۴٫۸)، پس شرط diamondConvergeMin (پایان ≤ ۰٫۷۵×شروع) نقض می‌شود؛
 * هر دو پنجره در عوض پهن‌شوندهٔ معتبرند.
 */
function wideningFive(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 108], [70, 88], [90, 110], [110, 90], [119, 95]],
    119,
  );
}

/**
 * قرینهٔ `wideningFive`: پنج پیوتِ متناوب با مرزهای همگرا. عرض‌ها کوچک می‌شوند
 * (۱۰٫۸ → ۵٫۸)، پس شرط broadeningMin (پایان ≥ ۱٫۲۵×شروع) نقض می‌شود؛ پنجرهٔ
 * سقف در عوض الماسِ معتبر است.
 */
function convergingFive(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 108], [70, 96], [90, 103], [110, 94], [119, 99]],
    119,
  );
}

/**
 * پنج پیوتِ متناوبِ نزدیک‌به‌مرزِ الماس: عرض ۱۲٫۸ → ۱۴٫۸ → ۱۰٫۸۸ (نسبت ۰٫۸۵).
 * `mid > end` و `midSpan > start` برقرارند، اما ۱۰٫۸۸ > ۰٫۷۵×۱۲٫۸ = ۹٫۶، پس
 * آستانهٔ همگرایی نقض می‌شود؛ پهن‌شونده هم نیست (۱۰٫۸۸ < ۱٫۲۵×۱۲٫۸).
 * همان سری با `diamondConvergeMin = 0.1` (مرز ۰٫۹×۱۲٫۸ = ۱۱٫۵۲) منتشر می‌شود.
 */
function nearMissDiamond(): EngineCandle[] {
  return path([[0, 88], [61, 100], [71, 90], [81, 106], [91, 94], [101, 106.08], [110, 90], [119, 88]], 119);
}

function nearMissDiamondMirror(): EngineCandle[] {
  return mirrored(pathValues(
    [[0, 88], [61, 100], [71, 90], [81, 106], [91, 94], [101, 106.08], [110, 90], [119, 88]],
    119,
  ));
}

/**
 * پنج پیوتِ متناوبِ نزدیک‌به‌مرزِ پهن‌شونده: عرض ۱۲٫۸ → ۱۳٫۴۴ → ۱۴٫۰۸ (نسبت
 * ۱٫۱). ۱۴٫۰۸ < ۱٫۲۵×۱۲٫۸ = ۱۶، پس آستانهٔ واگرایی نقض می‌شود؛ الماس هم نیست
 * (`mid > end` برقرار نیست). همان سری با `broadeningMin = 0.05` (مرز
 * ۱٫۰۵×۱۲٫۸ = ۱۳٫۴۴) منتشر می‌شود.
 */
function nearMissBroadening(): EngineCandle[] {
  return path([[0, 88], [61, 100], [71, 90], [81, 106], [91, 94], [101, 109.28], [110, 90], [119, 88]], 119);
}

function nearMissBroadeningMirror(): EngineCandle[] {
  return mirrored(pathValues(
    [[0, 88], [61, 100], [71, 90], [81, 106], [91, 94], [101, 109.28], [110, 90], [119, 88]],
    119,
  ));
}

/**
 * جزیرهٔ یک‌طرفه: گپ ورود در کندل ۱۵ بزرگ است (۱٫۶ ≥ islandGapAtr·ATR ≈ ۰٫۵۵)
 * اما گپ خروج تا آخرین کندلِ پنجرهٔ بلوک (۱۹) هرگز به آستانه نمی‌رسد؛ فقط یکی
 * از دو گپ لازم نقض می‌شود.
 */
function oneSidedGap(): EngineCandle[] {
  return seriesFrom([
    99, 99.2, 99.4, 99.5, 99.6, 99.5, 99.4, 99.3, 99.2, 99.3, 99.4, 99.5, 99.6, 99.5, 99.4,
    102, 103, 103.5, 102, 101.5,
  ]);
}

/**
 * جزیرهٔ نزدیک‌به‌مرزِ گپ خروج: همان گپ ورودِ بزرگ در کندل ۱۵، اما سقفِ کندل ۱۸
 * فقط ۰٫۳ زیر کفِ بلوک (۱۰۱٫۶) می‌ماند و آستانه ۰٫۵ × ATR ≈ ۰٫۵۱ است. با
 * `islandGapAtr = 0.25` (آستانه ≈ ۰٫۲۵) همان سری منتشر می‌شود.
 */
function nearMissExitGap(): EngineCandle[] {
  return seriesFrom([
    99, 99.1, 99.2, 99.3, 99.4, 99.45, 99.5, 99.55, 99.6, 99.6, 99.6, 99.6, 99.6, 99.6, 99.6,
    102, 102, 102, 100.9, 100.5, 100, 99.5, 99,
  ]);
}

/**
 * سه سقفِ ۱۰۰٫۴/۱۱۰٫۴/۱۰۱٫۴: سه‌گانه یکنوا نیست (سقف دوم از هر دو بالاتر
 * است)، پس با دروازهٔ تقدّمِ سختِ R-PA-15 هیچ‌کدام از دو گونهٔ سه‌قله منتشر
 * نمی‌شود.
 */
function spreadPeaks(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 110], [70, 88], [90, 101], [110, 90], [119, 95]],
    119,
  );
}

/**
 * سه سقفِ صعودیِ ۱۰۰٫۴/۱۰۱٫۴/۱۰۲٫۴ (کندل‌های ۱۰/۵۰/۹۰) با دو کفِ میانی:
 * h3 > h2 > h1 و h3 − h1 = ۲ ≥ threePeaksSlopeAtr·ATR؛ سه‌قلهٔ صعودی
 * (بازگشتیِ نزولی) از رجیستری بیرون می‌آید (R-PA-15).
 */
function ascendingSeries(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 101], [70, 92.2], [90, 102], [110, 91], [119, 96]],
    119,
  );
}

/**
 * آینهٔ شکلِ صعودی: سه سقفِ نزولیِ ۱۰۲٫۴/۱۰۱٫۴/۱۰۰٫۴ با دو کفِ میانی؛
 * h3 < h2 < h1 و h1 − h3 = ۲ ≥ threePeaksSlopeAtr·ATR؛ سه‌قلهٔ نزولی
 * (ادامه‌دهندهٔ نزولی) از رجیستری بیرون می‌آید (R-PA-15).
 */
function descendingSeries(): EngineCandle[] {
  return path(
    [[0, 98], [10, 102], [30, 94], [50, 101], [70, 94.5], [90, 100], [110, 90], [119, 95]],
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

/**
 * سه سقفِ صعودیِ نزدیک‌به‌هم‌سطح: ۱۰۰٫۴ → ۱۰۰٫۵ → ۱۰۰٫۶؛ تقدّم سخت برقرار
 * است اما h3 − h1 = ۰٫۲ < threePeaksSlopeAtr·ATR (~۰٫۴)، پس هر دو گونهٔ
 * سه‌قله رد می‌شوند (R-PA-15).
 */
function nearLevelPeaks(): EngineCandle[] {
  return path(
    [[0, 96], [10, 100], [30, 92], [50, 100.1], [70, 92.2], [90, 100.2], [110, 91], [119, 96]],
    119,
  );
}

describe('pattern accuracy', () => {
  it('assigns a tier to every emitted pattern', () => {
    const patterns = detectAllPatterns(series(300), PATTERN_CONFIG);
    expect(patterns.length).toBeGreaterThan(0);
    for (const p of patterns) expect(p.tier, p.id).toBe(PATTERN_TIER[p.kind]);
  });

  /**
   * R-PA-14: هر رویدادی که لنگرش دست‌کم `pivRight` کندل پیش از برش است باید در
   * سریِ بریده دقیقاً همان ساختار را داشته باشد. چهار برش، همهٔ رویدادهای
   * واجدشرط (نه فقط یکی) و شکل/مرز/نقطه‌ها مقایسه می‌شوند تا آزمون غیرتهی و
   * واقعاً حساس باشد.
   * وضعیت فقط وقتی مقایسه می‌شود که پیش از برش تعیین شده باشد (`confirmed` با
   * `breakoutIndex < cut`)؛ وضعیتِ `forming`/`invalidated` بنا به تعریف به
   * کندل‌های پس از لنگر — و نه پس از برش — وابسته است و با برش تغییر می‌کند.
   */
  it('never changes a recorded event when later bars are removed', () => {
    const full = detectAllPatterns(lookAheadSeries(300), PATTERN_CONFIG);
    for (const cut of CUTS) {
      const past = full.filter((p) => p.anchor.index <= cut - PATTERN_CONFIG.pivRight);
      expect(past.length, `cut ${cut}`).toBeGreaterThan(0);
      const truncated = detectAllPatterns(lookAheadSeries(cut), PATTERN_CONFIG);
      expect(truncated.length, `cut ${cut}`).toBeGreaterThan(0);
      for (const p of past) {
        const same = truncated.find((x) => x.id === p.id);
        expect(same, `${p.id} at cut ${cut}`).toBeDefined();
        expect(same!.kind, p.id).toBe(p.kind);
        expect(same!.family, p.id).toBe(p.family);
        expect(same!.direction, p.id).toBe(p.direction);
        expect(same!.anchor, p.id).toEqual(p.anchor);
        expect(same!.points.map((x) => [x.index, x.price]), p.id)
          .toEqual(p.points.map((x) => [x.index, x.price]));
        expect(same!.upper, p.id).toEqual(p.upper);
        expect(same!.lower, p.id).toEqual(p.lower);
        if (p.status === 'confirmed' && p.breakoutIndex !== undefined && p.breakoutIndex < cut) {
          expect(same!.status, p.id).toBe('confirmed');
          expect(same!.breakoutIndex, p.id).toBe(p.breakoutIndex);
        }
      }
    }
  });

  /**
   * R-PA-14: پیوتِ ۹۷ سه کندل پیش از برشِ ۱۰۰ است و با دادهٔ کامل شناسایی
   * می‌شود، اما در سریِ ۱۰۰ کندلی نمی‌تواند پیوت باشد (هر پیوت `pivRight = 4`
   * کندلِ سمت راست می‌خواهد). اگر تشخیص‌دهنده کندلِ بعد از برش را بخواند، این
   * رویداد در سریِ بریده هم ظاهر می‌شود و آزمون قرمز می‌شود.
   */
  it('never reaches a pivot that a truncated history cannot confirm', () => {
    const full = detectAllPatterns(lookAheadSeries(300), PATTERN_CONFIG);
    const nearCut = full.find((p) => p.kind === 'BROADENING_TOP' && p.anchor.index === NEAR_CUT_PIVOT);
    expect(nearCut, `BROADENING_TOP@${NEAR_CUT_PIVOT} in the full series`).toBeDefined();
    const truncated = detectAllPatterns(lookAheadSeries(100), PATTERN_CONFIG);
    expect(truncated.some((p) => p.anchor.index >= NEAR_CUT_PIVOT)).toBe(false);
  });

  const negatives: Array<[PatternKind, string, EngineCandle[]]> = [
    ['CUP_HANDLE', 'the rim gap exceeds cup.rimToleranceAtr', wideRimCup()],
    ['INVERSE_CUP_HANDLE', 'the rim gap exceeds cup.rimToleranceAtr', wideRimInverseCup()],
    ['ROUNDING_BOTTOM', 'the V leaves fewer than rounding.curvatureMin closes beyond the rim', vBottom()],
    ['ROUNDING_TOP', 'the V leaves fewer than rounding.curvatureMin closes beyond the rim', vTop()],
    ['DIAMOND_TOP', 'the five-pivot boundaries widen instead of converging', wideningFive()],
    ['DIAMOND_BOTTOM', 'the five-pivot boundaries widen instead of converging', wideningFive()],
    ['DIAMOND_TOP', 'the width shrinks by less than diamondConvergeMin', nearMissDiamond()],
    ['DIAMOND_BOTTOM', 'the width shrinks by less than diamondConvergeMin', nearMissDiamondMirror()],
    ['BROADENING_TOP', 'the five-pivot boundaries converge instead of widening', convergingFive()],
    ['BROADENING_BOTTOM', 'the five-pivot boundaries converge instead of widening', convergingFive()],
    ['BROADENING_TOP', 'the width grows by less than broadeningMin', nearMissBroadening()],
    ['BROADENING_BOTTOM', 'the width grows by less than broadeningMin', nearMissBroadeningMirror()],
    ['ISLAND_REVERSAL', 'only the entry gap reaches islandGapAtr, not the exit gap', oneSidedGap()],
    ['ISLAND_REVERSAL', 'the exit gap stays below islandGapAtr', nearMissExitGap()],
    ['THREE_RISING_PEAKS', 'the high trio is not monotone', spreadPeaks()],
    ['THREE_FALLING_PEAKS', 'the high trio is not monotone', spreadPeaks()],
    ['THREE_RISING_PEAKS', 'the highs lack a strict progression of at least threePeaksSlopeAtr', nearLevelPeaks()],
    ['THREE_FALLING_PEAKS', 'the highs lack a strict progression of at least threePeaksSlopeAtr', nearLevelPeaks()],
  ];

  it.each(negatives)('rejects %s when %s', (kind, rule, candles) => {
    const found = detectAllPatterns(candles, PATTERN_CONFIG);
    expect(found.some((p) => p.kind === kind), `${kind} emitted although ${rule}`).toBe(false);
  });

  /**
   * R-PA-15: هر دو گونهٔ سه‌قله با تقدّمِ سختِ سقف‌ها و کفِ شیبِ
   * `threePeaksSlopeAtr` از رجیستری بیرون می‌آیند؛ دیگر با سه‌قلوی هم‌سطح
   * هم‌پوشان نیستند.
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
    ['THREE_RISING_PEAKS', 2, ascendingSeries()],
    ['THREE_FALLING_PEAKS', 2, descendingSeries()],
  ];

  it.each(registered)('registers %s with tier %i through detectAllPatterns', (kind, tier, candles) => {
    const found = detectAllPatterns(candles, PATTERN_CONFIG).find((p) => p.kind === kind);
    expect(found, kind).toBeDefined();
    expect(found!.tier).toBe(tier);
    expect(found!.tier).toBe(PATTERN_TIER[kind]);
  });

  /**
   * R-PA-15: نزولِ سختِ سقف‌ها (h1 − h3 ≥ threePeaksSlopeAtr·ATR) با برابریِ
   * سطحِ سه‌قلو (گستره ≤ triple.levelToleranceAtr·ATR) ناسازگار است؛ پس دیگر
   * TRIPLE_TOP هم‌لنگرِ سه‌قلهٔ نزولی ساخته نمی‌شود و نمونهٔ رده‌دو در رجیستری
   * می‌ماند. اگر دروازهٔ برابری به سه‌قله‌ها برگردد، این آزمون قرمز می‌شود.
   */
  it('does not build a same-anchor TRIPLE_TOP for a strictly descending trio (R-PA-15)', () => {
    const patterns = detectAllPatterns(descendingSeries(), PATTERN_CONFIG);
    const falling = patterns.find((p) => p.kind === 'THREE_FALLING_PEAKS');
    expect(falling?.family).toBe('continuation');
    expect(falling?.direction).toBe('bearish');
    expect(patterns.some((p) => p.kind === 'TRIPLE_TOP')).toBe(false);
  });

  /**
   * R-PA-14 (کنترلِ مثبت): هر ردیفِ منفیِ آستانه‌ای باید با شل‌کردن همان کلید و
   * روی همان سری منتشر شود؛ وگرنه آزمون فقط یک نابرابری را ثابت می‌کند، نه
   * اینکه «همان کلید» دروازه است.
   */
  it('emits the diamond family on the near-miss series once diamondConvergeMin is relaxed', () => {
    const relaxed = relaxedTier2({ diamondConvergeMin: 0.1 });
    for (const [kind, candles] of [
      ['DIAMOND_TOP', nearMissDiamond()],
      ['DIAMOND_BOTTOM', nearMissDiamondMirror()],
    ] as Array<[PatternKind, EngineCandle[]]>) {
      expect(detectAllPatterns(candles, PATTERN_CONFIG).some((p) => p.kind === kind), kind).toBe(false);
      expect(detectAllPatterns(candles, relaxed).some((p) => p.kind === kind), kind).toBe(true);
    }
  });

  it('emits the broadening family on the near-miss series once broadeningMin is relaxed', () => {
    const relaxed = relaxedTier2({ broadeningMin: 0.05 });
    for (const [kind, candles] of [
      ['BROADENING_TOP', nearMissBroadening()],
      ['BROADENING_BOTTOM', nearMissBroadeningMirror()],
    ] as Array<[PatternKind, EngineCandle[]]>) {
      expect(detectAllPatterns(candles, PATTERN_CONFIG).some((p) => p.kind === kind), kind).toBe(false);
      expect(detectAllPatterns(candles, relaxed).some((p) => p.kind === kind), kind).toBe(true);
    }
  });

  it('emits ISLAND_REVERSAL on the near-miss series once islandGapAtr is relaxed', () => {
    const candles = nearMissExitGap();
    const relaxed = relaxedTier2({ islandGapAtr: 0.25 });
    expect(detectAllPatterns(candles, PATTERN_CONFIG).some((p) => p.kind === 'ISLAND_REVERSAL')).toBe(false);
    expect(detectAllPatterns(candles, relaxed).some((p) => p.kind === 'ISLAND_REVERSAL')).toBe(true);
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
