import type { FtsCard } from '../../api/useFtsCard';
import { formatAxisValue } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faThreshold } from './AxisPanel';

export function GrowthPanel({ card }: { card: FtsCard }) {
  const monetary = card.indicators?.['1']?.monetary;
  const status = cardStatus(card, 'growth');
  // R91: رشد همان قالبِ ستون جدول را دارد: علامتِ +/− و درصد.
  const pct = formatAxisValue(monetary?.monetary_pct ?? null, 'growth');
  const volume = card.indicators?.['1']?.volume?.applicable === false ? 'N/A' : '—';
  return (
    <AxisPanel
      testId="panel-growth"
      axis="growth"
      title="رشد فروش — ۱الف و ۱ب"
      subtitle="رشد ریالی در برابر کف، و تأیید رشد واقعی/تناژ"
      status={status}
      value={pct}
      threshold={`کف ${faThreshold(monetary?.threshold, '٪')}`}
      chart={<Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={monetary?.threshold ?? null} status={status} label="رشد فروش" />}
      rows={[
        ['۱الف — رشد ریالی', pct],
        ['۱ب — رشد واقعی/تناژ', volume],
        ['دلیل', monetary?.reason ?? '—'],
      ]}
      details={card.details?.['۱']}
    />
  );
}
