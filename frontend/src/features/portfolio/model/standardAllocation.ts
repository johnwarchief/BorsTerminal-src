// features/portfolio/model/standardAllocation.ts -- سبد استاندارد FTS + سنجهٔ هم‌ترازی (Twin Donuts)
// نسبت‌های مصوب سند: ۴۵٪ طلا و سکه · ۱۵٪ سهام مستقیم · ۱۵٪ ارز دیجیتال · ۱۰٪ نقره · ۱۵٪ درآمد ثابت/نقدینگی.
// وزنِ واقعی از همان buildDelta می‌آید (ترکیبِ طبقاتِ سبد ← ارزشِ دستی ← هیچ):
// این‌جا عددی دوباره حساب نمی‌شود، پس دونات و نوارِ شکاف دو جوابِ متفاوت نمی‌دهند.
// Circuit Breaker: نبود داده ⇒ actualPct=null («بدون داده») — هرگز صفر ساختگی.
import { toFaDigits } from '@shared/lib/fmt';
import type { DeltaRow } from '../stores/targetAllocation';

export type StdBucketId = 'gold' | 'equity' | 'crypto' | 'silver' | 'fixed';

export type StdBucket = {
  id: StdBucketId;
  label: string;
  /** نسبت مصوب سند (درصد) */
  pct: number;
  color: string;
  /** شناسهٔ طبقات استور هدف که این باکت را می‌سازند */
  classIds: string[];
};

/** نسبت‌های مصوب سند FTS — جمع ۱۰۰٪ */
export const FTS_STANDARD_BUCKETS: StdBucket[] = [
  { id: 'gold', label: 'طلا و سکه', pct: 45, color: '#f59e0b', classIds: ['gold', 'gold-cert'] },
  { id: 'equity', label: 'سهام مستقیم', pct: 15, color: '#10b981', classIds: ['equity'] },
  { id: 'crypto', label: 'ارز دیجیتال', pct: 15, color: '#22d3ee', classIds: ['crypto'] },
  { id: 'silver', label: 'نقره', pct: 10, color: '#94a3b8', classIds: ['silver'] },
  { id: 'fixed', label: 'درآمد ثابت و نقدینگی', pct: 15, color: '#64748b', classIds: ['fixed'] },
];

export const FTS_STANDARD_TOTAL_PCT = FTS_STANDARD_BUCKETS.reduce((s, b) => s + b.pct, 0);

/** کلیدهای استورِ «ارزشِ دستیِ طبقات» (تومان) — همان شناسه‌هایی که buildDelta می‌خواند */
export type AssetValueKey = 'gold' | 'crypto' | 'silver' | 'fixed';
export const ASSET_VALUE_KEYS: AssetValueKey[] = ['gold', 'crypto', 'silver', 'fixed'];

export type ActualSource = 'basket' | 'value' | null;

export type BucketComparison = {
  bucket: StdBucket;
  /** وزن هدف (درصد) — جمعِ هدفِ ردیف‌های همان باکت در استورِ هدف */
  targetPct: number;
  /** وزن واقعی (درصد) — null یعنی بدون داده */
  actualPct: number | null;
  /** منبع دادهٔ وزن واقعی */
  source: ActualSource;
  /** انحراف (واقعی − هدف) — null یعنی بدون داده */
  deviationPct: number | null;
  state: 'overweight' | 'underweight' | 'ok' | 'nodata';
};

/** آستانهٔ تشخیص مازاد/کسری (درصد) */
export const DEVIATION_EPS_PCT = 0.5;

const r1 = (x: number) => Math.round(x * 10) / 10;

/**
 * لایهٔ نمایشِ دونات: هر باکتِ سند را از ردیف‌های buildDelta می‌خواند.
 * دو قاعده که قبلاً اینجا می‌شد:
 * · «سهام = جمعِ وزنِ همهٔ پوزیشن‌ها» — سبدِ تمام‌طلا را «سهام ۱۰۰٪» می‌کرد.
 * · طبقه‌ای که چند ردیف دارد (طلا = فیزیکی + گواهی) فقط رویِ ردیفِ حمل‌کننده
 *   عدد می‌گیرد، پس جمعِ باکت هم دوباره‌شمار نمی‌کند.
 * ردیفِ بی‌داده هیچ‌گاه صفر نمی‌شود؛ باکتِ بی‌داده ⇒ actualPct=null.
 */
export function compareToStandard(rows: DeltaRow[]): BucketComparison[] {
  return FTS_STANDARD_BUCKETS.map((bucket) => {
    const members = rows.filter((r) => bucket.classIds.includes(r.id));
    const known = members.filter((r) => r.currentPct != null);
    const actualPct = known.length > 0 ? r1(known.reduce((s, r) => s + (r.currentPct as number), 0)) : null;
    const targetPct = r1(members.reduce((s, r) => s + (r.targetPct > 0 ? r.targetPct : 0), 0));
    const source: ActualSource =
      known.length === 0 ? null : known.some((r) => r.measure === 'asset_value') ? 'value' : 'basket';
    const deviationPct = actualPct == null ? null : r1(actualPct - targetPct);
    const state: BucketComparison['state'] =
      deviationPct == null
        ? 'nodata'
        : deviationPct > DEVIATION_EPS_PCT
          ? 'overweight'
          : deviationPct < -DEVIATION_EPS_PCT
            ? 'underweight'
            : 'ok';

    return { bucket, targetPct, actualPct, source, deviationPct, state };
  });
}

/** پوشش داده: چند طبقه از ۵ طبقه وزن واقعی دارند */
export function dataCoverage(rows: BucketComparison[]): { covered: number; total: number } {
  return { covered: rows.filter((r) => r.actualPct != null).length, total: rows.length };
}

/**
 * خطای انحراف (Tracking Error) به سبک انحراف معیار روی طبقات دارای داده:
 * TE = sqrt( Σ (w_actual − w_target)² ) — روی طبقات پوشش‌داده‌شده محاسبه می‌شود و
 * پوشش در UI شفاف اعلام می‌گردد (بدون تعمیم کاذب به طبقات بدون داده).
 */
export function trackingError(rows: BucketComparison[]): number | null {
  const covered = rows.filter((r) => r.deviationPct != null);
  if (covered.length === 0) return null;
  const sumSq = covered.reduce((s, r) => s + (r.deviationPct as number) ** 2, 0);
  return Math.round(Math.sqrt(sumSq) * 100) / 100;
}

/** ضریب تبدیل انحراف به نمرهٔ انطباق */
export const ALIGNMENT_TE_FACTOR = 2;

/** نمرهٔ انطباق ۰..۱۰۰ — null یعنی بدون داده */
export function alignmentScore(te: number | null): number | null {
  if (te == null) return null;
  return Math.max(0, Math.min(100, Math.round(100 - ALIGNMENT_TE_FACTOR * te)));
}

export type AlignmentStatus = {
  label: string;
  tone: 'green' | 'yellow' | 'red' | 'gray';
  /** بزرگ‌ترین انحراف — برای توضیح متنی */
  worst: BucketComparison | null;
};

/** وضعیت خلاصهٔ هم‌ترازی: «همگرایی متوسط — کسری شدید در طلا» */
export function alignmentStatus(rows: BucketComparison[], score: number | null): AlignmentStatus {
  const covered = rows.filter((r) => r.deviationPct != null);
  if (covered.length === 0 || score == null) {
    return { label: 'بدون داده — برای محاسبهٔ هم‌ترازی، ارزش دارایی‌ها یا پوزیشن سبد لازم است.', tone: 'gray', worst: null };
  }
  const worst = covered.reduce((m, r) => (Math.abs(r.deviationPct ?? 0) > Math.abs(m.deviationPct ?? 0) ? r : m), covered[0]);
  const kind = (worst.deviationPct ?? 0) > 0 ? 'مازاد' : 'کسری';
  const magnitude = Math.abs(worst.deviationPct ?? 0);
  const severity = magnitude >= 15 ? 'شدید' : magnitude >= 5 ? 'محسوس' : 'جزئی';
  const convergence = score >= 80 ? 'همگرایی بالا' : score >= 55 ? 'همگرایی متوسط' : 'واگرایی';
  const tone: AlignmentStatus['tone'] = score >= 80 ? 'green' : score >= 55 ? 'yellow' : 'red';
  return {
    label: `${convergence} — ${kind} ${severity} در ${worst.bucket.label} (${toFaDigits(magnitude)}٪)`,
    tone,
    worst,
  };
}

export type RebalanceOrder = {
  bucket: StdBucket;
  action: 'buy' | 'sell';
  amountToman: number | null;
  deltaPct: number;
  text: string;
};

/** دستورات ری‌بالانس — خرید کسری و فروش مازاد؛ مبلغ ریالی فقط با ارزش کل معلوم */
export function rebalanceOrders(rows: BucketComparison[], totalValueToman: number): RebalanceOrder[] {
  const total = totalValueToman > 0 ? totalValueToman : null;
  return rows
    .filter((r) => r.deviationPct != null && Math.abs(r.deviationPct) > DEVIATION_EPS_PCT)
    .map((r) => {
      const deltaPct = r.deviationPct as number;
      const amountToman = total != null ? Math.round((Math.abs(deltaPct) / 100) * total) : null;
      return {
        bucket: r.bucket,
        action: deltaPct > 0 ? ('sell' as const) : ('buy' as const),
        amountToman,
        deltaPct: Math.abs(deltaPct),
        text:
          deltaPct > 0
            ? `فروش ${toFaDigits(Math.abs(deltaPct))}٪ از ${r.bucket.label} برای برگشت به وزن هدف`
            : `خرید ${toFaDigits(Math.abs(deltaPct))}٪ در ${r.bucket.label} برای پر کردن کسری`,
      };
    });
}

/** درصد پرشدهٔ سبد واقعی (جمع وزن‌های دارای داده) — مرکز دونات چپ */
export function filledPct(rows: BucketComparison[]): number | null {
  const withData = rows.filter((r) => r.actualPct != null);
  if (withData.length === 0) return null;
  return Math.round(withData.reduce((s, r) => s + (r.actualPct as number), 0) * 10) / 10;
}
