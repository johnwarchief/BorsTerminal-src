// features/master/stores/capitalStore.ts -- سرمایه/نقدینگی کاربر برای ماشین‌حساب DCA
// توجه: استور پرتفو (features/portfolio/stores/targetAllocation) فقط درصد طبقات هدف را
// نگه می‌دارد و فیلد سرمایه ندارد؛ پس سرمایهٔ کل و نقدینگی اینجا ثبت می‌شود.
// صفر/نامشخص ⇒ اینپوت سریع در UI؛ هرگز عدد ساختگی.
import { create } from 'zustand';

const STORAGE_KEY = 'master.capital.v1';

type CapitalState = {
  /** کل دارایی (تومان) — 0 یعنی ثبت‌نشده */
  totalToman: number;
  /** نقدینگی آزاد (تومان) — 0 یعنی ثبت‌نشده */
  cashToman: number;
  /** رژیم ریسک/جنگ (اعلام کاربر — سیستم منبع خودکار ندارد) */
  warRegime: boolean;
  setTotalToman: (v: number) => void;
  setCashToman: (v: number) => void;
  setWarRegime: (v: boolean) => void;
  reset: () => void;
};

type Persisted = { totalToman: number; cashToman: number; warRegime: boolean };

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { totalToman: 0, cashToman: 0, warRegime: false };
    const p = JSON.parse(raw) as Partial<Persisted>;
    return {
      totalToman: typeof p.totalToman === 'number' && p.totalToman > 0 ? p.totalToman : 0,
      cashToman: typeof p.cashToman === 'number' && p.cashToman > 0 ? p.cashToman : 0,
      warRegime: p.warRegime === true,
    };
  } catch {
    return { totalToman: 0, cashToman: 0, warRegime: false };
  }
}

function persist(s: Persisted): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // حافظه در دسترس نیست — فقط state
  }
}

export const useCapitalStore = create<CapitalState>((set) => {
  const initial = load();
  const save = (patch: Partial<Persisted>) => {
    set((s) => {
      const next = { totalToman: s.totalToman, cashToman: s.cashToman, warRegime: s.warRegime, ...patch };
      persist(next);
      return next;
    });
  };
  return {
    ...initial,
    setTotalToman: (v) => save({ totalToman: Number.isFinite(v) && v > 0 ? Math.round(v) : 0 }),
    setCashToman: (v) => save({ cashToman: Number.isFinite(v) && v > 0 ? Math.round(v) : 0 }),
    setWarRegime: (v) => save({ warRegime: v === true }),
    reset: () => {
      persist({ totalToman: 0, cashToman: 0, warRegime: false });
      set({ totalToman: 0, cashToman: 0, warRegime: false });
    },
  };
});
