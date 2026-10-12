// features/fundamental/components/FtsCardDossier.tsx — پنج کارت بنیادی برایِ یک نماد
//
// چرا این فایل هست: پروندۀ نماد درِ «دیدهبان» و درِ «برآیند» هم باید همان پنج
// کارت را با همان داوری‌ها نشان دهد. کارت و مسیرِ داده (`/api/fundamental/{symbol}`)
// از قبل اند — این فقط همان ترکیبِ `FundamentalPage` را درِ یک پنلِ قابل‌استفاده
// دوباره می‌گذارد؛ موتورِ دوم یا شمارشِ دوم ساخته نمی‌شود.
//
// سه حالتِ جدا و صادق: در حالِ خواندن / خطا / بی‌داده. هیچ مقداری از صفر یا از
// «قبولی ضمنی» پر نمی‌شود.
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { statementAgeDays } from '@shared/lib/jalaali';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { useFtsCard } from '../api/useFtsCard';
import { useQuarters } from '../api/useQuarters';
import { deCumulateQuarters } from '../lib/fundMath';
import { isFinancialOrHolding, isPhysicalGrowthApplicable } from '../lib/assetScope';
import { cardAuditEvidence } from '../lib/auditEvidence';
import { FtsCard } from './FtsCard';
import { DataGapBanner } from './DataGapBanner';

export function FtsCardDossier({ symbol, className = '' }: { symbol: string; className?: string }) {
  const card = useFtsCard(symbol);
  const quarters = useQuarters(symbol);
  const [drillKey, setDrillKey] = useState<null | string>(null);

  const qRows = useMemo(() => quarters.data?.quarters ?? [], [quarters.data]);
  const fiscal = useMemo(() => deCumulateQuarters(qRows), [qRows]);
  const age = useMemo(
    () => statementAgeDays(qRows[0]?.period_end ?? card.data?.history?.[0]?.period_end ?? null),
    [qRows, card.data],
  );
  const rawSector = card.data?.sector ?? '';
  // نامِ شرکت درِ پاسخِ بنیادی نیست؛ از همان فیدِ مشترکِ تابلو خوانده می‌شود
  // (بی‌درخواستِ دوم) تا سطرِ سرِ پنل با بقیۀ صفحه یکی باشد.
  const norm = normalizeFa(symbol);
  const name = useMarketFeedShared((f) => {
    const hit = (f.data ?? []).find((r) => normalizeFa(String(r.symbol ?? '')) === norm);
    return hit ? String(hit.name ?? '') : '';
  }, 60_000).data ?? '';
  const physicalApplicable = useMemo(() => {
    if (isFinancialOrHolding({ name, sector_name: rawSector })) return false;
    const prof = card.data?.profile;
    if (prof?.volume_applicable != null) return prof.volume_applicable;
    return isPhysicalGrowthApplicable({ name, sector_name: rawSector });
  }, [card.data, name, rawSector]);
  const audit = useMemo(() => (card.data ? cardAuditEvidence(card.data) : null), [card.data]);

  if (!symbol) {
    return <p className={`text-2xs text-text-muted ${className}`}>نمادی انتخاب نشده است.</p>;
  }
  if (card.isPending) {
    return (
      <p className={`text-2xs text-text-muted ${className}`} role="status" data-testid={`fts-dossier-loading-${symbol}`}>
        کارت‌های بنیادیِ {symbol} در حالِ خواندن…
      </p>
    );
  }
  if (card.isError) {
    return (
      <p className={`text-2xs text-accent-red ${className}`} data-testid={`fts-dossier-error-${symbol}`}>
        کارت‌های بنیادیِ {symbol} نرسید — این با «بی‌داده» یکی نیست.
      </p>
    );
  }
  if (!card.data) {
    return (
      <p className={`text-2xs text-text-muted ${className}`} data-testid={`fts-dossier-empty-${symbol}`}>
        پاسخِ بنیادی برایِ {symbol} خالی بود.
      </p>
    );
  }

  return (
    <div className={`min-w-0 ${className}`} data-testid={`fts-dossier-${symbol}`}>
      <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-2xs text-text-muted">
        <span className="font-black text-text-primary">{symbol}</span>
        <span className="line-clamp-2 min-w-0">{name || '—'}</span>
        <span className="num">
          نمره: {card.data.score != null ? `${toFaDigits(card.data.score)} از ۵` : 'سنجیده نشده'}
        </span>
        <span className="num">{age != null ? `سن صورت مالی: ${toFaDigits(age)} روز` : 'صورت مالی معتبر'}</span>
      </div>
      <FtsCard
        score={card.data.score ?? null}
        passes={card.data.passes ?? {}}
        industryMode={card.data.pricing_mode ?? null}
        indicators={card.data.indicators ?? null}
        thresholds={card.data.thresholds ?? null}
        audit={audit}
        physicalApplicable={physicalApplicable}
        activeDrill={drillKey as never}
        onDrill={(k) => setDrillKey((cur) => (cur === k ? null : k))}
        quarters={fiscal}
      />
      <DataGapBanner gaps={card.data.data_gaps ?? []} eps={card.data.indicators?.['2']} />
    </div>
  );
}

export default FtsCardDossier;
