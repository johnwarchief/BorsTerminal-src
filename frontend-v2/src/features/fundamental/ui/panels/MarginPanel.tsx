import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faFixed, faThreshold } from './AxisPanel';

// R89/R103: طبقهٔ حاشیه از توکن‌های واقعیِ پاسخ به فارسی نگاشت می‌شود؛
// توکنِ ناشناخته عیناً می‌ماند (نه «—» و نه واژهٔ ساختگی).
const TIER_FA: Record<string, string> = {
  good: 'خوب',
  standard: 'استاندارد',
  floor: 'کف',
  above_floor: 'بالای کف',
  below_floor: 'زیر کف',
  acceptable: 'قابل قبول',
  ideal: 'ایده‌آل',
  // سازگاری با پاسخ‌های قدیمی‌ترِ همین فیلد.
  below: 'زیر کف',
  ok: 'قبول',
  na: 'بی‌نظر',
};

export function MarginPanel({ card }: { card: FtsCard }) {
  const margin = card.indicators?.['3'];
  const status = cardStatus(card, 'margin');
  const rawTier = margin?.margin_tier;
  const tier = typeof rawTier === 'string' ? TIER_FA[rawTier] ?? rawTier : '—';
  const rows: Array<[string, string]> = [
    ['سود ناخالص', faFixed(margin?.gross_profit_bt, 1)],
    ['درآمد', faFixed(margin?.revenue_bt, 1)],
    ['طبقه', tier],
    ['آستانهٔ ایده‌آل', faThreshold(margin?.optimal_threshold, '٪')],
  ];
  // R101: دلیلِ آشکار برای محورهای بی‌نظر/نامشخص.
  if (margin?.reason) rows.push(['دلیل', margin.reason]);
  return (
    <AxisPanel
      testId="panel-margin"
      axis="margin"
      title="حاشیه سود ناخالص"
      subtitle="سود ناخالص ÷ درآمد عملیاتی × ۱۰۰؛ کف ۲۰٪ · استاندارد ۳۰٪"
      status={status}
      value={faFixed(margin?.margin_pct, 1, '٪')}
      threshold={`کف ${faThreshold(margin?.threshold, '٪')}`}
      chart={<Bullet value={margin?.margin_pct ?? null} max={60} threshold={margin?.threshold ?? null} status={status} label="حاشیه سود ناخالص" />}
      rows={rows}
      details={card.details?.['۳']}
    />
  );
}
