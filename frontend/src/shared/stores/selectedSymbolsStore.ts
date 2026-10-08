// shared/stores/selectedSymbolsStore.ts — انتخابِ چندنمادیِ مشترکِ رابط
//
// چرا این فایل هست: تا پیش از این «انتخابِ نماد» یعنی یک رشتهٔ یکتا درِ
// `symbolStore` (نمادِ جاریِ صفحه). taskِ مالک یک selectionِ چندتایی می‌خواهد که
// درِ تابلو، بنیادی، قیف و سایدبار یکی باشد (§۲۱: «Market و Fundamental باید
// selection behavior یکسان داشته باشند»). این store فقط همان فهرستِ انتخاب است —
// داوریِ FTS اینجا نیست و با واچ‌لیست هم قاطی نمی‌شود:
//   selection  = موقتی، درِ همین دستگاه، بی‌سرور      (این فایل)
//   watchlist  = ماندگار، درِ `user_watchlists` بک‌اند (api/watchlist.py)
//
// هویت: کلیدِ canonical `normalizeFa(symbol)` است — همان قراردادِ soft-identityِ
// `user_watchlists` درِ بک‌اند (`watchlist_store.py:12-16` که ردیفِ تکراریِ هم‌نام را
// از املایِ عربی/فارسی می‌سازد). `insCode` هم کنارش حفظ می‌شود، چون رشتهٔ نمایشی
// ممکن است عوض شود یا دو ابزارِ هم‌نام داشته باشیم (§۲۲، §۲۳).

import { create } from 'zustand';
import { normalizeFa } from '@shared/lib/normalizeFa';

const STORAGE_KEY = ['bors', 'selected-symbols', 'v1'].join('-');

export type SelectedSymbol = {
  /** کلیدِ canonical — `normalizeFa(symbol)` */
  norm: string;
  /** همان چیزی که کاربر دیده و رویِ آن زده است */
  symbol: string;
  name: string;
  /** هر جا درِ ردیف باشد؛ نبودش `null` است، نه رشتهٔ ساختگی */
  insCode: string | null;
  addedAt: number;
};

export type SelectionInput = { symbol: string; name?: string; insCode?: string | null };

function read(): SelectedSymbol[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const p = JSON.parse(raw) as unknown;
    if (!Array.isArray(p)) return [];
    return p
      .filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
      .map((x) => {
        const symbol = typeof x.symbol === 'string' ? x.symbol : '';
        const norm = typeof x.norm === 'string' && x.norm ? x.norm : normalizeFa(symbol);
        if (!norm) return null;
        return {
          norm,
          symbol: symbol || norm,
          name: typeof x.name === 'string' ? x.name : '',
          insCode: typeof x.insCode === 'string' && x.insCode ? x.insCode : null,
          addedAt: typeof x.addedAt === 'number' ? x.addedAt : 0,
        } as SelectedSymbol;
      })
      .filter((x): x is SelectedSymbol => !!x);
  } catch {
    return [];
  }
}

function write(items: SelectedSymbol[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    /* حافظه در دسترس نیست — فقط state عوض می‌شود (مثل بقیۀ storeهایِ این repo) */
  }
}

type SelectionState = {
  items: SelectedSymbol[];
  /** روشن/خاموش کردنِ یک نماد — کلیکِ دوباره از فهرست بیرون می‌اندازد */
  toggle: (input: SelectionInput) => void;
  remove: (symbol: string) => void;
  clear: () => void;
};

export const useSelectedSymbolsStore = create<SelectionState>((set, get) => ({
  items: read(),
  toggle: ({ symbol, name = '', insCode = null }) => {
    const norm = normalizeFa(symbol);
    if (!norm) return;
    const cur = get().items;
    const hit = cur.find((i) => i.norm === norm);
    const next = hit
      ? cur.filter((i) => i.norm !== norm)
      : [...cur, { norm, symbol, name, insCode, addedAt: Date.now() }];
    write(next);
    set({ items: next });
  },
  remove: (symbol) => {
    const norm = normalizeFa(symbol);
    const next = get().items.filter((i) => i.norm !== norm);
    if (next.length === get().items.length) return;
    write(next);
    set({ items: next });
  },
  clear: () => {
    write([]);
    set({ items: [] });
  },
}));

/** تنها راهِ پرسیدنِ «انتخاب شده؟» از داخلِ جدول — بولینِ خالص برمی‌گرداند تا
 *  رندرِ ردیفِ دیگر با هر تغییرِ فهرست تازه نشود. */
export function useIsSelected(symbol: string | null | undefined): boolean {
  const norm = normalizeFa(symbol ?? '');
  return useSelectedSymbolsStore((s) => (norm ? s.items.some((i) => i.norm === norm) : false));
}

export function isSelectedSymbol(symbol: string | null | undefined): boolean {
  const norm = normalizeFa(symbol ?? '');
  if (!norm) return false;
  return useSelectedSymbolsStore.getState().items.some((i) => i.norm === norm);
}
