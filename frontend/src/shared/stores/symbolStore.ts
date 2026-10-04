// shared/stores/symbolStore.ts -- نماد انتخابی سراسری + اخیرها + pinnedها
// الگوی TradingView/Notion: سوییچرِ context از فهرستِ شخصیِ کاربر تغذیه می‌شود؛
// «اخیر» با هر انتخاب واقعی نوشته می‌شود (نه بازدیدِ خودکار) و «pinned» را
// خودِ کاربر تعیین می‌کند. همه درِ localStorage همین دستگاه — بی‌سمتِ سرور.
import { create } from 'zustand';

const STORAGE_KEY = ['bors', 'symbol'].join('-');
const RECENT_KEY = ['bors', 'symbol', 'recent'].join('-');
const PIN_KEY = ['bors', 'symbol', 'pinned'].join('-');
const RECENT_MAX = 8;

function read(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

function readList(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const p = JSON.parse(raw);
    return Array.isArray(p) ? p.filter((x) => typeof x === 'string' && x) : [];
  } catch {
    return [];
  }
}

function writeList(key: string, list: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(list));
  } catch {
    /* حافظه در دسترس نیست -- فقط state به‌روز می‌شود */
  }
}

type SymbolState = {
  /** نماد جاری -- خالی یعنی هنوز انتخاب نشده */
  symbol: string;
  recent: string[];
  pinned: string[];
  setSymbol: (s: string) => void;
  clearSymbol: () => void;
  togglePin: (s: string) => void;
};

export const useSymbolStore = create<SymbolState>((set, get) => ({
  symbol: read(),
  recent: readList(RECENT_KEY),
  pinned: readList(PIN_KEY),
  setSymbol: (s) => {
    try {
      localStorage.setItem(STORAGE_KEY, s);
    } catch {
      // حافظه در دسترس نیست -- فقط state به روز می شود
    }
    const recent = [s, ...get().recent.filter((x) => x !== s)].slice(0, RECENT_MAX);
    writeList(RECENT_KEY, recent);
    set({ symbol: s, recent });
  },
  clearSymbol: () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // نادیده بگیر
    }
    set({ symbol: '' });
  },
  togglePin: (s) => {
    const cur = get().pinned;
    const next = cur.includes(s) ? cur.filter((x) => x !== s) : [s, ...cur].slice(0, RECENT_MAX * 2);
    writeList(PIN_KEY, next);
    set({ pinned: next });
  },
}));
