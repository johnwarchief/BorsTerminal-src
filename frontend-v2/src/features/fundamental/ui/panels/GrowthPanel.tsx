import type { FtsCard } from '../../api/useFtsCard';
import { formatAxisValue, statusFa, type AxisStatus } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { AxisPanel, faThreshold } from './AxisPanel';

/** وضعیتِ ۱ب از pass خودش؛ «نامعطّل» بی‌نظر است و غیبتِ حکم نامشخص. */
function volumeStatus(card: FtsCard): AxisStatus {
  const volume = card.indicators?.['1']?.volume;
  if (volume?.applicable === false) return 'na';
  if (volume?.pass === true) return 'pass';
  if (volume?.pass === false) return 'fail';
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
  // R101: دلیلِ آشکار — دلیلِ ۱الف، وگرنه یادداشتِ ۱ب.
  const reason = monetary?.reason || volume?.note || '';
  const rows: Array<[string, string]> = [
    ['۱الف — رشد ریالی', pct],
    ['۱ب — رشد واقعی/تناژ', `${volumeValue(card)} · ${statusFa(volumeStatus(card))}`],
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
