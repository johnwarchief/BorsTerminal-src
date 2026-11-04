import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faFixed, faThreshold } from './AxisPanel';

export function SalesPanel({ card }: { card: FtsCard }) {
  const sales = card.indicators?.['4'];
  const status = cardStatus(card, 'sales');
  const rows: Array<[string, string]> = [
    ['پتانسیل سود', faFixed(sales?.potential_pct, 1, '٪')],
    ['آستانهٔ پتانسیل', faThreshold(sales?.potential_threshold, '٪')],
    ['فروش سالانه', faFixed(sales?.annual_sales_bt, 1)],
    ['ماه‌های سالانه‌سازی', sales?.months_used == null ? '—' : toFaDigits(sales.months_used)],
    ['معافیت', sales?.exempt ? 'معاف' : sales?.available === false ? 'N/A' : '—'],
  ];
  // R101: دلیلِ آشکار برای محورهای بی‌نظر/نامشخص/معاف.
  if (sales?.reason) rows.push(['دلیل', sales.reason]);
  return (
    <AxisPanel
      testId="panel-sales"
      axis="sales"
      title="فروش / ارزش بازار"
      subtitle="نسبت فروش سالانه‌شده و پتانسیل سود؛ مسیر OR"
      status={status}
      value={faFixed(sales?.sales_to_mcap, 2)}
      threshold={`کف ${faFixed(sales?.sales_threshold, 2)}`}
      chart={<Bullet value={sales?.sales_to_mcap ?? null} max={2} threshold={sales?.sales_threshold ?? null} status={status} label="فروش/ارزش" />}
      rows={rows}
      details={card.details?.['۴']}
    />
  );
}
