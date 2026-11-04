import { faNum } from '@shared/lib/fa';
import { useCodalHealth } from '../api/useCodalHealth';
import { useFtsCard } from '../api/useFtsCard';
import { useQuarters } from '../api/useQuarters';
import { useSectorPe } from '../api/useSectorPe';
import { AxisDrilldown } from './AxisDrilldown';
import { CodalHealthStrip } from './CodalHealthStrip';
import { CorporateCalendar } from './CorporateCalendar';
import { FundamentalCards } from './FundamentalCards';
import { FundamentalSummary } from './FundamentalSummary';
import { QuarterlyTrend } from './QuarterlyTrend';

interface Props {
  symbol: string;
  onBack: () => void;
}

export function FundamentalDetail({ symbol, onBack }: Props) {
  const query = useFtsCard(symbol);
  const quarters = useQuarters(symbol);
  const sectorPe = useSectorPe(symbol);
  const health = useCodalHealth();
  const card = query.data;

  return (
    <section data-testid="fundamental-detail" className="flex min-h-0 flex-1 flex-col bg-bg">
      <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-line px-3 py-2">
        <button
          type="button"
          data-testid="fundamental-back"
          onClick={onBack}
          className="tape-btn"
        >
          ← جدول بنیادی
        </button>
        <b data-testid="fundamental-title" className="t-125 font-extrabold text-text">{symbol}</b>
        {card?.sector ? <span className="t-9 text-text-3">{card.sector}</span> : null}
        {card?.verdict ? <span className="rounded-[3px] border border-line px-1 t-85 text-text-2">{card.verdict}</span> : null}
        {card?.score != null ? <span className="num t-9 text-text-3">امتیاز {card.score}</span> : null}
      </header>

      {query.isLoading ? (
        <p data-testid="fundamental-detail-loading" className="p-3 t-95 text-text-3">کارتِ پنج‌محور در حال خواندن…</p>
      ) : query.isError || !card ? (
        <p data-testid="fundamental-detail-error" className="p-3 t-95 leading-relaxed text-text-3">
          کارتِ بنیادیِ این نماد در دسترس نیست؛ جدول و بقیهٔ بخش‌ها دست‌نخورده‌اند.
        </p>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
          <FundamentalSummary symbol={symbol} />
          <FundamentalCards symbol={symbol} />

          <AxisDrilldown card={card} />

          <CorporateCalendar symbol={symbol} />

          <div className="grid gap-2 xl:grid-cols-[minmax(0,1.6fr)_minmax(220px,1fr)]">
            <section data-testid="quarterly-panel" className="rounded-[var(--radius-sm)] border border-line bg-panel p-2">
              <h3 className="mb-1 t-10 font-bold text-text-2">روند فصلی</h3>
              <QuarterlyTrend
                quarters={quarters.data?.quarters ?? []}
                loading={quarters.isLoading}
                error={quarters.isError}
              />
            </section>

            <section data-testid="sector-pe-panel" className="rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-9">
              <h3 className="mb-1 t-10 font-bold text-text-2">P/E صنعت</h3>
              <div className="flex flex-wrap items-baseline gap-1.5">
                <span className="text-text-3">این نماد</span>
                <b data-testid="sector-pe" className="num text-text">
                  {sectorPe.data?.pe != null ? faNum(sectorPe.data.pe, 1) : '—'}
                </b>
                <span className="text-text-3">میانهٔ صنعت</span>
                <b data-testid="sector-pe-median" className="num text-text">
                  {sectorPe.data?.median != null ? faNum(sectorPe.data.median, 1) : '—'}
                </b>
              </div>
              <p className="mt-1 text-text-3">
                {sectorPe.data?.sector ?? 'صنعت نامشخص'}
                {sectorPe.data?.peers != null ? ` · ${faNum(sectorPe.data.peers)} نماد با P/E مثبت` : ''}
              </p>
            </section>
          </div>

          <section className="rounded-[var(--radius-sm)] border border-line bg-panel px-2 py-1.5">
            <CodalHealthStrip health={health.data} loading={health.isLoading} />
          </section>
        </div>
      )}
    </section>
  );
}
