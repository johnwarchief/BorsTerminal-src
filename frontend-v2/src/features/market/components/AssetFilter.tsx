import { useState } from 'react';
import clsx from 'clsx';
import { ASSET_LABELS, ASSET_TYPES, type AssetType } from '../lib/assetType';
import { DEFAULT_ASSET_TYPES, sameAssetSets } from '../lib/assetDefaults';

interface Props {
  selected: readonly AssetType[];
  onChange: (list: AssetType[]) => void;
}

export function AssetFilter({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const isDefault = sameAssetSets(selected, DEFAULT_ASSET_TYPES);
  const summary = isDefault
    ? 'پیش‌فرض'
    : selected.length === 0
      ? 'هیچ'
      : selected.length === 1
        ? ASSET_LABELS[selected[0]!]
        : `${selected.length} نوع`;

  function toggle(type: AssetType) {
    onChange(selected.includes(type) ? selected.filter((t) => t !== type) : [...selected, type]);
  }

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="asset-filter"
        onClick={() => setOpen((v) => !v)}
        className="h-7 rounded border border-line bg-panel px-2 text-[11px] text-text-2 hover:border-line-strong hover:text-text"
      >
        دارایی: {summary}
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-52 rounded border border-line bg-panel-2 p-2 shadow-2xl">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10.5px] text-text-3">نوع دارایی</span>
            <button
              type="button"
              onClick={() => onChange([...DEFAULT_ASSET_TYPES])}
              className="text-[10.5px] text-accent hover:underline"
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
                  className={clsx(
                    'flex h-6 items-center gap-2 rounded px-1.5 text-start text-[11px]',
                    on ? 'text-text' : 'text-text-3 hover:bg-panel-3',
                  )}
                >
                  <span
                    className={clsx(
                      'inline-block h-3 w-3 rounded-sm border',
                      on ? 'border-accent bg-accent' : 'border-line-strong',
                    )}
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
