// features/execution/stores/orderLineStore.ts -- state مستقلِ هرِ تبِ سرخطی
//
// بندِ ۱.۲ مأموریتِ System 2: «چندِ تبِ ظاهری که همگی بهِ یکِ state مشترک
// وصل‌اند قابلِ قبول نیست.» پسِ اینجا تنها مرجعِ «چه درِ اینِ تب نوشته شده» است
// وِ هیچِ فیلدِ مشترکی بینِ تب‌ها وجود ندارد: نه نماد، نه قیمت، نه تعداد، نه
// execution_id، نه نتیجه.
//
// چهار تصمیمِ عمدی:
//  ۱) `executionId` کلیدِ idempotency است، نه هشِ فرم: درِ ساختِ تب ساخته می‌شود
//     وِ باِ ویرایشِ قیمت/تعداد عوض نمی‌شود. تنها پسِ رسیدنِ بهِ حالتِ پایان‌یافته
//     (reconciled/failed) وِ باِ «تبِ تازه» تازه می‌شود -- بی‌این، هرِ ویرایشِ کوچک
//     درِ چشمِ سرویس یکِ سفارشِ تازه است.
//  ۲) قفلِ ارسال درِ خودِ state است (`inFlight`)، نه درِ UI: دوِ کلیکِ سریع،
//     Enter+کلیک، یاِ دوِ تبِ هم‌زمان هیچ‌کدام نباید دومینِ dispatch را بسازند.
//  ۳) persistence فقطِ «پیش‌نویس» است. `sending`/`scheduled` هنگامِ بازیابی بهِ
//     `draft` برمی‌گردد باِ یکِ یادداشتِ روشن -- بازیابیِ صفحه هرگز سفارش را
//     دوباره اجرا نمی‌کند، وِ اینِ ادعا درِ همین‌جا نوشته می‌شود نه درِ آرزویِ UI.
//  ۴) هیچِ عددی ازِ تبِ دیگری قرض گرفته نمی‌شود؛ حتیِ «آخرینِ قیمتِ دیده‌شده» هم
//     درِ هرِ تب جدا می‌ماند، چون سرخطیِ چندنمادی دقیقاً باِ همینِ اشتباه می‌میرد.
import { create } from 'zustand';
import type { ExecutionPhase } from '../api/orderLineApi';

export type TabPhase = ExecutionPhase | 'idle' | 'sending';

export type OrderTab = {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  mode: 'safe' | 'fast' | 'ultra';
  price: string;
  quantity: string;
  /** کلیدِ idempotencyِ همینِ تب -- ثابت تاِ پایانِ همینِ تلاش */
  executionId: string;
  /** تیکِ صریحِ کاربر برایِ `mock_instrument` خودِ قرارداد؛ پیش‌فرض خاموش */
  mockInstrument: boolean;
  phase: TabPhase;
  inFlight: boolean;
  checks: Record<string, string>;
  reasons: Record<string, string>;
  unknown: string[];
  /** نتیجهٔ dispatch (record یاِ scheduled) -- بی‌موفقیتِ یکِ تب رویِ تبِ دیگر */
  result: Record<string, unknown> | null;
  note: string | null;
};

const STORAGE_KEY = 'bors-order-line-tabs';
const PHASES_DONE: TabPhase[] = ['reconciled', 'failed', 'acknowledged'];

export function newTabId(): string {
  return `t-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-4)}`;
}

/** شناسۀِ اجرایِ تب: ازِ همانِ لحظۀِ ساخت، ثابت وِ بی‌معنایِ تازه */
export function newExecutionId(): string {
  return `x-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-4)}`;
}

export function emptyTab(seed?: Partial<OrderTab>): OrderTab {
  return {
    id: newTabId(),
    symbol: '',
    side: 'buy',
    mode: 'safe',
    price: '',
    quantity: '',
    executionId: newExecutionId(),
    mockInstrument: false,
    phase: 'idle',
    inFlight: false,
    checks: {},
    reasons: {},
    unknown: [],
    result: null,
    note: null,
    ...seed,
  };
}

/** بازیابیِ امن: هیچِ حالتِ در-جریانِ دیروز امروز اجرا نمی‌شود */
export function sanitizeRehydrated(tab: OrderTab): OrderTab {
  if (tab.inFlight || tab.phase === 'sending' || tab.phase === 'scheduled' || tab.phase === 'dispatched') {
    return {
      ...tab,
      inFlight: false,
      phase: 'draft',
      note: 'ازِ نشستِ پیشین بازیابی شد؛ هیچِ سفارشی خودکار ارسال نمی‌شود.',
    };
  }
  return { ...tab, inFlight: false };
}

function load(): OrderTab[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Partial<OrderTab>[];
    return Array.isArray(parsed) ? parsed.map((t) => sanitizeRehydrated({ ...emptyTab(), ...t })) : [];
  } catch {
    return [];
  }
}

function save(tabs: OrderTab[]) {
  try {
    // فقطِ چیزی که کاربر تایپ کرده + شناسۀِ اجرا. نتیجه‌ها درِ ردِّپایِ سرویس‌اند.
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs.map((t) => ({
      id: t.id, symbol: t.symbol, side: t.side, mode: t.mode, price: t.price,
      quantity: t.quantity, executionId: t.executionId, mockInstrument: t.mockInstrument,
    }))));
  } catch {
    /* بی‌localStorage فقطِ یعنی یادش نمی‌ماند؛ ارسالِ دوباره ساخته نمی‌شود */
  }
}

type Store = {
  tabs: OrderTab[];
  activeId: string | null;
  addTab: (seed?: Partial<OrderTab>) => string;
  closeTab: (id: string) => void;
  activate: (id: string) => void;
  patch: (id: string, fields: Partial<Omit<OrderTab, 'id' | 'executionId' | 'inFlight'>>) => void;
  mark: (id: string, fields: Partial<OrderTab>) => void;
  /** قفلِ ارسال: `true` فقطِ اگرِ تب آزاد بوده باشد (اتمِ درِ همینِ تابع) */
  beginSend: (id: string) => boolean;
  endSend: (id: string) => void;
  /** تبِ پایان‌یافته را برایِ تلاشِ تازه باز می‌کند باِ شناسۀِ تازه */
  resetForNextAttempt: (id: string) => void;
  clearAll: () => void;
};

const initial = load();

export const useOrderLineStore = create<Store>((set, get) => ({
  tabs: initial,
  activeId: initial[0]?.id ?? null,

  addTab: (seed) => {
    const tab = emptyTab(seed);
    set((s) => {
      const tabs = [...s.tabs, tab];
      save(tabs);
      return { tabs, activeId: tab.id };
    });
    return tab.id;
  },

  closeTab: (id) => set((s) => {
    const tabs = s.tabs.filter((t) => t.id !== id);
    const activeId = s.activeId === id ? (tabs[tabs.length - 1]?.id ?? null) : s.activeId;
    save(tabs);
    return { tabs, activeId };
  }),

  activate: (id) => set({ activeId: id }),

  patch: (id, fields) => set((s) => {
    const tabs = s.tabs.map((t) => (t.id === id ? { ...t, ...fields, note: null } : t));
    save(tabs);
    return { tabs };
  }),

  mark: (id, fields) => set((s) => ({
    tabs: s.tabs.map((t) => (t.id === id ? { ...t, ...fields } : t)),
  })),

  beginSend: (id) => {
    const t = get().tabs.find((x) => x.id === id);
    if (!t || t.inFlight) return false;
    set((s) => ({ tabs: s.tabs.map((x) => (x.id === id ? { ...x, inFlight: true } : x)) }));
    return true;
  },

  endSend: (id) => set((s) => ({
    tabs: s.tabs.map((x) => (x.id === id ? { ...x, inFlight: false } : x)),
  })),

  resetForNextAttempt: (id) => set((s) => ({
    tabs: s.tabs.map((x) => (x.id === id && PHASES_DONE.includes(x.phase)
      ? { ...emptyTab({ symbol: x.symbol, side: x.side, mode: x.mode, price: x.price,
                        quantity: x.quantity, mockInstrument: x.mockInstrument }), id: x.id }
      : x)),
  })),

  clearAll: () => {
    save([]);
    set({ tabs: [], activeId: null });
  },
}));

export function tabOf(id: string | null): OrderTab | undefined {
  return useOrderLineStore.getState().tabs.find((t) => t.id === id);
}

/** عددِ فرم: `''` باِ `0` یکی نیست (بی‌داده ≠ صفر) */
export function formNumber(raw: string): number | null {
  const t = raw.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))).replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).trim();
  if (!t) return null;
  const n = Number(t.replace(/[,\s]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/** چراِ تبِ خالیِ تبِ دیگری را قفل نمی‌کند -- کمکِ آزمون‌هایِ استقلال */
export function tabSignature(t: OrderTab): string {
  return [t.symbol, t.side, t.mode, t.price, t.quantity, t.executionId].join('|');
}
