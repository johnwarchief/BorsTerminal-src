import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { ASSET_LABELS, ASSET_TYPES, type AssetType } from '../lib/assetType';
import { DEFAULT_ASSET_TYPES, sameAssetSets } from '../lib/assetDefaults';

interface Props {
  selected: readonly AssetType[];
  onChange: (list: AssetType[]) => void;
}

export function AssetFilter({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const isDefault = sameAssetSets(selected, DEFAULT_ASSET_TYPES);
  const summary = isDefault
    ? 'پیش‌فرض'
    : selected.length === 0
      ? 'هیچ'
      : selected.length === 1
        ? ASSET_LABELS[selected[0]!]
        : `${selected.length} نوع`;

  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function toggle(type: AssetType) {
    onChange(selected.includes(type) ? selected.filter((t) => t !== type) : [...selected, type]);
  }

  return (
    <div className="relative flex-none" ref={rootRef}>
      <button
        type="button"
        data-testid="asset-filter"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={clsx(
          'flex h-[25px] items-center gap-1 rounded-[var(--radius-sm)] border px-2 t-10',
          open
            ? 'border-line-strong bg-panel-2 text-text'
            : 'border-line bg-panel text-text-3 hover:border-line-strong hover:text-text-2',
        )}
      >
        <span>دارایی:</span>
        <span className="font-semibold text-text-2">{summary}</span>
      </button>
      {open && (
        <div className="absolute start-0 top-full z-30 mt-1 w-[220px] rounded-[var(--radius-sm)] border border-line bg-panel-2 p-2 shadow-2xl">
          <div className="mb-1 flex items-center justify-between">
            <span className="t-95 text-text-3">نوع دارایی</span>
            <button
              type="button"
              onClick={() => onChange([...DEFAULT_ASSET_TYPES])}
              className="t-95 text-accent hover:underline"
            >
              پیش‌فرض
            </button>
          </div>
          <div className="flex flex-col gap-0.5">
            {ASSET_TYPES.map((type) => {
              const on = selected.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggle(type)}
                  aria-pressed={on}
                  className={clsx(
                    'flex h-6 items-center gap-2 rounded-[var(--radius-xs)] px-1.5 text-start t-10',
                    on ? 'text-text' : 'text-text-3 hover:bg-panel-3',
                  )}
                >
                  <span
                    className={clsx(
                      'inline-block h-3 w-3 rounded-[2px] border',
                      on ? 'border-accent bg-accent' : 'border-line-strong',
                    )}
                    aria-hidden
                  />
                  {ASSET_LABELS[type]}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
