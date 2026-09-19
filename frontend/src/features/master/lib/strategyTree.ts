// features/master/lib/strategyTree.ts -- مدل درختی و تنظیمات استراتژی معاملاتی FTS
// امکان کاستومایز کردن هر شاخه از ۴ مرحله به صورت درخت تصمیم‌گیری (Decision Tree)

export type ConditionType = 'veto' | 'required' | 'weighted';

export type TapeBranchConfig = {
  id: 'tape';
  title: 'غربالگری تابلوی بازار و حجم';
  enabled: boolean;
  clockPatternRequired: boolean;
  minVolumeRatio: number; // مثلاً 3.0×
  minBuyerPower: number; // مثلاً 1.2
  weight: number;
};

export type TechnicalBranchConfig = {
  id: 'technical';
  title: 'تحلیل تکنیکال ۲ زمانه';
  enabled: boolean;
  weeklyUptrendVeto: boolean; // وتوی قطعی در نزول هفتگی
  jetSetupAllowed: boolean;
  chochSetupAllowed: boolean;
  pointHuntAllowed: boolean;
  doubleBottomAllowed: boolean;
  stopLossMode: 'fixed_5pct' | 'major_low' | 'ma14';
  weight: number;
};

export type FundamentalBranchConfig = {
  id: 'fundamental';
  title: 'سلامت ۵ شاخص بنیادی';
  enabled: boolean;
  minScore: number; // 1 تا 5
  strictPriceControlExclusion: boolean; // حذف صنایع دستوری
  minGrossMarginPct: number; // پیش‌فرض 20%
  weight: number;
};

export type MasterBranchConfig = {
  id: 'master';
  title: 'داوری مستر و مدیریت سرمایه';
  enabled: boolean;
  halfExitAtResistance: boolean; // ذخیره سود 50%
  basePositionWeightPct: number; // وزن هر پله: 2 تا 10%
  hourglassLeverageEnabled: boolean; // اهرم ساعت شنی 2 تا 4 برابر
  weight: number;
};

export type StrategyTreeConfig = {
  name: string;
  presetKey: 'standard_trend' | 'fast_swing' | 'deep_hourglass' | 'custom';
  tape: TapeBranchConfig;
  technical: TechnicalBranchConfig;
  fundamental: FundamentalBranchConfig;
  master: MasterBranchConfig;
};

export const DEFAULT_STRATEGY_TREES: Record<'standard_trend' | 'fast_swing' | 'deep_hourglass', StrategyTreeConfig> = {
  standard_trend: {
    name: 'پلن سهامداری روندی استاندارد FTS',
    presetKey: 'standard_trend',
    tape: {
      id: 'tape',
      title: 'غربالگری تابلوی بازار و حجم',
      enabled: true,
      clockPatternRequired: false,
      minVolumeRatio: 2.0,
      minBuyerPower: 1.1,
      weight: 25,
    },
    technical: {
      id: 'technical',
      title: 'تحلیل تکنیکال ۲ زمانه',
      enabled: true,
      weeklyUptrendVeto: true,
      jetSetupAllowed: true,
      chochSetupAllowed: true,
      pointHuntAllowed: true,
      doubleBottomAllowed: true,
      stopLossMode: 'major_low',
      weight: 35,
    },
    fundamental: {
      id: 'fundamental',
      title: 'سلامت ۵ شاخص بنیادی',
      enabled: true,
      minScore: 4,
      strictPriceControlExclusion: true,
      minGrossMarginPct: 20,
      weight: 40,
    },
    master: {
      id: 'master',
      title: 'داوری مستر و مدیریت سرمایه',
      enabled: true,
      halfExitAtResistance: true,
      basePositionWeightPct: 5.0,
      hourglassLeverageEnabled: false,
      weight: 100,
    },
  },
  fast_swing: {
    name: 'پلن نوسان‌گیری سریع FTS',
    presetKey: 'fast_swing',
    tape: {
      id: 'tape',
      title: 'غربالگری تابلوی بازار و حجم',
      enabled: true,
      clockPatternRequired: true,
      minVolumeRatio: 3.0,
      minBuyerPower: 1.3,
      weight: 40,
    },
    technical: {
      id: 'technical',
      title: 'تحلیل تکنیکال ۲ زمانه',
      enabled: true,
      weeklyUptrendVeto: false,
      jetSetupAllowed: true,
      chochSetupAllowed: true,
      pointHuntAllowed: true,
      doubleBottomAllowed: false,
      stopLossMode: 'fixed_5pct',
      weight: 40,
    },
    fundamental: {
      id: 'fundamental',
      title: 'سلامت ۵ شاخص بنیادی',
      enabled: true,
      minScore: 3,
      strictPriceControlExclusion: false,
      minGrossMarginPct: 15,
      weight: 20,
    },
    master: {
      id: 'master',
      title: 'داوری مستر و مدیریت سرمایه',
      enabled: true,
      halfExitAtResistance: false, // خروج 100% در R1
      basePositionWeightPct: 3.5,
      hourglassLeverageEnabled: false,
      weight: 100,
    },
  },
  deep_hourglass: {
    name: 'پلن سرمایه‌گذاری ساعت شنی FTS',
    presetKey: 'deep_hourglass',
    tape: {
      id: 'tape',
      title: 'غربالگری تابلوی بازار و حجم',
      enabled: false, // بدون اهمیت به تابلوی روزانه
      clockPatternRequired: false,
      minVolumeRatio: 1.0,
      minBuyerPower: 0.8,
      weight: 10,
    },
    technical: {
      id: 'technical',
      title: 'تحلیل تکنیکال ۲ زمانه',
      enabled: true,
      weeklyUptrendVeto: false,
      jetSetupAllowed: true,
      chochSetupAllowed: false,
      pointHuntAllowed: true,
      doubleBottomAllowed: true,
      stopLossMode: 'major_low',
      weight: 30,
    },
    fundamental: {
      id: 'fundamental',
      title: 'سلامت ۵ شاخص بنیادی',
      enabled: true,
      minScore: 5,
      strictPriceControlExclusion: true,
      minGrossMarginPct: 25,
      weight: 60,
    },
    master: {
      id: 'master',
      title: 'داوری مستر و مدیریت سرمایه',
      enabled: true,
      halfExitAtResistance: false,
      basePositionWeightPct: 10.0,
      hourglassLeverageEnabled: true,
      weight: 100,
    },
  },
};

const STRATEGY_TREE_STORAGE_KEY = 'fts.strategy.tree.config.v1';

export function loadStrategyTree(): StrategyTreeConfig {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const raw = localStorage.getItem(STRATEGY_TREE_STORAGE_KEY);
      if (raw) {
        return JSON.parse(raw);
      }
    }
  } catch {
    // fallback
  }
  return DEFAULT_STRATEGY_TREES.standard_trend;
}

export function saveStrategyTree(config: StrategyTreeConfig): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem(STRATEGY_TREE_STORAGE_KEY, JSON.stringify(config));
    }
  } catch {
    // fallback
  }
}
