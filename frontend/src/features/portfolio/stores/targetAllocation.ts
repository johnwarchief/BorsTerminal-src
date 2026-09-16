// features/portfolio/stores/targetAllocation.ts -- استور محلی پرتفوی هدف
// state هدف/فعلی طبق ماموریت باید داخل features/portfolio باشد — نه استور اشتراکی.
// persist با localStorage؛ نرمال‌سازی جمع درصدها به ۱۰۰٪.
import { create } from 'zustand';

/** یک طبقه دارایی هدف */
export type TargetClass = {
  id: string;
  label: string;
  /** درصد پیشنهادی FTS (نقطه شروع) */
  pct: number;
  /** رنگ CSS برای چارت دونات */
  color: string;
  /** توضیح طبقه */
  hint?: string;
};

/** طبقات پیش‌فرض FTS — نسبت‌های مصوب سند: طلا و سکه ۴۵٪ (فیزیکی+گواهی) · سهام ۱۵٪ · ارز دیجیتال ۱۵٪ · نقره ۱۰٪ · درآمد ثابت ۱۵٪ — جمع ۱۰۰٪ */
export const FTS_DEFAULT_TARGETS: TargetClass[] = [
  { id: 'gold', label: 'طلای فیزیکی، سکه و شمش', pct: 30, color: '#f59e0b', hint: '۴۵٪ طلا و سکه طبق سند (فیزیکی + گواهی) — پوشش ریسک تورمی/جنگی' },
  { id: 'gold-cert', label: 'صندوق‌ها و گواهی سپردهٔ طلا', pct: 15, color: '#eab308', hint: 'مکمل طلا تا سقف ۴۵٪ سند' },
  { id: 'crypto', label: 'ارز دیجیتال', pct: 15, color: '#22d3ee', hint: '۱۵٪ طبق سند مدیریت سرمایه' },
  { id: 'silver', label: 'نقره / گواهی سپردهٔ کالایی', pct: 10, color: '#94a3b8', hint: '۱۰٪ طبق سند' },
  { id: 'equity', label: 'صندوق سهامی و سهام مستقیم', pct: 15, color: '#10b981', hint: '۱۵٪ سهام مستقیم — سقف هر تک‌سهم ۲۰٪' },
  { id: 'fixed', label: 'صندوق درآمد ثابت / نقدینگی پارک‌شده', pct: 15, color: '#64748b', hint: '۱۵٪ درآمد ثابت و نقدینگی' },
];

const STORAGE_KEY = 'bors-portfolio-target';

/** جمع درصدها؛ درصد نامعتبر صفر حساب می‌شود */
export function sumPct(classes: TargetClass[]): number {
  return classes.reduce((s, c) => s + (Number.isFinite(c.pct) && c.pct > 0 ? c.pct : 0), 0);
}

/** نرمال‌سازی به ۱۰۰٪ — جمع صفر یعنی بدون تغییر (بازگشت به پیش‌فرض) */
export function normalizePct(classes: TargetClass[]): TargetClass[] {
  const total = sumPct(classes);
  if (total <= 0) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
  if (Math.abs(total - 100) < 0.05) return classes.map((c) => ({ ...c }));
  return classes.map((c) => ({
    ...c,
    pct: Math.round(((c.pct > 0 ? c.pct : 0) / total) * 1000) / 10,
  }));
}

/** اعتبارسنجی: جمع ≤ ۱۰۰ (اجازه فضای نقد آزاد بیشتر) */
export function isValidAllocation(classes: TargetClass[]): boolean {
  const total = sumPct(classes);
  return total > 0 && total <= 100 + 1e-9;
}

function loadInitial(): TargetClass[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
    const parsed = JSON.parse(raw) as TargetClass[];
    if (!Array.isArray(parsed) || parsed.length === 0) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
    return parsed.map((c) => ({ ...c, pct: Number(c.pct) || 0 }));
  } catch {
    return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
  }
}

type TargetState = {
  classes: TargetClass[];
  /** نمای فعال: هدف یا فعلی */
  view: 'target' | 'current';
  setView: (v: 'target' | 'current') => void;
  /** ویرایش دستی درصدها — قبل از ذخیره نرمال می‌شود */
  setClasses: (classes: TargetClass[]) => void;
  editClass: (id: string, pct: number) => void;
  addClass: (c: TargetClass) => void;
  removeClass: (id: string) => void;
  reset: () => void;
};

export const useTargetAllocation = create<TargetState>((set) => {
  const persist = (classes: TargetClass[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(classes));
    } catch {
      // حافظه در دسترس نیست — فقط state
    }
  };
  return {
    classes: loadInitial(),
    view: 'target',
    setView: (v) => set({ view: v }),
    setClasses: (classes) => {
      const norm = normalizePct(classes);
      persist(norm);
      set({ classes: norm });
    },
    editClass: (id, pct) =>
      set((s) => {
        const next = s.classes.map((c) => (c.id === id ? { ...c, pct: Math.max(0, Math.round(pct * 10) / 10) } : c));
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    addClass: (c) =>
      set((s) => {
        const next = [...s.classes, c];
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    removeClass: (id) =>
      set((s) => {
        const next = s.classes.filter((c) => c.id !== id);
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    reset: () => {
      const fresh = FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
      persist(fresh);
      set({ classes: fresh });
    },
  };
});

// ─── نوار شکاف و ری‌بالانس (Rebalancing Delta) ──────────────────────────

export type DeltaRow = {
  id: string;
  label: string;
  color: string;
  targetPct: number;
  currentPct: number;
  /** مازاد/کسری: مثبت یعنی بیشتر از هدف (فروش)، منفی یعنی کسری (خرید) */
  delta: number;
};

/** نگاشت وزن فعلی سهم‌های سبد (equity) به طبقهٔ سهام؛ سایر طبقات فعلی صفر */
function equityCurrentPct(holdings: { weight_eff_pct?: number | null }[]): number {
  return (
    Math.round(
      holdings.reduce((s, h) => s + (typeof h.weight_eff_pct === 'number' ? h.weight_eff_pct : 0), 0) * 10,
    ) / 10
  );
}

/**
 * مقایسهٔ وزن فعلی با هدف — فعلی فقط برای طبقهٔ سهام از سبد واقعی می‌آید؛
 * سایر طبقات (طلا/رمز/…) دادهٔ فعلی ندارند و کسری کامل نشان می‌دهند.
 */
export function buildDelta(
  classes: TargetClass[],
  holdings: { weight_eff_pct?: number | null }[],
): DeltaRow[] {
  const eq = equityCurrentPct(holdings);
  return classes.map((c) => {
    const currentPct = c.id === 'equity' ? eq : 0;
    return {
      id: c.id,
      label: c.label,
      color: c.color,
      targetPct: c.pct,
      currentPct,
      delta: Math.round((currentPct - c.pct) * 10) / 10,
    };
  });
}
