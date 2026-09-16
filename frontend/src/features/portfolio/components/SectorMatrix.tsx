// features/portfolio/components/SectorMatrix.tsx -- ماتریس تخصیص صنایع سهام (سند FTS §۴)
// خودکفا: تصمیم‌های سبد را خودش از /api/selection/portfolio می‌خواند و وزن فعلی هر صنعت را
// با بازهٔ سند مقایسه می‌کند. غیب داده ⇒ «بدون داده»؛ عبور از سقف ⇒ هشدار «نقض تنوع‌بخشی (Overweight)».
import { useMemo } from 'react';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { usePortfolio } from '../api/usePortfolio';
import {
  bandRangeLabel,
  computeSectorAllocation,
  overweightAlerts,
  type SectorRow,
} from '../model/sectorAllocation';

function RowBar({ row }: { row: SectorRow }) {
  const cap = row.band.max > 0 ? row.band.max : 100;
  const pct = Math.min(100, Math.round((row.actualPct / cap) * 100));
  return (
    <div className="relative h-1.5 w-24 overflow-hidden rounded-full bg-bg-card" dir="ltr" aria-hidden>
      <span
        className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${
          row.overweight ? 'bg-accent-red' : 'bg-accent-green/70'
        }`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function SectorMatrix() {
  const portfolio = usePortfolio();
  const decisions = useMemo(() => portfolio.data?.decisions ?? [], [portfolio.data]);
  const alloc = useMemo(() => computeSectorAllocation(decisions), [decisions]);
  const alerts = useMemo(() => overweightAlerts(alloc.rows), [alloc.rows]);

  const state: 'loading' | 'error' | 'empty' | 'ready' = portfolio.isLoading
    ? 'loading'
    : portfolio.isError
      ? 'error'
      : alloc.hasData
        ? 'ready'
        : 'empty';

  return (
    <section className="glass-panel relative overflow-hidden p-4" aria-label="ماتریس تخصیص صنایع سهام (سند FTS)">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-black text-text-primary">تفکیک صنایع سهام (سند FTS)</h3>
          <p className="mt-0.5 text-2xs leading-5 text-text-muted">
            بازه‌ها طبق سند مدیریت سرمایه §۴ برای سبد ۵ تا ۷ نمادی؛ وزن فعلی از تصمیم‌های ثبت‌شدهٔ سبد محاسبه می‌شود.
          </p>
        </div>
        {state === 'ready' ? (
          <Badge tone="blue">مجموع وزن صنایع {toFaDigits(alloc.mappedTotalPct)}٪</Badge>
        ) : state === 'empty' ? (
          <Badge tone="gray">بدون داده</Badge>
        ) : state === 'loading' ? (
          <Badge tone="gray">در حال دریافت…</Badge>
        ) : (
          <Badge tone="red">خطای دریافت سبد</Badge>
        )}
      </div>

      {/* هشدار نقض تنوع‌بخشی */}
      {alerts.length > 0 ? (
        <div
          role="alert"
          className="mb-3 rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2"
        >
          <div className="mb-1 flex items-center gap-2">
            <Badge tone="red">نقض تنوع‌بخشی (Overweight)</Badge>
            <span className="text-2xs font-bold text-accent-red">
              {toFaDigits(alerts.length)} صنعت از سقف سند عبور کرده است
            </span>
          </div>
          <ul className="flex list-inside list-disc flex-col gap-0.5">
            {alerts.map((a) => (
              <li key={a.bandId} className="text-2xs leading-5 text-accent-red">
                {a.reason}
                {a.symbols.length > 0 ? <span className="text-text-secondary"> (نمادها: {a.symbols.join('، ')})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {state === 'error' ? (
        <p className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-2 py-1 text-2xs leading-5 text-accent-red">
          دریافت تصمیم‌های سبد ناموفق بود؛ مقایسه با بازه‌های سند انجام نشد.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="bg-bg-card/70 text-start text-2xs uppercase tracking-wider text-text-secondary">
                <th className="px-3 py-2 font-bold">صنعت</th>
                <th className="px-3 py-2 font-bold">بازهٔ سند</th>
                <th className="px-3 py-2 font-bold">نمونه‌ها</th>
                <th className="px-3 py-2 font-bold">وزن فعلی سبد</th>
                <th className="px-3 py-2 font-bold">پوزیشن‌ها</th>
                <th className="px-3 py-2 font-bold">وضعیت</th>
              </tr>
            </thead>
            <tbody>
              {alloc.rows.map((r) => (
                <tr key={r.band.id} className="border-b border-[var(--hairline)] odd:bg-bg-secondary/40">
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2 font-bold text-text-primary">
                      <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: r.band.color }} aria-hidden />
                      {r.band.label}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">{bandRangeLabel(r.band)}</td>
                  <td className="px-3 py-2 text-text-muted">{r.band.examples.join('، ')}</td>
                  <td className="px-3 py-2">
                    {state === 'ready' ? (
                      <span className="flex items-center gap-2">
                        <span className="num font-bold text-text-primary">{toFaDigits(r.actualPct)}٪</span>
                        <RowBar row={r} />
                      </span>
                    ) : (
                      <span className="text-text-muted">بدون داده</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {state === 'ready' && r.members.length > 0 ? (
                      <span className="flex flex-wrap gap-1">
                        {r.members.map((m) => (
                          <span key={m.symbol} className="rounded-full border border-border-c bg-bg-card px-1.5 py-0.5 text-2xs text-text-secondary">
                            {m.symbol} <span className="num">{toFaDigits(m.weightPct)}٪</span>
                          </span>
                        ))}
                      </span>
                    ) : (
                      <span className="text-text-muted">بدون پوزیشن</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {state !== 'ready' ? (
                      <Badge tone="gray">بدون داده</Badge>
                    ) : r.overweight ? (
                      <Badge tone="red">نقض سقف وزنی (Overweight) · {toFaDigits(r.overByPct)}٪+</Badge>
                    ) : (
                      <Badge tone="green">در محدوده</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {state === 'ready' && alloc.zeroWeightCount > 0 ? (
        <p className="mt-2 text-2xs leading-5 text-text-muted">
          {toFaDigits(alloc.zeroWeightCount)} نماد در سبد بدون وزن ثبت‌شده است؛ در جمع صنعت صفر لحاظ شده‌اند.
        </p>
      ) : null}
    </section>
  );
}
