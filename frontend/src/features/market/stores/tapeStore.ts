// features/market/stores/tapeStore.ts -- فیلترهای محلی تابلو
import { create } from 'zustand';
import { ASSET_TYPES, type AssetType } from '../lib/assetType';

import {
  DEFAULT_TAPE_FILTER_CONFIG,
  TAPE_PRESETS,
  type TapeFilterConfig,
  type TapePresetKey,
} from '../lib/tapeAlgorithms';

export const QUICK_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart_flow'] as const;
export type QuickFilter = (typeof QUICK_FILTERS)[number];

export const QUICK_LABELS: Record<QuickFilter, string> = {
  f_clock: 'الگوی ساعت',
  f_susp: 'حجم مشکوک',
  f_jet: 'فیلتر جت',
  f_roobi: 'کف‌روبی',
  f_noqteh: 'نقطه زنی',
  f_smart_flow: 'پول هوشمند',
};

/** آستانه تقریبی صف در TSETMC (۵ درصد منهای ارف) */
export const LIMIT_PCT = 4.9;

/** بازهٔ مجاز و پیش‌فرض فیلتر ضریب حجم مشکوک (روی vol_ratio) */
export const VOL_RATIO_MIN = 1.5;
export const VOL_RATIO_MAX = 5;
export const VOL_RATIO_DEFAULT = 3;

/** ترتیب غربالگری سه‌ایجنتی */
export const SCREEN_ORDERS = ['tape_first', 'technical_first', 'fundamental_first'] as const;
export type ScreenOrder = (typeof SCREEN_ORDERS)[number];
export const SCREEN_ORDER_LABELS: Record<ScreenOrder, string> = {
  tape_first: 'تابلو → تکنیکال → بنیادی',
  technical_first: 'تکنیکال → تابلو → بنیادی',
  fundamental_first: 'بنیادی → تابلو → تکنیکال',
};

/** ترکیب «خروج از انباشت»: هم‌زمان الگوی ساعت و حجم مشکوک */
export const EXIT_ACCUM_LABEL = 'خروج از انباشت';
export const EXIT_ACCUM_HINT =
  'نمایش فیلتر ترکیبی ساعت + حجم مشکوک روی تابلو؛ باکس واقعیِ این ترکیب در اندپوینت چارت / تب تکنیکال ساخته می‌شود.';

export const DIRECTIONS = ['all', 'pos', 'neg', 'limitUp', 'limitDown'] as const;
export type DirectionFilter = (typeof DIRECTIONS)[number];

export const DIRECTION_LABELS: Record<DirectionFilter, string> = {
  all: 'همه',
  pos: 'مثبت',
  neg: 'منفی',
  limitUp: 'صف خرید',
  limitDown: 'صف فروش',
};

/** آیا درصد تغییر با جهت انتخابی می خواند؟ مقدار ناقص فقط در «همه» رد می نشود. */
export function matchesDirection(pct: number | null | undefined, dir: DirectionFilter): boolean {
  if (dir === 'all') return true;
  if (pct == null || !Number.isFinite(pct)) return false;
  if (dir === 'pos') return pct > 0;
  if (dir === 'neg') return pct < 0;
  if (dir === 'limitUp') return pct >= LIMIT_PCT;
  return pct <= -LIMIT_PCT;
}

/** عبور از فیلتر ضریب حجم: vol_ratio موجود و بالای آستانه */
export function matchesVolRatio(volRatio: number | null | undefined, min: number): boolean {
  if (typeof volRatio !== 'number' || !Number.isFinite(volRatio)) return false;
  return volRatio >= min;
}

/** عبور از فیلتر «خروج از انباشت»: هر دو پرچم ساعت و حجم مشکوک فعال */
export function matchesExitAccum(row: { f_clock?: boolean | null; f_susp?: boolean | null }): boolean {
  return !!row.f_clock && !!row.f_susp;
}

/** پنج نوع پیش‌فرض فعال در بارگذاری اولیه و پس از بازنشانی (مطابق استاندارد ۱۱‌گانه TSETMC) */
export const DEFAULT_ASSET_TYPES: AssetType[] = ['stock', 'payeh', 'right', 'energy', 'fund'];

/** سوییچ‌های سریع تک‌کلیکهٔ نوار فیلتر -- مجموعهٔ صریح نوع دارایی */
export const ASSET_QUICK_PRESETS = {
  payeh_only: ['payeh'] as AssetType[],
  bourse_stocks: ['stock', 'payeh'] as AssetType[],
} as const;
export type AssetQuickPreset = keyof typeof ASSET_QUICK_PRESETS;

export const ASSET_PRESET_LABELS: Record<AssetQuickPreset, string> = {
  payeh_only: 'فقط بازار پایه',
  bourse_stocks: 'فقط سهام بورس/فرابورس',
};

/** دو مجموعه یکسان‌اند؟ (مجموعه‌ای، بی‌توجه به ترتیب) */
export function sameAssetSets(a: readonly AssetType[], b: readonly AssetType[]): boolean {
  return a.length === b.length && a.every((t) => b.includes(t));
}

/** آیا مجموعهٔ فعال دقیقاً همان پنج‌تایی پیش‌فرض است؟ (بی‌توجه به ترتیب) */
export function isDefaultAssetTypes(types: AssetType[]): boolean {
  return sameAssetSets(types, DEFAULT_ASSET_TYPES);
}

function loadInitialTapeConfig(): TapeFilterConfig {
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem('bors_tape_filter_config_v1') : null;
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        clock: { ...DEFAULT_TAPE_FILTER_CONFIG.clock, ...(parsed.clock ?? {}) },
        suspiciousVolume: { ...DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume, ...(parsed.suspiciousVolume ?? {}) },
        jet: { ...DEFAULT_TAPE_FILTER_CONFIG.jet, ...(parsed.jet ?? {}) },
        roobi: { ...DEFAULT_TAPE_FILTER_CONFIG.roobi, ...(parsed.roobi ?? {}) },
        noqteh: { ...DEFAULT_TAPE_FILTER_CONFIG.noqteh, ...(parsed.noqteh ?? {}) },
        smartFlow: { ...DEFAULT_TAPE_FILTER_CONFIG.smartFlow, ...(parsed.smartFlow ?? {}) },
      };
    }
  } catch {
    // ignore
  }
  return DEFAULT_TAPE_FILTER_CONFIG;
}

function saveTapeConfig(cfg: TapeFilterConfig) {
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem('bors_tape_filter_config_v1', JSON.stringify(cfg));
    }
  } catch {
    // ignore
  }
}

type TapeState = {
  /** جستجوی نماد و نام */
  query: string;
  /** نوع های دارایی فعال -- مجموعهٔ صریح؛ خالی یعنی هیچ‌کدام (دیگر «همه» نیست) */
  assetTypes: AssetType[];
  /** فیلترهای سریع فعال */
  quickFilters: QuickFilter[];
  /** صنعت انتخابی -- خالی یعنی همه */
  sector: string;
  /** فقط نمادهای زنده (is_live !== false) */
  liveOnly: boolean;
  /** جهت تغییر قیمت */
  direction: DirectionFilter;
  /** فیلتر ضریب حجم مشکوک فعال است؟ */
  volRatioOn: boolean;
  /** آستانهٔ vol_ratio (۱.۵ تا ۵، پیش‌فرض ۳) */
  volRatioMin: number;
  /** فیلتر ترکیبی «خروج از انباشت» (فقط در صفحهٔ تابلو) */
  exitAccum: boolean;
  /** کانفیگ شخصی‌سازی‌شدهٔ الگوریتم‌های تابلو */
  tapeFilterConfig: TapeFilterConfig;
  /** ترتیب غربالگری سه‌ایجنتی */
  screenOrder: ScreenOrder;
  setQuery: (q: string) => void;
  toggleAssetType: (t: AssetType) => void;
  setAssetTypes: (list: AssetType[]) => void;
  toggleAssetPreset: (p: AssetQuickPreset) => void;
  setAllAssetTypes: () => void;
  resetAssetTypes: () => void;
  toggleQuickFilter: (f: QuickFilter) => void;
  setSector: (s: string) => void;
  setLiveOnly: (v: boolean) => void;
  setDirection: (d: DirectionFilter) => void;
  setVolRatioOn: (v: boolean) => void;
  setVolRatioMin: (v: number) => void;
  toggleExitAccum: () => void;
  setTapeFilterConfig: (cfg: Partial<TapeFilterConfig>) => void;
  resetTapeFilterConfig: () => void;
  applyTapePreset: (presetKey: TapePresetKey) => void;
  setScreenOrder: (o: ScreenOrder) => void;
  /** بازنشانی همه فیلترها به حالت پیش فرض */
  resetFilters: () => void;
};

function toggle<T>(list: T[], v: T): T[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

const INITIAL = {
  query: '',
  assetTypes: [...DEFAULT_ASSET_TYPES] as AssetType[],
  quickFilters: [] as QuickFilter[],
  sector: '',
  liveOnly: false,
  direction: 'all' as DirectionFilter,
  volRatioOn: false,
  volRatioMin: VOL_RATIO_DEFAULT,
  exitAccum: false,
  tapeFilterConfig: loadInitialTapeConfig(),
  screenOrder: 'tape_first' as ScreenOrder,
};

/** آستانهٔ حجم را در بازهٔ مجاز نگه می‌دارد */
export function clampVolRatio(v: number): number {
  if (!Number.isFinite(v)) return VOL_RATIO_DEFAULT;
  return Math.min(VOL_RATIO_MAX, Math.max(VOL_RATIO_MIN, v));
}

export const useTapeStore = create<TapeState>((set) => ({
  ...INITIAL,
  setQuery: (query) => set({ query }),
  toggleAssetType: (t) => set((s) => ({ assetTypes: toggle(s.assetTypes, t) })),
  setAssetTypes: (list) => set({ assetTypes: [...list] }),
  // سوییچ سریع تک‌کلیکه: فعال‌سازی پرست؛ کلیک دوباره روی پرست فعال → بازگشت به پیش‌فرض
  toggleAssetPreset: (p) =>
    set((s) => ({
      assetTypes: sameAssetSets(s.assetTypes, ASSET_QUICK_PRESETS[p])
        ? [...DEFAULT_ASSET_TYPES]
        : [...ASSET_QUICK_PRESETS[p]],
    })),
  setAllAssetTypes: () => set({ assetTypes: [...ASSET_TYPES] }),
  resetAssetTypes: () => set({ assetTypes: [...DEFAULT_ASSET_TYPES] }),
  toggleQuickFilter: (f) => set((s) => ({ quickFilters: toggle(s.quickFilters, f) })),
  setSector: (sector) => set({ sector }),
  setLiveOnly: (liveOnly) => set({ liveOnly }),
  setDirection: (direction) => set({ direction }),
  setVolRatioOn: (volRatioOn) => set({ volRatioOn }),
  setVolRatioMin: (v) => set({ volRatioMin: clampVolRatio(v) }),
  toggleExitAccum: () => set((s) => ({ exitAccum: !s.exitAccum })),
  setTapeFilterConfig: (partial) =>
    set((s) => {
      const updated: TapeFilterConfig = {
        clock: { ...s.tapeFilterConfig.clock, ...(partial.clock ?? {}) },
        suspiciousVolume: { ...s.tapeFilterConfig.suspiciousVolume, ...(partial.suspiciousVolume ?? {}) },
        jet: { ...s.tapeFilterConfig.jet, ...(partial.jet ?? {}) },
        roobi: { ...s.tapeFilterConfig.roobi, ...(partial.roobi ?? {}) },
        noqteh: { ...s.tapeFilterConfig.noqteh, ...(partial.noqteh ?? {}) },
        smartFlow: { ...s.tapeFilterConfig.smartFlow, ...(partial.smartFlow ?? {}) },
      };
      saveTapeConfig(updated);
      return { tapeFilterConfig: updated };
    }),
  resetTapeFilterConfig: () => {
    saveTapeConfig(DEFAULT_TAPE_FILTER_CONFIG);
    set({ tapeFilterConfig: DEFAULT_TAPE_FILTER_CONFIG });
  },
  applyTapePreset: (presetKey) => {
    const p = TAPE_PRESETS[presetKey];
    if (p) {
      saveTapeConfig(p.config);
      set({ tapeFilterConfig: p.config });
    }
  },
  setScreenOrder: (screenOrder) => set({ screenOrder }),
  resetFilters: () => set({ ...INITIAL }),
}));
