import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Density = 'compact' | 'comfortable';
export type Surface = 'paper' | 'ink';
export type SortKey = 'score' | 'symbol' | 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type SortDir = 'asc' | 'desc';

interface FundamentalPrefs {
  density: Density; surface: Surface; sortKey: SortKey; sortDir: SortDir;
  setDensity: (density: Density) => void;
  setSurface: (surface: Surface) => void;
  setSort: (sortKey: SortKey, sortDir: SortDir) => void;
}

export const useFundamentalPrefs = create<FundamentalPrefs>()(
  persist(
    (set) => ({
      density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc',
      setDensity: (density) => set({ density }),
      setSurface: (surface) => set({ surface }),
      setSort: (sortKey, sortDir) => set({ sortKey, sortDir }),
    }),
    { name: 'bors-fundamental-v1' },
  ),
);
