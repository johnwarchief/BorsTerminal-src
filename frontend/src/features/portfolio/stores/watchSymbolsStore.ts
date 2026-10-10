// features/portfolio/stores/watchSymbolsStore.ts -- فهرستِ نمادهایِ «دیده‌بان بازار»
//
// ماندگاری درِ localStorageِ همین دستگاه، دقیقاً با همان الگویِ این feature
// (`bors-portfolio-target` درِ targetAllocation.ts؛ کلیدِ `bors-` پیشوندِ
// symbolStore.ts). این فهرستِ رصدِ شخصیِ کاربر است و با واچ‌لیستِ سرور
// (`/api/watchlist`) یکی نیست: آن فهرست درِ پنج سطح ستاره می‌خورد، این فهرست
// فقط زیرتبِ «دیده‌بان بازار» را تغذیه می‌کند و هیچ درخواستِ تازه‌ای نمی‌سازد.
// نمادهایِ دیده‌بان هرگز «داراییِ پرتفوی» حساب نمی‌شوند (منبعِ داده جدا:
// همین store، نه usePortfolio).
import { create } from 'zustand';
import { normalizeFa } from '@shared/lib/normalizeFa';

const STORAGE_KEY = 'bors-portfolio-watch';
/** سقفِ رصد — همان مرتبۀِ USER_WATCHLIST_MAXِ بک‌اند؛ بی‌سقفِ بی‌نهایت جدول بی‌فایده است */
export const WATCH_MAX = 60;

function readList(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === 'string' && x.trim() !== '').slice(0, WATCH_MAX);
  } catch {
    return [];
  }
}

function writeList(list: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    /* حافظه در دسترس نیست -- فقط state به‌روز می‌شود */
  }
}

/** حذفِ تکرار با کلیدِ نرمال (املایِ عربی/فارسی یک نمادند — مثلِ بک‌اند) */
function dedupe(list: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of list) {
    const norm = normalizeFa(s);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push(s.trim());
  }
  return out.slice(0, WATCH_MAX);
}

type WatchSymbolsState = {
  symbols: string[];
  /** افزودن به ابتدای فهرست؛ نمادِ تکراری (با املایِ نرمال) جا نمی‌نشیند */
  add: (symbol: string) => void;
  remove: (symbol: string) => void;
  /** جایگزینیِ کامل — فقط برایِ بازیابی/تست */
  setList: (list: string[]) => void;
};

export const useWatchSymbolsStore = create<WatchSymbolsState>((set, get) => ({
  symbols: readList(),
  add: (symbol) => {
    const s = (symbol ?? '').trim();
    if (!s) return;
    const next = dedupe([s, ...get().symbols]);
    writeList(next);
    set({ symbols: next });
  },
  remove: (symbol) => {
    const norm = normalizeFa(symbol);
    const next = get().symbols.filter((x) => normalizeFa(x) !== norm);
    writeList(next);
    set({ symbols: next });
  },
  setList: (list) => {
    const next = dedupe(list);
    writeList(next);
    set({ symbols: next });
  },
}));

/** عضویتِ یک نماد درِ فهرستِ رصد — با کلیدِ نرمال */
export function isWatched(symbol: string | null | undefined): boolean {
  if (!symbol) return false;
  const norm = normalizeFa(symbol);
  return useWatchSymbolsStore.getState().symbols.some((x) => normalizeFa(x) === norm);
}
