import { faNum } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { formatAxisValue, statusFa, type AxisStatus } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { Bullet } from '../mini/Bullet';
import { HistoryBars } from '../mini/HistoryBars';
import { AxisPanel, faThreshold } from './AxisPanel';

type MetricSignal = {
  applicable?: boolean | null;
  data_gap?: boolean | null;
  pass?: boolean | null;
};

/**
 * R104: ترتیبِ تقدمِ وضعیتِ زیرردیف: «نامعطّل» به بی‌نظر، شکافِ داده به نامشخص،
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
  // R-P1-1: نمودار/وضعیت روی کفِ threshold می‌ایستند؛ target_threshold فقط برچسبِ هدف است.
  const floor = monetary?.threshold ?? null;
  const target = monetary?.target_threshold ?? null;
  const thresholdText = `کف ${faThreshold(floor, '٪')}${target == null || target === floor ? '' : ` · هدف ${faThreshold(target, '٪')}`}`;
  const volumeStatus = metricStatus(volume);
  // R101: دلیلِ آشکار — دلیلِ ۱الف، وگرنه دلیلِ ۱ب، وگرنه یادداشتِ ۱ب.
  const reason = monetary?.reason || volume?.reason || volume?.note || '';
  // R104: شکافِ دادهٔ ۱الف هم ارزشِ ریالی را «نامشخص» می‌کند، نه ردیفِ بی‌حکم.
  const monetaryGap = monetary?.data_gap === true;
  // R-P1-2: فروشِ دورهٔ جاری/قبل در میلیارد تومان؛ نبودِ مقدار «—».
  const money = (value: number | null | undefined) => value == null ? '—' : `${faNum(value, 0)} میلیارد تومان`;
  const rows: Array<[string, string]> = [
    ['۱الف — رشد ریالی', monetaryGap ? `${pct} · ${statusFa(metricStatus(monetary))}` : pct],
    ['۱ب — رشد واقعی/تناژ', `${volumeValue(card)} · ${statusFa(volumeStatus)}`],
    ['فروش دورهٔ جاری', money(monetary?.ytd_now_bt)],
    ['فروش دورهٔ قبل', money(monetary?.ytd_prev_bt)],
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
      threshold={thresholdText}
      chart={<Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={floor} status={status} label="رشد فروش" />}
      rows={rows}
      details={card.details?.['۱']}
    >
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1">
          <span className="fd-meta text-[var(--fd-text-3)]">۱ب — رشد واقعی</span>
          <div className="h-[24px]">
            <Bullet
              value={volume?.applicable === false ? null : volume?.real_pct ?? null}
              max={100}
              threshold={volume?.threshold ?? null}
              status={volumeStatus}
              label="رشد واقعی ۱ب"
            />
          </div>
        </div>
        <div data-testid="growth-sales-pair" className="flex flex-col gap-1">
          <span className="fd-meta text-[var(--fd-text-3)]">فروش جاری / دورهٔ قبل</span>
          <div className="h-[40px]">
            {/* R-P1-8: جفتِ فروش شاهد است، نه گیت؛ تُنِ خنثی و برچسبِ خودش. */}
            <HistoryBars
              values={[monetary?.ytd_prev_bt ?? null, monetary?.ytd_now_bt ?? null]}
              labels={['دوره قبل', 'دوره جاری']}
              status="evidence"
              label="فروش دورهٔ جاری و قبل"
            />
          </div>
        </div>
      </div>
    </AxisPanel>
  );
}
