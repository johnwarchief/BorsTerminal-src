import clsx from 'clsx';
import { fmtInt } from '@shared/lib/fa';
import { TAPES, type TapeKey } from '../lib/tapeFilters';

interface Props {
  counts: Record<TapeKey, number>;
  unevaluated: Record<TapeKey, number>;
  hiddenCounts: Record<TapeKey, number>;
  baseCount: number;
  active: TapeKey[];
  logic: 'and' | 'or';
  onToggle: (tape: TapeKey) => void;
  onClear: () => void;
  onLogic: (logic: 'and' | 'or') => void;
}

export function TapeBar({
  counts,
  unevaluated,
  hiddenCounts,
  baseCount,
  active,
  logic,
  onToggle,
  onClear,
  onLogic,
}: Props) {
  return (
    <div
      data-testid="tape-bar"
      className="flex h-[33px] shrink-0 items-center gap-1 overflow-hidden border-b border-line bg-panel px-3"
      aria-label="فیلترهای تابلوخوانی"
    >
      <span
        className="t-9 me-1 flex-none font-bold text-text-2"
        title={`شمارش روی ${fmtInt(baseCount)} ردیفِ پایه؛ نسنجیده و پنهان جدا شمرده می‌شوند.`}
      >
        تابلوخوانی
      </span>
      <button
        type="button"
        className="tape-btn is-all"
        aria-pressed={active.length === 0}
        onClick={onClear}
      >
        همه
        <span className="count num">{fmtInt(baseCount)}</span>
      </button>
      <div className="inline-flex h-[22px] flex-none items-center gap-px rounded-[var(--radius-sm)] border border-line p-[2px]" role="group" aria-label="منطق ترکیب فیلترها">
        {(['and', 'or'] as const).map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={logic === key}
            onClick={() => onLogic(key)}
            className={clsx(
              'h-[16px] rounded-[var(--radius-xs)] px-1.5 t-85',
              logic === key ? 'bg-panel-3 font-bold text-accent' : 'text-text-3 hover:text-text-2',
            )}
          >
            {key === 'and' ? 'و' : 'یا'}
          </button>
        ))}
      </div>
      {TAPES.map((tape) => (
        <button
          key={tape.key}
          type="button"
          data-testid={`tape-${tape.key}`}
          className="tape-btn"
          aria-pressed={active.includes(tape.key)}
          aria-label={tape.label}
          title={`${tape.label} · نسنجیده: ${fmtInt(unevaluated[tape.key])} · پنهان: ${fmtInt(hiddenCounts[tape.key])}`}
          onClick={() => onToggle(tape.key)}
        >
          {tape.short}
          <span className="count num">{fmtInt(counts[tape.key])}</span>
        </button>
      ))}
      {active.length > 0 && (
        <span className="t-85 ms-auto flex-none whitespace-nowrap text-text-3">
          {fmtInt(active.length)} فیلتر فعال · {logic === 'and' ? 'همه با هم' : 'دست‌کم یکی'}
        </span>
      )}
    </div>
  );
}
