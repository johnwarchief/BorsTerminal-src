// features/technical/stores/patternPrefsStore.ts -- ترجیحات ۹ الگوی FTS (روشن/خاموش + رنگ + شفافیت)
// سراسری و پایدار در localStorage؛ هر الگو مستقل است و خاموش‌بودن یعنی «هیچ اورلی نساز».
import { create } from 'zustand';
import { PATTERN_PREFS_DEFAULT, type PatternKind, type PatternPref, type PatternPrefs } from '../lib/patternOverlays';

const KEY = 'fts-pattern-prefs';

function load(): PatternPrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...PATTERN_PREFS_DEFAULT };
    const parsed = JSON.parse(raw) as Partial<Record<PatternKind, Partial<PatternPref>>>;
    const out = { ...PATTERN_PREFS_DEFAULT };
    (Object.keys(out) as PatternKind[]).forEach((k) => {
      const v = parsed?.[k];
      if (v) out[k] = { ...out[k], ...v };
    });
    return out;
  } catch {
    return { ...PATTERN_PREFS_DEFAULT };
  }
}

function persist(prefs: PatternPrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // حافظه در دسترس نیست
  }
}

type PatternPrefsState = {
  prefs: PatternPrefs;
  setPref: (kind: PatternKind, patch: Partial<PatternPref>) => void;
  toggle: (kind: PatternKind) => void;
  reset: () => void;
};

export const usePatternPrefsStore = create<PatternPrefsState>((set) => ({
  prefs: load(),
  setPref: (kind, patch) =>
    set((s) => {
      const next = { ...s.prefs, [kind]: { ...s.prefs[kind], ...patch } };
      persist(next);
      return { prefs: next };
    }),
  toggle: (kind) =>
    set((s) => {
      const next = { ...s.prefs, [kind]: { ...s.prefs[kind], enabled: !s.prefs[kind].enabled } };
      persist(next);
      return { prefs: next };
    }),
  reset: () => {
    persist({ ...PATTERN_PREFS_DEFAULT });
    set({ prefs: { ...PATTERN_PREFS_DEFAULT } });
  },
}));

/** آیا این الگو باید ترسیم شود؟ (برای لایهٔ چارت) */
export function isPatternEnabled(prefs: PatternPrefs, kind: PatternKind): boolean {
  return prefs[kind]?.enabled !== false;
}
