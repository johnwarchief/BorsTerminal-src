import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useFtsCard } from '../api/useFtsCard';
import { AXES, statusFa, type AxisStatus } from '../lib/axisMeta';
import { cardStatus } from '../lib/cardStatus';
import { useFundamentalPrefs } from '../stores/prefs';

/** گذرِ وضعیت به توکنِ رنگ؛ na=flat و unknown=warn طبق R66. */
const BAR_COLOR: Record<AxisStatus, string> = {
  pass: 'var(--fd-up)',
  fail: 'var(--fd-down)',
  na: 'var(--fd-flat)',
  unknown: 'var(--fd-warn)',
};

interface Props {
  symbol: string | null;
  expanded?: boolean;
  onToggle?: () => void;
}

export function FundamentalSummary({ symbol, expanded, onToggle }: Props) {
  const query = useFtsCard(symbol);
  const surface = useFundamentalPrefs((state) => state.surface);
  const card = query.data;
  const statuses = card ? AXES.map((meta) => cardStatus(card, meta.key)) : [];
  const passed = statuses.filter((status) => status === 'pass').length;
  const failed = statuses.filter((status) => status === 'fail').length;
  const abstained = statuses.filter((status) => status === 'na' || status === 'unknown').length;

  let body: ReactNode;
  if (!symbol) {
    body = (
      <span className="text-[10.5px] text-[var(--fd-text-3)]">
        برای دیدن بنیادی، نمادی را از تابلو انتخاب کن.
      </span>
    );
  } else if (query.isLoading) {
    body = (
      <span className="text-[10.5px] text-[var(--fd-text-3)]">
        پنج محورِ بنیادی در حال خواندن…
      </span>
    );
  } else if (query.isError || !card) {
    body = (
      <span data-testid="symbol-fund-unavailable" className="text-[10.5px] text-[var(--fd-text-3)]">
        بنیادی این نماد در دسترس نیست.
      </span>
    );
  } else {
    body = (
      <>
        <span className="flex flex-wrap items-baseline gap-1">
          <b data-testid="fund-summary-count" className="text-[11px] font-extrabold text-[var(--fd-text)]">
            {toFaDigits(passed)} از ۵
          </b>
          <span className="text-[9px] text-[var(--fd-text-3)]">محور قبول</span>
          {failed ? (
            <span className="text-[9px] text-[var(--fd-down)]">
              · {toFaDigits(failed)} {statusFa('fail')}
            </span>
          ) : null}
          {abstained ? (
            <span className="text-[9px] text-[var(--fd-text-3)]">
              · {toFaDigits(abstained)} بی‌نظر/نامشخص
            </span>
          ) : null}
        </span>
        <span className="flex gap-1" aria-hidden="true">
          {statuses.map((status, index) => {
            const axis = AXES[index].key;
            return (
              <span key={axis} data-axis={axis}
                className={`h-1 w-4 rounded-full fd-status--${status}`}
                style={{ background: BAR_COLOR[status] }} />
            );
          })}
        </span>
      </>
    );
  }

  const className = 'fundamental-surface flex w-full flex-col gap-0.5 border-y border-[var(--fd-line)] px-2 py-1 text-start';
  if (!onToggle) {
    return (
      <div data-testid="symbol-fund-summary" data-fund-surface={surface} className={className}>
        {body}
      </div>
    );
  }
  return (
    <button type="button" data-testid="symbol-fund-summary" data-fund-surface={surface}
      aria-expanded={Boolean(expanded)} onClick={onToggle}
      className={`${className} hover:bg-[var(--fd-panel-2)]`}>
      {body}
      <span className="text-[9px] text-[var(--fd-text-3)]">
        {expanded ? 'بستن کارت‌های بنیادی' : 'باز کردن کارت‌های بنیادی'}
      </span>
    </button>
  );
}
