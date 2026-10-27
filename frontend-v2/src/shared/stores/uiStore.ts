import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'brass' | 'light';

interface UiState {
  collapsed: boolean;
  theme: Theme;
  toggleSidebar: () => void;
  setTheme: (theme: Theme) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      collapsed: false,
      theme: 'brass',
      toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
      setTheme: (theme) => set({ theme }),
    }),
    { name: 'bors-ui' },
  ),
);
