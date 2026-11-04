import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { EpsBars } from '../mini/EpsBars';
import { AxisPanel, faInt } from './AxisPanel';

export function EpsPanel({ card }: { card: FtsCard }) {
  const eps = card.indicators?.['2'];
  const status = cardStatus(card, 'eps');
  const series = eps?.eps_series ?? [];
  const last = series.length ? series[series.length - 1] : null;
  // رأی R50: غیبتِ سابقه «—» است، نه صفرِ ساختگی.
  const years = eps?.years_available == null ? '—/۳' : `${toFaDigits(eps.years_available)}/۳`;
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
        ['شواهد', eps?.evidence ?? '—'],
        ['تلفیقی', eps?.consolidated_used ? 'بله' : '—'],
      ]}
      details={card.details?.['۲']}
    />
  );
}
