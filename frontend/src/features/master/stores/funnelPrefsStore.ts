// features/master/stores/funnelPrefsStore.ts -- دستِ کاربر درِ قیفِ غربالگری
//
// قیفِ FTS چهار مرحلۀ جزوه را می‌گذراند و درِ بنیادی سخت‌گیرترینشان است.
// این گزینه‌ها سخت‌گیریِ جزوه را کم نمی‌کنند، فقط حقِ انتخاب را به خودِ مالک
// می‌دهند؛ پیش‌فرض‌هایشان عینِ جزوه است (کفِ سه از پنج، «بی‌داده وتو نیست»،
// و تکنیکالِ غربال‌کن):
//   - `fundFloor`   : چند شاخص از پنج‌شاخصهٔ کدال کافی است.
//   - `unmeasured`  : با ردیفی که بنیادش واقعاً سنجیده نشده چه شود.
//   - `techScreens`: آیا وتوی تکنیکال نماد را حذف کند، یا فقط برچسب بخورد
//                    و ردیف به بنیادی برسد تا خودِ مالک روندِ هفتگی را ببیند.
import { create } from 'zustand';

/** دو حالتِ کشفِ نماد — هر دو از یک قراردادِ داوری (`lib/ftsFunnel.ts`). */
export type FunnelMode = 'reverse' | 'review';
/** پیش‌فرضِ جزوه: مهندسیِ معکوس (S ➔ T ➔ F ➔ M). */
export const DEFAULT_FUNNEL_MODE: FunnelMode = 'reverse';

const STORAGE_KEY = 'fts.funnel.prefs.v1';

/** پیش‌فرضِ جزوه: سه از پنج. */
export const DEFAULT_FUND_FLOOR = 3;
export const FUND_FLOOR_MAX = 5;

/** «سنجیده‌نشده» درِ بنیادی: درِ انتظار بماند (جزوه) / عبور کند / حذف شود. */
export type UnmeasuredPolicy = 'hold' | 'pass' | 'drop';
export const DEFAULT_UNMEASURED: UnmeasuredPolicy = 'hold';

export const UNMEASURED_LABEL: Record<UnmeasuredPolicy, string> = {
  hold: 'در انتظارِ گزارش',
  pass: 'عبور با برچسب',
  drop: 'حذف از قیف',
};

export const UNMEASURED_HINT: Record<UnmeasuredPolicy, string> = {
  hold: 'نه رد می‌شوند نه تحویل؛ در گروهِ «سنجیده نشد» زیرِ همان مرحله می‌مانند — قانونِ جزوه.',
  pass: 'با برچسبِ «سنجیده نشد» به تحویل می‌روند؛ خودتان می‌دانید که بنیادشان خوانده نشده.',
  drop: 'از قیف بیرون می‌افتند تا فهرستِ تحویل فقط سنجیده‌ها را نشان دهد.',
};

/** پیش‌فرضِ جزوه: تکنیکال غربال می‌کند (رأیِ مالک، چارت ۳ ستون T). */
export const DEFAULT_TECH_SCREENS = true;

export const TECH_SCREEN_LABEL = { on: 'رد می‌کند', off: 'خودم چک می‌کنم' } as const;

export const TECH_SCREEN_HINT = {
  on: 'وتوی هفتگی یا نبودِ ستاپِ سبک، نماد را از قیف بیرون می‌اندازد — عینِ درِ چارت.',
  off: 'ردشده‌ها درِ جدولِ تکنیکال با دلیل (روندِ هفتگی و ستاپ) می‌مانند و به بنیادی هم می‌روند؛ آنجا خودشان فیلتر می‌شوند.',
} as const;

export type FunnelPrefsState = {
  fundFloor: number;
  unmeasured: UnmeasuredPolicy;
  techScreens: boolean;
  mode: FunnelMode;
  setFundFloor: (n: number) => void;
  setUnmeasured: (p: UnmeasuredPolicy) => void;
  setTechScreens: (on: boolean) => void;
  setMode: (m: FunnelMode) => void;
  reset: () => void;
};

function clampFloor(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_FUND_FLOOR;
  return Math.min(FUND_FLOOR_MAX, Math.max(1, Math.round(n)));
}

type SavedPrefs = { fundFloor: number; unmeasured: UnmeasuredPolicy; techScreens: boolean; mode: FunnelMode };

const JOZVE: SavedPrefs = {
  fundFloor: DEFAULT_FUND_FLOOR,
  unmeasured: DEFAULT_UNMEASURED,
  techScreens: DEFAULT_TECH_SCREENS,
  mode: DEFAULT_FUNNEL_MODE,
};

function saved(): SavedPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return JOZVE;
    const p = JSON.parse(raw) as { fundFloor?: unknown; unmeasured?: unknown; techScreens?: unknown; mode?: unknown };
    return {
      fundFloor: clampFloor(typeof p.fundFloor === 'number' ? p.fundFloor : DEFAULT_FUND_FLOOR),
      unmeasured:
        p.unmeasured === 'pass' || p.unmeasured === 'drop' ? p.unmeasured : DEFAULT_UNMEASURED,
      // کلیدِ تازه: فایلِ ذخیره‌شده‌هایِ قدیم این را ندارد. نبودش یعنی همان
      // رفتارِ همیشگی (غربال)، نه تغییرِ بی‌صدا.
      techScreens: typeof p.techScreens === 'boolean' ? p.techScreens : DEFAULT_TECH_SCREENS,
      // نبودِ کلیدِ mode درِ فایل‌هایِ قدیم یعنی همان رفتارِ همیشگی (معکوس).
      mode: p.mode === 'review' ? 'review' : DEFAULT_FUNNEL_MODE,
    };
  } catch {
    return JOZVE;
  }
}

function persist(s: SavedPrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // حافظه در دسترس نیست — فقط state به‌روز می‌شود
  }
}

export const useFunnelPrefsStore = create<FunnelPrefsState>((set, get) => {
  const init = saved();
  return {
    fundFloor: init.fundFloor,
    unmeasured: init.unmeasured,
    techScreens: init.techScreens,
    mode: init.mode,
    setFundFloor: (n) => {
      const v = clampFloor(n);
      persist({ ...get(), fundFloor: v });
      set({ fundFloor: v });
    },
    setUnmeasured: (p) => {
      persist({ ...get(), unmeasured: p });
      set({ unmeasured: p });
    },
    setTechScreens: (on) => {
      persist({ ...get(), techScreens: on });
      set({ techScreens: on });
    },
    setMode: (m) => {
      persist({ ...get(), mode: m });
      set({ mode: m });
    },
    reset: () => {
      persist(JOZVE);
      set(JOZVE);
    },
  };
});
