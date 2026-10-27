import clsx from 'clsx';
import { toFaDigits } from '@shared/lib/fa';
import { TAPES, type ScreenLogic, type TapeKey } from '../lib/tapeFilters';

interface Props {
  counts: Record<TapeKey, number>;
  active: readonly TapeKey[];
  logic: ScreenLogic;
  onToggle: (key: TapeKey) => void;
  onLogic: (logic: ScreenLogic) => void;
  onClear: () => void;
}

export function TapeBar({ counts, active, logic, onToggle, onLogic, onClear }: Props) {
  return (
    <div className="flex h-9 shrink-0 items-center gap-1.5 overflow-x-auto border-b border-line bg-panel px-2">
      <button
        type="button"
        onClick={onClear}
        className={clsx(
          'h-6 shrink-0 rounded px-2 text-[11px]',
          active.length === 0 ? 'bg-accent text-[#171307]' : 'text-text-2 hover:bg-panel-2 hover:text-text',
        )}
      >
        همه
      </button>
      {TAPES.map((tape) => {
        const on = active.includes(tape.key);
        return (
          <button
            key={tape.key}
            type="button"
            data-testid={`tape-${tape.key}`}
            onClick={() => onToggle(tape.key)}
            title={tape.label}
            className={clsx(
              'flex h-6 shrink-0 items-center gap-1 rounded border px-1.5 text-[11px]',
              on
                ? 'border-accent/60 bg-[var(--accent-soft)] text-accent'
                : 'border-transparent text-text-2 hover:bg-panel-2 hover:text-text',
            )}
          >
            <span>{tape.label}</span>
            <span className="num text-[10px] text-text-3">{toFaDigits(counts[tape.key])}</span>
          </button>
        );
      })}
      {active.length > 1 && (
        <div className="ms-auto flex shrink-0 items-center gap-1 ps-2">
          <button
            type="button"
            onClick={() => onLogic('and')}
            className={clsx('h-6 rounded px-2 text-[10px]', logic === 'and' ? 'bg-panel-3 text-text' : 'text-text-3 hover:text-text')}
          >
            اشتراک
          </button>
          <button
            type="button"
            onClick={() => onLogic('or')}
            className={clsx('h-6 rounded px-2 text-[10px]', logic === 'or' ? 'bg-panel-3 text-text' : 'text-text-3 hover:text-text')}
          >
            اجتماع
          </button>
        </div>
      )}
    </div>
  );
}
