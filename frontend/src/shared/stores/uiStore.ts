// shared/stores/uiStore.ts -- تم و سایدبار سراسری
// اینجا نگه داشته می شود چون همه فیچرها (چارت تکنیکال و غیره) به تم نیاز دارند.
import { create } from 'zustand';

type UiState = {
  theme: 'dark' | 'light';
  sidebarOpen: boolean;
  /** null = جمعشدن خودکار بر اساس اندازهٔ نمایشگر */
  sidebarCollapsed: boolean | null;
  toggleTheme: () => void;
  setTheme: (t: 'dark' | 'light') => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean | null) => void;
};

const STORAGE_KEY = 'bors-theme';

function initialTheme(): 'dark' | 'light' {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === 'light' ? 'light' : 'dark';
}

function applyTheme(t: 'dark' | 'light') {
  document.documentElement.dataset.theme = t;
  if (t === 'dark') {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
  } else {
    document.documentElement.classList.remove('dark');
    document.documentElement.classList.add('light');
  }
}

export const useUiStore = create<UiState>((set, get) => ({
  theme: initialTheme(),
  sidebarOpen: true,
  sidebarCollapsed: null,
  toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
  setTheme: (t) => {
    applyTheme(t);
    localStorage.setItem(STORAGE_KEY, t);
    set({ theme: t });
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
}));

applyTheme(useUiStore.getState().theme);
