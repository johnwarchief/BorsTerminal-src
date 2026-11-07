import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { formatAxisValue, potentialPath, potentialStatusOf, type PotentialPath } from '../../lib/axisMeta';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faFixed, faThreshold } from './AxisPanel';

export function SalesPanel({ card }: { card: FtsCard }) {
  const sales = card.indicators?.['4'];
  // R-P0-1: وضعیتِ هدر ترکیبی (مسیر OR) است؛ نمودار و تیتر فقط زیرگیتِ پتانسیل را
  // نشان می‌دهند تا نمودارِ قرمزِ پتانسیل با قبولِ ترکیبی از مسیر فروش/ارزش هم‌زیستی کند.
  const status = cardStatus(card, 'sales');
  const potentialStatus = potentialStatusOf(
    { profit_potential_pct: sales?.potential_pct ?? null },
    { profit_potential_min: sales?.potential_threshold ?? null },
  );
  // مسیر از پرچم‌های زیرگیتِ کارت می‌آید، وگرنه از همان مقادیر/آستانه‌های نشان.
  const pathByValue = potentialPath(
    { profit_potential_pct: sales?.potential_pct ?? null, sales_to_mcap: sales?.sales_to_mcap ?? null },
    { profit_potential_min: sales?.potential_threshold ?? null, v10_sales_to_mcap_min: sales?.sales_threshold ?? null },
  );
  // R-P0-4: ردیفِ مسیر فقط با قبولیِ ترکیبیِ محور معنا دارد؛ وگرنه «—».
  const path: PotentialPath = status !== 'pass'
    ? null
    : card.passes?.['4b_profit_potential']
      ? 'potential'
      : card.passes?.['4a_sales_to_mcap']
        ? 'sales'
        : pathByValue;
  const pathLabel = path === 'potential' ? '۴ب — پتانسیل سود' : path === 'sales' ? '۴الف — فروش/ارزش' : '—';
  // کفِ فروش/ارزش نسبت است؛ دو رقم اعشار (۰٫۳۳) نه یک رقم (۰٫۳).
  const salesFloor = sales?.sales_threshold == null ? '—' : faFixed(sales.sales_threshold, 2);
  const rows: Array<[string, string]> = [
    ['فروش/ارزش (شاهد)', faFixed(sales?.sales_to_mcap, 2)],
    ['آستانهٔ فروش/ارزش', faFixed(sales?.sales_threshold, 2)],
    ['فروش سالانه', faFixed(sales?.annual_sales_bt, 1)],
    ['ماه‌های سالانه‌سازی', sales?.months_used == null ? '—' : toFaDigits(sales.months_used)],
    ['آستانهٔ پتانسیل', faThreshold(sales?.potential_threshold, '٪')],
    ['مسیر قبولی', pathLabel],
    ['معافیت', sales?.exempt ? 'معاف' : sales?.available === false ? 'N/A' : '—'],
  ];
  // R101: دلیلِ آشکار برای محورهای بی‌نظر/نامشخص/معاف.
  if (sales?.reason) rows.push(['دلیل', sales.reason]);
  return (
    <AxisPanel
      testId="panel-sales"
      axis="sales"
      title="پتانسیل سود تا آخر سال"
      subtitle={`درصد نهایی پتانسیل سود؛ مسیر OR: فروش/ارزش ≥ ${salesFloor} یا پتانسیل ≥ آستانه`}
      status={status}
      value={formatAxisValue(sales?.potential_pct ?? null, 'sales')}
      threshold={`کف ${faThreshold(sales?.potential_threshold, '٪')}`}
      chart={<Bullet value={sales?.potential_pct ?? null} max={100} threshold={sales?.potential_threshold ?? null} status={potentialStatus} label="پتانسیل سود" />}
      rows={rows}
      details={card.details?.['۴']}
    />
  );
}
