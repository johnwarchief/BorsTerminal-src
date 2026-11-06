/**
 * frontend-v2/src/features/technical/workspace/technicalWorkspaceStore.ts
 *
 * استور میزکار ۲.۰ (E1): سه مود، چیدمان‌های نام‌دار، داکینگ چهارپنلی و
 * undo/redo. عملیات درخت از `@shared/workspace/layout` می‌آید (بدون منطق موازی).
 * کلید persist جداست (`bors-technical-workspace-v2`) تا `bors-workspace-v1`
 * میزکار بازار دست‌نخورده بماند.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  closeTile, depthOf, panelsInOrder, splitTile, swapTiles as swapTilePanels, swapWithNeighbor,
  type LayoutNode, type MoveDir, type SplitDir,
} from '@shared/workspace/layout';
import { TECHNICAL_LIMITS } from '@shared/workspace/types';
import {
  MODE_LABEL, TECHNICAL_PANEL_MIN, WORKSPACE_MODES,
  clampTechnicalRatio, cloneLayout, initialLayouts, panelKindsOf,
  type NamedLayout, type TechnicalPanelKind, type WorkspaceMode,
} from './presets';

const MAX_HISTORY = 20;

const PANEL_KINDS = Object.keys(TECHNICAL_PANEL_MIN) as TechnicalPanelKind[];

type TechnicalRoot = LayoutNode<TechnicalPanelKind>;

export interface TechnicalWorkspaceData {
  mode: WorkspaceMode;
  root: TechnicalRoot;
  layouts: Record<WorkspaceMode, NamedLayout[]>;
  activeLayoutId: string;
  undoStacks: Record<WorkspaceMode, TechnicalRoot[]>;
  redoStacks: Record<WorkspaceMode, TechnicalRoot[]>;
}

export interface TechnicalWorkspaceState extends TechnicalWorkspaceData {
  setMode: (mode: WorkspaceMode) => void;
  saveLayout: (name: string) => string;
  loadLayout: (id: string) => void;
  split: (tileId: string, dir: SplitDir, panel: TechnicalPanelKind) => void;
  close: (tileId: string) => void;
  swap: (tileId: string, dir: MoveDir) => void;
  swapPanels: (tileId: string, targetId: string) => void;
  setRatio: (splitId: string, ratio: number, width: number, height: number) => void;
  togglePanel: (panel: TechnicalPanelKind) => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
  panelKindsOf: (root: TechnicalRoot) => Record<string, TechnicalPanelKind>;
}

function emptyStacks(): Record<WorkspaceMode, TechnicalRoot[]> {
  return { analysis: [], scan: [], research: [] };
}

export function getInitialTechnicalState(): TechnicalWorkspaceData {
  const layouts = initialLayouts();
  return {
    mode: 'analysis',
    root: cloneLayout(layouts.analysis[0]!.root),
    layouts,
    activeLayoutId: layouts.analysis[0]!.id,
    undoStacks: emptyStacks(),
    redoStacks: emptyStacks(),
  };
}

function isValidTechnicalRoot(node: unknown): node is TechnicalRoot {
  let tiles = 0;
  let charts = 0;

  function walk(n: unknown, depth: number): boolean {
    if (!n || typeof n !== 'object') return false;
    const item = n as Record<string, unknown>;
    if (item.kind === 'tile') {
      tiles += 1;
      if (!PANEL_KINDS.includes(item.panel as TechnicalPanelKind)) return false;
      if (item.panel === 'chart') charts += 1;
      return typeof item.id === 'string' && typeof item.follow === 'boolean';
    }
    if (item.kind === 'split') {
      if (depth >= TECHNICAL_LIMITS.maxDepth) return false;
      const ratio = Number(item.ratio);
      if (!(ratio >= 0.05 && ratio <= 0.95)) return false;
      if (item.dir !== 'row' && item.dir !== 'col') return false;
      return walk(item.first, depth + 1) && walk(item.second, depth + 1);
    }
    return false;
  }

  return walk(node, 1)
    && charts === 1
    && tiles <= TECHNICAL_LIMITS.maxTiles
    && depthOf(node as TechnicalRoot) <= TECHNICAL_LIMITS.maxDepth;
}

function sanitizeLayout(value: unknown, fallbackMode: WorkspaceMode): NamedLayout | null {
  if (!value || typeof value !== 'object') return null;
  const raw = value as Partial<NamedLayout>;
  if (typeof raw.id !== 'string' || raw.id.length === 0) return null;
  if (!isValidTechnicalRoot(raw.root)) return null;
  const mode = WORKSPACE_MODES.includes(raw.mode as WorkspaceMode)
    ? (raw.mode as WorkspaceMode)
    : fallbackMode;
  const root = cloneLayout(raw.root);
  const name = typeof raw.name === 'string' && raw.name.trim().length > 0
    ? raw.name.trim().slice(0, 40)
    : MODE_LABEL[mode];
  return { id: raw.id, name, mode, root, panelKinds: panelKindsOf(root) };
}

/** نرمال‌سازی دادهٔ ذخیره‌شده؛ هر مود همیشه حداقل یک چیدمان معتبر دارد. */
export function sanitizeTechnicalWorkspace(persisted: unknown): TechnicalWorkspaceData | null {
  if (!persisted || typeof persisted !== 'object') return null;
  const raw = persisted as Record<string, unknown>;
  const defaults = initialLayouts();
  const rawLayouts = raw.layouts && typeof raw.layouts === 'object'
    ? (raw.layouts as Record<string, unknown>)
    : {};

  const layouts = {} as Record<WorkspaceMode, NamedLayout[]>;
  for (const mode of WORKSPACE_MODES) {
    const list = Array.isArray(rawLayouts[mode]) ? rawLayouts[mode] : [];
    const clean = list
      .map((item) => sanitizeLayout(item, mode))
      .filter((item): item is NamedLayout => item !== null && item.mode === mode);
    layouts[mode] = clean.length > 0 ? clean : defaults[mode];
  }

  const mode = WORKSPACE_MODES.includes(raw.mode as WorkspaceMode)
    ? (raw.mode as WorkspaceMode)
    : 'analysis';
  const activeLayoutId = typeof raw.activeLayoutId === 'string'
    && layouts[mode].some((layout) => layout.id === raw.activeLayoutId)
    ? raw.activeLayoutId
    : layouts[mode][0]!.id;
  const root = isValidTechnicalRoot(raw.root)
    ? cloneLayout(raw.root)
    : cloneLayout(layouts[mode][0]!.root);

  return { mode, root, layouts, activeLayoutId, undoStacks: emptyStacks(), redoStacks: emptyStacks() };
}

function findSplit(
  node: TechnicalRoot, splitId: string,
): Extract<TechnicalRoot, { kind: 'split' }> | null {
  if (node.kind === 'tile') return null;
  if (node.id === splitId) return node;
  return findSplit(node.first, splitId) ?? findSplit(node.second, splitId);
}

let layoutCounter = 0;
function nextLayoutId(mode: WorkspaceMode): string {
  layoutCounter += 1;
  return `layout-${mode}-${Date.now().toString(36)}-${layoutCounter}`;
}

export const useTechnicalWorkspaceStore = create<TechnicalWorkspaceState>()(
  persist(
    (set, get) => {
      /** ثبت تغییر درخت با فشردنِ وضعیت فعلی روی پشتهٔ undo همان مود. */
      const commit = (next: TechnicalRoot | null) => {
        if (!next) return;
        const state = get();
        set({
          root: next,
          undoStacks: {
            ...state.undoStacks,
            [state.mode]: [...state.undoStacks[state.mode], state.root].slice(-MAX_HISTORY),
          },
          redoStacks: { ...state.redoStacks, [state.mode]: [] },
        });
      };

      return {
        ...getInitialTechnicalState(),

        setMode: (mode) => {
          const state = get();
          if (state.mode === mode) return;
          const target = state.layouts[mode][0];
          if (!target) return;
          set({
            mode,
            root: cloneLayout(target.root),
            activeLayoutId: target.id,
            undoStacks: { ...state.undoStacks, [mode]: [] },
            redoStacks: { ...state.redoStacks, [mode]: [] },
          });
        },

        saveLayout: (name) => {
          const state = get();
          const trimmed = name.trim().slice(0, 40) || `${MODE_LABEL[state.mode]} ${state.layouts[state.mode].length + 1}`;
          const layout: NamedLayout = {
            id: nextLayoutId(state.mode),
            name: trimmed,
            mode: state.mode,
            root: cloneLayout(state.root),
            panelKinds: panelKindsOf(state.root),
          };
          set({
            layouts: { ...state.layouts, [state.mode]: [...state.layouts[state.mode], layout] },
            activeLayoutId: layout.id,
          });
          return layout.id;
        },

        loadLayout: (id) => {
          const state = get();
          for (const mode of WORKSPACE_MODES) {
            const found = state.layouts[mode].find((layout) => layout.id === id);
            if (!found) continue;
            set({
              mode,
              root: cloneLayout(found.root),
              activeLayoutId: found.id,
              undoStacks: { ...state.undoStacks, [mode]: [] },
              redoStacks: { ...state.redoStacks, [mode]: [] },
            });
            return;
          }
        },

        split: (tileId, dir, panel) => {
          const state = get();
          commit(splitTile(state.root, tileId, dir, panel, TECHNICAL_LIMITS));
        },

        close: (tileId) => {
          const state = get();
          commit(closeTile(state.root, tileId, 'chart'));
        },

        swap: (tileId, dir) => {
          const state = get();
          const moved = swapWithNeighbor(state.root, tileId, dir);
          if (moved) commit(moved.root);
        },

        swapPanels: (tileId, targetId) => {
          const state = get();
          const moved = swapTilePanels(state.root, tileId, targetId);
          if (moved) commit(moved.root);
        },

        setRatio: (splitId, ratio, width, height) => {
          const state = get();
          const node = findSplit(state.root, splitId);
          if (!node) return;
          const clamped = clampTechnicalRatio(node, ratio, width, height);
          if (clamped === null) return;
          const walk = (item: TechnicalRoot): TechnicalRoot => {
            if (item.kind === 'tile') return item;
            if (item.id === splitId) return { ...item, ratio: clamped };
            return { ...item, first: walk(item.first), second: walk(item.second) };
          };
          commit(walk(state.root));
        },

        togglePanel: (panel) => {
          if (panel === 'chart') return;
          const state = get();
          const existing = panelsInOrder(state.root).find((tile) => tile.panel === panel);
          if (existing) {
            commit(closeTile(state.root, existing.id, 'chart'));
            return;
          }
          const chart = panelsInOrder(state.root).find((tile) => tile.panel === 'chart');
          if (!chart) return;
          commit(splitTile(state.root, chart.id, 'col', panel, TECHNICAL_LIMITS));
        },

        undo: () => {
          const state = get();
          const stack = state.undoStacks[state.mode];
          if (stack.length === 0) return;
          const previous = stack[stack.length - 1]!;
          set({
            root: previous,
            undoStacks: { ...state.undoStacks, [state.mode]: stack.slice(0, -1) },
            redoStacks: {
              ...state.redoStacks,
              [state.mode]: [...state.redoStacks[state.mode], state.root].slice(-MAX_HISTORY),
            },
          });
        },

        redo: () => {
          const state = get();
          const stack = state.redoStacks[state.mode];
          if (stack.length === 0) return;
          const next = stack[stack.length - 1]!;
          set({
            root: next,
            redoStacks: { ...state.redoStacks, [state.mode]: stack.slice(0, -1) },
            undoStacks: {
              ...state.undoStacks,
              [state.mode]: [...state.undoStacks[state.mode], state.root].slice(-MAX_HISTORY),
            },
          });
        },

        reset: () => set(getInitialTechnicalState()),

        panelKindsOf,
      };
    },
    {
      name: 'bors-technical-workspace-v2',
      version: 1,
      partialize: (state) => ({
        mode: state.mode,
        root: state.root,
        layouts: state.layouts,
        activeLayoutId: state.activeLayoutId,
      }),
      merge: (persisted, current) => {
        const cleaned = sanitizeTechnicalWorkspace(persisted);
        if (!cleaned) return current;
        return { ...current, ...cleaned };
      },
    },
  ),
);
