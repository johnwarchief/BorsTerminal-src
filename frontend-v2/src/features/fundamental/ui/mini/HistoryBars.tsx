import { toFaDigits } from '@shared/lib/fa';
import { statusFa, type AxisStatus } from '../../lib/axisMeta';

export function HistoryBars({ values, labels, status }: { values: Array<number | null>; labels: string[]; status: AxisStatus }) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  return (
    <div className="flex h-full items-end gap-1" role="img" aria-label={`تاریخچهٔ گزارش‌ها — ${statusFa(status)}`}>
      {values.map((v, i) => (
        <div key={i} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1" title={`${labels[i]} — ${v == null ? '—' : toFaDigits(String(v))}`}>
          <span className={`fd-history-bar is-${status} w-full rounded-t-sm`} style={{ height: `${Math.max(2, (Math.abs(v ?? 0) / max) * 100)}%` }} />
          <span className="truncate text-[9px] text-[var(--fd-text-3)]">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}
