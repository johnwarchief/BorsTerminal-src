// features/portfolio/stores/assetValues.ts -- ارزش ثبت‌شدهٔ دارایی‌های غیرسهامی + ارزش کل
// لازمهٔ دونات «پرتفوی واقعی» و مبلغ ریالی دستورات ری‌بالانس.
// توجه: این «ارزش کل دارایی‌های ثبت‌شده» است، نه «سرمایهٔ قابل معامله» تب ایجنت ارشد — دو مفهوم جدا.
// صفر ⇒ ثبت‌نشده (UI صادقانه «بدون داده» می‌زند)؛ هرگز عدد ساختگی.
import { create } from 'zustand';
import type { AssetValueKey } from '../model/standardAllocation';

const STORAGE_KEY = 'bors-portfolio-asset-values';

type Persisted = { totalToman: number; values: Record<AssetValueKey, number> };

type AssetValueState = Persisted & {
  setTotalToman: (v: number) => void;
  setValue: (key: AssetValueKey, v: number) => void;
  reset: () => void;
};

const EMPTY_VALUES: Record<AssetValueKey, number> = { gold: 0, crypto: 0, silver: 0, fixed: 0 };

function load(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { totalToman: 0, values: { ...EMPTY_VALUES } };
    const p = JSON.parse(raw) as Partial<Persisted>;
    const values = { ...EMPTY_VALUES };
    for (const k of Object.keys(EMPTY_VALUES) as AssetValueKey[]) {
      const v = p.values?.[k];
      values[k] = typeof v === 'number' && Number.isFinite(v) && v > 0 ? Math.round(v) : 0;
    }
    return { totalToman: typeof p.totalToman === 'number' && p.totalToman > 0 ? Math.round(p.totalToman) : 0, values };
  } catch {
    return { totalToman: 0, values: { ...EMPTY_VALUES } };
  }
}

function persist(p: Persisted): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    // حافظه در دسترس نیست — فقط state
  }
}

export const useAssetValues = create<AssetValueState>((set) => {
  const initial = load();
  const save = (patch: Partial<Persisted>) => {
    set((s) => {
      const next: Persisted = {
        totalToman: patch.totalToman ?? s.totalToman,
        values: { ...s.values, ...(patch.values ?? {}) },
      };
      persist(next);
      return next;
    });
  };
  return {
    ...initial,
    setTotalToman: (v) => save({ totalToman: Number.isFinite(v) && v > 0 ? Math.round(v) : 0 }),
    setValue: (key, v) => save({ values: { [key]: Number.isFinite(v) && v > 0 ? Math.round(v) : 0 } as Record<AssetValueKey, number> }),
    reset: () => {
      const empty: Persisted = { totalToman: 0, values: { ...EMPTY_VALUES } };
      persist(empty);
      set(empty);
    },
  };
});
