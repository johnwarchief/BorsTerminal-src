import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'brass' | 'warm' | 'terminal' | 'cool';
export type StatusMode = 'full' | 'ribbon' | 'minimal';

interface UiState {
  collapsed: boolean;
  theme: Theme;
  statusMode: StatusMode;
  toggleSidebar: () => void;
  setTheme: (theme: Theme) => void;
  setStatusMode: (mode: StatusMode) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      collapsed: false,
      theme: 'brass',
      statusMode: 'ribbon',
      toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
      setTheme: (theme) => set({ theme }),
      setStatusMode: (statusMode) => set({ statusMode }),
    }),
    { name: 'bors-ui-v2' },
  ),
);
