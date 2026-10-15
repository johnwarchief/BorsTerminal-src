// shared/stores/workspaceStore.ts -- تب‌های فضای کاری (مسیرِ هر تب = منبع حقیقت)
//
// چرا این store فقط دو چیز نگه می‌دارد: دستورِ مالک درِ سندِ بازطراحی صریح است که
// «برای شبیه‌سازیِ مرورگر state manager پیچیده نساز». پس اینجا نه scroll حفظ
// می‌شود، نه تاریخچۀِ back، نه split-view. تنها چیزی که جا می‌ماند همان است که
// نبودنش نقصِ ثابت‌شدۀِ فاز صفر بود: هر تب یکِ **مسیر** دارد وِ یکِ **نماد**، وِ
// نمادِ یکِ تب نباید بی‌دلیل تبِ دیگر را عوض کند (سناریویِ فولاد/فملی).
//
// ── ۱) نوع و کلیدها
import { create } from 'zustand';

export type WorkspaceTab = {
  /** شناسۀ پایدارِ تب — درِ DOM هم به همین شکل می‌آید (ws-tab-<id>) */
  id: string;
  /** مسیرِ hash بدونِ «#»، مثلِ `/technical/فولاد` */
  path: string;
  /** نمادی که این تب با آن کار می‌کند (برایِ routeهای بی‌:symbol از استور می‌آید) */
  symbol: string;
};

const STORAGE_KEY = ['bors', 'workspace', 'tabs'].join('-');

/** صفحۀ نخستِ برنامه — با رأیِ مالکِ ۱۴۰۵-۰۷-۱۷ غربالگریِ FTS است */
export const DEFAULT_TAB_PATH = '/master';

/** routeهایی که نماد درِ خودِ مسیرشان است (فاز صفر، بندِ ۳) */
const SYMBOL_ROUTES = ['technical', 'fundamental', 'master', 'strategy-tree'];

function newId(): string {
  try {
    const c = globalThis.crypto;
    if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  } catch {
    /* jsdom/بدونِ crypto */
  }
  return ['t', Date.now().toString(36), Math.random().toString(36).slice(2, 8)].join('-');
}

/** نمادِ درونِ مسیر، یا رشتهٔ خالی. تنها راهِ خواندنِ نمادِ یکِ مسیر. */
export function symbolInPath(path: string): string {
  const m = /^\/([a-z-]+)\/([^/?#]+)/.exec(path);
  if (!m) return '';
  if (!SYMBOL_ROUTES.includes(m[1])) return '';
  try {
    return decodeURIComponent(m[2]);
  } catch {
    return m[2];
  }
}

function isTab(v: unknown): v is WorkspaceTab {
  if (!v || typeof v !== 'object') return false;
  const t = v as Record<string, unknown>;
  return typeof t.id === 'string' && t.id.length > 0 && typeof t.path === 'string' && t.path.startsWith('/');
}

function oneTab(path: string = DEFAULT_TAB_PATH): { tabs: WorkspaceTab[]; activeId: string } {
  const tab = { id: newId(), path, symbol: symbolInPath(path) };
  return { tabs: [tab], activeId: tab.id };
}

/** دادهٔlocalStorage می‌تواند کهنه/خراب باشد — خرابی‌اش هرگز نباید برنامه را سفید کند */
function readSaved(): { tabs: WorkspaceTab[]; activeId: string } | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { tabs?: unknown; activeId?: unknown };
    const tabs = Array.isArray(parsed.tabs) ? parsed.tabs.filter(isTab).map(normalize) : [];
    if (!tabs.length) return null;
    const want = typeof parsed.activeId === 'string' ? parsed.activeId : '';
    const activeId = tabs.some((t) => t.id === want) ? want : tabs[tabs.length - 1].id;
    return { tabs, activeId };
  } catch {
    return null;
  }
}

function normalize(t: WorkspaceTab): WorkspaceTab {
  const path = t.path.startsWith('/') ? t.path : `/${t.path}`;
  return { id: t.id, path, symbol: t.symbol || symbolInPath(path) };
}

function save(tabs: WorkspaceTab[], activeId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ tabs, activeId }));
  } catch {
    /* بی‌حافظه: فقطِ state زنده می‌ماند */
  }
}

// ── ۲) store
type WorkspaceState = {
  tabs: WorkspaceTab[];
  activeId: string;
  /**
   * تب تازه. `forceNew` یعنی «دقیقاً یکِ تبِ نو بساز» (دکمۀِ +)، وِ بی‌آنِ اگرِ همانِ
   * مسیرِ بازِ دیگري هست، فقطِ همانِ فعال می‌شود (پیوندِ «بازکردنِ نماد»).
   */
  openTab: (path: string, symbol?: string, opts?: { forceNew?: boolean }) => string;
  /** بستنِ تب. اگرِ آخرینِ تب باشد، یکِ تبِ پیش‌فرض جایش می‌آید. */
  closeTab: (id: string) => string | undefined;
  activateTab: (id: string) => void;
  /** همگامیِ تبِ فعال باِ مسیرِ واقعیِ router (ناوبریِ درونِ صفحه، backِ مرورگر، reload) */
  syncActive: (path: string, symbol: string) => void;
  /** بازنویسیِ نمادِ تبِ فعال — تنها راهی که انتخابِ نماد درِ یکِ تب بیرونِ تبِ دیگر می‌ماند */
  setActiveSymbol: (symbol: string) => void;
  closeOthers: (id: string) => void;
};

const initial = readSaved() ?? oneTab();

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  tabs: initial.tabs,
  activeId: initial.activeId,

  openTab: (path, symbol, opts) => {
    const tabs = get().tabs;
    const found = opts?.forceNew ? undefined : tabs.find((t) => t.path === path);
    if (found) {
      set({ activeId: found.id });
      save(tabs, found.id);
      return found.id;
    }
    const tab: WorkspaceTab = { id: newId(), path, symbol: symbol || symbolInPath(path) };
    const next = [...tabs, tab];
    set({ tabs: next, activeId: tab.id });
    save(next, tab.id);
    return tab.id;
  },

  closeTab: (id) => {
    const { tabs, activeId } = get();
    const at = tabs.findIndex((t) => t.id === id);
    if (at < 0) return undefined;
    const next = tabs.filter((t) => t.id !== id);
    if (!next.length) {
      const fresh = oneTab();
      set({ tabs: fresh.tabs, activeId: fresh.activeId });
      save(fresh.tabs, fresh.activeId);
      return fresh.activeId;
    }
    // همسایه‌ای که جایش می‌آید: اگرِ تبِ میانی/نخست بسته شد، همانِ ایندکس؛ وگرنه قبلی.
    const stay = activeId !== id ? activeId : next[Math.min(at, next.length - 1)].id;
    set({ tabs: next, activeId: stay });
    save(next, stay);
    return stay;
  },

  activateTab: (id) => {
    if (!get().tabs.some((t) => t.id === id)) return;
    set({ activeId: id });
    save(get().tabs, id);
  },

  syncActive: (path, symbol) => {
    const { tabs, activeId } = get();
    const at = tabs.findIndex((t) => t.id === activeId);
    if (at < 0) return;
    const cur = tabs[at];
    if (cur.path === path && cur.symbol === symbol) return;
    const next = tabs.slice();
    next[at] = { ...cur, path, symbol };
    set({ tabs: next });
    save(next, activeId);
  },

  setActiveSymbol: (symbol) => {
    const { tabs, activeId } = get();
    const at = tabs.findIndex((t) => t.id === activeId);
    if (at < 0 || tabs[at].symbol === symbol) return;
    const next = tabs.slice();
    next[at] = { ...next[at], symbol };
    set({ tabs: next });
    save(next, activeId);
  },

  closeOthers: (id) => {
    const tab = get().tabs.find((t) => t.id === id);
    if (!tab) return;
    set({ tabs: [tab], activeId: tab.id });
    save([tab], tab.id);
  },
}));

/** تبِ فعال — برایِ مصرفِ کامپوننت‌ها (idِ DOM وِ برچسب ازِ همین گرفته می‌شود) */
export function useActiveTab(): WorkspaceTab | undefined {
  return useWorkspaceStore((s) => s.tabs.find((t) => t.id === s.activeId));
}
