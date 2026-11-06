/**
 * frontend-v2/src/features/technical/ui/workspace/CommandPalette.tsx
 *
 * پالت دستور میزکار ۲.۰ (Ctrl+K): جستجوی نماد، تغییر مود، ذخیره/بازیابی
 * چیدمان و روشن/خاموش‌کردن پنل‌ها. بدون وابستگی تازه؛ همهٔ اکشن‌ها از
 * استور تکنیکال و استور نماد فعال می‌آیند.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import { useTechnicalWorkspaceStore } from '../../workspace/technicalWorkspaceStore';
import {
  MODE_LABEL, PANEL_KIND_LABEL, WORKSPACE_MODES, panelsOfKind,
  type TechnicalPanelKind, type WorkspaceMode,
} from '../../workspace/presets';

interface PaletteAction {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

export interface CommandPaletteProps {
  onClose: () => void;
  className?: string;
}

const PANEL_ACTIONS: TechnicalPanelKind[] = ['inspector', 'feed', 'scanner', 'fundamental', 'indicators'];

export const CommandPalette: React.FC<CommandPaletteProps> = ({ onClose, className = '' }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mode = useTechnicalWorkspaceStore((s) => s.mode);
  const layouts = useTechnicalWorkspaceStore((s) => s.layouts);
  const root = useTechnicalWorkspaceStore((s) => s.root);
  const setMode = useTechnicalWorkspaceStore((s) => s.setMode);
  const saveLayout = useTechnicalWorkspaceStore((s) => s.saveLayout);
  const loadLayout = useTechnicalWorkspaceStore((s) => s.loadLayout);
  const togglePanel = useTechnicalWorkspaceStore((s) => s.togglePanel);
  const setSelectedSymbol = useTechnicalStore((s) => s.setSelectedSymbol);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const trimmed = query.trim();

  const applySymbol = (symbol: string) => {
    setSelectedSymbol(symbol);
    if (typeof window !== 'undefined') {
      window.location.hash = `#/technical/${encodeURIComponent(symbol)}`;
    }
    onClose();
  };

  const runAction = (run: () => void) => {
    run();
    onClose();
  };

  const actions: PaletteAction[] = [];

  if (trimmed) {
    actions.push({
      id: 'symbol-apply',
      label: `نمایش نماد «${trimmed}»`,
      hint: 'نماد',
      run: () => applySymbol(trimmed),
    });
  }

  for (const item of WORKSPACE_MODES) {
    actions.push({
      id: `mode-${item}`,
      label: `حالت ${MODE_LABEL[item]}`,
      hint: item === mode ? 'فعال' : 'مود',
      run: () => setMode(item as WorkspaceMode),
    });
  }

  for (const kind of PANEL_ACTIONS) {
    const isOpen = panelsOfKind(root).includes(kind);
    actions.push({
      id: `panel-${kind}`,
      label: `${isOpen ? 'بستن' : 'افزودن'} ${PANEL_KIND_LABEL[kind]}`,
      hint: 'پنل',
      run: () => togglePanel(kind),
    });
  }

  actions.push({
    id: 'layout-save',
    label: 'ذخیرهٔ چیدمان فعلی',
    hint: 'چیدمان',
    run: () => { saveLayout(`${MODE_LABEL[mode]} ${layouts[mode].length + 1}`); },
  });

  for (const layout of layouts[mode]) {
    actions.push({
      id: `layout-load-${layout.id}`,
      label: `بازیابی چیدمان «${layout.name}»`,
      hint: 'چیدمان',
      run: () => loadLayout(layout.id),
    });
  }

  const needle = trimmed.toLowerCase();
  const visible = needle
    ? actions.filter((action) => action.label.toLowerCase().includes(needle))
    : actions;

  return (
    <div
      data-testid="command-palette-backdrop"
      className={`fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-16 ${className}`}
      dir="rtl"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        data-testid="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="پالت دستور میزکار"
        className="w-full max-w-lg bg-panel border border-line rounded-xl overflow-hidden"
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-line">
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Escape') onClose(); }}
            placeholder="نماد، مود، پنل یا چیدمان"
            aria-label="جستجوی دستور یا نماد"
            className="h-9 flex-1 min-w-0 bg-panel-2 border border-line rounded-[var(--radius-md)] px-2 text-xs text-text focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          />
          <button
            type="button"
            data-testid="command-palette-close"
            onClick={onClose}
            className="h-9 px-2 rounded-[var(--radius-md)] border border-line text-xs text-text-3 hover:text-text hover:bg-panel-2 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Esc
          </button>
        </div>

        <ul data-testid="command-palette-actions" className="max-h-80 overflow-y-auto p-2 flex flex-col gap-1">
          {visible.length === 0 ? (
            <li className="px-2 py-2 text-xs text-text-3">دستوری با این جستجو پیدا نشد</li>
          ) : visible.map((action) => (
            <li key={action.id}>
              <button
                type="button"
                data-testid={`command-action-${action.id}`}
                onClick={() => runAction(action.run)}
                className="flex w-full items-center justify-between gap-2 min-h-9 px-2 rounded-[var(--radius-md)] text-start text-xs text-text-2 hover:text-text hover:bg-panel-2 transition-colors outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                <span className="truncate">{action.label}</span>
                {action.hint ? <span className="text-xs text-text-3 shrink-0">{action.hint}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
