import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import type { SavedBoardView } from '../stores/prefs';

function ViewsIcon() {
  return (
    <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5" />
    </svg>
  );
}

interface Props {
  views: readonly SavedBoardView[];
  onSave: (name: string) => void;
  onApply: (name: string) => void;
  onDelete: (name: string) => void;
}

export function BoardViewMenu({ views, onSave, onApply, onDelete }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') close();
    }
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function close() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function save() {
    if (!draft.trim()) return;
    onSave(draft);
    setDraft('');
  }

  return (
    <div className="relative flex-none" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        data-testid="saved-views-btn"
        aria-label="نماهای ذخیره‌شده"
        aria-expanded={open}
        aria-controls="saved-board-views"
        title="نماهای ذخیره‌شده"
        onClick={() => setOpen((value) => !value)}
        className={clsx(
          'flex h-[24px] items-center gap-1 rounded-[var(--radius-sm)] border px-1.5 t-10 font-semibold whitespace-nowrap',
          open ? 'border-accent/40 bg-accent-soft text-accent' : 'border-line text-text-3 hover:border-line-strong hover:text-text-2',
        )}
      >
        <ViewsIcon />
        <span className="board-tool-text">نماها</span>
      </button>
      {open && (
        <div
          id="saved-board-views"
          role="dialog"
          aria-label="نماهای ذخیره‌شده"
          className="absolute end-0 top-full z-30 mt-1 w-[280px] max-w-[calc(100vw-16px)] rounded-[var(--radius-sm)] border border-line bg-panel-2 p-2 shadow-2xl"
        >
          <form
            className="flex gap-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              save();
            }}
          >
            <input
              ref={inputRef}
              autoFocus
              data-testid="view-name-input"
              aria-label="نام نمای تازه"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="نام این نما…"
              maxLength={60}
              className="h-7 min-w-0 flex-1 rounded-[var(--radius-xs)] border border-line bg-panel px-2 t-10 text-text outline-none placeholder:text-text-3 focus:border-line-strong"
            />
            <button
              type="submit"
              data-testid="save-view-btn"
              disabled={!draft.trim()}
              className="h-7 rounded-[var(--radius-xs)] border border-line px-2 t-10 text-text-2 hover:border-line-strong disabled:cursor-not-allowed disabled:opacity-40"
            >
              ذخیره
            </button>
          </form>
          <div className="mt-2 max-h-[180px] overflow-y-auto border-t border-line pt-1">
            {views.length === 0 ? (
              <p className="px-1 py-2 t-95 text-text-3">هنوز نمایی ذخیره نشده است.</p>
            ) : views.map((view) => (
              <div key={view.name} className="flex h-8 items-center gap-1 rounded-[var(--radius-xs)] hover:bg-panel-3">
                <button
                  type="button"
                  data-testid={`view-apply-${view.name}`}
                  onClick={() => {
                    onApply(view.name);
                    close();
                  }}
                  className="h-full min-w-0 flex-1 truncate px-2 text-start t-10 text-text-2 hover:text-text"
                  title={`بازیابی ${view.name}`}
                >
                  {view.name}
                </button>
                <button
                  type="button"
                  aria-label={`حذف نمای ${view.name}`}
                  title="حذف نما"
                  onClick={() => {
                    onDelete(view.name);
                    inputRef.current?.focus();
                  }}
                  className="grid h-6 w-6 flex-none place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel hover:text-down"
                >
                  <svg viewBox="0 0 24 24" width={12} height={12} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
                    <path d="M5 7h14M9 7V4h6v3M8 7l1 13h6l1-13" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <p className="mt-1 border-t border-line pt-1.5 t-85 leading-relaxed text-text-3">
            فیلتر، ستون، جستجو، مرتب‌سازی و تراکم در هر نما نگه داشته می‌شود.
          </p>
        </div>
      )}
    </div>
  );
}
