import type { FtsCard } from '../../api/useFtsCard';
import { regimeFa } from '../../lib/axisMeta';
import { cardStatus } from '../../lib/cardStatus';
import { PeDots } from '../mini/PeDots';
import { AxisPanel, faFixed, faInt } from './AxisPanel';

export interface SectorPeLike {
  pe?: number | null;
  median?: number | null;
  peers?: number | null;
  sector?: string | null;
}

export function IndustryPanel({ card, sectorPe }: { card: FtsCard; sectorPe?: SectorPeLike | null }) {
  const industry = card.indicators?.['5'];
  const status = cardStatus(card, 'industry');
  const regime = industry?.label ?? industry?.regime_label ?? '—';
  return (
    <AxisPanel
      testId="panel-industry"
      axis="industry"
      title="نرخ‌گذاری صنعت"
      subtitle={`${industry?.sector ?? card.sector ?? '—'} — رژیم ${regime}`}
      status={status}
      value={regime}
      threshold="رژیم"
      chart={<PeDots pe={sectorPe?.pe ?? null} median={sectorPe?.median ?? null} peers={sectorPe?.peers ?? null} />}
      rows={[
        ['P/E این نماد', faFixed(sectorPe?.pe, 1)],
        ['میانهٔ صنعت', faFixed(sectorPe?.median, 1)],
        ['همتاها', faInt(sectorPe?.peers)],
        ['سهم بازار', faFixed(industry?.market_share_pct, 1, '٪')],
        ['چشم‌انداز', industry?.outlook ?? '—'],
        ['رژیم', regimeFa(industry?.verdict)],
      ]}
      details={card.details?.['۵']}
    />
  );
}
