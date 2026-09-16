// features/market/components/SnapshotGauge.tsx -- حالت «نمایشگر لحظه‌ای» (تک‌اسنپ‌شات)
// وقتی تایم‌لاین خطی کمتر از ۲ نقطه دارد، به‌جای کادر خالی این دو نمایشگر لحظه‌ای
// رندر می‌شوند: نوار پیشرفت دوتایی صف خرید/فروش + باکس مقایسهٔ نمادهای مثبت/منفی.
// نبود عدد ⇒ «بدون داده» صادقانه (بدون mock).
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

const MISSING = <span className="text-2xs text-text-muted">بدون داده</span>;

function mt(v: number | null | undefined): string {
  return v == null ? '—' : fmtInt(v);
}

/** نوار پیشرفت دوتاییِ ارزش صف خرید/فروش با اعداد خوانا (میلیارد تومان) */
export function OrderBookGauge({ bq, sq }: { bq: number | null; sq: number | null }) {
  if (bq == null && sq == null) {
    return (
      <div
        data-testid="orderbook-gauge-empty"
        className="flex h-20 items-center justify-center rounded-lg border border-dashed border-border-c"
      >
        {MISSING}
      </div>
    );
  }
  const buy = bq ?? 0;
  const sell = sq ?? 0;
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 0;

  return (
    <div data-testid="orderbook-gauge" className="flex flex-col gap-2">
      <div
        className="flex h-3 w-full overflow-hidden rounded-full border border-border-c"
        title={`سهم خرید ${toFaDigits(buyPct.toFixed(0))}٪ از کل صف‌ها`}
      >
        <span className="h-full bg-accent-green" style={{ width: `${buyPct}%` }} />
        <span className="h-full flex-1 bg-accent-red/80" />
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="num font-bold text-accent-green">خرید {mt(bq)} ب.ت</span>
        <span className="num text-2xs text-text-muted">سهم خرید {toFaDigits(buyPct.toFixed(0))}٪</span>
        <span className="num font-bold text-accent-red">فروش {mt(sq)} ب.ت</span>
      </div>
    </div>
  );
}

/** باکس مقایسه‌ای مینیمالِ نمادهای مثبت/منفی */
export function BreadthGauge({ pos, neg }: { pos: number | null; neg: number | null }) {
  if (pos == null && neg == null) {
    return (
      <div
        data-testid="breadth-gauge-empty"
        className="flex h-20 items-center justify-center rounded-lg border border-dashed border-border-c"
      >
        {MISSING}
      </div>
    );
  }
  const p = pos ?? 0;
  const n = neg ?? 0;
  const total = p + n;
  const posPct = total > 0 ? (p / total) * 100 : 0;

  return (
    <div
      data-testid="breadth-gauge"
      className="flex h-20 items-center gap-3 rounded-lg border border-border-c bg-bg-card/40 px-3"
    >
      <div className="flex flex-col">
        <span className="num text-lg font-black text-accent-green">{mt(pos)}</span>
        <span className="text-2xs text-text-muted">نمادهای مثبت</span>
      </div>
      <div className="h-8 w-px bg-border-c" />
      <div className="flex flex-col">
        <span className="num text-lg font-black text-accent-red">{mt(neg)}</span>
        <span className="text-2xs text-text-muted">نمادهای منفی</span>
      </div>
      <span className="num ms-auto text-2xs text-text-muted">سهم مثبت {toFaDigits(posPct.toFixed(0))}٪</span>
    </div>
  );
}
