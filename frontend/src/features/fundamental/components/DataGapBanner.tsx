// features/fundamental/components/DataGapBanner.tsx -- دلیل و راه نبود داده
// متون خام موتور بک‌اند (fts_engine، annualize و…) هرگز به کاربر نشان
// داده نمی‌شوند — هر شکاف به علتِ کوتاه + راه‌حل ترجمه می‌شود
// (منبع یکتای متون: lib/gapReason تا در کل ویژگی یکدست بماند).
import type { FtsCard } from '../api/useFtsCard';
import { toFaDigits } from '@shared/lib/fmt';
import { standardizeGap } from '../lib/gapReason';
import { EPS_REQUIRED_YEARS, epsFailReason } from '../lib/epsHistory';

type EpsIndicator = NonNullable<FtsCard['indicators']>['2'];

/** بنر علت‌دار نبود داده + تفکیک «ردِ گیت» از «نقص داده»:
 *  وقتی سابقهٔ ۳ سالهٔ EPS کامل است ولی گیت رد شده، نباید بنر بگوید «دادهٔ کدال
 *  ناقص است» — دلیل واقعی شکست (مثلاً سقوط سود به زیان در سال آخر) نشان داده می‌شود. */
export function DataGapBanner({
  gaps,
  eps,
}: {
  gaps: NonNullable<FtsCard['data_gaps']>;
  eps?: EpsIndicator;
}) {
  const list = gaps ?? [];
  const epsYears = Array.isArray(eps?.period_slots) ? eps.period_slots.length : 0;
  const epsRequired = eps?.years_required ?? EPS_REQUIRED_YEARS;
  const epsComplete =
    eps != null &&
    (eps.years_available ?? epsYears) >= epsRequired &&
    eps.data_gap !== true &&
    eps.pass !== true;
  const epsReason = epsComplete
    ? epsFailReason({
        series: eps?.eps_series,
        slots: eps?.period_slots ?? eps?.fiscal_years,
        strictlyRising: eps?.strictly_rising,
        allProfitable: eps?.all_profitable,
      })
    : null;

  /** ردیف‌های شکاف واقعی — وقتی دلیل ردِ شاخص ۲ استخراج شده، آن ردیف از بنر حذف می‌شود */
  const gapItems = list.filter((g) => !(g.axis === '2_eps_trend' && epsReason != null)).map(standardizeGap);

  if (gapItems.length === 0 && epsReason == null) return null;

  return (
    <div className="flex flex-col gap-3">
      {epsReason != null ? (
        <div className="rounded-2xl border border-accent-red/40 bg-accent-red/10 p-4" data-testid="reject-reason-banner">
          <h3 className="mb-2 text-sm font-black text-accent-red">چرا شاخص ۲ رد شد</h3>
          <p className="text-xs text-text-primary">{epsReason}</p>
          <p className="mt-1 text-2xs text-text-secondary">
            سابقهٔ سه‌ساله کامل است؛ علت، خودِ روندِ سود است نه کمبود داده.
          </p>
        </div>
      ) : null}
      {gapItems.length > 0 ? (
        <div className="rounded-2xl border border-accent-yellow/40 bg-accent-yellow/10 p-4" data-testid="data-gap-banner">
          <h3 className="mb-2 text-sm font-black text-accent-yellow">
            دادهٔ کدال برای <span className="num">{toFaDigits(gapItems.length)}</span> شاخص کامل نیست
          </h3>
          <ul className="flex flex-col gap-2">
            {gapItems.map((g, i) => (
              <li key={`${g.layer}-${i}`} className="text-xs text-text-primary" title={`${g.why} — راه‌حل: ${g.fix}`} data-testid="data-gap-item">
                <span className="font-bold">شاخص {g.layer}: </span>
                {g.why} <span className="text-text-secondary">راه‌حل: {g.fix}</span>
                <span aria-hidden className="text-2xs leading-none text-text-muted"> ⓘ</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
