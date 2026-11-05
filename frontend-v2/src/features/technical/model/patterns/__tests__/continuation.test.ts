// model/patterns/__tests__/continuation.test.ts
import { describe, expect, it } from 'vitest';
import { detectContinuation } from '../detectContinuation';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/**
 * سری مصنوعی: هر پا یک خط بین دو قیمت بستهٔ چرخش است، پس پیوت‌های ۱/۱ دقیقاً
 * روی نقاط چرخش می‌افتند (R-PAT-4: فقط پنجرهٔ پیوت در تست کوچک می‌شود).
 */
function zigzag(start: number, legs: Array<[to: number, bars: number]>): EngineCandle[] {
  const closes = [start];
  for (const [to, bars] of legs) {
    const from = closes[closes.length - 1]!;
    const step = (to - from) / bars;
    for (let k = 1; k <= bars; k++) {
      closes.push(k === bars ? to : from + step * k);
    }
  }
  return closes.map((close, i) => ({
    timestamp: i * 60_000,
    open: close,
    high: close + 1,
    low: close - 1,
    close,
  }));
}

const FIXTURE_CONFIG = { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 };
const ATR = 2;

/** فقط دامنهٔ یک کندل را بازشکل می‌دهد؛ عدد آستانه‌ای تغییر نمی‌کند. */
function reshape(
  candles: EngineCandle[],
  index: number,
  shape: Partial<Pick<EngineCandle, 'high' | 'low' | 'close'>>,
): EngineCandle[] {
  candles[index] = { ...candles[index]!, ...shape };
  return candles;
}

/** لگ صعودی تند، بعد کانال نزولی موازی ۳ کندلی، بعد ادامه. */
function flagSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2], // درهٔ شروع لگ
    [130, 8], // قلهٔ پایان لگ
    [125.5, 3],
    [128, 3],
    [122.5, 3],
    [125, 3],
    [125, 1], // داخل کانال؛ پیوت قلهٔ قبلی را حفظ می‌کند
    [136, 4], // شکست و ادامه
  ]), 23, { low: 124.2 });
}

/**
 * همان پرچم، ولی پیش از شکست قطع می‌شود: فشرده‌سازی با سقف (نه کف) تمام می‌شود؛
 * لنگر باید دیرترین پیوت (سقف ۲۲) باشد، نه lows[1] (۱۹).
 */
function formingFlagSeries(): EngineCandle[] {
  return flagSeries().slice(0, 24);
}

/** آینهٔ پرچم صعودی: لگ نزولی تند، بعد کانال صعودی تنگ، بعد ادامهٔ نزولی. */
function bearFlagSeries(): EngineCandle[] {
  return reshape(zigzag(130, [
    [132, 2], // سقف شروع لگ
    [100, 8], // کف پایان لگ
    [104.5, 3],
    [102, 3],
    [107.5, 3],
    [105, 3],
    [105, 1], // داخل کانال؛ پیوت کف قبلی را حفظ می‌کند
    [94, 4], // شکست و ادامه
  ]), 23, { high: 105.8 });
}

/** کانال عریض‌تر از ۳۵٪ ارتفاع لگ: نامزد پرچم/پنانت باید رد شود. */
function wideChannelSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2],
    [130, 8],
    [118, 3],
    [132, 3],
    [114, 3],
    [128, 3],
    [128, 1],
    [136, 4],
  ]), 23, { low: 127.2 });
}

/** همان لگ، بعد کانال همگرا: سقف پایین‌آینده و کف بالارونده. */
function pennantSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2],
    [130, 8],
    [120, 3],
    [132, 3],
    [125, 3],
    [130, 3],
    [130, 1],
    [140, 4],
  ]), 23, { low: 129.2 });
}

/** سه‌گوشهٔ صعودی: سقف‌های هم‌سطح و کف‌های بالارونده. */
function ascendingTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [100, 3],
    [130, 6],
    [108, 6],
    [130, 6],
    [116, 6],
    [116, 1], // کف آخر را پیوت نگه می‌دارد
    [136, 4],
  ]);
}

/** سه‌گوشهٔ نزولی: کف‌های هم‌سطح و سقف‌های پایین‌آینده. */
function descendingTriangleSeries(): EngineCandle[] {
  return reshape(zigzag(120, [
    [128, 5],
    [100, 6],
    [126, 6],
    [100, 6],
    [124, 6],
    [100, 6],
    [101, 1], // برگشت کوچک تا کف آخر پیوت بماند
    [97, 1],
  ]), 36, { high: 100.9, low: 99.4, close: 100.5 });
}

/** سه‌گوشهٔ متقارن: سقف پایین‌آینده و کف بالارونده. */
function symmetricTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [126, 8],
    [108, 8],
    [130, 5],
  ]);
}

/** مستطیل: سقف و کف تخت، بعد شکست رو به بالا. */
function rectangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [130, 8],
    [100, 8],
    [134, 4],
  ]);
}

/**
 * همان جفت مرزی، هم مجازِ پرچم و هم همگرا: کانال در legEnd باریک‌تر از ۳۵٪ لگ است
 * (شرط پرچم) و در پایان فشرده‌سازی از ۶۵٪ عرض شروع کوچک‌تر می‌شود (شرط پنانت).
 */
function flagAndPennantSeries(): EngineCandle[] {
  return reshape(zigzag(100, [
    [98, 2],
    [130, 8], // لگ صعودی (۳۴ واحد)
    [127, 3],
    [133, 3],
    [129, 3],
    [130.5, 3],
    [130.5, 1],
    [140, 4],
  ]), 23, { low: 130.2 });
}

/**
 * یک شکل که هم مستطیل است و هم مثلث صعودی: سقف‌ها ۰٫۲ = ۰٫۱×ATR تخت و
 * کف‌ها ۰٫۸ = ۰٫۴×ATR بالارونده (درون تحمل مستطیل ۰٫۵×ATR، بیرون تحمل تختِ مثلث).
 */
function rectangleAndAscendingTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [130.2, 8],
    [100.8, 8],
    [134, 3],
  ]);
}

/**
 * مثلث صعودی قدیمی (پایان ~۲۸) و سپس یک پلکانِ صعودی ثابت‌عرض در انتهای سری:
 * پنجرهٔ تازه هیچ شکل خانوادهٔ مثلث نمی‌دهد، پس فقط پنجرهٔ قدیمی باید پیدا شود.
 */
function olderTriangleSeries(): EngineCandle[] {
  return zigzag(120, [
    [100, 3],
    [130, 6],
    [108, 6],
    [130, 6],
    [116, 6],
    [116, 1],
    [136, 4], // شکست صعودی و تأیید مثلث قدیمی
    [130, 3],
    [140, 3],
    [134, 3],
    [144, 3],
    [138, 3],
    [148, 3],
    [142, 3],
    [152, 3],
    [146, 3],
    [156, 3],
    [150, 3],
    [160, 3],
  ]);
}

/** گُوهٔ برخاسته: سقف و کف بالارونده با همگرایی، شکست نزولی. */
function risingWedgeSeries(): EngineCandle[] {
  return zigzag(120, [
    [130, 5],
    [100, 8],
    [134, 8],
    [120, 8],
    [120.1, 1],
  ]);
}

/** گُوهٔ افتاده: سقف و کف پایین‌آینده با همگرایی، شکست صعودی. */
function fallingWedgeSeries(): EngineCandle[] {
  return zigzag(120, [
    [136, 5],
    [110, 8],
    [120, 8],
    [104, 8],
    [120.5, 1],
  ]);
}

describe('continuation detectors', () => {
  it('finds a bull flag after an impulse leg', () => {
    const found = detectContinuation(flagSeries(), ATR, FIXTURE_CONFIG);
    expect(found.some((p) => p.kind === 'FLAG_BULL')).toBe(true);
    const flag = found.find((p) => p.kind === 'FLAG_BULL')!;
    expect(flag.family).toBe('continuation');
    expect(flag.direction).toBe('bullish');
    expect(flag.upper.to.price).toBeGreaterThan(flag.lower.to.price);
    expect(flag.quality).toBeGreaterThan(0);
    // تأییدشده با شکست پس از لنگر.
    expect(flag.status).toBe('confirmed');
    expect(flag.breakoutIndex).toBeDefined();
    expect(flag.breakoutIndex! > flag.anchor.index).toBe(true);
    expect(found.some((p) => p.kind === 'PENNANT')).toBe(false);
  });

  it('finds a bear flag after a bear impulse leg', () => {
    const candles = bearFlagSeries();
    const found = detectContinuation(candles, ATR, FIXTURE_CONFIG);
    const flag = found.find((p) => p.kind === 'FLAG_BEAR')!;
    expect(flag.family).toBe('continuation');
    expect(flag.direction).toBe('bearish');
    expect(flag.status).toBe('confirmed');
    expect(flag.breakoutIndex).toBeDefined();
    expect(flag.breakoutIndex! > flag.anchor.index).toBe(true);
    // جهت نزولی: هدف زیر ورود و حد ضرر بالای آن.
    const entry = candles[flag.breakoutIndex!]!.close;
    expect(flag.target).toBeLessThan(entry);
    expect(flag.stopLoss).toBeGreaterThan(entry);
    expect(found.some((p) => p.kind === 'FLAG_BULL' || p.kind === 'PENNANT')).toBe(false);
  });

  it('rejects a channel wider than the flag width limit', () => {
    const found = detectContinuation(wideChannelSeries(), ATR, FIXTURE_CONFIG);
    expect(found.some((p) => p.kind === 'FLAG_BULL' || p.kind === 'FLAG_BEAR' || p.kind === 'PENNANT')).toBe(false);
  });

  it('anchors on the latest point when the consolidation ends on a high', () => {
    const found = detectContinuation(formingFlagSeries(), ATR, FIXTURE_CONFIG);
    const flag = found.find((p) => p.kind === 'FLAG_BULL');
    expect(flag).toBeDefined();
    // آرایهٔ بریف با lows[1] (۱۹) تمام می‌شد؛ لنگر درست دیرترین نقطه (سقف ۲۲) است.
    expect(flag!.anchor.index).toBe(Math.max(...flag!.points.map((p) => p.index)));
    expect(flag!.anchor.index).toBe(22);
    expect(flag!.points.map((p) => p.index)).toEqual(
      [...flag!.points.map((p) => p.index)].sort((a, b) => a - b),
    );
    // حالت باز: هنوز شکستی رخ نداده و اسکن شکست هرگز پیش از لنگر شروع نمی‌شود.
    expect(flag!.status).toBe('forming');
    expect(flag!.breakoutIndex).toBeUndefined();
    expect(flag!.breakoutIndex === undefined || flag!.breakoutIndex > flag!.anchor.index).toBe(true);
  });

  it('does not invent a pattern on a straight line', () => {
    const flat: EngineCandle[] = Array.from({ length: 40 }, (_, i) => ({
      timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100,
    }));
    expect(detectContinuation(flat, 1.5, PATTERN_CONFIG)).toEqual([]);
  });

  it('finds a pennant when the consolidation converges', () => {
    const found = detectContinuation(pennantSeries(), ATR, FIXTURE_CONFIG);
    expect(found.some((p) => p.kind === 'PENNANT')).toBe(true);
    const pennant = found.find((p) => p.kind === 'PENNANT')!;
    expect(pennant.family).toBe('continuation');
    expect(pennant.direction).toBe('bullish');
    expect(pennant.quality).toBeGreaterThan(0);
    // همگرایی از مسیر خودش (نه از دروازهٔ عرض کانال پرچم) آمده است.
    expect(found.some((p) => p.kind === 'FLAG_BULL')).toBe(false);
    // R-PAT-14: پنانت همین جفت پیوت مرزی را مصرف کرده، پس مثلث متقارن تکراری حذف می‌شود.
    expect(found.some((p) => p.kind === 'TRIANGLE_SYM')).toBe(false);
    // یک شکل برای هر جفت مرزی: پنانت تنها شکل این فشرده‌سازی است.
    expect(found).toHaveLength(1);
    expect(found[0]!.kind).toBe('PENNANT');
  });

  it('keeps the flag when a flag and a pennant share the same boundary pair', () => {
    const found = detectContinuation(flagAndPennantSeries(), ATR, FIXTURE_CONFIG);
    const overlapping = found.filter((p) => p.kind === 'FLAG_BULL' || p.kind === 'PENNANT');
    // پیش از رفع: هر دو برای جفت یکسان منتشر می‌شدند؛ اکنون فقط پرچم می‌ماند.
    expect(overlapping).toHaveLength(1);
    expect(overlapping[0]!.kind).toBe('FLAG_BULL');
    expect(overlapping[0]!.direction).toBe('bullish');
  });

  it('emits one shape for a window that is both a rectangle and an ascending triangle', () => {
    const found = detectContinuation(rectangleAndAscendingTriangleSeries(), ATR, FIXTURE_CONFIG);
    const flatFamily = found.filter((p) => p.kind === 'RECTANGLE' || p.kind === 'TRIANGLE_ASC');
    // پیش از رفع، همین پنجره هر دو شکل را می‌داد.
    expect(flatFamily).toHaveLength(1);
    expect(flatFamily[0]!.kind).toBe('TRIANGLE_ASC');
  });

  it('scans older pivot windows so a historical triangle still contributes a confirmed sample', () => {
    const candles = olderTriangleSeries();
    const found = detectContinuation(candles, ATR, FIXTURE_CONFIG);
    const triangles = found.filter((p) => p.kind.startsWith('TRIANGLE_'));
    expect(triangles.length).toBeGreaterThan(0);
    // لنگر باید در تاریخچه باشد، نه انتهای سری (پنجرهٔ «دو پیوت آخر» این را از دست می‌داد).
    const historic = triangles.filter((p) => p.anchor.index < candles.length - 20);
    expect(historic.length).toBeGreaterThan(0);
    // الزامِ تسک: مثلثِ تاریخی‌ای که بعداً شکسته می‌شود باید نمونهٔ confirmed بدهد.
    expect(historic.some((p) => p.status === 'confirmed' && p.breakoutIndex != null)).toBe(true);
    expect(triangles.some((p) => p.anchor.index === candles.length - 1)).toBe(false);
  });

  it('finds an ascending triangle with flat highs and rising lows', () => {
    const found = detectContinuation(ascendingTriangleSeries(), ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_ASC');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('bullish');
    expect(triangle?.family).toBe('continuation');
  });

  it('finds a descending triangle with flat lows and falling highs', () => {
    const candles = descendingTriangleSeries();
    const found = detectContinuation(candles, ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_DESC');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('bearish');
    expect(triangle?.family).toBe('continuation');
    // R-PAT-15: هدف زیر مرز پایین منهای ارتفاع و حد ضرر بالای مرز بالا به‌علاوهٔ ATR.
    const entry = candles[triangle!.breakoutIndex!]!.close;
    expect(triangle!.target).toBeLessThan(entry);
    expect(triangle!.stopLoss).toBeGreaterThan(entry);
  });

  it('finds a symmetric triangle when both boundaries converge', () => {
    const found = detectContinuation(symmetricTriangleSeries(), ATR, FIXTURE_CONFIG);
    const triangle = found.find((p) => p.kind === 'TRIANGLE_SYM');
    expect(triangle).toBeDefined();
    expect(triangle?.direction).toBe('neutral');
    expect(triangle?.family).toBe('continuation');
  });

  it('finds a rectangle with flat highs and flat lows', () => {
    const found = detectContinuation(rectangleSeries(), ATR, FIXTURE_CONFIG);
    const rectangle = found.find((p) => p.kind === 'RECTANGLE');
    expect(rectangle).toBeDefined();
    expect(rectangle?.direction).toBe('neutral');
    expect(rectangle?.family).toBe('continuation');
  });

  it('finds a rising wedge and reports its bearish resolution', () => {
    const candles = risingWedgeSeries();
    const found = detectContinuation(candles, ATR, FIXTURE_CONFIG);
    const wedge = found.find((p) => p.kind === 'WEDGE_RISING');
    expect(wedge).toBeDefined();
    expect(wedge?.direction).toBe('bearish');
    expect(wedge?.family).toBe('continuation');
    // R-PAT-15: گُوهٔ نزولی هدف زیر ورود و حد ضرر بالای ورود دارد.
    const entry = candles[wedge!.breakoutIndex!]!.close;
    expect(wedge!.target).toBeLessThan(entry);
    expect(wedge!.stopLoss).toBeGreaterThan(entry);
  });

  it('finds a falling wedge and reports its bullish resolution', () => {
    const found = detectContinuation(fallingWedgeSeries(), ATR, FIXTURE_CONFIG);
    const wedge = found.find((p) => p.kind === 'WEDGE_FALLING');
    expect(wedge).toBeDefined();
    expect(wedge?.direction).toBe('bullish');
    expect(wedge?.family).toBe('continuation');
  });

  it('ignores non-positive ATR', () => {
    expect(detectContinuation(flagSeries(), 0, FIXTURE_CONFIG)).toEqual([]);
    expect(detectContinuation(flagSeries(), Number.NaN, FIXTURE_CONFIG)).toEqual([]);
  });
});
