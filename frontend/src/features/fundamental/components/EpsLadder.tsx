// features/fundamental/components/EpsLadder.tsx -- نردبان EPS با حفظ دوره ناقص
// دوره‌های میاندوره‌ای (۳ ماهه و…) با برچسب «میاندوره» و رنگ متمایز از
// سود سالانهٔ کامل ۱۲ماهه جدا می‌شوند تا افت‌های غیرواقعی (مقایسهٔ
// ۳ ماهه با ۱۲ ماهه) به چشم نیاید.
// سابقهٔ ناقصِ ≥۲ ساله: همان سال‌های موجود رندر می‌شود + برچسب نارنجیِ
// «مردود در شاخص ۲ — سابقهٔ ناقص» تا داده حیف نشود ولی ردِ گیت روشن بماند.
// <۲ سال: برچسب علت‌دار («سابقهٔ EPS کمتر از ۲ سال»/«صورت مالی سالانه در کدال نیست»).
import { toFaDigits } from '@shared/lib/fmt';
import { GapHint, epsGapReason } from './GapHint';
import {
  EPS_PARTIAL_TESTID,
  EPS_REQUIRED_YEARS,
  epsChangeText,
  epsChanges,
  epsGapLabel,
  epsHistory,
  epsRealYears,
} from '../lib/epsHistory';

export type InterimInfo = {
  available: boolean;
  periodEnd: string | null;
  months: number | null;
  eps: number | null;
};

export function EpsLadder({
  slots,
  series,
  partial,
  interim,
  requiredYears = 3,
}: {
  slots: string[];
  series: (number | null)[];
  partial: boolean;
  interim?: InterimInfo;
  /** تعداد سالِ لازم برای گیت شاخص ۲ — برای برچسبِ «X از Y سال» */
  requiredYears?: number;
}) {
  if (slots.length === 0 && series.length === 0 && !interim?.available) return null;
  const n = Math.max(slots.length, series.length);
  const cells = Array.from({ length: n }, (_, i) => ({
    slot: slots[i] ?? '',
    value: series[i] ?? null,
  }));
  const realYears = epsRealYears(series);
  /** همان منطق و برچسب جدولِ غربالگری (lib/epsHistory):
   *  ≥۲ سالِ واقعی ولی سابقهٔ ناقص ⇒ داده نمایش + برچسب مردودِ ناقص */
  const hist = epsHistory(series, requiredYears ?? EPS_REQUIRED_YEARS);
  /** درصد رشد هر سال نسبت به سالِ قبل (#101) — همان منبعِ جدول و کارت */
  const changes = epsChanges(series);
  const partialRejected = partial && hist.state === 'partial';
  const gapReason = epsGapReason({ available: realYears, required: hist.requiredYears, interimAvailable: interim?.available ?? false });
  return (
    <div className="glass-panel panel-in p-4" data-testid="eps-ladder">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-black text-text-primary">نردبان EPS</h3>
        {partialRejected ? (
          <span
            data-testid={EPS_PARTIAL_TESTID}
            title={gapReason}
            className="rounded-full border border-accent-susp/40 bg-accent-susp-bg px-2.5 py-0.5 text-xs font-bold text-accent-susp"
          >
            {hist.label} ⓘ
          </span>
        ) : partial ? (
          <GapHint reason={gapReason}>
            <span className="text-xs font-bold text-accent-red">{epsGapLabel(realYears)}</span>
          </GapHint>
        ) : null}
      </div>
      <div className="flex gap-2 overflow-x-auto">
        {cells.map((c, i) => (
          <div
            key={i}
            className={`min-w-20 flex-1 rounded-xl border p-2 text-center ${
              // قرمز یعنی «زیان»، نه «نبودِ داده». سالِ بدون EPS خنثی و کم‌رنگ
              // می‌ماند و شکافش را بجِ بالای همان پانل می‌گوید؛ اگر روزی
              // EPS منفی شد، همان قرمزِ واقعی را می‌گیرد.
              c.value != null && c.value < 0
                ? 'border-accent-red/40 bg-accent-red/10'
                : 'border-border-c bg-bg-primary'
            }`}
          >
            <div className="text-2xs text-text-muted">{c.slot || '-'}</div>
            <div
              className={`text-sm font-black ${
                c.value == null
                  ? 'text-text-muted'
                  : c.value < 0
                    ? 'text-accent-red'
                    : 'text-text-primary'
              }`}
            >
              {c.value == null ? '-' : toFaDigits(c.value)}
            </div>
            {/* #101 — درصد رشد همین سال نسبت به سالِ قبل. نبودِ درصد (سالِ
                نخست، سالِ غایب، مبنای صفر/زیان) با «—» و بی‌هیچ رنگِ
                صعودی/نزولی نشان داده می‌شود؛ ۰٪ جعلی ممنوع. */}
            <div
              className="text-2xs"
              data-testid={`eps-cell-change-${i}`}
              title={
                changes[i] != null
                  ? 'رشد سود هر سهم نسبت به سال مالی قبل'
                  : i === 0
                    ? 'نخستین دورهٔ سری — مقایسه‌ای وجود ندارد'
                    : 'دادهٔ کافی برای درصد رشد نیست'
              }
            >
              {changes[i] != null ? (
                <span
                  className={`num font-black ${
                    changes[i]! > 0 ? 'text-accent-green' : changes[i]! < 0 ? 'text-accent-red' : 'text-text-secondary'
                  }`}
                >
                  {epsChangeText(changes[i])}
                </span>
              ) : (
                <span className="text-text-muted">—</span>
              )}
            </div>
            <div className="text-2xs text-text-muted">سال مالی کامل</div>
          </div>
        ))}
        {interim?.available && interim.eps != null ? (
          <div className="min-w-20 flex-1 rounded-xl border border-accent-blue/40 bg-accent-blue/10 p-2 text-center" data-testid="eps-interim-cell">
            <div className="text-2xs text-text-muted">
              میاندوره {interim.months != null ? `${toFaDigits(interim.months)} ماهه` : ''}
            </div>
            <div className="num text-sm font-black text-accent-blue">{toFaDigits(interim.eps)}</div>
            <div className="text-2xs text-text-muted">جزئی — با ۱۲ماهه مقایسه نشود</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
