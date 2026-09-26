// features/technical/stores/priceAlertStore.ts -- هشدارهایِ قیمتی، محلی و پایدار
// واحدِ price همان ریالِ تابلو است؛ دقیقاً همان عددی که نوارِ بالایِ چارت نشان
// می‌دهد، پس کاربر چیزی را که نمی‌بیند وارد نمی‌کند.
import { create } from 'zustand';

export type AlertSide = 'above' | 'below';

export type PriceAlert = {
  id: string;
  symbol: string;
  side: AlertSide;
  /** آستانه به ریال — همیشه بزرگ‌تر از صفر (آستانۀ صفر یعنی هشدارِ همیشگی) */
  price: number;
  createdAt: number;
  /** زمانِ شلیک؛ null یعنی هنوز شلیک نشده */
  firedAt: number | null;
  /** پس از شلیک خاموش می‌شود؛ کاربر با بازنشانی دوباره فعالش می‌کند */
  active: boolean;
  /** پرچمِ دیده‌شدنِ بنرِ شلیک */
  seen: boolean;
};

export type NewAlert = { symbol: string; side: AlertSide; price: number };

const STORAGE_KEY = 'fts.price-alerts.v1';

function newId(): string {
  return `al_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/** یک ردیفِ ذخیره‌شده را می‌سازد؛ هر چیزِ نامعتبر ⇒ null (نه صفر، نه هشدارِ همیشگی) */
function saneAlert(raw: unknown): PriceAlert | null {
  if (!raw || typeof raw !== 'object') return null;
  const a = raw as Record<string, unknown>;
  const price = typeof a.price === 'number' ? a.price : Number(a.price);
  if (!Number.isFinite(price) || price <= 0) return null;
  if (typeof a.symbol !== 'string' || !a.symbol.trim()) return null;
  if (a.side !== 'above' && a.side !== 'below') return null;
  const firedAt = typeof a.firedAt === 'number' && Number.isFinite(a.firedAt) ? a.firedAt : null;
  return {
    id: typeof a.id === 'string' && a.id ? a.id : newId(),
    symbol: a.symbol.trim(),
    side: a.side,
    price,
    createdAt: typeof a.createdAt === 'number' && Number.isFinite(a.createdAt) ? a.createdAt : Date.now(),
    firedAt,
    active: a.active === true,
    seen: a.seen === true,
  };
}

function load(): PriceAlert[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    const list = Array.isArray(parsed) ? parsed : (parsed as { alerts?: unknown[] })?.alerts ?? [];
    const out: PriceAlert[] = [];
    for (const item of Array.isArray(list) ? list : []) {
      const a = saneAlert(item);
      if (a) out.push(a);
    }
    return out;
  } catch {
    return [];
  }
}

function persist(alerts: PriceAlert[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ alerts }));
  } catch {
    // localStorage در حالتِ خصوصی یا دیسکِ پُر بی‌صدا رد می‌شود؛ حافظهٔ داخلی
    // همچنان کار می‌کند و کاربر هیچ خطایی نمی‌بیند.
  }
}

type PriceAlertState = {
  alerts: PriceAlert[];
  /** افزودن: idِ هشدار برمی‌گردد؛ اگر نماد خالی یا آستانه نامعتبر بود null */
  addAlert: (input: NewAlert) => string | null;
  removeAlert: (id: string) => void;
  /** بازنشانیِ هشدارِ شلیک‌شده برای شلیکِ دوباره */
  rearm: (id: string) => void;
  setEnabled: (id: string, on: boolean) => void;
  /** توسطِ نگهبانِ قیمت صدا زده می‌شود: آستانه رد شده ⇒ شلیک و خاموشی */
  fire: (ids: string[], when?: number) => void;
  markSeen: (ids: string[]) => void;
  clearAll: () => void;
};

function commit(set: (partial: { alerts: PriceAlert[] }) => void, next: PriceAlert[]): void {
  persist(next);
  set({ alerts: next });
}

export const usePriceAlertStore = create<PriceAlertState>((set, get) => ({
  alerts: load(),
  addAlert: ({ symbol, side, price }) => {
    const clean = typeof symbol === 'string' ? symbol.trim() : '';
    if (!clean || (side !== 'above' && side !== 'below')) return null;
    if (!Number.isFinite(price) || price <= 0) return null;
    // همان نماد، همان جهت و همان آستانه دو بار لازم نیست
    const dup = get().alerts.find((a) => a.symbol === clean && a.side === side && a.price === price);
    if (dup) return dup.id;
    const alert: PriceAlert = {
      id: newId(),
      symbol: clean,
      side,
      price,
      createdAt: Date.now(),
      firedAt: null,
      active: true,
      seen: true,
    };
    commit(set, [alert, ...get().alerts]);
    return alert.id;
  },
  removeAlert: (id) => commit(set, get().alerts.filter((a) => a.id !== id)),
  rearm: (id) =>
    commit(
      set,
      get().alerts.map((a) => (a.id === id ? { ...a, active: true, firedAt: null, seen: true } : a)),
    ),
  setEnabled: (id, on) =>
    commit(set, get().alerts.map((a) => (a.id === id ? { ...a, active: on, seen: on ? a.seen : true } : a))),
  fire: (ids, when = Date.now()) => {
    if (ids.length === 0) return;
    const want = new Set(ids);
    commit(
      set,
      get().alerts.map((a) => (want.has(a.id) && a.active ? { ...a, active: false, firedAt: when, seen: false } : a)),
    );
  },
  markSeen: (ids) => {
    if (ids.length === 0) return;
    const want = new Set(ids);
    commit(set, get().alerts.map((a) => (want.has(a.id) ? { ...a, seen: true } : a)));
  },
  clearAll: () => commit(set, []),
}));
