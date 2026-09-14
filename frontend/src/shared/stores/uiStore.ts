// shared/stores/uiStore.ts -- تم و سایدبار سراسری
// اینجا نگه داشته می شود چون همه فیچرها (چارت تکنیکال و غیره) به تم نیاز دارند.
import { create } from 'zustand';

type UiState = {
  theme: 'dark' | 'light';
  sidebarOpen: boolean;
  toggleTheme: () => void;
  setTheme: (t: 'dark' | 'light') => void;
  toggleSidebar: () => void;
};

const STORAGE_KEY = 'bors-theme';

function initialTheme(): 'dark' | 'light' {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === 'light' ? 'light' : 'dark';
}

function applyTheme(t: 'dark' | 'light') {
  document.documentElement.dataset.theme = t;
}

export const useUiStore = create<UiState>((set, get) => ({
  theme: initialTheme(),
  sidebarOpen: true,
  toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
  setTheme: (t) => {
    applyTheme(t);
    localStorage.setItem(STORAGE_KEY, t);
    set({ theme: t });
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));

applyTheme(useUiStore.getState().theme);
