/**
 * model/patterns/detectChannelPivot.ts
 *
 * پورت p19 — «Wedge & Channel Detector» (Indi 407، MPL-2.0، @IndicatorsforTV):
 * - انتخاب خودکار ساختار از ۵ پیوت آخر هر لبه (طول پیوت ۲۰)، با فاصلهٔ حداقل ۱۰ کندل
 * - امتیاز p19: touches(۳۵) + balance(۱۵) + violations(۲۵) + span(۱۰) + recency(۱۰) + width(۵)
 *   با کپ‌های ۵۹/۸۴ و جریمهٔ عدم‌توازن
 * - طبقه‌بندی موازی (اختلاف شیب ≤ ۱۰٪) → Channel؛ همگرا → مثلث/گوه؛ واگرا → Expanding
 * - چرخه: شکست با دو بستهٔ آخر خارج از خط ±۰.۳ ATR، reclaim دو بستهٔ داخل، expiry ۱۰ کندل بعد
 * - پنجرهٔ متریک به اندازهٔ autoLookbackBars از «شروع ساختار» بسته می‌شود تا افزودن کندل
 *   آینده، لمس/نقض گذشته را تغییر ندهد (no-look-ahead).
 *
 * تابع خالص است؛ نه React، نه KLineCharts. پیوت‌ها از `pivots.ts` بازاستفاده می‌شوند.
 */
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import { isPivotHigh, isPivotLow } from './pivots';
import type { PatternPoint } from './types';

export type ChannelStructureKind =
  | 'PIVOT_CHANNEL'
  | 'CONVERGING_WEDGE'
  | 'SYMMETRIC_TRIANGLE'
  | 'ASCENDING_TRIANGLE'
  | 'DESCENDING_TRIANGLE'
  | 'EXPANDING_STRUCTURE';

export type ChannelPivotConfig = PatternConfig['channelPivot'];

export interface ChannelAnchor {
  index: number;
  price: number;
}

export interface ChannelLine {
  from: ChannelAnchor;
  to: ChannelAnchor;
}

export interface ChannelGeometry {
  upper: ChannelLine;
  lower: ChannelLine;
}

export interface ChannelScoreComponents {
  touch: number;
  balance: number;
  violation: number;
  span: number;
  recency: number;
  width: number;
}

export interface ChannelScore {
  score: number;
  grade: 'A' | 'B' | 'C';
  components: ChannelScoreComponents;
  touchesUpper: number;
  touchesLower: number;
  violationsUpper: number;
  violationsLower: number;
  touchRatio: number | null;
  widthAtr: number;
  spanBars: number;
  recencyBars: number;
}

export interface ChannelMetrics {
  upperSlope: number;
  lowerSlope: number;
  slopeDiff: number;
  widthAtr: number;
  convergencePct: number | null;
  apexIndex: number | null;
  barsToApex: number | null;
  touchesUpper: number;
  touchesLower: number;
  violationsUpper: number;
  violationsLower: number;
  spanBars: number;
  recencyBars: number;
  components: ChannelScoreComponents;
}

export interface ChannelCandidate {
  kind: ChannelStructureKind;
  upper: ChannelLine;
  lower: ChannelLine;
  points: PatternPoint[];
  score: number;
  grade: 'A' | 'B' | 'C';
  touches: { upper: number; lower: number; total: number };
  violations: number;
  apexIndex?: number;
  barsToApex?: number;
  convergencePct?: number;
  lateStage: boolean;
  lifecycle: 'active' | 'late' | 'broken' | 'expired';
  metrics: ChannelMetrics;
}

const EPS = 1e-9;

function lineValue(fromIndex: number, fromPrice: number, toIndex: number, toPrice: number, index: number): number {
  const span = toIndex - fromIndex;
  if (span === 0) return toPrice;
  return fromPrice + ((toPrice - fromPrice) * (index - fromIndex)) / span;
}

function upperAt(geometry: ChannelGeometry, index: number): number {
  const { from, to } = geometry.upper;
  return lineValue(from.index, from.price, to.index, to.price, index);
}

function lowerAt(geometry: ChannelGeometry, index: number): number {
  const { from, to } = geometry.lower;
  return lineValue(from.index, from.price, to.index, to.price, index);
}

/** p19: A ≥ 85 (Excellent)، B ≥ 65 (Good)، بقیه C. */
export function gradeForChannel(score: number): 'A' | 'B' | 'C' {
  if (score >= 85) return 'A';
  if (score >= 65) return 'B';
  return 'C';
}

export function classifyChannelStructure(
  upperSlope: number,
  lowerSlope: number,
): ChannelStructureKind {
  const largest = Math.max(Math.abs(upperSlope), Math.abs(lowerSlope));
  const slopeDiff = Math.abs(upperSlope - lowerSlope);
  if (largest === 0 || slopeDiff <= largest * 0.1) return 'PIVOT_CHANNEL';
  if (upperSlope < lowerSlope) {
    if (upperSlope < 0 && lowerSlope > 0) return 'SYMMETRIC_TRIANGLE';
    if (upperSlope < 0 && lowerSlope >= 0) return 'DESCENDING_TRIANGLE';
    if (upperSlope <= 0 && lowerSlope > 0) return 'ASCENDING_TRIANGLE';
    return 'CONVERGING_WEDGE';
  }
  return 'EXPANDING_STRUCTURE';
}

export function isChannelLateStage(
  args: {
    converging: boolean;
    apexPassed: boolean;
    widthAtr: number | null | undefined;
    barsToApex: number | null | undefined;
  },
  config: ChannelPivotConfig,
): boolean {
  if (!args.converging || args.apexPassed) return false;
  const lateByWidth = args.widthAtr != null && args.widthAtr <= config.lateStageWidthAtr;
  const lateByApex = args.barsToApex != null
    && args.barsToApex > 0
    && args.barsToApex <= config.lateStageApexBars;
  return lateByWidth || lateByApex;
}

/**
 * امتیاز یک ساختار با فرمول‌های p19 (تا 1e-9).
 * پنجرهٔ اسکن از `structureStart` تا `structureStart + autoLookbackBars` است (بسته و replay-safe).
 */
export function scoreChannelStructure(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  geometry: ChannelGeometry,
  config: ChannelPivotConfig,
  lastIndex: number,
): ChannelScore | null {
  if (candles.length === 0 || lastIndex < 0 || lastIndex >= candles.length) return null;
  const structureStart = Math.max(geometry.upper.from.index, geometry.lower.from.index);
  if (lastIndex < structureStart) return null;

  const windowEnd = Math.min(lastIndex, structureStart + config.autoLookbackBars);
  let touchesUpper = 0;
  let touchesLower = 0;
  let violationsUpper = 0;
  let violationsLower = 0;
  let lastUpperTouchX: number | null = null;
  let lastLowerTouchX: number | null = null;

  for (let testX = structureStart; testX <= windowEnd; testX++) {
    const testUpper = upperAt(geometry, testX);
    const testLower = lowerAt(geometry, testX);
    const testAtr = atr[testX];
    // p19: ATR نامعلوم ⇒ تلورانس صفر.
    const touchTol = testAtr != null && Number.isFinite(testAtr) ? testAtr * config.touchTolAtr : 0;
    const violationTol = testAtr != null && Number.isFinite(testAtr) ? testAtr * config.violationTolAtr : 0;
    const bar = candles[testX];

    const upperNear = Math.abs(bar.high - testUpper) <= touchTol;
    const lowerNear = Math.abs(bar.low - testLower) <= touchTol;
    const upperViolation = bar.close > testUpper + violationTol;
    const lowerViolation = bar.close < testLower - violationTol;

    if (upperNear && (lastUpperTouchX == null || Math.abs(testX - lastUpperTouchX) >= config.minTouchSpacing)) {
      touchesUpper += 1;
      lastUpperTouchX = testX;
    }
    if (lowerNear && (lastLowerTouchX == null || Math.abs(testX - lastLowerTouchX) >= config.minTouchSpacing)) {
      touchesLower += 1;
      lastLowerTouchX = testX;
    }
    if (upperViolation) violationsUpper += 1;
    if (lowerViolation) violationsLower += 1;
  }

  const totalTouches = touchesUpper + touchesLower;
  const totalViolations = violationsUpper + violationsLower;
  const minTouches = Math.min(touchesUpper, touchesLower);
  const maxTouches = Math.max(touchesUpper, touchesLower);

  const touch = Math.min(35, totalTouches * 5);
  const balanceFactor = totalTouches > 0
    ? 1 - Math.abs(touchesUpper - touchesLower) / totalTouches
    : 0;
  const balance = balanceFactor * 15;
  const violation = Math.max(0, 25 - totalViolations * 3);

  const upperSpan = geometry.upper.to.index - geometry.upper.from.index;
  const lowerSpan = geometry.lower.to.index - geometry.lower.from.index;
  const averageSpan = (upperSpan + lowerSpan) / 2;
  const span = Math.min(10, averageSpan / 15);

  const newestAnchor = Math.max(geometry.upper.to.index, geometry.lower.to.index);
  const recencyBars = Math.max(0, lastIndex - newestAnchor);
  const recency = Math.max(0, 10 - recencyBars * 0.15);

  const currentWidth = upperAt(geometry, lastIndex) - lowerAt(geometry, lastIndex);
  const lastAtr = atr[lastIndex];
  const widthAtr = lastAtr != null && lastAtr > 0 ? currentWidth / lastAtr : Number.NaN;
  let width = 0;
  if (Number.isFinite(widthAtr)) {
    if (widthAtr >= config.minWidthAtr && widthAtr <= config.maxWidthAtr) width = 5;
    else if (widthAtr < config.minWidthAtr) width = Math.max(0, (widthAtr / config.minWidthAtr) * 5);
    else width = Math.max(0, 5 - (widthAtr - config.maxWidthAtr) * 0.25);
  }

  let score = touch + balance + violation + span + recency + width;
  // اعتبار دوطرفه (p19): لمس کمتر از ۲ در یک سمت ⇒ سقف ۵۹؛ کمتر از ۳ ⇒ سقف ۸۴.
  if (minTouches < 2) score = Math.min(score, 59);
  else if (minTouches < 3) score = Math.min(score, 84);

  // جریمهٔ عدم‌توازن و کپ‌های نسبتی.
  const touchRatio = minTouches > 0 ? maxTouches / minTouches : null;
  if (touchRatio != null && touchRatio > config.balancePenaltyStart) {
    score -= (touchRatio - config.balancePenaltyStart) * config.balancePenaltyStrength;
    if (touchRatio >= 2) score = Math.min(score, 84);
    if (touchRatio >= 2.5) score = Math.min(score, 74);
    if (touchRatio >= 3) score = Math.min(score, 59);
  }
  score = Math.max(0, Math.min(100, score));

  return {
    score,
    grade: gradeForChannel(score),
    components: { touch, balance, violation, span, recency, width },
    touchesUpper,
    touchesLower,
    violationsUpper,
    violationsLower,
    touchRatio,
    widthAtr,
    spanBars: averageSpan,
    recencyBars,
  };
}

interface BreakState {
  direction: 1 | -1 | 0;
  breakBar: number | null;
}

/** شکست تأییدشده در انتهای سری + reclaim دو بستهٔ داخل (p19). */
function evaluateBreak(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  geometry: ChannelGeometry,
  config: ChannelPivotConfig,
  lastIndex: number,
  newestAnchor: number,
): BreakState {
  const start = Math.max(newestAnchor, lastIndex - config.breakoutConfirmBars * 4);
  let direction: 1 | -1 | 0 = 0;
  let runStart: number | null = null;
  let runLength = 0;

  const beyondUp = (index: number): boolean => {
    const tol = (atr[index] ?? 0) * config.breakoutAtr;
    return candles[index].close > upperAt(geometry, index) + tol;
  };
  const beyondDown = (index: number): boolean => {
    const tol = (atr[index] ?? 0) * config.breakoutAtr;
    return candles[index].close < lowerAt(geometry, index) - tol;
  };

  for (let index = lastIndex; index >= start; index--) {
    if (beyondUp(index) && !beyondDown(index)) {
      if (direction === -1) break;
      direction = 1;
      runStart = index;
      runLength += 1;
    } else if (beyondDown(index) && !beyondUp(index)) {
      if (direction === 1) break;
      direction = -1;
      runStart = index;
      runLength += 1;
    } else {
      break;
    }
    if (runLength >= config.breakoutConfirmBars) break;
  }

  if (direction === 0 || runStart == null || runLength < config.breakoutConfirmBars) {
    return { direction: 0, breakBar: null };
  }

  // reclaim: اگر reclaimBars بستهٔ آخر دوباره داخل دو مرز باشند، شکست باطل است.
  let inside = 0;
  for (let offset = 0; offset < config.reclaimBars; offset++) {
    const index = lastIndex - offset;
    if (index < 0) break;
    if (candles[index].close <= upperAt(geometry, index) && candles[index].close >= lowerAt(geometry, index)) {
      inside += 1;
    }
  }
  if (inside === config.reclaimBars) return { direction: 0, breakBar: null };

  return { direction, breakBar: runStart };
}

export function detectPivotChannel(
  candles: readonly EngineCandle[],
  atr: readonly number[],
  config: ChannelPivotConfig,
  offset = 0,
): ChannelCandidate[] {
  const n = candles.length;
  const lastIndex = n - 1;
  if (n < config.pivotLen * 2 + 2) return [];
  const lastAtr = atr[lastIndex];
  if (!(lastAtr > 0)) return [];

  const highs: ChannelAnchor[] = [];
  const lows: ChannelAnchor[] = [];
  for (let i = config.pivotLen; i <= n - config.pivotLen - 1; i++) {
    if (isPivotHigh(candles as EngineCandle[], i, config.pivotLen, config.pivotLen)) {
      highs.push({ index: i, price: candles[i].high });
    }
    if (isPivotLow(candles as EngineCandle[], i, config.pivotLen, config.pivotLen)) {
      lows.push({ index: i, price: candles[i].low });
    }
  }
  const dedup = (arr: ChannelAnchor[]): ChannelAnchor[] =>
    arr.filter((p, i) => i === 0 || Math.abs(p.price - arr[i - 1].price) > 1e-9 || p.index - arr[i - 1].index > config.pivotLen);
  const upperPivots = dedup(highs).slice(-config.autoPivotCount);
  const lowerPivots = dedup(lows).slice(-config.autoPivotCount);
  if (upperPivots.length < 2 || lowerPivots.length < 2) return [];

  const results: ChannelCandidate[] = [];
  const seen = new Set<string>();

  for (let ui = 0; ui < upperPivots.length - 1; ui++) {
    for (let uj = ui + 1; uj < upperPivots.length; uj++) {
      const uA = upperPivots[ui];
      const uB = upperPivots[uj];
      if (uB.index - uA.index < config.minAnchorSpacing) continue;

      for (let li = 0; li < lowerPivots.length - 1; li++) {
        for (let lj = li + 1; lj < lowerPivots.length; lj++) {
          const lA = lowerPivots[li];
          const lB = lowerPivots[lj];
          if (lB.index - lA.index < config.minAnchorSpacing) continue;

          const key = `${uA.index}-${uB.index}-${lA.index}-${lB.index}`;
          if (seen.has(key)) continue;

          const geometry: ChannelGeometry = {
            upper: { from: uA, to: uB },
            lower: { from: lA, to: lB },
          };
          const structureStart = Math.max(uA.index, lA.index);
          if (lastIndex <= structureStart) continue;

          const widthAtStart = upperAt(geometry, structureStart) - lowerAt(geometry, structureStart);
          const widthNow = upperAt(geometry, lastIndex) - lowerAt(geometry, lastIndex);
          if (!(widthAtStart > 0) || !(widthNow > 0)) continue;

          const upperSlope = (uB.price - uA.price) / (uB.index - uA.index);
          const lowerSlope = (lB.price - lA.price) / (lB.index - lA.index);
          const converging = upperSlope < lowerSlope;
          const slopeDiff = Math.abs(upperSlope - lowerSlope);
          const largestSlope = Math.max(Math.abs(upperSlope), Math.abs(lowerSlope));
          const roughlyParallel = largestSlope === 0 || slopeDiff <= largestSlope * 0.1;

          const denominator = upperSlope - lowerSlope;
          let apexX: number | null = null;
          if (!roughlyParallel && Math.abs(denominator) > 1e-7) {
            const upperIntercept = uA.price - upperSlope * uA.index;
            const lowerIntercept = lA.price - lowerSlope * lA.index;
            apexX = (lowerIntercept - upperIntercept) / denominator;
          }
          const apexPassed = converging && apexX != null && apexX <= lastIndex;
          if (apexPassed) continue;

          const scored = scoreChannelStructure(candles, atr, geometry, config, lastIndex);
          if (!scored) continue;

          const barsToApex = converging && apexX != null ? apexX - lastIndex : null;
          const convergencePct = converging && widthNow > 0
            ? (() => {
                const projection = lastIndex + config.convergenceProjectionBars;
                const projectedWidth = upperAt(geometry, projection) - lowerAt(geometry, projection);
                return ((widthNow - projectedWidth) / widthNow) * 100;
              })()
            : null;
          const lateStage = isChannelLateStage(
            { converging, apexPassed, widthAtr: scored.widthAtr, barsToApex },
            config,
          );

          const newestAnchor = Math.max(uB.index, lB.index);
          const breakState = evaluateBreak(candles, atr, geometry, config, lastIndex, newestAnchor);
          let lifecycle: ChannelCandidate['lifecycle'];
          if (breakState.direction !== 0 && breakState.breakBar != null) {
            lifecycle = lastIndex - breakState.breakBar >= config.expireAfterBreakBars ? 'expired' : 'broken';
          } else if (lateStage) {
            lifecycle = 'late';
          } else {
            lifecycle = 'active';
          }

          const kind = classifyChannelStructure(upperSlope, lowerSlope);
          const toPoint = (anchor: ChannelAnchor): PatternPoint => ({
            index: anchor.index + offset,
            price: anchor.price,
            timestamp: candles[anchor.index]?.timestamp ?? 0,
          });
          const upper = {
            from: toPoint(uA),
            to: toPoint(uB),
          };
          const lower = {
            from: toPoint(lA),
            to: toPoint(lB),
          };
          // For B7, breakDirection/content doesn't matter; keep metric-level detail.
          results.push({
            kind,
            upper,
            lower,
            points: [upper.from, upper.to, lower.from, lower.to],
            score: scored.score,
            grade: scored.grade,
            touches: {
              upper: scored.touchesUpper,
              lower: scored.touchesLower,
              total: scored.touchesUpper + scored.touchesLower,
            },
            violations: scored.violationsUpper + scored.violationsLower,
            apexIndex: apexX != null ? Math.round(apexX) + offset : undefined,
            barsToApex: barsToApex ?? undefined,
            convergencePct: convergencePct ?? undefined,
            lateStage,
            lifecycle,
            metrics: {
              upperSlope,
              lowerSlope,
              slopeDiff,
              widthAtr: scored.widthAtr,
              convergencePct,
              apexIndex: apexX != null ? Math.round(apexX) + offset : null,
              barsToApex,
              touchesUpper: scored.touchesUpper,
              touchesLower: scored.touchesLower,
              violationsUpper: scored.violationsUpper,
              violationsLower: scored.violationsLower,
              spanBars: scored.spanBars,
              recencyBars: scored.recencyBars,
              components: scored.components,
            },
          });
          seen.add(key);
        }
      }
    }
  }

  return results.sort((a, b) => b.score - a.score || b.upper.to.index - a.upper.to.index);
}
