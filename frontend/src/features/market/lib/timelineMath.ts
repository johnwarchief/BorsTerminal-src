// features/market/lib/timelineMath.ts -- تحلیل سری زمانی درون‌روز (میکرو چارت‌ها)
// ورودی خام: آرایه‌های ستونی /api/mstat/timeline?mode=cum. هیچ عددی ساخته نمی‌شود؛
// هر نقطه ناقص حذف می‌شود و سریِ کوتاه‌تر از ۲ نقطه سیگنال نمی‌دهد (Circuit Breaker).

type NumSeries = (number | null | undefined)[] | null | undefined;
type TimeSeries = (string | null | undefined)[] | null | undefined;

/** هر خانهٔ سری از بک‌اند: عدد، رشتهٔ عددی یا null (TSETMC رشته می‌فرستد؛ پایپ‌لاین عدد) */
export type RawCell = number | string | null | undefined;

export type TimelineSeriesInput = {
  t?: TimeSeries;
  bq_bt?: NumSeries;
  sq_bt?: NumSeries;
  pos?: NumSeries;
  neg?: NumSeries;
};

export type TimelinePoint = { t: string; bq: number | null; sq: number | null; pos: number | null; neg: number | null };

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/** coerce تک‌خانه: رشتهٔ عددی → عدد؛ هر چیز نامعتبر → null (ساختن عدد ممنوع) */
export function numCell(v: RawCell): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** coerce زمان: هر سلول غیرخالی به رشته؛ خالی → null */
export function timeCell(v: RawCell): string | null {
  if (typeof v === 'string' && v.trim() !== '') return v;
  if (typeof v === 'number' && Number.isFinite(v)) return String(v);
  return null;
}

/**
 * Transformer دو-قالبی: بک‌اندِ موجود ستونی می‌دهد
 * `{t:[...], bq_bt:[...], ...}`؛ اگر قالب به ردیفِ نقطه‌ای
 * `[{t, bq_bt, ...}, ...]` برسد، اینجا به ستونی نرمال می‌شود.
 * هر چیز نامعتبر آرایهٔ خالی/null می‌دهد تا UI صادقانه «بدون داده» بخورد.
 */
export function toSeriesColumns(series: unknown): TimelineSeriesInput {
  const EMPTY: TimelineSeriesInput = { t: [], bq_bt: [], sq_bt: [], pos: [], neg: [] };
  if (!series || typeof series !== 'object') return EMPTY;
  if (Array.isArray(series)) {
    const rows = (series as Record<string, RawCell>[]).filter((r) => r != null && typeof r === 'object');
    const col = (key: 't' | 'bq_bt' | 'sq_bt' | 'pos' | 'neg') => rows.map((r) => r[key] ?? null);
    return {
      t: col('t').map(timeCell),
      bq_bt: col('bq_bt').map(numCell),
      sq_bt: col('sq_bt').map(numCell),
      pos: col('pos').map(numCell),
      neg: col('neg').map(numCell),
    };
  }
  const obj = series as Record<string, RawCell[] | undefined>;
  const numCol = (k: 'bq_bt' | 'sq_bt' | 'pos' | 'neg') => (Array.isArray(obj[k]) ? obj[k].map(numCell) : []);
  return {
    t: Array.isArray(obj.t) ? obj.t.map(timeCell) : [],
    bq_bt: numCol('bq_bt'),
    sq_bt: numCol('sq_bt'),
    pos: numCol('pos'),
    neg: numCol('neg'),
  };
}

/** زیپ ستون‌های موازی به نقطه‌های زمانی؛ بدون زمانِ معتبر، نقطه‌ای نیست */
export function timelinePoints(s: TimelineSeriesInput | null | undefined): TimelinePoint[] {
  const times = s?.t;
  if (!Array.isArray(times) || times.length === 0) return [];
  const at = (arr: NumSeries, i: number) => (Array.isArray(arr) ? (arr[i] ?? null) : null);
  const out: TimelinePoint[] = [];
  for (let i = 0; i < times.length; i++) {
    const t = times[i];
    if (typeof t !== 'string' || !t) continue;
    out.push({
      t,
      bq: finite(at(s?.bq_bt, i)) ? (at(s?.bq_bt, i) as number) : null,
      sq: finite(at(s?.sq_bt, i)) ? (at(s?.sq_bt, i) as number) : null,
      pos: finite(at(s?.pos, i)) ? (at(s?.pos, i) as number) : null,
      neg: finite(at(s?.neg, i)) ? (at(s?.neg, i) as number) : null,
    });
  }
  return out;
}

export type BullishCrossResult = { hit: boolean; crossIndex: number | null; widening: boolean };

/**
 * Bullish Cross اردر‌بوک: خط ارزش صف خرید (bq_bt) از صف فروش (sq_bt) عبور کند
 * و پس از آن فاصله بگیرد. hit یعنی سیگنال کامل (عبور + باز شدن شکاف).
 */
export function detectBullishCross(bq: NumSeries, sq: NumSeries): BullishCrossResult {
  if (!Array.isArray(bq) || !Array.isArray(sq)) return { hit: false, crossIndex: null, widening: false };
  const n = Math.min(bq.length, sq.length);
  const diff: number[] = [];
  for (let i = 0; i < n; i++) {
    const a = bq[i];
    const b = sq[i];
    if (finite(a) && finite(b)) diff.push(a - b);
  }
  if (diff.length < 2) return { hit: false, crossIndex: null, widening: false };
  let crossIndex: number | null = null;
  for (let i = 1; i < diff.length; i++) {
    if (diff[i - 1] < 0 && diff[i] >= 0) crossIndex = i;
  }
  if (crossIndex == null) return { hit: false, crossIndex: null, widening: false };
  if (crossIndex >= diff.length - 1) return { hit: false, crossIndex, widening: false };
  const widening = diff[diff.length - 1] > diff[crossIndex];
  return { hit: widening, crossIndex, widening };
}

/**
 * معکوس‌شدن جهت روز در پهنای باند: تفاوت pos-neg در آخرین نقطه نسبت
 * به نقطه پیش علامت عوض کند. bull = ورود به قلمرو مثبت.
 */
export function detectBreadthFlip(pos: NumSeries, neg: NumSeries): 'bull' | 'bear' | null {
  if (!Array.isArray(pos) || !Array.isArray(neg)) return null;
  const n = Math.min(pos.length, neg.length);
  const diff: number[] = [];
  for (let i = 0; i < n; i++) {
    const a = pos[i];
    const b = neg[i];
    if (finite(a) && finite(b)) diff.push(a - b);
  }
  if (diff.length < 2) return null;
  const last = diff[diff.length - 1];
  const prev = diff[diff.length - 2];
  if (prev < 0 && last >= 0) return 'bull';
  if (prev > 0 && last <= 0) return 'bear';
  return null;
}

/** حداقل نقاط برای رندر منحنی -- کمتر از آن «بدون داده» */
export const MIN_CHART_POINTS = 2;
