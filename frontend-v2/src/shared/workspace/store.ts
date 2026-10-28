import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, findTile, isValidLayout, splitTile, swapWithNeighbor,
  type LayoutNode, type MoveDir, type SplitDir, type TilePanel,
} from './layout';
import { CHART_SHARE, DOCK_HEIGHT, SIDE_WIDTH } from './sizes';

export type CardId =
  | 'tedpix' | 'retailValue' | 'breadth' | 'boardValueComposition'
  | 'boardVolume' | 'marketTrades';

export const DEFAULT_SLOTS: CardId[] = ['tedpix', 'retailValue', 'breadth', 'boardValueComposition'];

export interface Workspace {
  id: string;
  name: string;
  layout: LayoutNode;
  slots: CardId[];
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  sideCollapsed: boolean;
  sideWidth: number;
  dockHeight: number;
  chartShare: number;
  updatedAt: number;
}

interface WorkspaceStore {
  version: 2;
  activeWorkspaceId: string;
  activeSymbol: string | null;
  pinned: Record<string, string | null>;
  workspaces: Workspace[];
  history: LayoutNode[];
  undo: () => void;
  split: (tileId: string, dir: SplitDir, panel: TilePanel) => void;
  close: (tileId: string) => void;
  swap: (tileId: string, dir: MoveDir) => void;
  setRatio: (splitId: string, ratio: number, width: number, height: number) => void;
  setSlots: (slots: CardId[]) => void;
  setActiveSymbol: (key: string | null) => void;
  setChartOpen: (open: boolean) => void;
  setFundamentalsOpen: (open: boolean) => void;
  setSideCollapsed: (collapsed: boolean) => void;
  setSideWidth: (width: number) => void;
  setDockHeight: (height: number) => void;
  setChartShare: (share: number) => void;
  toggleFollow: (tileId: string) => void;
  resetLayout: () => void;
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

const DEFAULT_WORKSPACE: Workspace = {
  id: 'ws-tablo', name: 'تابلوخوانی', layout: DEFAULT_LAYOUT,
  slots: DEFAULT_SLOTS, chartOpen: true,
  fundamentalsOpen: true, sideCollapsed: false,
  sideWidth: SIDE_WIDTH.default, dockHeight: DOCK_HEIGHT.default,
  chartShare: CHART_SHARE.default,
  updatedAt: 0,
};

const ALLOWED_CARDS: CardId[] = ['tedpix', 'retailValue', 'breadth', 'boardValueComposition',
  'boardVolume', 'marketTrades'];

function cleanSlots(slots: unknown): CardId[] {
  const list = Array.isArray(slots) ? slots : [];
  const out: CardId[] = [];
  for (const slot of list) {
    if (ALLOWED_CARDS.includes(slot as CardId) && !out.includes(slot as CardId)) out.push(slot as CardId);
  }
  return out.slice(0, 5);
}

function readPinned(value: unknown): Record<string, string | null> {
  const pinned: Record<string, string | null> = {};
  if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (typeof item === 'string') pinned[key] = item;
    }
  }
  return pinned;
}

export function sanitizeWorkspace(persisted: unknown): Workspace | null {
  if (!persisted || typeof persisted !== 'object') return null;
  const persistedVersion = Number((persisted as { version?: unknown }).version ?? 1);
  if (persistedVersion !== 1 && persistedVersion !== 2) return null;
  const raw = persisted as { workspaces?: unknown };
  const list = Array.isArray(raw.workspaces) ? raw.workspaces : [];
  const first = list[0] as Partial<Workspace> | undefined;
  if (!first || !isValidLayout(first.layout)) return null;
  const slots = cleanSlots(first.slots);
  return {
    id: typeof first.id === 'string' ? first.id : 'ws-tablo',
    name: typeof first.name === 'string' ? first.name : 'تابلوخوانی',
    layout: first.layout,
    slots: slots.length >= 3 ? slots : DEFAULT_SLOTS,
    chartOpen: first.chartOpen !== false,
    fundamentalsOpen: first.fundamentalsOpen !== false,
    sideCollapsed: first.sideCollapsed === true,
    sideWidth: clampNumber(first.sideWidth, SIDE_WIDTH.min, SIDE_WIDTH.max, SIDE_WIDTH.default),
    dockHeight: clampNumber(first.dockHeight, DOCK_HEIGHT.min, DOCK_HEIGHT.max, DOCK_HEIGHT.default),
    chartShare: clampNumber(first.chartShare, CHART_SHARE.min, CHART_SHARE.max, CHART_SHARE.default),
    updatedAt: Number(first.updatedAt ?? 0),
  };
}

export const useWorkspace = create<WorkspaceStore>()(
  persist(
    (set, get) => {
      const patch = (layout: LayoutNode, extra: Partial<Workspace> = {}) => {
        const ws = get().workspaces[0];
        set({
          history: [...get().history.slice(-9), ws.layout],
          workspaces: [{ ...ws, layout, ...extra, updatedAt: Date.now() }],
        });
      };

      const update = (extra: Partial<Workspace>) => {
        const ws = get().workspaces[0];
        set({ workspaces: [{ ...ws, ...extra, updatedAt: Date.now() }] });
      };

      return {
        version: 2,
        activeWorkspaceId: DEFAULT_WORKSPACE.id,
        activeSymbol: null,
        pinned: {},
        workspaces: [DEFAULT_WORKSPACE],
        history: [],
        undo: () => {
          const past = get().history;
          if (past.length === 0) return;
          const ws = get().workspaces[0];
          set({
            history: past.slice(0, -1),
            workspaces: [{ ...ws, layout: past[past.length - 1], updatedAt: Date.now() }],
          });
        },
        split: (tileId, dir, panel) => {
          const next = splitTile(get().workspaces[0].layout, tileId, dir, panel);
          if (next) patch(next);
        },
        close: (tileId) => {
          const next = closeTile(get().workspaces[0].layout, tileId);
          if (next) patch(next);
        },
        swap: (tileId, dir) => {
          const moved = swapWithNeighbor(get().workspaces[0].layout, tileId, dir);
          if (moved) patch(moved.root);
        },
        setRatio: (splitId, ratio, width, height) => {
          const walk = (node: LayoutNode): LayoutNode => {
            if (node.kind === 'tile') return node;
            if (node.id === splitId) {
              const next = clampRatio(node, ratio, width, height);
              return next === null ? node : { ...node, ratio: next };
            }
            return { ...node, first: walk(node.first), second: walk(node.second) };
          };
          patch(walk(get().workspaces[0].layout));
        },
        setSlots: (slots) => {
          const clean = cleanSlots(slots);
          if (clean.length < 3) return;
          const ws = get().workspaces[0];
          set({ workspaces: [{ ...ws, slots: clean, updatedAt: Date.now() }] });
        },
        setActiveSymbol: (activeSymbol) => set({ activeSymbol }),
        setChartOpen: (chartOpen) => update({ chartOpen }),
        setFundamentalsOpen: (fundamentalsOpen) => update({ fundamentalsOpen }),
        setSideCollapsed: (sideCollapsed) => update({ sideCollapsed }),
        setSideWidth: (sideWidth) => update({
          sideWidth: clampNumber(sideWidth, SIDE_WIDTH.min, SIDE_WIDTH.max, SIDE_WIDTH.default),
        }),
        setDockHeight: (dockHeight) => update({
          dockHeight: clampNumber(dockHeight, DOCK_HEIGHT.min, DOCK_HEIGHT.max, DOCK_HEIGHT.default),
        }),
        setChartShare: (chartShare) => update({
          chartShare: clampNumber(chartShare, CHART_SHARE.min, CHART_SHARE.max, CHART_SHARE.default),
        }),
        toggleFollow: (tileId) => {
          const ws = get().workspaces[0];
          const tile = findTile(ws.layout, tileId);
          if (!tile) return;
          const nextFollow = !tile.follow;
          const walk = (node: LayoutNode): LayoutNode => {
            if (node.kind === 'tile') {
              return node.id === tileId ? { ...node, follow: nextFollow } : node;
            }
            return { ...node, first: walk(node.first), second: walk(node.second) };
          };
          const pinned = { ...get().pinned };
          if (nextFollow) delete pinned[tileId];
          else pinned[tileId] = get().activeSymbol;
          set({
            pinned,
            workspaces: [{ ...ws, layout: walk(ws.layout), updatedAt: Date.now() }],
          });
        },
        resetLayout: () => patch(DEFAULT_LAYOUT),
      };
    },
    {
      name: 'bors-workspace-v1',
      version: 2,
      // تنها نرمال‌ساز merge() است؛ این فقط پیامِ ناسازگاریِ نسخه را خاموش می‌کند.
      migrate: (persisted) => persisted as never,
      partialize: (state) => ({
        version: state.version,
        activeWorkspaceId: state.activeWorkspaceId,
        activeSymbol: state.activeSymbol,
        pinned: state.pinned,
        workspaces: state.workspaces,
      }),
      merge: (persisted, current) => {
        const raw = (persisted ?? {}) as { activeSymbol?: unknown; pinned?: unknown };
        const activeSymbol = typeof raw.activeSymbol === 'string' ? raw.activeSymbol : null;
        const pinned = readPinned(raw.pinned);
        const ws = sanitizeWorkspace(persisted);
        if (!ws) return { ...current, activeSymbol, pinned };
        return {
          ...current,
          activeWorkspaceId: ws.id,
          workspaces: [ws],
          activeSymbol,
          pinned,
        };
      },
    },
  ),
);

export const getWorkspace = (): Workspace => useWorkspace.getState().workspaces[0];
