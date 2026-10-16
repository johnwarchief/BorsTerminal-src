// features/market/stores/noticePrefsStore.ts -- خوانده‌شده/ناخوانده و تنظیمِ مرکزِ اعلان
//
// چرا درِ localStorage و نه درِ `market.db`: دو بک‌اند هم‌زمان رویِ یک بانک
// می‌نویسند (نصبی + dev) و «وضعیتِ خواندن» یک حالتِ شخصیِ همین دستگاه است،
// نه دادهٔ بازار. گاردِ تک‌نویسنده هم همین را می‌خواهد.
//
// سه چیز جدا نگه داشته می‌شوند (رأیِ مالک، بند ۶):
//   • تاریخچۀِ خوانده‌شده‌ها (بی‌حذفِ خودکار؛ سقفِ تعداد برایِ بی‌مُرده شدن)
//   • فیلترِ سطحِ اهمیت (بالا/متوسط/پایین/بی‌طبقه)
//   • فیلترِ نوعِ اطلاعیه (صورتهایِ مالی، مجمع، ماهانه، …)
// «اعلانِ ویندوز» درِ همین کلید است و پیش‌فرض خاموش — تا کاربر خودش روشن
// نکند، هیچ پیامِ سیستمی‌ای ارسال نمی‌شود.
import { create } from 'zustand';

const STORAGE_KEY = 'bors-notice-prefs';
const READ_MAX = 800;

export type NoticePrefs = {
  read: string[];
  levels: string[];
  kinds: string[];
  /** اعلانِ بومیِ ویندوز — صریحاً خاموش تا کاربر روشنش کند */
  native: boolean;
};

const DEFAULTS: NoticePrefs = { read: [], levels: [], kinds: [], native: false };

function read(): NoticePrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const p = JSON.parse(raw) as Partial<NoticePrefs>;
    const arr = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);
    return {
      read: arr(p.read).slice(0, READ_MAX),
      levels: arr(p.levels),
      kinds: arr(p.kinds),
      native: p.native === true,
    };
  } catch {
    return DEFAULTS;
  }
}

function write(p: NoticePrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* بی‌localStorage فقط یعنی یادش نمی‌ماند */
  }
}

type Store = NoticePrefs & {
  isRead: (id: string) => boolean;
  markRead: (id: string) => void;
  markAllRead: (ids: string[]) => void;
  clearHistory: () => void;
  toggleLevel: (lvl: string) => void;
  toggleKind: (kind: string) => void;
  setNative: (on: boolean) => void;
};

export const useNoticePrefsStore = create<Store>((set, get) => ({
  ...read(),
  isRead: (id) => get().read.includes(id),
  markRead: (id) => set((s) => {
    if (s.read.includes(id)) return s;
    const next = { ...s, read: [id, ...s.read].slice(0, READ_MAX) };
    write(next);
    return next;
  }),
  markAllRead: (ids) => set((s) => {
    const merged = Array.from(new Set([...ids, ...s.read])).slice(0, READ_MAX);
    const next = { ...s, read: merged };
    write(next);
    return next;
  }),
  clearHistory: () => set((s) => {
    const next = { ...s, read: [] };
    write(next);
    return next;
  }),
  toggleLevel: (lvl) => set((s) => {
    const levels = s.levels.includes(lvl) ? s.levels.filter((x) => x !== lvl) : [...s.levels, lvl];
    const next = { ...s, levels };
    write(next);
    return next;
  }),
  toggleKind: (kind) => set((s) => {
    const kinds = s.kinds.includes(kind) ? s.kinds.filter((x) => x !== kind) : [...s.kinds, kind];
    const next = { ...s, kinds };
    write(next);
    return next;
  }),
  setNative: (on) => set((s) => {
    const next = { ...s, native: on };
    write(next);
    return next;
  }),
}));
