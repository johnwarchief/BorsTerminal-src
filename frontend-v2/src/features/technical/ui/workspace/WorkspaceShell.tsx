/**
 * frontend-v2/src/features/technical/ui/workspace/WorkspaceShell.tsx
 *
 * پوستهٔ میزکار ۲.۰ (E1) — مودهای تحلیل/اسکن/پژوهش + داکینگ درختی ۴پنلی:
 *   نوار بالا ۵۶px │ نوار فعالیت ۴۰px │ ناحیهٔ درخت چیدمان
 * فقط شبکهٔ بیرونی CSS Grid است؛ داخل ناحیه، همان split-tree مشترک
 * (`@shared/workspace/layout`) پنل‌ها را می‌چیند. هر برگ یک
 * `WorkspacePanelHost` با testid پایدار `panel-<kind>` است.
 * چارت/بازرس/فید خودشان دست‌نخورده می‌مانند و فقط میزبانی می‌شوند.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useTechnicalStore } from '../../model/technicalStore';
import {
  useTechnicalWorkspaceStore,
} from '../../workspace/technicalWorkspaceStore';
import {
  PANEL_KIND_LABEL, type TechnicalPanelKind,
} from '../../workspace/presets';
import { WorkspacePanelHost } from '../../workspace/WorkspacePanelHost';
import type { LayoutNode } from '@shared/workspace/layout';
import { Splitter } from '@shared/workspace/Splitter';
import { WorkspaceTopbar } from './WorkspaceTopbar';
import { ActivityBar } from './ActivityBar';
import { CommandPalette } from './CommandPalette';

export const WORKSPACE_GRID_TEMPLATE_COLUMNS = '40px minmax(0,1fr)';
export const WORKSPACE_GRID_TEMPLATE_ROWS = '56px minmax(0,1fr)';
export const WORKSPACE_GRID_TEMPLATE_AREAS = '"topbar topbar" "activity dock"';

export interface WorkspaceShellProps {
  /** نماد فعال؛ اگر نرسد از استور خوانده می‌شود. */
  activeSymbol?: string;
  className?: string;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

interface TileChromeProps {
  id: string;
  panel: TechnicalPanelKind;
  focused: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onSwap: (id: string, dir: 'left' | 'right' | 'up' | 'down') => void;
  onDragStart: (id: string) => void;
  onDropTile: (targetId: string) => void;
}

const TileChrome: React.FC<TileChromeProps> = ({
  id, panel, focused, onFocus, onClose, onSwap, onDragStart, onDropTile,
}) => (
  <div
    data-testid={`tw-tile-${id}`}
    data-tile-panel={panel}
    onMouseDown={() => onFocus(id)}
    onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; }}
    onDrop={(event) => { event.preventDefault(); onDropTile(id); }}
    style={{
      minWidth: panel === 'chart' ? 480 : 320,
      minHeight: panel === 'chart' ? 320 : 240,
    }}
    className={`relative flex h-full min-h-0 min-w-0 flex-col bg-panel overflow-hidden ${
      focused ? 'outline outline-1 outline-accent' : ''
    }`}
  >
    <div
      data-testid={`tw-tile-header-${id}`}
      draggable
      tabIndex={0}
      role="group"
      aria-label={`پنل ${PANEL_KIND_LABEL[panel]}`}
      onFocus={() => onFocus(id)}
      onDragStart={(event) => {
        event.dataTransfer.setData('text/plain', id);
        event.dataTransfer.effectAllowed = 'move';
        onDragStart(id);
      }}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') { event.preventDefault(); onSwap(id, 'left'); }
        if (event.key === 'ArrowRight') { event.preventDefault(); onSwap(id, 'right'); }
        if (event.key === 'ArrowUp') { event.preventDefault(); onSwap(id, 'up'); }
        if (event.key === 'ArrowDown') { event.preventDefault(); onSwap(id, 'down'); }
      }}
      className="flex h-7 flex-none items-center gap-2 border-b border-line bg-panel-2 px-2 text-xs text-text-2 cursor-grab select-none outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      <span className="truncate">{PANEL_KIND_LABEL[panel]}</span>
      {focused ? (
        <span className="text-xs text-text-3 whitespace-nowrap">با ←→↑↓ جابه‌جا کن</span>
      ) : null}
      {panel !== 'chart' ? (
        <button
          type="button"
          data-testid={`tw-tile-close-${id}`}
          aria-label={`بستن پنل ${PANEL_KIND_LABEL[panel]}`}
          title="بستن پنل"
          onClick={(event) => { event.stopPropagation(); onClose(id); }}
          className="ms-auto grid h-6 w-6 flex-none place-items-center rounded-[var(--radius-xs)] text-sm text-text-3 hover:text-accent hover:bg-panel-3 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          ×
        </button>
      ) : null}
    </div>

    <div className="min-h-0 flex-1 overflow-hidden">
      <WorkspacePanelHost kind={panel} />
    </div>
  </div>
);

export const WorkspaceShell: React.FC<WorkspaceShellProps> = ({
  activeSymbol,
  className = '',
}) => {
  const storedSymbol = useTechnicalStore((s) => s.selectedSymbol);
  const symbol = activeSymbol || storedSymbol;

  const root = useTechnicalWorkspaceStore((s) => s.root);
  const close = useTechnicalWorkspaceStore((s) => s.close);
  const swap = useTechnicalWorkspaceStore((s) => s.swap);
  const swapPanels = useTechnicalWorkspaceStore((s) => s.swapPanels);
  const setRatio = useTechnicalWorkspaceStore((s) => s.setRatio);
  const undo = useTechnicalWorkspaceStore((s) => s.undo);
  const redo = useTechnicalWorkspaceStore((s) => s.redo);

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [focusedTile, setFocusedTile] = useState<string | null>(null);
  const [draggedTile, setDraggedTile] = useState<string | null>(null);
  const treeRoot = useRef<HTMLDivElement>(null);

  // میان‌برهای سراسری میزکار: Ctrl+K پالت، Ctrl+Z/Shift+Z undo/redo، Esc بستن.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      const mod = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();
      if (mod && !event.shiftKey && key === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
        return;
      }
      if (mod && !event.shiftKey && key === 'z') {
        event.preventDefault();
        undo();
        return;
      }
      if (mod && event.shiftKey && key === 'z') {
        event.preventDefault();
        redo();
        return;
      }
      if (event.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo]);

  function renderNode(node: LayoutNode<TechnicalPanelKind>): React.ReactNode {
    if (node.kind === 'tile') {
      return (
        <TileChrome
          key={node.id}
          id={node.id}
          panel={node.panel}
          focused={focusedTile === node.id}
          onFocus={setFocusedTile}
          onClose={close}
          onSwap={swap}
          onDragStart={setDraggedTile}
          onDropTile={(targetId) => {
            if (draggedTile && draggedTile !== targetId) swapPanels(draggedTile, targetId);
            setDraggedTile(null);
          }}
        />
      );
    }

    const resize = (ratio: number) => {
      const rect = treeRoot.current?.getBoundingClientRect();
      setRatio(node.id, ratio, rect?.width ?? 0, rect?.height ?? 0);
    };

    return (
      <div
        key={node.id}
        className={node.dir === 'row'
          ? 'flex h-full min-h-0 min-w-0'
          : 'flex h-full min-h-0 min-w-0 flex-col'}
      >
        <div className="min-h-0 min-w-0" style={{ flex: `${node.ratio} 1 0%` }}>
          {renderNode(node.first)}
        </div>
        <Splitter dir={node.dir} container={treeRoot} onRatio={resize} />
        <div className="min-h-0 min-w-0" style={{ flex: `${1 - node.ratio} 1 0%` }}>
          {renderNode(node.second)}
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="workspace-shell"
      className={`workspace-grid w-full h-full min-h-0 min-w-0 ${className}`}
      dir="ltr"
      style={{
        display: 'grid',
        gridTemplateColumns: WORKSPACE_GRID_TEMPLATE_COLUMNS,
        gridTemplateRows: WORKSPACE_GRID_TEMPLATE_ROWS,
        gridTemplateAreas: WORKSPACE_GRID_TEMPLATE_AREAS,
      }}
    >
      <WorkspaceTopbar onOpenPalette={() => setPaletteOpen(true)} />

      <ActivityBar />

      <section
        aria-label="ناحیهٔ پنل‌های میزکار"
        data-testid="workspace-dock"
        style={{ gridArea: 'dock' }}
        className="h-full min-h-0 min-w-0 overflow-hidden border-s border-line bg-bg"
        dir="rtl"
      >
        <div ref={treeRoot} className="h-full min-h-0 w-full min-w-0">
          {renderNode(root)}
          {/* نماد در استور همگام است؛ این span فقط برای دسترس‌پذیری نام نماد است. */}
          <span className="sr-only">{symbol}</span>
        </div>
      </section>

      {paletteOpen ? <CommandPalette onClose={() => setPaletteOpen(false)} /> : null}
    </div>
  );
};
