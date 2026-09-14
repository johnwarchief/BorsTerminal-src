// shared/stores/symbolStore.ts -- نماد انتخابی سراسری
import { create } from 'zustand';

type SymbolState = {
  /** نماد جاری -- خالی یعنی هنوز انتخاب نشده */
  symbol: string;
  setSymbol: (s: string) => void;
  clearSymbol: () => void;
};

const STORAGE_KEY = 'bors-symbol';

function initialSymbol(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

export const useSymbolStore = create<SymbolState>((set) => ({
  symbol: initialSymbol(),
  setSymbol: (s) => {
    try {
      localStorage.setItem(STORAGE_KEY, s);
    } catch {
      // حافظه در دسترس نیست -- فقط state به روز می شود
    }
    set({ symbol: s });
  },
  clearSymbol: () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // نادیده بگیر
    }
    set({ symbol: '' });
  },
}));
