// features/market/components/FtsStatusBadge.tsx -- بج وضعیت FTS با هاورکارت دلایل
// ورودی، خروجی resolveFtsStatus است؛ این کامپوننت کاملاً نمایشی و مستقل از بک‌اند است.
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsStatus, FtsView } from '../api/useFtsScreener';

const TONE: Record<FtsStatus, string> = {
  confirm: 'border-accent-green/50 bg-accent-green/10 text-accent-green',
  reject: 'border-accent-red/50 bg-accent-red/10 text-accent-red',
  na: 'border-border-c bg-bg-card text-text-muted',
};

export function FtsStatusBadge({ symbol, view }: { symbol: string; view: FtsView }) {
  const hasCard = view.reasons.length > 0 || view.score != null;
  const title = [
    view.score != null ? `امتیاز FTS: ${view.score}/۵` : null,
    ...view.reasons,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <span className="group/fts relative inline-flex justify-center" data-testid={`fts-${symbol}`}>
      <span
        data-testid={`fts-badge-${symbol}`}
        data-fts-status={view.status}
        aria-label={`وضعیت FTS ${symbol}: ${view.label}`}
        title={title || undefined}
        className={`num shrink-0 cursor-help rounded-full border px-2 py-0.5 text-2xs font-bold ${TONE[view.status]}`}
      >
        {view.label}
      </span>
      {hasCard ? (
        <span
          role="tooltip"
          data-testid={`fts-card-${symbol}`}
          className="pointer-events-none invisible absolute bottom-full end-0 z-20 mb-1 w-56 rounded-lg border border-border-c bg-bg-primary p-2 text-right text-2xs leading-5 text-text-secondary opacity-0 shadow-xl transition-opacity group-hover/fts:visible group-hover/fts:opacity-100"
        >
          {view.score != null ? (
            <span className="num block font-bold text-text-primary">
              امتیاز FTS: {toFaDigits(view.score)} از ۵
            </span>
          ) : null}
          {view.reasons.map((r) => (
            <span key={r} className="mt-0.5 block">
              • {r}
            </span>
          ))}
        </span>
      ) : null}
    </span>
  );
}
