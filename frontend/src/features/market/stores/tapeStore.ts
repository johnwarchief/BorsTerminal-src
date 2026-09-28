// features/market/stores/tapeStore.ts -- فیلترهای محلی تابلو
import { create } from 'zustand';
import { ASSET_TYPES, type AssetType } from '../lib/assetType';

import {
  DEFAULT_TAPE_FILTER_CONFIG,
  TAPE_PRESETS,
  coerceLookback,
  tapeFilterVerdict,
  type TapeFilterConfig,
  type TapePresetKey,
} from '../lib/tapeAlgorithms';

export const QUICK_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'] as const;
export type QuickFilter = (typeof QUICK_FILTERS)[number];

export const QUICK_LABELS: Record<QuickFilter, string> = {
  f_clock: 'الگوی ساعت',
  f_susp: 'حجم مشکوک',
  f_jet: 'فیلتر جت',
  f_roobi: 'کف‌روبی',
  f_noqteh: 'نقطه زنی',
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

/**
 * عبور از فیلتر «خروج از انباشت»: هم ساعت و هم حجم مشکوک. داوری از همان
 * `tapeFilterVerdict` واحد می‌آید — پیش از این پرچمِ خامِ بک‌اند خوانده می‌شد،
 * پس همین یک فیلتر می‌توانست با چیپ و ستونِ «الگو»یِ همان صفحه نخواند.
 */
export function matchesExitAccum(
  row: Parameters<typeof tapeFilterVerdict>[0],
  config?: TapeFilterConfig,
): boolean {
  if (!config) {
    return Boolean((row as unknown as Record<string, unknown>).f_clock) &&
      Boolean((row as unknown as Record<string, unknown>).f_susp);
  }
  return tapeFilterVerdict(row, 'f_clock', config) && tapeFilterVerdict(row, 'f_susp', config);
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

/**
 * v2: پنج فیلتر به فرمول‌هایِ جزوه تنظیم مجدد شد. کلیدِ قدیمی اگر می‌ماند،
 * آستانه‌هایِ غلطِ نسخهٔ قبل (مثل دلتای ۱٪ ساعت یا «۲۰۰ طبق جزوهٔ» کف‌روبی)
 * برایِ همیشه رویِ دستگاهِ کاربر باقی می‌ماند و اصلاحِ پیش‌فرض‌ها به کاربر
 * نمی‌رسید.
 */
const TAPE_CONFIG_KEY = 'bors_tape_filter_config_v2';

/**
 * «نمایشِ ردیف‌های پسوندِ عددی» یک تنظیمِ ماندگار است، نه یک فیلترِ جلسه‌ای:
 * ردیف‌هایِ «فولاد۱» ردیف‌هایِ روزهایِ قبل‌اند و کاربری که یک‌بار آن‌ها را
 * می‌خواهد هر روز نباید دوباره کلیک کند. پیش‌فرض = رفتارِ همیشگیِ تابلو
 * (حذف)، پس این کلید رویِ نصبِ به‌روز نشده هیچ چیز را عوض نمی‌کند.
 */
const SHOW_SUFFIX_KEY = 'bors_tape_show_numeric_suffix_v1';

function loadShowSuffix(): boolean {
  try {
    return typeof window !== 'undefined' && localStorage.getItem(SHOW_SUFFIX_KEY) === '1';
  } catch {
    return false;
  }
}

function saveShowSuffix(v: boolean) {
  try {
    if (typeof window !== 'undefined') localStorage.setItem(SHOW_SUFFIX_KEY, v ? '1' : '0');
  } catch {
    // ignore
  }
}

function mergeBlock<T extends object>(base: T, saved: unknown): T {
  const s = (saved && typeof saved === 'object' ? saved : {}) as Record<string, unknown>;
  return { ...base, ...s } as T;
}

function loadInitialTapeConfig(): TapeFilterConfig {
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem(TAPE_CONFIG_KEY) : null;
    if (!raw) return DEFAULT_TAPE_FILTER_CONFIG;
    const parsed = JSON.parse(raw) as Partial<TapeFilterConfig>;
    return {
      clock: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.clock, parsed.clock),
      suspiciousVolume: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume, parsed.suspiciousVolume),
      jet: { ...mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.jet, parsed.jet),
             lookbackDays: coerceLookback((parsed.jet as { lookbackDays?: unknown } | undefined)?.lookbackDays) },
      roobi: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.roobi, parsed.roobi),
      noqteh: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.noqteh, parsed.noqteh),
      smartFlow: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.smartFlow, parsed.smartFlow),
      basis: mergeBlock(DEFAULT_TAPE_FILTER_CONFIG.basis, parsed.basis),
    };
  } catch {
    // ignore
  }
  return DEFAULT_TAPE_FILTER_CONFIG;
}

function saveTapeConfig(cfg: TapeFilterConfig) {
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem(TAPE_CONFIG_KEY, JSON.stringify(cfg));
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
  /** فقط نمادهای زنده (is_live !== false) — پیش‌فرض روشن (#197) */
  liveOnly: boolean;
  /** جهت تغییر قیمت */
  direction: DirectionFilter;
  /** فیلتر ضریب حجم مشکوک فعال است؟ */
  volRatioOn: boolean;
  /** آستانهٔ vol_ratio (۱.۵ تا ۵، پیش‌فرض ۳) */
  volRatioMin: number;
  /** فیلتر ترکیبی «خروج از انباشت» (فقط در صفحهٔ تابلو) */
  exitAccum: boolean;
  /**
   * ردیف‌های «پسوندِ عددی» (فولاد۱، وخار۲ …) در تابلو دیده شوند؟
   * `false` = قاعدۀ همیشگی: این ردیف‌ها از نما کنار گذاشته می‌شوند.
   */
  showNumericSuffix: boolean;
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
  setShowNumericSuffix: (v: boolean) => void;
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
  // #197: «فقط زنده» پیش‌فرضِ جدول است. اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵ ساعت ۱۱:۱۴ روی
  // برنامۀ نصب‌شده: در ۷۵ ثانیه هیچ عددی در ۷۳۱ سلولِ دیدنی تکان نخورد و هیچ
  // فلشی اجرا نشد — چون چیدمانِ پیش‌فرض ۱۶ ردیفِ بیرونِ تابلو (مُهرِ ۲۰۲۱) را
  // بالا می‌آورد و اعدادِ آن‌ها هرگز عوض نمی‌شود. فلش سالم بود، فقط روی
  // ردیف‌هایِ مُرده حساب می‌شد. کاربر خودش رأی داد: جدول فقط زنده باشد.
  liveOnly: true,
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
  showNumericSuffix: loadShowSuffix(),
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
  setShowNumericSuffix: (v) => {
    saveShowSuffix(v);
    set({ showNumericSuffix: v });
  },
  setTapeFilterConfig: (partial) =>
    set((s) => {
      const updated: TapeFilterConfig = {
        clock: { ...s.tapeFilterConfig.clock, ...(partial.clock ?? {}) },
        suspiciousVolume: { ...s.tapeFilterConfig.suspiciousVolume, ...(partial.suspiciousVolume ?? {}) },
        jet: { ...s.tapeFilterConfig.jet, ...(partial.jet ?? {}) },
        roobi: { ...s.tapeFilterConfig.roobi, ...(partial.roobi ?? {}) },
        noqteh: { ...s.tapeFilterConfig.noqteh, ...(partial.noqteh ?? {}) },
        smartFlow: { ...s.tapeFilterConfig.smartFlow, ...(partial.smartFlow ?? {}) },
        basis: { ...s.tapeFilterConfig.basis, ...(partial.basis ?? {}) },
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
  resetFilters: () => {
    // «بازنشانی» همان چیزی است که کاربر برای برگشت به تابلویِ پیش‌فرض می‌زند؛
    // تنظیمِ ماندگارِ پسوندِ عددی هم مثل liveOnly به پیش‌فرض برمی‌گردد.
    saveShowSuffix(false);
    set({ ...INITIAL, showNumericSuffix: false });
  },
}));
