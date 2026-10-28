import type { ReactNode } from 'react';
import { faNum } from '@shared/lib/fa';
import { useFtsCard } from '../api/useFtsCard';
import { fundamentalFacts } from './FundamentalCards';

interface Props {
  symbol: string | null;
  expanded?: boolean;
  onToggle?: () => void;
}

export function FundamentalSummary({ symbol, expanded, onToggle }: Props) {
  const query = useFtsCard(symbol);

  let body: ReactNode;
  if (!symbol) {
    body = <span className="t-95 text-text-3">برای دیدنِ بنیادی، نمادی را از تابلو انتخاب کن.</span>;
  } else if (query.isLoading) {
    body = <span className="t-95 text-text-3">پنج محورِ بنیادی در حال خواندن…</span>;
  } else if (query.isError || !query.data) {
    body = <span data-testid="symbol-fund-unavailable" className="t-95 text-text-3">بنیادیِ این نماد در دسترس نیست.</span>;
  } else {
    const facts = fundamentalFacts(query.data);
    const accepted = facts.filter((fact) => fact.quality === 'ideal' || fact.quality === 'ok').length;
    const rejected = facts.filter((fact) => fact.quality === 'below').length;
    const abstained = facts.filter((fact) => fact.quality === 'na').length;
    const weakest = facts.find((fact) => fact.quality === 'below')
      ?? facts.find((fact) => fact.quality === 'na')
      ?? null;
    body = (
      <>
        <span className="flex flex-wrap items-baseline gap-1">
          <b data-testid="fund-summary-count" className="num t-105 font-extrabold text-text">
            {faNum(accepted)} از ۵ محور قبول
          </b>
          {abstained > 0 ? <span className="t-9 text-text-3">· {faNum(abstained)} بینظر</span> : null}
          {rejected > 0 ? <span className="t-9 text-down">· {faNum(rejected)} رد</span> : null}
        </span>
        <span data-testid="fund-summary-weakest" className="t-9 text-text-3">
          {weakest ? `ضعیف‌ترین: ${weakest.label}` : 'هر پنج محور قبول‌اند.'}
        </span>
      </>
    );
  }

  const className = 'flex w-full flex-col gap-0.5 border-y border-line px-2 py-1 text-start';
  if (!onToggle) {
    return <div data-testid="symbol-fund-summary" className={className}>{body}</div>;
  }
  return (
    <button
      type="button"
      data-testid="symbol-fund-summary"
      aria-expanded={Boolean(expanded)}
      onClick={onToggle}
      className={`${className} hover:bg-panel-2`}
    >
      {body}
      <span className="t-85 text-text-3">
        {expanded ? 'بستنِ کارت‌های بنیادی' : 'باز کردنِ کارت‌های بنیادی'}
      </span>
    </button>
  );
}
