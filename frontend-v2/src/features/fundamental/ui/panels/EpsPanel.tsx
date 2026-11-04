import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import {
  epsChangeText,
  epsChanges,
  epsDeltaText,
  formatEpsTrend,
  lastSeriesValue,
} from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { DeltaBars } from '../mini/DeltaBars';
import { EpsBars } from '../mini/EpsBars';
import { AxisPanel, faInt } from './AxisPanel';

// R88/R103: توکن‌های انگلیسیِ شواهد به واژهٔ فارسی نگاشت می‌شوند؛ ناشناخته عیناً می‌ماند.
const EVIDENCE_FA: Record<string, string> = {
  audited_year_end: 'سال‌پایانِ حسابرسی‌شده',
  annualized_interim_short: 'سال‌سازیِ میاندورهٔ کوتاه',
  annualized_interim: 'سال‌سازیِ میاندوره',
  interim_annualized: 'سال‌سازیِ میاندوره',
  consolidated: 'تلفیقی',
  consolidated_audited: 'تلفیقیِ حسابرسی‌شده',
  consolidated_unaudited: 'تلفیقیِ حسابرسی‌نشده',
  audited: 'حسابرسی‌شده',
};

function evidenceFa(token: string): string {
  return EVIDENCE_FA[token] ?? token;
}

export function EpsPanel({ card }: { card: FtsCard }) {
  const eps = card.indicators?.['2'];
  const status = cardStatus(card, 'eps');
  const series = eps?.eps_series ?? [];
  // R106: همان آخرین مقدارِ متناهیِ سرصفحه، نه آخرین خانهٔ سری (که گاه null است).
  const last = lastSeriesValue(series);
  // R99: مخرجِ «سال‌های موجود» از تنظیمِ گیت می‌آید، نه ۳ سخت‌کد؛ نامعلوم «—».
  const required = eps?.years_required ?? card.thresholds?.v10_eps_years ?? null;
  const years = required == null
    ? '—'
    : eps?.years_available == null
      ? `—/${toFaDigits(required)}`
      : `${toFaDigits(eps.years_available)}/${toFaDigits(required)}`;
  // R82/R88: شواهد می‌تواند رشته یا آرایهٔ رشته باشد؛ آرایه پس از نگاشتِ
  // توکن‌ها با «، » پیوند می‌خورد و رشتهٔ ساده دست‌نخورده می‌ماند.
  const evidence = eps?.evidence;
  const evidenceText = Array.isArray(evidence)
    ? (evidence.length ? evidence.map(evidenceFa).join('، ') : '—')
    : (evidence ?? '—');
  // R101: دلیلِ آشکار — شکافِ دادهٔ EPS یا دلیلِ ثبت‌شده.
  const reason = eps?.data_gap ? 'شکاف دادهٔ EPS' : eps?.reason ?? '';
  const rows: Array<[string, string]> = [
    ['آخرین EPS', last == null ? '—' : faInt(last)],
    ['سال‌های موجود', years],
    ['نیاز گیت', required == null ? '—' : `${toFaDigits(required)} سال متوالی`],
    ['شواهد', evidenceText],
    ['تلفیقی', eps?.consolidated_used ? 'بله' : '—'],
  ];
  if (reason) rows.push(['دلیل', reason]);
  // R-P1-3: رشدِ هر دوره — از پاسخِ بک‌اند اگر هم‌طول باشد، وگرنه از سری؛ دورهٔ اول رشد ندارد.
  const changes = epsChanges(series, eps?.eps_yoy_pct);
  // R-P1-3: سریِ همه‌تهی نمودارِ برچسب‌دار نمی‌سازد؛ وضعیتِ خالیِ صادق می‌آید.
  const hasSeries = last != null;
  // R-P1-3: برچسبِ دوره از period_ends با ارقامِ فارسی؛ نبودش «دوره ۱..».
  const rawPeriods = eps?.period_ends ?? [];
  const labels = series.map((_, index) => {
    const period = rawPeriods[index];
    return period == null || period === '' ? `دوره ${toFaDigits(index + 1)}` : toFaDigits(period);
  });
  return (
    <AxisPanel
      testId="panel-eps"
      axis="eps"
      title="سودآوری ۳ساله"
      subtitle="سابقهٔ EPS و روند سال‌به‌سال؛ «سنجیده‌نشده» از «رد» جدا است"
      status={status}
      value={formatEpsTrend(series)}
      threshold={required == null ? '—' : `${toFaDigits(required)} سال`}
      chart={<EpsBars series={series} status={status} label="سری EPS" />}
      rows={rows}
      details={card.details?.['۲']}
    >
      <div className="flex flex-col gap-1">
        {hasSeries ? (
          <div className="h-[30px]" data-testid="eps-growth-chart">
            <DeltaBars values={changes} labels={labels} />
          </div>
        ) : (
          <p className="text-[9px] text-[var(--fd-text-3)]" data-testid="eps-growth-empty">داده‌ای ثبت نشده</p>
        )}
        <div className="grid grid-cols-1 gap-0.5">
          {series.map((value, index) => {
            const change = changes[index] ?? null;
            const changeTone = change == null
              ? 'text-[var(--fd-text-3)]'
              : change < 0
                ? 'text-[var(--fd-down)]'
                : change > 0
                  ? 'text-[var(--fd-up)]'
                  : 'text-[var(--fd-flat)]';
            const deltaText = index === 0 ? '—' : epsDeltaText(series[index - 1], value);
            const changeText = epsChangeText(change);
            return (
              <div
                key={index}
                data-testid={`eps-period-${index}`}
                role="group"
                aria-label={`${labels[index]}، EPS ${faInt(value)}، تغییر ${index === 0 ? 'بدون دورهٔ قبل' : deltaText}، رشد ${changeText}`}
                className="flex items-center justify-between gap-2 border-b border-[var(--fd-line)] py-0.5 text-[9.5px]"
              >
                <span className="text-[var(--fd-text-3)]">{labels[index]}</span>
                <b className="text-[var(--fd-text)]">{faInt(value)}</b>
                <span className="text-[var(--fd-text-2)]">{deltaText}</span>
                <span className={changeTone}>{changeText}</span>
              </div>
            );
          })}
        </div>
      </div>
    </AxisPanel>
  );
}
