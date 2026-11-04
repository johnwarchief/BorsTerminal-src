import { toFaDigits } from '@shared/lib/fa';
import { statusFa, type AxisStatus } from '../../lib/axisMeta';

/** R-P1-8: «شاهد» تُنِ خنثی است و هرگز «قبول/رد» اعلام نمی‌کند. */
export type HistoryBarTone = AxisStatus | 'evidence';

export function HistoryBars({ values, labels, status, label }: {
  values: Array<number | null>;
  labels: string[];
  status: HistoryBarTone;
  label?: string;
}) {
  // R-P1-8: نبودِ هر دو مقدار → وضعیتِ خالیِ صادق، نه میله‌های حداقلی.
  if (!values.some((value) => value != null)) {
    return (
      <p className="flex h-full items-center justify-center text-[9px] text-[var(--fd-text-3)]">
        {label ? `${label} — داده‌ای ثبت نشده` : 'داده‌ای برای نمایش ثبت نشده'}
      </p>
    );
  }
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  const ariaLabel = status === 'evidence'
    ? label ?? 'نمودار شاهد'
    : label ? `${label} — ${statusFa(status)}` : `تاریخچهٔ گزارش‌ها — ${statusFa(status)}`;
  return (
    <div className="flex h-full gap-1" role="img" aria-label={ariaLabel}>
      {values.map((v, i) => (
        <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center gap-1" title={`${labels[i]} — ${v == null ? '—' : toFaDigits(String(v))}`}>
          {/* R93: ناحیهٔ میله ارتفاع قطعی می‌گیرد تا ارتفاعِ درصدیِ میله حل شود
              و میله‌ها در ستونِ auto-height ناپدید نشوند.
              R-P1-12: کفِ مقدارِ غیرصفر از ۲٪ به ۸٪ رسید تا مقدارِ واقعیِ کوچک به شکلِ
              خطِ باریک دیده نشود؛ تُنِ خنثیِ «شاهد» و حالتِ خالی دست‌نخورده‌اند. */}
          <span className="flex min-h-0 w-full flex-1 items-end">
            <span className={`fd-history-bar is-${status} w-full rounded-t-sm`} style={{ height: `${Math.max(8, (Math.abs(v ?? 0) / max) * 100)}%` }} />
          </span>
          <span className="w-full truncate text-center text-[9px] text-[var(--fd-text-3)]">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}
