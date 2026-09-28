// features/master/stores/funnelPrefsStore.ts -- دستِ کاربر درِ قیفِ غربالگری
//
// قیفِ FTS چهار مرحلۀ جزوه را می‌گذراند و درِ بنیادی سخت‌گیرترینشان است.
// این دو گزینه سخت‌گیریِ جزوه را کم نمی‌کنند، فقط حقِ انتخاب را به خودِ مالک
// می‌دهند؛ پیش‌فرض‌هایشان عینِ جزوه است (کفِ سه از پنج، و «بی‌داده وتو نیست»):
//   - `fundFloor`   : چند شاخص از پنج‌شاخصهٔ کدال کافی است.
//   - `unmeasured`  : با ردیفی که بنیادش واقعاً سنجیده نشده چه شود.
import { create } from 'zustand';

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

export type FunnelPrefsState = {
  fundFloor: number;
  unmeasured: UnmeasuredPolicy;
  setFundFloor: (n: number) => void;
  setUnmeasured: (p: UnmeasuredPolicy) => void;
  reset: () => void;
};

function clampFloor(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_FUND_FLOOR;
  return Math.min(FUND_FLOOR_MAX, Math.max(1, Math.round(n)));
}

function saved(): { fundFloor: number; unmeasured: UnmeasuredPolicy } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { fundFloor: DEFAULT_FUND_FLOOR, unmeasured: DEFAULT_UNMEASURED };
    const p = JSON.parse(raw) as { fundFloor?: unknown; unmeasured?: unknown };
    return {
      fundFloor: clampFloor(typeof p.fundFloor === 'number' ? p.fundFloor : DEFAULT_FUND_FLOOR),
      unmeasured:
        p.unmeasured === 'pass' || p.unmeasured === 'drop' ? p.unmeasured : DEFAULT_UNMEASURED,
    };
  } catch {
    return { fundFloor: DEFAULT_FUND_FLOOR, unmeasured: DEFAULT_UNMEASURED };
  }
}

function persist(s: { fundFloor: number; unmeasured: UnmeasuredPolicy }) {
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
    setFundFloor: (n) => {
      const v = clampFloor(n);
      persist({ ...get(), fundFloor: v });
      set({ fundFloor: v });
    },
    setUnmeasured: (p) => {
      persist({ ...get(), unmeasured: p });
      set({ unmeasured: p });
    },
    reset: () => {
      persist({ fundFloor: DEFAULT_FUND_FLOOR, unmeasured: DEFAULT_UNMEASURED });
      set({ fundFloor: DEFAULT_FUND_FLOOR, unmeasured: DEFAULT_UNMEASURED });
    },
  };
});
