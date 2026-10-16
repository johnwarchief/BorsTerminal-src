// shared/stores/screenFilterStore.ts — کلیدِ «اشتراک/اجتماع»ِ غربالگری
//
// رأیِ مالک (۱۴۰۵-۰۷-۲۰): «روی نوارِ جدولِ تابلوخوانی همان چیپ‌ها که تعداد را
// می‌نویسند، روی هرکدام که بزنیم همان‌جا فیلترها درِ غربالگری اعمال شوند» و
// «یک تنظیم روشن/خاموش برایِ اینکه اشتراک باشد یا اجتماع».
//
// فهرستِ فیلترها از همان `useTapeStore.quickFilters` خوانده می‌شود (یک منبع؛
// `useFtsFunnel` همان را به موتور می‌فرستد) — اینجا فقط «منطقِ ترکیب» نگه داشته
// می‌شود، که تنظیمِ کاربر است نه داوریِ روش‌شناسی.
import { create } from 'zustand';

export type ScreenLogic = 'and' | 'or';

const LS_LOGIC = 'bors.screen.logic.v1';

function loadLogic(): ScreenLogic {
  try {
    if (typeof window === 'undefined') return 'and';
    return window.localStorage.getItem(LS_LOGIC) === 'or' ? 'or' : 'and';
  } catch {
    return 'and';
  }
}

export interface ScreenLogicState {
  logic: ScreenLogic;
  setLogic: (l: ScreenLogic) => void;
}

export const useScreenFilterStore = create<ScreenLogicState>((set) => ({
  logic: loadLogic(),
  setLogic: (l) => {
    // هر چیزِ غیرِ «or» صریح همان اشتراک است (رفتارِ دیروزِ موتور).
    const next: ScreenLogic = l === 'or' ? 'or' : 'and';
    try {
      if (typeof window !== 'undefined') window.localStorage.setItem(LS_LOGIC, next);
    } catch {
      /* حالتِ خصوصیِ مرورگر: انتخاب فقط درِ همین اجرا می‌ماند */
    }
    set({ logic: next });
  },
}));
