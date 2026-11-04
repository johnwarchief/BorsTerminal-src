import { fmtPct } from '@shared/lib/fa';

/** R-P1-3/R-P1-5: میله‌های رشد دوره‌ای EPS — مثبت/منفی با رنگ، برچسبِ دوره زیرِ هر میله. */
export function DeltaBars({ values, labels, height = 30 }: {
  values: Array<number | null>;
  labels: string[];
  height?: number;
}) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  return (
    <div className="flex h-full items-end gap-1" style={{ height }} role="img" aria-label="رشد دوره‌ای EPS">
      {values.map((v, i) => {
        const magnitude = v == null ? 0 : (Math.abs(v) / max) * 48;
        // مقدارِ گم‌شده میلهٔ صفرِ ساختگی و رنگِ جهت نمی‌گیرد.
        const tone = v == null ? 'is-empty' : v < 0 ? 'is-down' : 'is-up';
        return (
          <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end" title={`${labels[i]} — ${v == null ? '—' : fmtPct(v, 1)}`}>
            <div className="flex h-full w-full flex-col justify-center">
              <span className={`fd-delta-bar ${tone}`} style={{ height: `${Math.max(v == null ? 0 : 3, magnitude)}%` }} />
            </div>
            <span className="truncate text-[8px] text-[var(--fd-text-3)]">{labels[i]}</span>
          </div>
        );
      })}
    </div>
  );
}
