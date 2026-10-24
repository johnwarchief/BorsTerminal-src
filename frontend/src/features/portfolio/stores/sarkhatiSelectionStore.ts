// features/portfolio/stores/sarkhatiSelectionStore.ts — فهرستِ سرخطیِ ذخیره‌شده
//
// این فهرست با دیده‌بانِ EasyTrader و دیده‌بانِ محلیِ بازار یکی نیست: انتخابِ
// خودِ کاربر برایِ سرخطی است. فقط نماد/منبع/هدف/اولویت/مبلغِ واردشده و زمان‌هایِ
// منابع ذخیره می‌شود؛ هیچ token/cookie یا مقدارِ مالیِ حساب در آن نمی‌نشیند.
import { create } from 'zustand';
import { normalizeFa } from '@shared/lib/normalizeFa';

const KEY = 'bors-sarkhati-selection-v1';
const MAX_ITEMS = 120;

export type SelectionGoal = 'buy' | 'sell' | 'unknown';
export type SelectionSource = 'watchlist' | 'portfolio' | 'market';

export type SelectedSymbol = {
  /** هویتِ پایدار: ISINِ معتبر، وگرنه نمادِ نرمال‌شده. */
  key: string;
  symbol: string;
  name: string;
  isin: string | null;
  ins_code: string | null;
  sources: SelectionSource[];
  goal: SelectionGoal;
  /** بودجهٔ واردشدهٔ کاربر (ریال) — نه قدرت خریدِ کارگزاری */
  amount: string;
};

export type SelectionSourceTimes = {
  watchlist?: string | null;
  portfolio?: string | null;
  buyingPower?: string | null;
};

type Saved = {
  items: SelectedSymbol[];
  savedAt: string | null;
  sourceTimes: SelectionSourceTimes;
};

const SOURCES: SelectionSource[] = ['watchlist', 'portfolio', 'market'];
const GOALS: SelectionGoal[] = ['buy', 'sell', 'unknown'];

/** ISINِ معتبر تنها هویتِ مشترکِ دیده‌بان/پرتفوی است؛ نماد فقط fallbackِ تابلو. */
export function selectionKey(item: { symbol: string; isin?: string | null }): string {
  const isin = String(item.isin ?? '').trim().toUpperCase();
  return isin ? `isin:${isin}` : `sym:${normalizeFa(item.symbol)}`;
}

function cleanItem(value: unknown): SelectedSymbol | null {
  if (!value || typeof value !== 'object') return null;
  const o = value as Record<string, unknown>;
  const symbol = String(o.symbol ?? '').trim();
  if (!symbol) return null;
  const isin = o.isin == null ? null : String(o.isin);
  return {
    key: selectionKey({ symbol, isin }),
    symbol,
    name: String(o.name ?? ''),
    isin,
    ins_code: o.ins_code == null ? null : String(o.ins_code),
    sources: Array.isArray(o.sources)
      ? [...new Set(o.sources.filter((s): s is SelectionSource =>
        SOURCES.includes(s as SelectionSource)))]
      : ['market'],
    goal: GOALS.includes(o.goal as SelectionGoal) ? o.goal as SelectionGoal : 'unknown',
    amount: String(o.amount ?? ''),
  };
}

function read(): Saved {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { items: [], savedAt: null, sourceTimes: {} };
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const items = Array.isArray(parsed.items)
      ? parsed.items.map(cleanItem).filter((x): x is SelectedSymbol => x != null)
        .slice(0, MAX_ITEMS)
      : [];
    const times = parsed.sourceTimes && typeof parsed.sourceTimes === 'object'
      ? parsed.sourceTimes as SelectionSourceTimes : {};
    return { items, savedAt: parsed.savedAt == null ? null : String(parsed.savedAt),
             sourceTimes: times };
  } catch {
    return { items: [], savedAt: null, sourceTimes: {} };
  }
}

function write(items: SelectedSymbol[], savedAt: string,
               sourceTimes: SelectionSourceTimes): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ items, savedAt, sourceTimes }));
  } catch {
    /* پروفایلِ بی‌storage: فقط حافظه، بی‌خطایِ صفحه */
  }
}

type State = {
  items: SelectedSymbol[];
  savedAt: string | null;
  sourceTimes: SelectionSourceTimes;
  dirty: boolean;
  toggle: (item: Omit<SelectedSymbol, 'key' | 'goal' | 'amount'>) => void;
  remove: (key: string) => void;
  clear: () => void;
  setGoal: (key: string, goal: SelectionGoal) => void;
  setAmount: (key: string, amount: string) => void;
  move: (key: string, delta: -1 | 1) => void;
  save: (sourceTimes: SelectionSourceTimes) => void;
};

const initial = read();

export const useSarkhatiSelectionStore = create<State>((set, get) => ({
  items: initial.items,
  savedAt: initial.savedAt,
  sourceTimes: initial.sourceTimes,
  dirty: false,
  toggle: (item) => {
    const symbol = String(item.symbol ?? '').trim();
    if (!symbol) return;
    const key = selectionKey({ symbol, isin: item.isin });
    const current = get().items;
    const exists = current.some((x) => x.key === key);
    const next = exists
      ? current.filter((x) => x.key !== key)
      : [...current, {
        key, ...item, symbol, name: String(item.name ?? ''),
        sources: item.sources.length ? item.sources
          : (['market'] as SelectionSource[]),
        goal: 'unknown' as SelectionGoal, amount: '',
      }].slice(0, MAX_ITEMS);
    set({ items: next, dirty: true });
  },
  remove: (key) => set({
    items: get().items.filter((x) => x.key !== key),
    dirty: true,
  }),
  clear: () => set({ items: [], dirty: true }),
  setGoal: (key, goal) => set({
    items: get().items.map((x) => x.key === key ? { ...x, goal } : x),
    dirty: true,
  }),
  setAmount: (key, amount) => set({
    items: get().items.map((x) => x.key === key ? { ...x, amount } : x),
    dirty: true,
  }),
  move: (key, delta) => {
    const items = [...get().items];
    const i = items.findIndex((x) => x.key === key);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= items.length) return;
    [items[i], items[j]] = [items[j], items[i]];
    set({ items, dirty: true });
  },
  save: (sourceTimes) => {
    const savedAt = new Date().toISOString();
    write(get().items, savedAt, sourceTimes || {});
    set({ savedAt, sourceTimes: sourceTimes || {}, dirty: false });
  },
}));

export function selectedSymbolNames(): string[] {
  return useSarkhatiSelectionStore.getState().items.map((x) => x.symbol);
}
