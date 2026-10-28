import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, findTile, isValidLayout, splitTile, swapWithNeighbor,
  type LayoutNode, type MoveDir, type SplitDir, type TilePanel,
} from './layout';

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
  updatedAt: number;
}

interface WorkspaceStore {
  version: 1;
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
  toggleFollow: (tileId: string) => void;
  resetLayout: () => void;
}

const DEFAULT_WORKSPACE: Workspace = {
  id: 'ws-tablo', name: 'تابلوخوانی', layout: DEFAULT_LAYOUT,
  slots: DEFAULT_SLOTS, chartOpen: true, updatedAt: 0,
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

export function sanitizeWorkspace(persisted: unknown): Workspace | null {
  if (!persisted || typeof persisted !== 'object') return null;
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

      return {
        version: 1,
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
        setChartOpen: (chartOpen) => {
          const ws = get().workspaces[0];
          set({ workspaces: [{ ...ws, chartOpen, updatedAt: Date.now() }] });
        },
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
      version: 1,
      partialize: (state) => ({
        version: state.version,
        activeWorkspaceId: state.activeWorkspaceId,
        activeSymbol: state.activeSymbol,
        pinned: state.pinned,
        workspaces: state.workspaces,
      }),
      merge: (persisted, current) => {
        const ws = sanitizeWorkspace(persisted);
        if (!ws) return current;
        const raw = persisted as { activeSymbol?: unknown; pinned?: unknown };
        const pinned: Record<string, string | null> = {};
        if (raw.pinned && typeof raw.pinned === 'object') {
          for (const [key, value] of Object.entries(raw.pinned as Record<string, unknown>)) {
            if (typeof value === 'string') pinned[key] = value;
          }
        }
        return {
          ...current,
          activeWorkspaceId: ws.id,
          workspaces: [ws],
          activeSymbol: typeof raw.activeSymbol === 'string' ? raw.activeSymbol : null,
          pinned,
        };
      },
    },
  ),
);

export const getWorkspace = (): Workspace => useWorkspace.getState().workspaces[0];
