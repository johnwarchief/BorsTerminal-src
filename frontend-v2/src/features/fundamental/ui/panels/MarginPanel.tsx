import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faFixed, faThreshold } from './AxisPanel';

const TIER_FA: Record<string, string> = {
  ideal: 'ایده‌آل',
  ok: 'قبول',
  below: 'زیر کف',
  na: 'بی‌نظر',
};

export function MarginPanel({ card }: { card: FtsCard }) {
  const margin = card.indicators?.['3'];
  const status = cardStatus(card, 'margin');
  const rawTier = margin?.margin_tier;
  const tier = typeof rawTier === 'string' ? TIER_FA[rawTier] ?? rawTier : '—';
  return (
    <AxisPanel
      testId="panel-margin"
      axis="margin"
      title="حاشیهٔ ناخالص"
      subtitle="فاصله تا کف/ایده‌آل؛ باندهای ۲۰/۳۰/۴۰"
      status={status}
      value={faFixed(margin?.margin_pct, 1, '٪')}
      threshold={`کف ${faThreshold(margin?.threshold, '٪')}`}
      chart={<Bullet value={margin?.margin_pct ?? null} max={60} threshold={margin?.threshold ?? null} status={status} label="حاشیهٔ ناخالص" />}
      rows={[
        ['سود ناخالص', faFixed(margin?.gross_profit_bt, 1)],
        ['درآمد', faFixed(margin?.revenue_bt, 1)],
        ['طبقه', tier],
        ['آستانهٔ ایده‌آل', faThreshold(margin?.optimal_threshold, '٪')],
      ]}
      details={card.details?.['۳']}
    />
  );
}
