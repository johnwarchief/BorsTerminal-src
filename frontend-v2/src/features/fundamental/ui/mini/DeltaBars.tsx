import { fmtPct } from '@shared/lib/fa';

/** R-P1-3/R-P1-5: میله‌های رشد دوره‌ای EPS — مثبت/منفی با رنگ، برچسبِ دوره زیرِ هر میله. */
export function DeltaBars({ values, labels }: {
  values: Array<number | null>;
  labels: string[];
}) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  // R-P1-13 (Minor 3): `role="img"` presentational است و title هر میله اعلام نمی‌شود؛
  // عددِ دقیق در نامِ ظرف می‌آید و پیشوندِ «رشد دوره‌ای EPS» حفظ می‌شود.
  const figure = (v: number | null) => (v == null ? '—' : fmtPct(v, 1));
  const ariaLabel = `رشد دوره‌ای EPS — ${values.map((v, i) => `${labels[i] ? `${labels[i]}: ` : ''}${figure(v)}`).join('، ')}`;
  return (
    <div className="flex h-full items-end gap-1" role="img" aria-label={ariaLabel}>
      {values.map((v, i) => {
        // R-P1-12: میله‌ها ارتفاعِ کاملِ ناحیه را پر می‌کنند؛ مقدارِ کوچکِ غیرصفر حداقل ۱۰٪ می‌گیرد.
        const barHeight = v == null || v === 0 ? 0 : Math.max(10, (Math.abs(v) / max) * 100);
        // مقدارِ گم‌شده میلهٔ صفرِ ساختگی و رنگِ جهت نمی‌گیرد؛ صفرِ واقعی «بی‌تغییر» است.
        const tone = v == null ? 'is-empty' : v < 0 ? 'is-down' : v > 0 ? 'is-up' : 'is-flat';
        return (
          <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center gap-1" title={`${labels[i]} — ${figure(v)}`}>
            {/* R93: ناحیهٔ میله ارتفاع قطعی می‌گیرد تا درصدِ ارتفاع حل شود. */}
            <span className="flex min-h-0 w-full flex-1 items-end">
              <span className={`fd-delta-bar ${tone} w-full rounded-t-sm`} style={{ height: `${barHeight}%` }} />
            </span>
            <span className="w-full truncate text-center fd-meta text-[var(--fd-text-3)]">{labels[i]}</span>
          </div>
        );
      })}
    </div>
  );
}
