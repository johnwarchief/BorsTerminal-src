/**
 * frontend-v2/src/features/technical/ui/workspace/LayoutMenu.tsx
 *
 * منوی چیدمان‌های نام‌دار میزکار ۲.۰: ذخیره/بازیابی per-mode، ارجاع سریع
 * به مودهای دیگر و undo/redo. بازیابی هر چیدمان، مود همان چیدمان را هم
 * فعال می‌کند تا ترکیب پنل‌ها دقیقاً همان چیزی باشد که ذخیره شده است.
 */

import React, { useEffect, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalWorkspaceStore } from '../../workspace/technicalWorkspaceStore';
import { MODE_LABEL, WORKSPACE_MODES } from '../../workspace/presets';

export interface LayoutMenuProps {
  className?: string;
}

export const LayoutMenu: React.FC<LayoutMenuProps> = ({ className = '' }) => {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);

  const mode = useTechnicalWorkspaceStore((s) => s.mode);
  const layouts = useTechnicalWorkspaceStore((s) => s.layouts);
  const activeLayoutId = useTechnicalWorkspaceStore((s) => s.activeLayoutId);
  const saveLayout = useTechnicalWorkspaceStore((s) => s.saveLayout);
  const loadLayout = useTechnicalWorkspaceStore((s) => s.loadLayout);
  const undo = useTechnicalWorkspaceStore((s) => s.undo);
  const redo = useTechnicalWorkspaceStore((s) => s.redo);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    return () => window.removeEventListener('mousedown', onDown);
  }, [open]);

  const submitSave = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    saveLayout(trimmed);
    setName('');
    setOpen(false);
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        data-testid="layout-menu-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="چیدمان‌های نام‌دار"
        className="h-9 px-2 rounded-[var(--radius-md)] border border-line bg-panel-2 text-xs text-text-2 hover:text-accent hover:bg-panel-3 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        چیدمان‌ها · {MODE_LABEL[mode]}
      </button>

      {open ? (
        <div
          data-testid="layout-menu"
          role="menu"
          aria-label="چیدمان‌های نام‌دار میزکار"
          className="absolute end-0 top-full mt-1 z-40 w-72 bg-panel border border-line rounded-[var(--radius-md)] overflow-hidden"
        >
          <div className="flex items-center gap-2 p-2 border-b border-line">
            <input
              data-testid="layout-name-input"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') submitSave(); }}
              placeholder="نام چیدمان"
              aria-label="نام چیدمان تازه"
              className="h-8 flex-1 min-w-0 bg-panel-2 border border-line rounded-[var(--radius-md)] px-2 text-xs text-text focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            />
            <button
              type="button"
              data-testid="layout-save-btn"
              disabled={name.trim().length === 0}
              onClick={submitSave}
              className="h-8 px-2 rounded-[var(--radius-md)] border border-accent/40 bg-accent/15 text-xs text-accent hover:bg-accent/20 disabled:opacity-50 disabled:cursor-not-allowed outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              ذخیره
            </button>
          </div>

          <div className="max-h-64 overflow-y-auto p-1">
            {WORKSPACE_MODES.map((modeKey) => (
              <div key={modeKey} className="flex flex-col">
                <div className="px-2 py-1 text-xs text-text-3">{MODE_LABEL[modeKey]}</div>
                {layouts[modeKey].map((layout) => {
                  const isActive = mode === modeKey && activeLayoutId === layout.id;
                  return (
                    <button
                      key={layout.id}
                      type="button"
                      role="menuitem"
                      data-testid={`layout-item-${layout.id}`}
                      onClick={() => { loadLayout(layout.id); setOpen(false); }}
                      className={`flex items-center justify-between gap-2 min-h-9 px-2 rounded-[var(--radius-xs)] text-start text-xs transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                        isActive
                          ? 'text-accent bg-panel-3'
                          : 'text-text-2 hover:text-text hover:bg-panel-2'
                      }`}
                    >
                      <span className="truncate">{layout.name}</span>
                      <span className="text-xs text-text-3 shrink-0">
                        {toFaDigits(Object.keys(layout.panelKinds).length)} پنل
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-2 p-2 border-t border-line">
            <button
              type="button"
              data-testid="layout-undo-btn"
              onClick={() => { undo(); setOpen(false); }}
              title="برگشت (Ctrl+Z)"
              className="h-8 px-2 rounded-[var(--radius-md)] border border-line bg-panel-2 text-xs text-text-2 hover:text-text hover:bg-panel-3 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              برگشت
            </button>
            <button
              type="button"
              data-testid="layout-redo-btn"
              onClick={() => { redo(); setOpen(false); }}
              title="دوباره (Ctrl+Shift+Z)"
              className="h-8 px-2 rounded-[var(--radius-md)] border border-line bg-panel-2 text-xs text-text-2 hover:text-text hover:bg-panel-3 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              دوباره
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
};
