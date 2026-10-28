import clsx from 'clsx';
import type { MarketRow } from '@shared/types/market';
import {
  DEFAULT_TAPE_FILTER_CONFIG, tapeFilterState, tapeFilterVerdict,
} from '../lib/tapeAlgorithms';
import { TAPES } from '../lib/tapeFilters';

const REASON = {
  pass: 'روشن',
  fail: 'زیرِ آستانه یا بی‌داده',
  unevaluated: 'داده برای سنجش نیست',
} as const;

export function TapeFilterChips({ row }: { row: MarketRow | null }) {
  if (!row) return null;
  return (
    <div data-testid="symbol-tapes" aria-label="فیلترهای تابلوی این نماد"
      className="flex flex-wrap gap-1 border-t border-line px-2 py-1">
      {TAPES.map((tape) => {
        const on = tapeFilterVerdict(row, tape.key, DEFAULT_TAPE_FILTER_CONFIG);
        const state = on ? 'pass' : tapeFilterState(row, tape.key, DEFAULT_TAPE_FILTER_CONFIG);
        return (
          <span
            key={tape.key}
            data-testid={`symbol-tape-${tape.key}`}
            data-on={on ? 'true' : 'false'}
            data-state={state}
            title={`${tape.label} — ${REASON[state]}`}
            className={clsx(
              'inline-flex items-center gap-1 rounded-full border px-1.5 t-85',
              on
                ? 'border-accent/60 bg-accent/10 font-bold text-accent'
                : 'border-line text-text-3',
            )}
          >
            <span className={clsx('h-1 w-1 rounded-full', on ? 'bg-accent' : 'bg-text-3/50')} />
            {tape.short}
          </span>
        );
      })}
    </div>
  );
}
