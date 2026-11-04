import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faFixed, faThreshold } from './AxisPanel';

export function GrowthPanel({ card }: { card: FtsCard }) {
  const monetary = card.indicators?.['1']?.monetary;
  const status = cardStatus(card, 'growth');
  const pct = faFixed(monetary?.monetary_pct, 1, '٪');
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
