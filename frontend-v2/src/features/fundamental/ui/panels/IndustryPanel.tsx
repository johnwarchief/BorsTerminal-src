import type { FtsCard } from '../../api/useFtsCard';
import { regimeFa } from '../../lib/axisMeta';
import { faSectorName } from '../../lib/faOrthography';
import { cardStatus } from '../../lib/cardStatus';
import { PeDots } from '../mini/PeDots';
import { AxisPanel, faFixed, faInt } from './AxisPanel';

export interface SectorPeLike {
  pe?: number | null;
  median?: number | null;
  peers?: number | null;
  sector?: string | null;
}

/** R103: سهم بازارِ کوچک‌تر از ۱٪ با سه رقمِ اعشار تا «۰٫۰٪» نشود (زنده: ۰٫۰۲۵٪). */
function shareFixed(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return Math.abs(value) < 1 ? faFixed(value, 3, '٪') : faFixed(value, 2, '٪');
}

export function IndustryPanel({ card, sectorPe }: { card: FtsCard; sectorPe?: SectorPeLike | null }) {
  const industry = card.indicators?.['5'];
  const status = cardStatus(card, 'industry');
  const regime = industry?.label ?? industry?.regime_label ?? '—';
  const rows: Array<[string, string]> = [
    ['P/E این نماد', faFixed(sectorPe?.pe, 1)],
    ['میانهٔ صنعت', faFixed(sectorPe?.median, 1)],
    ['همتاها', faInt(sectorPe?.peers)],
    ['سهم بازار', shareFixed(industry?.market_share_pct)],
    ['چشم‌انداز', industry?.outlook ?? '—'],
    ['رژیم', regimeFa(industry?.verdict)],
  ];
  // R-V1-6 (B-1/M-1): «چرا» در همین پنل نوشته می‌شود — وتویِ طبقه یا نبودِ تعریفِ نرخ برایِ این طبقه.
  if (card.excluded === true) {
    rows.push(['دلیل', `وتوی طبقه — نماد از غربال حذف شده${card.exclusion_reasons?.length ? ` (${card.exclusion_reasons.join(' · ')})` : ''}.`]);
  } else if (status === 'na') {
    rows.push(['دلیل', 'شاخص ۵ برایِ این طبقه سنجیده نمی‌شود؛ نرخِ محصولِ فروش برایِ هلدینگ/سرمایه‌گذاری و بانک تعریف نشده است.']);
  }
  return (
    <AxisPanel
      testId="panel-industry"
      axis="industry"
      title="نرخ‌گذاری صنعت"
      subtitle={`${faSectorName(industry?.sector ?? card.sector) || '—'} — رژیم ${regime}`}
      status={status}
      value={regime}
      threshold="رژیم"
      chart={<PeDots pe={sectorPe?.pe ?? null} median={sectorPe?.median ?? null} peers={sectorPe?.peers ?? null} />}
      rows={rows}
      details={card.details?.['۵']}
    />
  );
}
