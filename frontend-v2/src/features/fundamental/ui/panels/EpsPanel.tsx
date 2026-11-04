import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { formatEpsTrend, lastSeriesValue } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
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
    />
  );
}
