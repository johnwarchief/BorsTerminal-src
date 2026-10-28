import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { AssetFilter } from './AssetFilter';
import { BoardFilterMenu } from './BoardFilterMenu';
import { BoardViewMenu } from './BoardViewMenu';
import type { AssetType } from '../lib/assetType';
import type { BoardFilterValues } from '../lib/boardFilters';
import { COLUMNS, COLUMN_ORDER, PROFILE_ORDER, PROFILES, type ColumnKey, type ProfileKey } from '../lib/columns';
import type { Density, SavedBoardView } from '../stores/prefs';

const DENSITIES: { key: Density; label: string }[] = [
  { key: 'compact', label: 'فشرده' },
  { key: 'normal', label: 'متعادل' },
  { key: 'comfortable', label: 'راحت' },
];

function ColumnsIcon() {
  return (
    <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="1" />
      <path d="M9 4v16M15 4v16" />
    </svg>
  );
}

interface Props {
  query: string;
  onQuery: (query: string) => void;
  profile: ProfileKey;
  onProfile: (profile: ProfileKey) => void;
  density: Density;
  onDensity: (density: Density) => void;
  columns: readonly ColumnKey[];
  onToggleColumn: (column: ColumnKey) => void;
  assetTypes: readonly AssetType[];
  onAssetTypes: (types: AssetType[]) => void;
  filters: BoardFilterValues;
  onFilters: (patch: Partial<BoardFilterValues>) => void;
  sectors: readonly string[];
  pollMs: number;
  onPollMs: (ms: number) => void;
  savedViews?: readonly SavedBoardView[];
  onSaveView?: (name: string) => void;
  onApplyView?: (name: string) => void;
  onDeleteView?: (name: string) => void;
  onExport?: () => void;
  onFocusSearch?: () => void;
}

export function BoardToolbar({
  query,
  onQuery,
  profile,
  onProfile,
  density,
  onDensity,
  columns,
  onToggleColumn,
  assetTypes,
  onAssetTypes,
  filters,
  onFilters,
  sectors,
  pollMs,
  onPollMs,
  savedViews = [],
  onSaveView,
  onApplyView,
  onDeleteView,
  onExport,
  onFocusSearch,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const columnsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const focus = () => {
      if (onFocusSearch) {
        onFocusSearch();
        return;
      }
      inputRef.current?.focus();
      inputRef.current?.select();
    };
    const onShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        focus();
      }
    };
    window.addEventListener('bors:focus-search', focus);
    window.addEventListener('keydown', onShortcut);
    return () => {
      window.removeEventListener('bors:focus-search', focus);
      window.removeEventListener('keydown', onShortcut);
    };
  }, [onFocusSearch]);

  useEffect(() => {
    if (!columnsOpen) return;
    function onDown(event: MouseEvent) {
      if (columnsRef.current && !columnsRef.current.contains(event.target as Node)) setColumnsOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setColumnsOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [columnsOpen]);

  const active = new Set(columns);

  return (
    <div
      data-testid="board-toolbar"
      className="flex h-[37px] shrink-0 items-center justify-between gap-2 border-b border-line bg-panel px-3"
    >
      <div className="flex min-w-0 items-center gap-1.5 overflow-hidden">
        <AssetFilter selected={assetTypes} onChange={onAssetTypes} />
        <div
          className="inline-flex h-[25px] flex-none items-center gap-px rounded-[var(--radius-sm)] border border-line p-[2px]"
          role="group"
          aria-label="پروفایل ستون‌ها"
        >
          {PROFILE_ORDER.map((key) => (
            <button
              key={key}
              type="button"
              data-testid={`profile-${key}`}
              aria-pressed={profile === key}
              onClick={() => onProfile(key)}
              className={clsx(
                'h-[19px] rounded-[var(--radius-xs)] px-[9px] t-10 whitespace-nowrap',
                profile === key
                  ? 'bg-panel-3 font-bold text-accent'
                  : 'text-text-3 hover:text-text-2',
              )}
            >
              {PROFILES[key].label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-1.5">
        <input
          ref={inputRef}
          id="board-search"
          data-testid="board-search"
          type="search"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="جستجو در تابلو…"
          aria-label="جستجو در تابلو"
          autoComplete="off"
          className="board-search h-[23px] min-w-[138px] max-w-[360px] flex-1 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 t-10 text-text outline-none placeholder:text-text-3 focus:border-line-strong focus:bg-panel"
        />
        <BoardFilterMenu
          filters={filters}
          onChange={onFilters}
          sectors={sectors}
          pollMs={pollMs}
          onPollMs={onPollMs}
        />
        <div
          className="inline-flex h-[24px] flex-none items-center gap-px rounded-[var(--radius-sm)] border border-line p-[2px]"
          role="group"
          aria-label="تراکم جدول"
        >
          {DENSITIES.map((d) => (
            <button
              key={d.key}
              type="button"
              data-testid={`density-${d.key}`}
              aria-pressed={density === d.key}
              onClick={() => onDensity(d.key)}
              className={clsx(
                'h-[18px] rounded-[var(--radius-xs)] px-1.5 t-95 whitespace-nowrap',
                density === d.key ? 'bg-panel-3 font-bold text-accent' : 'text-text-3 hover:text-text-2',
              )}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="relative" ref={columnsRef}>
          <button
            type="button"
            data-testid="columns-btn"
            aria-expanded={columnsOpen}
            aria-pressed={columnsOpen}
            onClick={() => setColumnsOpen((v) => !v)}
            title="انتخاب ستون‌ها"
            className={clsx(
              'flex h-[24px] items-center gap-1 rounded-[var(--radius-sm)] border px-1.5 t-10 font-semibold whitespace-nowrap',
              columnsOpen
                ? 'border-accent/40 bg-accent-soft text-accent'
                : 'border-line text-text-3 hover:border-line-strong hover:text-text-2',
            )}
          >
            <ColumnsIcon />
            ستون‌ها
          </button>
          {columnsOpen && (
            <div className="absolute end-0 top-full z-30 mt-1 w-[252px] rounded-[var(--radius-sm)] border border-line bg-panel-2 p-2 shadow-2xl">
              <div className="mb-1 flex items-baseline justify-between">
                <span className="t-95 font-bold text-text-2">ستون‌های تابلو</span>
                <span className="t-9 text-text-3">{PROFILES[profile].label}</span>
              </div>
              <div className="flex flex-col gap-px">
                {COLUMN_ORDER.map((key) => {
                  const def = COLUMNS[key];
                  const on = active.has(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      data-testid={`column-${key}`}
                      aria-pressed={on}
                      disabled={!def.available}
                      onClick={() => onToggleColumn(key)}
                      className={clsx(
                        'flex h-6 items-center gap-2 rounded-[var(--radius-xs)] px-1.5 text-start t-10',
                        def.available
                          ? clsx(on ? 'text-text' : 'text-text-3', 'hover:bg-panel-3')
                          : 'cursor-not-allowed text-text-3/60',
                      )}
                      title={def.hint}
                    >
                      <span
                        className={clsx(
                          'inline-grid h-3 w-3 flex-none place-items-center rounded-[2px] border text-[7px] leading-none',
                          on && def.available ? 'border-accent bg-accent text-accent-ink' : 'border-line-strong',
                        )}
                        aria-hidden
                      >
                        {on && def.available ? '✓' : ''}
                      </span>
                      <span className="flex-1">{def.label}</span>
                      {!def.available && (
                        <span className="rounded-[2px] border border-line px-1 t-85 text-text-3">وصل نیست</span>
                      )}
                    </button>
                  );
                })}
              </div>
              <p className="mt-1.5 border-t border-line pt-1.5 t-85 leading-relaxed text-text-3">
                پروفایل، ستون‌ها را عوض می‌کند؛ ستونِ ناوصل در نما نمی‌آید و صفر یا تخمین ندارد.
              </p>
            </div>
          )}
        </div>

        {onSaveView && onApplyView && onDeleteView && (
          <BoardViewMenu
            views={savedViews}
            onSave={onSaveView}
            onApply={onApplyView}
            onDelete={onDeleteView}
          />
        )}
        {onExport && (
          <button
            type="button"
            data-testid="export-board"
            aria-label="خروجی CSV از تابلو"
            title="خروجی از ردیف‌های همین نما"
            onClick={onExport}
            className="flex h-[24px] flex-none items-center gap-1 rounded-[var(--radius-sm)] border border-line px-1.5 t-10 font-semibold whitespace-nowrap text-text-3 hover:border-line-strong hover:text-text-2"
          >
            <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <path d="M12 3v12M7 10l5 5 5-5M5 20h14" />
            </svg>
            <span className="board-tool-text">خروجی</span>
          </button>
        )}
      </div>
    </div>
  );
}
