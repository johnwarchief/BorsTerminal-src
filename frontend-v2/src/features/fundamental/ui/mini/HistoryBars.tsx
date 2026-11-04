import { toFaDigits } from '@shared/lib/fa';
import { statusFa, type AxisStatus } from '../../lib/axisMeta';

export function HistoryBars({ values, labels, status }: { values: Array<number | null>; labels: string[]; status: AxisStatus }) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  return (
    <div className="flex h-full gap-1" role="img" aria-label={`تاریخچهٔ گزارش‌ها — ${statusFa(status)}`}>
      {values.map((v, i) => (
        <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center gap-1" title={`${labels[i]} — ${v == null ? '—' : toFaDigits(String(v))}`}>
          {/* R93: ناحیهٔ میله ارتفاع قطعی می‌گیرد تا ارتفاعِ درصدیِ میله حل شود
              و میله‌ها در ستونِ auto-height ناپدید نشوند. */}
          <span className="flex min-h-0 w-full flex-1 items-end">
            <span className={`fd-history-bar is-${status} w-full rounded-t-sm`} style={{ height: `${Math.max(2, (Math.abs(v ?? 0) / max) * 100)}%` }} />
          </span>
          <span className="w-full truncate text-center text-[9px] text-[var(--fd-text-3)]">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}
