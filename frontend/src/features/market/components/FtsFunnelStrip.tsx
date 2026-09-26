// features/market/components/FtsFunnelStrip.tsx -- قیفِ پنج‌محوریِ FTS در نوارِ شاخص
// چرا این‌جاست: جزوه، FTS را قیف تعریف می‌کند (پنج محور پیاپی، سپس وتوها)؛ هیچ
// ابزارِ بیرونیِ بازار این ریزش را رویِ کلِ بازار نشان نمی‌دهد. شماره‌ها از
// /api/fundamental/funnel می‌آیند — همان ردیف‌های کش‌شدهٔ جدولِ غربالگری، پس
// این‌جا چیزی دوباره محاسبه نمی‌شود و با ستون‌هایِ جدولِ بنیادی می‌خواند.
import { toFaDigits } from '@shared/lib/fmt';
import { FTS_FUNNEL } from '@shared/lib/ftsLabels';
import { funnelPass, useFtsFunnel } from '../api/useFtsFunnel';

const fa = (n: number): string => toFaDigits(String(n));

export function FtsFunnelStrip() {
  const { data, isError } = useFtsFunnel();
  const tested = typeof data?.tested === 'number' ? data.tested : null;

  if (isError || !data || tested == null || tested <= 0) {
    // نبودِ داده = هیچ؛ جای آن را عددِ ساختگی یا صفر نمی‌گذاریم.
    return null;
  }

  return (
    <div
      data-testid="fts-funnel"
      className="flex min-w-0 flex-1 flex-col gap-1 border-s border-border-c/60 ps-3"
      title="قیف FTS رویِ کلِ بازار: چند نماد از هر محور رد می‌شوند (همان داوریِ جدول بنیادی)"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-3xs font-black text-text-secondary">قیف FTS</span>
        <span className="num text-3xs font-bold text-text-muted">
          {fa(tested)}
          <span className="font-medium"> از </span>
          {fa(typeof data.total === 'number' ? data.total : 0)}
          <span className="font-medium"> نماد سنجیده شد</span>
        </span>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {FTS_FUNNEL.map((ax) => {
          const pass = funnelPass(data, ax.column);
          const pct = pass >= 0 ? Math.max(2, Math.round((pass / tested) * 100)) : 0;
          return (
            <div key={ax.axis} className="flex min-w-0 flex-col gap-0.5" title={`${ax.label} — ${pass < 0 ? 'بدون داده' : `${fa(pass)} نماد`}`}>
              <span className="truncate text-3xs font-bold text-text-muted">{ax.short}</span>
              <span className={`num text-2xs font-black leading-4 ${pass >= 0 ? 'text-text-primary' : 'text-text-muted'}`}>
                {pass >= 0 ? fa(pass) : '—'}
              </span>
              <span className="h-1 w-full overflow-hidden rounded-full bg-border-c/60">
                {pass >= 0 ? <span className="block h-full rounded-full bg-accent-blue" style={{ width: `${pct}%` }} /> : null}
              </span>
            </div>
          );
        })}
      </div>
      <span className="text-3xs font-medium text-text-muted">
        {typeof data.vetoed === 'number' ? `${fa(data.vetoed)} وتو · ` : ''}
        {(data.verdicts?.SUPER_FUNDAMENTAL ?? 0) + (data.verdicts?.PASSED ?? 0) > 0 ? (
          <>
            <span className="num font-black text-accent-green">
              {fa((data.verdicts?.SUPER_FUNDAMENTAL ?? 0) + (data.verdicts?.PASSED ?? 0))}
            </span>
            <span> نمادِ چهار و پنج‌امتیازی</span>
          </>
        ) : null}
      </span>
    </div>
  );
}
