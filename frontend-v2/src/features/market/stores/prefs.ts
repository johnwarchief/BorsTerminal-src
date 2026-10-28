import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AssetType } from '../lib/assetType';
import { DEFAULT_ASSET_TYPES } from '../lib/assetDefaults';
import { DEFAULT_BOARD_FILTER_VALUES, type BoardFilterValues } from '../lib/boardFilters';
import { defaultColumns, type ColumnKey, type ProfileKey, type SortDir, type SortKey } from '../lib/columns';
import type { TapeKey } from '../lib/tapeFilters';

export type Density = 'compact' | 'normal' | 'comfortable';

export interface BoardViewState {
  query: string;
  sortKey: SortKey;
  sortDir: SortDir;
  profile: ProfileKey;
  density: Density;
  quickFilters: TapeKey[];
  quickLogic: 'and' | 'or';
  assetTypes: AssetType[];
  visibleColumns: ColumnKey[];
  filters: BoardFilterValues;
  pollMs: number;
}

export interface SavedBoardView {
  name: string;
  state: BoardViewState;
}

interface MarketPrefs {
  profile: ProfileKey;
  density: Density;
  quickFilters: TapeKey[];
  quickLogic: 'and' | 'or';
  assetTypes: AssetType[];
  visibleColumns: ColumnKey[];
  filters: BoardFilterValues;
  pollMs: number;
  savedViews: SavedBoardView[];
  setProfile: (profile: ProfileKey) => void;
  setDensity: (density: Density) => void;
  toggleQuickFilter: (tape: TapeKey) => void;
  clearQuickFilters: () => void;
  setQuickLogic: (logic: 'and' | 'or') => void;
  setAssetTypes: (types: AssetType[]) => void;
  toggleColumn: (column: ColumnKey) => void;
  setFilters: (patch: Partial<BoardFilterValues>) => void;
  setPollMs: (ms: number) => void;
  saveView: (name: string, state: BoardViewState) => void;
  restoreView: (name: string) => BoardViewState | null;
  deleteView: (name: string) => void;
}

function copyView(state: BoardViewState): BoardViewState {
  return {
    ...state,
    quickFilters: [...state.quickFilters],
    assetTypes: [...state.assetTypes],
    visibleColumns: [...state.visibleColumns],
    filters: { ...state.filters },
  };
}

export const useMarketPrefs = create<MarketPrefs>()(
  persist(
    (set, get) => ({
      profile: 'general',
      density: 'compact',
      quickFilters: [],
      quickLogic: 'and',
      assetTypes: [...DEFAULT_ASSET_TYPES],
      visibleColumns: defaultColumns('general'),
      filters: { ...DEFAULT_BOARD_FILTER_VALUES },
      pollMs: 5_000,
      savedViews: [],
      setProfile: (profile) => set({ profile, visibleColumns: defaultColumns(profile) }),
      setDensity: (density) => set({ density }),
      toggleQuickFilter: (tape) => set((state) => ({
        quickFilters: state.quickFilters.includes(tape)
          ? state.quickFilters.filter((key) => key !== tape)
          : [...state.quickFilters, tape],
      })),
      clearQuickFilters: () => set({ quickFilters: [] }),
      setQuickLogic: (quickLogic) => set({ quickLogic }),
      setAssetTypes: (assetTypes) => set({ assetTypes }),
      toggleColumn: (column) => set((state) => ({
        visibleColumns: state.visibleColumns.includes(column)
          ? state.visibleColumns.filter((key) => key !== column)
          : [...state.visibleColumns, column],
      })),
      setFilters: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
      setPollMs: (pollMs) => set({ pollMs }),
      saveView: (name, state) => {
        const trimmed = name.trim();
        if (!trimmed) return;
        const saved = { name: trimmed, state: copyView(state) };
        set((current) => ({
          savedViews: current.savedViews.some((view) => view.name === trimmed)
            ? current.savedViews.map((view) => view.name === trimmed ? saved : view)
            : [...current.savedViews, saved],
        }));
      },
      restoreView: (name) => {
        const saved = get().savedViews.find((view) => view.name === name);
        if (!saved) return null;
        const state = copyView(saved.state);
        set({
          profile: state.profile,
          density: state.density,
          quickFilters: state.quickFilters,
          quickLogic: state.quickLogic,
          assetTypes: state.assetTypes,
          visibleColumns: state.visibleColumns,
          filters: state.filters,
          pollMs: state.pollMs,
        });
        return state;
      },
      deleteView: (name) => set((state) => ({
        savedViews: state.savedViews.filter((view) => view.name !== name),
      })),
    }),
    { name: 'bors-market-v2' },
  ),
);
