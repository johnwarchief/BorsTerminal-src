// shared/stores/navHistoryStore.ts — تاریخچۀِ درون‌برنامه، بی‌ادعایِ مرورگر
//
// چرا یکِ storeِ جدا و نه چیزی درِ `workspaceStore`: رأیِ مالک درِ همان سند
// صریح است که «برایِ شبیه‌سازیِ مرورگر state manager پیچیده نساز» —
// `workspaceStore.ts:3`. پس اینجا نه scroll نگه داشته می‌شود، نه split-view،
// نه عنوانِ صفحه. فقط یکِ چیز: «ازِ کجا آمدم و آیا می‌توانم برگردم».
//
// چرا `window.history.length` تنها منبع نیست: آن شمارۀِ
// مرورگر صفحاتِ بیرونِ برنامه را هم می‌شمارد. درِ حالتِ بازِ شدنِ مستقیمِ یکِ
// آدرس، history.length ممکن است ۷ باشد ولی تاریخچۀِ *درونِ برنامه* هیچ باشد —
// دکمه‌ای که درِ آن حالت روشن شود، کاربر را به بیرونِ برنامه می‌فرستد.
//
// سه حالتِ ورودی، سه رفتارِ متفاوت:
//   PUSH    ⇒ اگر مقصد همانِ صفحۀِ فعلی بود، چیزی اضافه نمی‌شود (حلقۀِ تکراری
//             نمی‌سازیم)؛ وگرنه دمِ forward بی‌اعتبار و صفحۀِ تازه افزوده می‌شود.
//   REPLACE ⇒ همان خانۀِ فعلی بازنویسی می‌شود؛ ورودیِ کاذب ساخته نمی‌شود.
//   POP     ⇒ اگر مقصد همسایۀِ چپ/راستِ ما بود، فقط انگشتِ نشانگر جابه‌جا می‌شود
//             (این همان back/forwardِ واقعیِ مرورگر است). اگر نبود، یعنی
//             ناوبری ازِ بیرونِ مدلِ ما آمده و آن را به‌عنوانِ صفحۀِ تازه ثبت
//             می‌کنیم: گذشته می‌ماند، دمِ forward بی‌اعتبار — همانِ قاعدۀِ PUSH.

import { create } from 'zustand';

export type NavKind = 'PUSH' | 'REPLACE' | 'POP';

/** سقفِ تاریخچۀِ درونِ برنامه. یکِ نشستِ کاریِ طولانی هم نباید بی‌حد رشد کند؛
 *  ازِ دمِ قدیمی کم می‌شود و نشانگر باِ همان مقدار جلو می‌رود. */
export const NAV_HISTORY_MAX = 60;

export type NavHistoryState = {
  /** مسیرهایِ کامل — `pathname + search`؛ نشانیِ بی‌query ناقص است */
  entries: string[];
  /** خانۀِ صفحۀِ فعلی */
  index: number;
  record: (path: string, kind: NavKind) => void;
};

/** همانِ `index` را نگه می‌دارد و ازِ دو سر کوتاه می‌کند */
function trim(entries: string[], index: number): { entries: string[]; index: number } {
  if (entries.length <= NAV_HISTORY_MAX) return { entries, index };
  const drop = entries.length - NAV_HISTORY_MAX;
  return { entries: entries.slice(drop), index: Math.max(0, index - drop) };
}

export const useNavHistoryStore = create<NavHistoryState>((set, get) => ({
  entries: [],
  index: -1,

  record: (path, kind) => {
    const clean = String(path || '');
    if (!clean.startsWith('/')) return;
    const { entries, index } = get();
    if (index < 0) {                        // نخستین صفحۀِ برنامه: بی‌تاریخچه
      set({ entries: [clean], index: 0 });
      return;
    }
    if (kind === 'REPLACE') {
      if (entries[index] === clean) return;
      const next = entries.slice();
      next[index] = clean;
      set({ entries: next });
      return;
    }
    if (kind === 'POP') {
      if (index > 0 && entries[index - 1] === clean) { set({ index: index - 1 }); return; }
      if (index < entries.length - 1 && entries[index + 1] === clean) {
        set({ index: index + 1 });
        return;
      }
      // POPِ بیرونِ مدلِ ما: گذشته می‌ماند، دمِ forward بی‌اعتبار
      const t = trim([...entries.slice(0, index + 1), clean], index + 1);
      set({ entries: t.entries, index: t.index });
      return;
    }
    // PUSH
    if (entries[index] === clean) return;   // همان صفحه دوباره: حلقه نساز
    const t = trim([...entries.slice(0, index + 1), clean], index + 1);
    set({ entries: t.entries, index: t.index });
  },
}));

// ── انتخابگرها (تابعِ خالص، بی‌hook — تا درِ گارد هم قابلِ استفاده باشند) ──
export const canGoBack = (s: Pick<NavHistoryState, 'entries' | 'index'>) =>
  s.index > 0 && s.entries.length > 1;
export const canGoForward = (s: Pick<NavHistoryState, 'entries' | 'index'>) =>
  s.index >= 0 && s.index < s.entries.length - 1;
/** مقصدِ احتمالیِ هر جهت — برایِ `title` و برایِ آزمون. بی‌امکان ⇒ null. */
export const backTarget = (s: Pick<NavHistoryState, 'entries' | 'index'>) =>
  canGoBack(s) ? s.entries[s.index - 1] : null;
export const forwardTarget = (s: Pick<NavHistoryState, 'entries' | 'index'>) =>
  canGoForward(s) ? s.entries[s.index + 1] : null;

export function useNavGates() {
  const entries = useNavHistoryStore((s) => s.entries);
  const index = useNavHistoryStore((s) => s.index);
  const view = { entries, index };
  return {
    canBack: canGoBack(view),
    canForward: canGoForward(view),
    backTo: backTarget(view),
    forwardTo: forwardTarget(view),
  };
}
