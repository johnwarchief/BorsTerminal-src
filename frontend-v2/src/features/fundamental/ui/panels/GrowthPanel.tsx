import type { FtsCard } from '../../api/useFtsCard';
import { formatAxisValue, statusFa, type AxisStatus } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faThreshold } from './AxisPanel';

type MetricSignal = {
  applicable?: boolean | null;
  data_gap?: boolean | null;
  pass?: boolean | null;
};

/**
 * R104: ترتیبِ تقدمِ وضعیتِ زیرردیف: «نامعطّل» → بی‌نظر، شکافِ داده → نامشخص،
 * سپس حکمِ pass؛ غیبتِ حکم نامشخص. شکافِ داده هرگز «رد» دیده نمی‌شود.
 */
function metricStatus(signal: MetricSignal | null | undefined): AxisStatus {
  if (signal?.applicable === false) return 'na';
  if (signal?.data_gap === true) return 'unknown';
  if (signal?.pass === true) return 'pass';
  if (signal?.pass === false) return 'fail';
  return 'unknown';
}

function volumeValue(card: FtsCard): string {
  const volume = card.indicators?.['1']?.volume;
  if (volume?.applicable === false) return 'N/A';
  const real = volume?.real_pct ?? volume?.volume_pct ?? null;
  return formatAxisValue(real, 'growth');
}

export function GrowthPanel({ card }: { card: FtsCard }) {
  const monetary = card.indicators?.['1']?.monetary;
  const volume = card.indicators?.['1']?.volume;
  const status = cardStatus(card, 'growth');
  // R91: رشد همان قالبِ ستون جدول را دارد: علامتِ +/− و درصد.
  const pct = formatAxisValue(monetary?.monetary_pct ?? null, 'growth');
  // R97: آستانهٔ نمایش همان گیتِ S4b است (target_threshold)، وگرنه threshold.
  const threshold = monetary?.target_threshold ?? monetary?.threshold ?? null;
  // R101: دلیلِ آشکار — دلیلِ ۱الف، وگرنه دلیلِ ۱ب، وگرنه یادداشتِ ۱ب.
  const reason = monetary?.reason || volume?.reason || volume?.note || '';
  // R104: شکافِ دادهٔ ۱الف هم ارزشِ ریالی را «نامشخص» می‌کند، نه ردیفِ بی‌حکم.
  const monetaryGap = monetary?.data_gap === true;
  const rows: Array<[string, string]> = [
    ['۱الف — رشد ریالی', monetaryGap ? `${pct} · ${statusFa(metricStatus(monetary))}` : pct],
    ['۱ب — رشد واقعی/تناژ', `${volumeValue(card)} · ${statusFa(metricStatus(volume))}`],
  ];
  if (reason) rows.push(['دلیل', reason]);
  return (
    <AxisPanel
      testId="panel-growth"
      axis="growth"
      title="رشد فروش — ۱الف و ۱ب"
      subtitle="رشد ریالی در برابر کف، و تأیید رشد واقعی/تناژ"
      status={status}
      value={pct}
      threshold={`کف ${faThreshold(threshold, '٪')}`}
      chart={<Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={threshold} status={status} label="رشد فروش" />}
      rows={rows}
      details={card.details?.['۱']}
    />
  );
}
