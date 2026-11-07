// model/patterns/__tests__/cupRounding.test.ts
import { describe, expect, it } from 'vitest';
import { detectCupRounding } from '../detectCupRounding';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/**
 * سری مصنوعی بدون نویز: هر کندل حول قیمت بسته ساخته می‌شود تا دنبالهٔ
 * سقف/کف با پیوت‌های ۱/۱ (R-PAT-4: فقط پنجرهٔ پیوت در تست کوچک می‌شود).
 */
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

const FIXTURE_CONFIG = { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 };
const ATR = 2;

/**
 * کاپ: لبهٔ چپ سقف ۱۰۰ (پایان صعود ابتدایی)، کف گردِ ۹۰، لبهٔ راست ۱۰۰،
 * دستهٔ کم‌عمق تا ۹۷٫۵۵ و شکستِ بالای خطِ لبه.
 * عمق کاپ = ۱۰٫۸ = ۵٫۴×ATR؛ عمق دسته = ۳٫۲۵ ≈ ۳۰٪ عمق (زیر سقف ۳۳٪).
 */
const CUP_CLOSES = [
  ...Array.from({ length: 11 }, (_, i) => 96 + i * 0.4), // 0..10 → 100 (سقف چپ)
  ...Array.from({ length: 15 }, (_, i) => 100 - (i + 1) * (10 / 15)), // 11..25 → 90 (کف)
  ...Array.from({ length: 17 }, (_, i) => 90 + (i + 1) * (10 / 17)), // 26..42 → 100 (سقف راست)
  ...Array.from({ length: 7 }, (_, i) => 100 - (i + 1) * 0.35), // 43..49 → 97.55 (دسته)
  ...Array.from({ length: 10 }, (_, i) => 97.55 + (i + 1) * 0.45), // 50..59 → 102.05 (شکست)
];

/**
 * U بدون دسته: همان دو لبهٔ ۱۰۰ و کفِ ۹۰، اما سری روی لبهٔ راست تمام می‌شود؛
 * هیچ پیوتِ کفی پس از لبهٔ دوم شکل نمی‌گیرد، پس کاپ نباید صادر شود (R-PA-7).
 */
const CUP_NO_HANDLE_CLOSES = [
  ...Array.from({ length: 11 }, (_, i) => 96 + i * 0.4), // 0..10 → 100 (لبهٔ چپ)
  ...Array.from({ length: 15 }, (_, i) => 100 - (i + 1) * (10 / 15)), // 11..25 → 90 (کف)
  ...Array.from({ length: 17 }, (_, i) => 90 + (i + 1) * (10 / 17)), // 26..42 → 100 (لبهٔ راست)
  100, // 43: تخت روی لبه، بدون بازگشت
];

/**
 * همان کاپِ معتبر، اما دسته تا ۹۵٫۹ می‌رود: عمقِ دسته ۴٫۹ در برابر سقفِ
 * ۳۳٪ از ۱۰٫۸ (۳٫۵۶)؛ باید رد شود.
 */
const CUP_DEEP_HANDLE_CLOSES = [
  ...Array.from({ length: 11 }, (_, i) => 96 + i * 0.4), // 0..10 → 100
  ...Array.from({ length: 15 }, (_, i) => 100 - (i + 1) * (10 / 15)), // 11..25 → 90
  ...Array.from({ length: 17 }, (_, i) => 90 + (i + 1) * (10 / 17)), // 26..42 → 100
  ...Array.from({ length: 7 }, (_, i) => 100 - (i + 1) * 0.5857), // 43..49 → 95.9 (کف ۹۵٫۵)
  ...Array.from({ length: 10 }, (_, i) => 95.9 + (i + 1) * 0.6), // 50..59 → 101.9
];

/**
 * کاسهٔ کم‌عمق: لبه‌های ۹۱٫۶ و ۹۲٫۱ (خطِ لبهٔ شیب‌دار)، قعرِ ۸۸٫۶ در کندلِ ۲۶
 * و شکستِ سه کندل بعد (۲۹) بالای خطِ لبه. عمق ۳٫۲۵؛ هدف ۹۵٫۱.
 */
const LATE_BREAKOUT_CLOSES = [
  ...Array.from({ length: 15 }, (_, i) => 100 - i * (8 / 14)), // 0..14 → 100..92
  ...Array.from({ length: 11 }, (_, i) => 91.9 - i * (2 / 10)), // 15..25 → 91.9..89.9
  89, 89.6, 90.6, 92.2, // 26..29 → قعر و شکستِ سه‌کندل بعد
  ...Array.from({ length: 15 }, (_, i) => 92.5 + i * (7.5 / 14)), // 30..44 → 92.5..100
];

/**
 * کاسهٔ کم‌عمق: ۱۰۰ → ۹۲، قعرِ سهمیِ ۸۹ در یک‌سومِ میانی، بازگشت به ۱۰۰.
 * عمق = ۳٫۰ (۱٫۵×ATR)؛ بیش از نیمی از بسته‌های میانی زیرِ خطِ لبه‌اند.
 */
const BOWL_CLOSES = [
  ...Array.from({ length: 15 }, (_, i) => 100 - i * (8 / 14)), // 0..14 → 92
  ...Array.from({ length: 15 }, (_, i) => 89 + 3 * ((i - 7) / 7) ** 2), // 15..29 → 89 (قعر)
  ...Array.from({ length: 15 }, (_, i) => 92 + i * (8 / 14)), // 30..44 → 100
];

/**
 * کفِ V تیز بدون گردشدن: سقفِ صاف، شکافِ باریک تا ۹۴ و بازگشت به سقف؛
 * سپس سکوی کمی پایین‌تر (۹۸) تا دامنهٔ لبه‌های کاپ (۱۰۰٫۴ و ۹۹؟) بیرون از
 * رواداریِ لبه بماند و هیچ کاپی ساخته نشود. فقط ۹ کندل از ۲۰ کندلِ بخش
 * میانی زیرِ خطِ لبه‌اند: سهم ۰٫۴۵ < ۰٫۵۵، پس گردشدن رد می‌شود.
 */
const V_CLOSES = [
  ...Array.from({ length: 26 }, () => 100), // 0..25
  99.2, 98.4, 97.2, 95.6, 94, 95.6, 97.2, 98.4, 99.2, // 26..34 (شکاف V)
  99.6, 99.2, 98.8, 98.4, 98.2, // 35..39
  ...Array.from({ length: 20 }, () => 98), // 40..59
];

describe('detectCupRounding', () => {
  it('emits a confirmed CUP_HANDLE for aligned rims, a rounded cup and a shallow handle', () => {
    const result = detectCupRounding(seriesFrom(CUP_CLOSES), ATR, FIXTURE_CONFIG);
    const cup = result.find((p) => p.kind === 'CUP_HANDLE');
    expect(cup).toBeDefined();
    expect(cup?.status).toBe('confirmed');
    expect(cup?.direction).toBe('bullish');
    expect(cup?.family).toBe('continuation');
    expect(cup?.tier).toBe(1);
    expect(result.every((p) => p.tier === 1)).toBe(true);
  });

  it('emits a confirmed INVERSE_CUP_HANDLE for the mirrored series', () => {
    const result = detectCupRounding(mirrored(CUP_CLOSES), ATR, FIXTURE_CONFIG);
    const cup = result.find((p) => p.kind === 'INVERSE_CUP_HANDLE');
    expect(cup).toBeDefined();
    expect(cup?.status).toBe('confirmed');
    expect(cup?.direction).toBe('bearish');
    expect(cup?.family).toBe('continuation');
    expect(cup?.tier).toBe(1);
    expect(result.every((p) => p.tier === 1)).toBe(true);
  });

  it('requires a handle pivot: a U with no pullback after the right rim is not a CUP_HANDLE', () => {
    expect(
      detectCupRounding(seriesFrom(CUP_NO_HANDLE_CLOSES), ATR, FIXTURE_CONFIG).some((p) => p.kind === 'CUP_HANDLE'),
    ).toBe(false);
    expect(
      detectCupRounding(mirrored(CUP_NO_HANDLE_CLOSES), ATR, FIXTURE_CONFIG).some((p) => p.kind === 'INVERSE_CUP_HANDLE'),
    ).toBe(false);
  });

  it('rejects a handle deeper than handleDepthPct of the cup depth', () => {
    expect(
      detectCupRounding(seriesFrom(CUP_CLOSES), ATR, FIXTURE_CONFIG).some((p) => p.kind === 'CUP_HANDLE'),
    ).toBe(true);
    expect(
      detectCupRounding(seriesFrom(CUP_DEEP_HANDLE_CLOSES), ATR, FIXTURE_CONFIG).some((p) => p.kind === 'CUP_HANDLE'),
    ).toBe(false);
    expect(
      detectCupRounding(mirrored(CUP_DEEP_HANDLE_CLOSES), ATR, FIXTURE_CONFIG).some((p) => p.kind === 'INVERSE_CUP_HANDLE'),
    ).toBe(false);
  });

  it('uses cup.minDepthAtr as the depth gate, not a literal', () => {
    const cup = seriesFrom(CUP_CLOSES);
    expect(detectCupRounding(cup, ATR, FIXTURE_CONFIG).some((p) => p.kind === 'CUP_HANDLE')).toBe(true);
    const strict = {
      ...FIXTURE_CONFIG,
      cup: { ...FIXTURE_CONFIG.cup, minDepthAtr: 6 },
    };
    expect(detectCupRounding(cup, ATR, strict).some((p) => p.kind === 'CUP_HANDLE')).toBe(false);
  });

  it('rejects a sharp V-notch whose curvature share below the rim is under curvatureMin', () => {
    expect(detectCupRounding(seriesFrom(V_CLOSES), ATR, FIXTURE_CONFIG)).toEqual([]);
  });

  it('consumes curvatureMin as a real gate: the same V-notch passes when it is lowered', () => {
    const loose = {
      ...FIXTURE_CONFIG,
      rounding: { ...FIXTURE_CONFIG.rounding, curvatureMin: 0.4 },
    };
    const result = detectCupRounding(seriesFrom(V_CLOSES), ATR, loose);
    expect(result.some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(true);
    expect(result.every((p) => p.tier === 1)).toBe(true);
  });

  it('emits ROUNDING_BOTTOM for a rounded bowl whose middle third stays below the rim', () => {
    const result = detectCupRounding(seriesFrom(BOWL_CLOSES), ATR, FIXTURE_CONFIG);
    const bottom = result.find((p) => p.kind === 'ROUNDING_BOTTOM');
    expect(bottom).toBeDefined();
    expect(bottom?.direction).toBe('bullish');
    expect(bottom?.family).toBe('reversal');
    expect(bottom?.tier).toBe(1);
  });

  it('emits ROUNDING_TOP for the mirrored bowl', () => {
    const result = detectCupRounding(mirrored(BOWL_CLOSES), ATR, FIXTURE_CONFIG);
    const top = result.find((p) => p.kind === 'ROUNDING_TOP');
    expect(top).toBeDefined();
    expect(top?.direction).toBe('bearish');
    expect(top?.family).toBe('reversal');
    expect(top?.tier).toBe(1);
  });

  it('uses rounding.minDepthAtr as the depth gate, not a literal', () => {
    const bowl = seriesFrom(BOWL_CLOSES);
    expect(detectCupRounding(bowl, ATR, FIXTURE_CONFIG).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(true);
    const strict = {
      ...FIXTURE_CONFIG,
      rounding: { ...FIXTURE_CONFIG.rounding, minDepthAtr: 2 },
    };
    expect(detectCupRounding(bowl, ATR, strict).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(false);
  });

  it('anchors ROUNDING_BOTTOM on the real extreme bar and confirms the breakout 3 bars later', () => {
    const result = detectCupRounding(seriesFrom(LATE_BREAKOUT_CLOSES), ATR, FIXTURE_CONFIG);
    const bottom = result.find((p) => p.kind === 'ROUNDING_BOTTOM');
    expect(bottom).toBeDefined();
    // لنگر = کندلِ واقعیِ قعر (۲۶)، نه انتهای پنجره.
    expect(bottom?.anchor.index).toBe(26);
    expect(bottom?.anchor.price).toBeCloseTo(88.6, 6);
    expect(bottom?.status).toBe('confirmed');
    expect(bottom?.breakoutIndex).toBe(29);
    expect((bottom?.breakoutIndex ?? -1) - (bottom?.anchor.index ?? -1)).toBe(3);
  });

  it('targets rim ± depth beyond the rim, not the rim itself', () => {
    const bowl = detectCupRounding(seriesFrom(BOWL_CLOSES), ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'ROUNDING_BOTTOM');
    expect(bowl).toBeDefined();
    // لبهٔ کف = ۹۱٫۶ (میانگین دو سر)، عمق ۳٫۰.
    expect(bowl?.target).toBeCloseTo(94.6, 3);
    const top = detectCupRounding(mirrored(BOWL_CLOSES), ATR, FIXTURE_CONFIG)
      .find((p) => p.kind === 'ROUNDING_TOP');
    expect(top).toBeDefined();
    // لبهٔ سقف = ۱۰۸٫۴، عمق ۳٫۰.
    expect(top?.target).toBeCloseTo(105.4, 3);
  });

  it('consumes rounding.minBulgeAtr as a real gate', () => {
    const bowl = seriesFrom(BOWL_CLOSES);
    expect(detectCupRounding(bowl, ATR, FIXTURE_CONFIG).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(true);
    const flat = {
      ...FIXTURE_CONFIG,
      rounding: { ...FIXTURE_CONFIG.rounding, minBulgeAtr: 10 },
    };
    expect(detectCupRounding(bowl, ATR, flat).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(false);
  });

  it('consumes rounding.endSkewPct as a real gate', () => {
    const skewed = seriesFrom(LATE_BREAKOUT_CLOSES);
    expect(detectCupRounding(skewed, ATR, FIXTURE_CONFIG).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(true);
    const aligned = {
      ...FIXTURE_CONFIG,
      rounding: { ...FIXTURE_CONFIG.rounding, endSkewPct: 0 },
    };
    expect(detectCupRounding(skewed, ATR, aligned).some((p) => p.kind === 'ROUNDING_BOTTOM')).toBe(false);
  });
});
