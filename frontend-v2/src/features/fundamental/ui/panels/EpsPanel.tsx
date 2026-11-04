import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { EpsBars } from '../mini/EpsBars';
import { AxisPanel, faInt } from './AxisPanel';

// R88: توکن‌های انگلیسیِ شواهد به واژهٔ فارسی نگاشت می‌شوند؛ ناشناخته عیناً می‌ماند.
const EVIDENCE_FA: Record<string, string> = {
  audited_year_end: 'سال‌پایانِ حسابرسی‌شده',
  annualized_interim_short: 'سال‌سازیِ میاندورهٔ کوتاه',
  interim_annualized: 'سال‌سازیِ میاندوره',
  consolidated: 'تلفیقی',
  audited: 'حسابرسی‌شده',
};

function evidenceFa(token: string): string {
  return EVIDENCE_FA[token] ?? token;
}

export function EpsPanel({ card }: { card: FtsCard }) {
  const eps = card.indicators?.['2'];
  const status = cardStatus(card, 'eps');
  const series = eps?.eps_series ?? [];
  const last = series.length ? series[series.length - 1] : null;
  // رأی R50: غیبتِ سابقه «—» است، نه صفرِ ساختگی.
  const years = eps?.years_available == null ? '—/۳' : `${toFaDigits(eps.years_available)}/۳`;
  // R82/R88: شواهد می‌تواند رشته یا آرایهٔ رشته باشد؛ آرایه پس از نگاشتِ
  // توکن‌ها با «، » پیوند می‌خورد و رشتهٔ ساده دست‌نخورده می‌ماند.
  const evidence = eps?.evidence;
  const evidenceText = Array.isArray(evidence)
    ? (evidence.length ? evidence.map(evidenceFa).join('، ') : '—')
    : (evidence ?? '—');
  return (
    <AxisPanel
      testId="panel-eps"
      axis="eps"
      title="سودآوری ۳ساله"
      subtitle="سابقهٔ EPS و روند سال‌به‌سال؛ «سنجیده‌نشده» از «رد» جدا است"
      status={status}
      value={years}
      threshold="سال"
      chart={<EpsBars series={series} status={status} label="سری EPS" />}
      rows={[
        ['آخرین EPS', last == null ? '—' : faInt(last)],
        ['نیاز گیت', eps?.years_required == null ? '۳ سال متوالی' : `${toFaDigits(eps.years_required)} سال متوالی`],
        ['شواهد', evidenceText],
        ['تلفیقی', eps?.consolidated_used ? 'بله' : '—'],
      ]}
      details={card.details?.['۲']}
    />
  );
}
