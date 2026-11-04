import { useFtsCard } from '../api/useFtsCard';
import { FundamentalCards } from './FundamentalCards';
import { FundamentalSummary } from './FundamentalSummary';

interface Props {
  symbol: string;
  onBack: () => void;
}

export function FundamentalDetail({ symbol, onBack }: Props) {
  const query = useFtsCard(symbol);
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
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          <FundamentalSummary symbol={symbol} />
          <FundamentalCards symbol={symbol} />
        </div>
      )}
    </section>
  );
}
