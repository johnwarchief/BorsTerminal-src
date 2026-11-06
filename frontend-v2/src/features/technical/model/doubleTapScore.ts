/**
 * model/doubleTapScore.ts
 *
 * امتیاز وفادار p12 (Double Tap 3D، Indi 516):
 *   ۲۵ تطابق قله/دره + ۲۰ واگرایی RSI + ۱۵ واگرایی حجم + ۱۵ ارتفاع + ۱۰ تقارن + ۱۵ روند قبلی
 * حجمِ نامعلوم (بدون داده) نصفِ سهم را می‌گیرد: ۷٫۵ — دقیقاً مثل `s3` در Pine.
 * گرید: A ≥ ۷۵، B ≥ ۵۵، C < ۵۵.
 *
 * تابع خالص است؛ نه React، نه KLineCharts، نه I/O.
 */
import type { DoubleTapGrade, DoubleTapScoreBreakdown } from './types';

export interface DoubleTapScoreInput {
  /** درصد تطابق دو قله/دره (۰..۱)؛ پاین ۱ − |ΔP| / (tol × ATR). */
  matchPct: number;
  rsiDivergence: boolean;
  volumeDivergence: boolean;
  volumeKnown: boolean;
  /** ارتفاع الگو بر حسب ATR (h / ATR). */
  heightAtr: number;
  /** تقارن بازوها (۰..۱). */
  symmetry: number;
  /** حرکت قبلی نسبت به ارتفاع الگو (۰..۱). */
  priorTrendRatio: number;
}

export interface DoubleTapScoreResult {
  score: number;
  grade: DoubleTapGrade;
  breakdown: DoubleTapScoreBreakdown;
}

const clamp01 = (value: number): number =>
  Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;

export function gradeForScore(score: number): DoubleTapGrade {
  if (score >= 75) return 'A';
  if (score >= 55) return 'B';
  return 'C';
}

export function scoreDoubleTap(input: DoubleTapScoreInput): DoubleTapScoreResult {
  const match = 25 * clamp01(input.matchPct);
  const rsi = input.rsiDivergence ? 20 : 0;
  const volume = input.volumeKnown ? (input.volumeDivergence ? 15 : 0) : 7.5;
  const height = 15 * clamp01(input.heightAtr / 3);
  const symmetry = 10 * clamp01(input.symmetry);
  const trend = 15 * clamp01(input.priorTrendRatio);
  const breakdown: DoubleTapScoreBreakdown = { match, rsi, volume, height, symmetry, trend };
  const score = Math.round(match + rsi + volume + height + symmetry + trend);
  return { score, grade: gradeForScore(score), breakdown };
}

/**
 * RSI وایلدر (هم‌خانوادهٔ `ta.rsi` پاین) برای واگرایی p12.
 * خروجی هم‌طول ورودی است؛ تا قبل از گرم‌شدن ۵۰ (بی‌طرف) می‌ماند.
 */
export function rsiSeries(values: readonly number[], period = 14): number[] {
  const n = values.length;
  const out = new Array<number>(n).fill(50);
  if (n === 0) return out;
  const p = Math.max(1, Math.floor(period));
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i < n; i++) {
    const change = values[i] - values[i - 1];
    const gain = Math.max(0, change);
    const loss = Math.max(0, -change);
    if (i <= p) {
      avgGain += gain / p;
      avgLoss += loss / p;
      if (i === p) out[i] = rsiFromAverages(avgGain, avgLoss);
    } else {
      avgGain = (avgGain * (p - 1) + gain) / p;
      avgLoss = (avgLoss * (p - 1) + loss) / p;
      out[i] = rsiFromAverages(avgGain, avgLoss);
    }
  }
  return out;
}

function rsiFromAverages(avgGain: number, avgLoss: number): number {
  if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}
