// features/master/stores/strategyParamsStore.ts -- استور پارامترهای قابل تغییر و شخصی‌سازی استراتژی FTS
// بر پایه مهندسی معکوس و متدولوژی ۴ صفحه‌ای دوره نوسان‌گیری FTS (عرفان نصرتی)
import { create } from 'zustand';

export interface StrategyParameters {
  // فاز ۳: تابلوخوانی و غربالگری S (صفحه ۳)
  minVolumeRatio: number; // ضریب حجم مشکوک (پیش‌فرض جزوه: 3.0 برابر)
  minBuyerPower: number; // حداقل قدرت خریدار به فروشنده (پیش‌فرض: 1.2)
  clockPriceDiffPct: number; // درصد اختلاف آخرین از پایانی در الگوی ساعت (پیش‌فرض: 1.0%)
  clockStrictNegativeClose: boolean; // الزام پایانی منفی و آخرین مثبت در الگوی ساعت
  marketLiquidityMinHemmat: number; // حداقل ارزش معاملات خرد بازار مساعد (پیش‌فرض جزوه: 20 همت)

  // فاز ۲: تکنیکال دو زمانه T (صفحه ۲)
  stopLossMaPeriod: number; // دوره میانگین متحرک استاپ (پیش‌فرض جزوه: 14)
  stopLossFixedPct: number; // درصد استاپ ثابت نوسانی (پیش‌فرض: 5.0%)
  jetStabilizationDays: number; // مهلت روزهای تثبیت ستاپ جت (پیش‌فرض: 3 روز)
  fibStep1Level: number; // تراز پله ۱ فیبو (پیش‌فرض: 38.2%)
  fibStep2Level: number; // تراز پله ۲ فیبو (پیش‌فرض: 61.8%)
  hourglassWeeklyRsi: number; // سقف RSI هفتگی در کف تاریخی (پیش‌فرض: 7)
  thirdPeakWeeklyPct: number; // آستانه نزدیکی به خط روند در سقف سوم هفتگی (پیش‌فرض: 10%)
  thirdPeakDailyPct: number; // آستانه نزدیکی به خط روند در سقف سوم روزانه (پیش‌فرض: 5%)

  // فاز ۱: فیلتر بنیادی کدال F (صفحه ۱)
  minGrossMarginPct: number; // حداقل حاشیه سود ناخالص (پیش‌فرض: 20%)
  minMonthlySalesGrowthPct: number; // حداقل رشد فروش ماهانه کدال (پیش‌فرض: 40%)
  minFundScore: number; // حداقل امتیاز بنیادی از ۵ (پیش‌فرض: 4)
  excludePriceControlled: boolean; // حذف صنایع مشمول نرخ دستوری شدید نظیر خودرو
  psAnnualMultiplier: number; // ضریب سالانه کردن فروش ۳ ماهه (پیش‌فرض جزوه: 4)

  // فاز ۴: مدیریت سرمایه، مهندسی معکوس و خروج M (صفحه ۴)
  exitHalfPct: number; // درصد ذخیره سود در مقاومت اول R1 (پیش‌فرض جزوه: 50%)
  minRiskRewardRatio: number; // حداقل نسبت سود به ریسک (پیش‌فرض: 2.0)
  maxIndustryWeightPct: number; // سقف مجاز سرمایه‌گذاری در هر صنعت (پیش‌فرض: 20%)
  singleStockMaxWeightPct: number; // سقف مجاز تک‌سهم نوسانی (پیش‌فرض: 3.5%)
  hourglassLeverageMultiplier: number; // ضریب اهرم خرید پله‌ای در کف ساعت شنی (پیش‌فرض: 3.0 برابر)
  maxTotalPortfolioCapPct: number; // سقف کل دارایی در بورس (پیش‌فرض: 70%)
  warConditionCapPct: number; // سقف دارایی در شرایط جنگی (پیش‌فرض: 15%)
}

export const FTS_DEFAULT_PARAMS: StrategyParameters = {
  // تابلوخوانی
  minVolumeRatio: 3.0,
  minBuyerPower: 1.2,
  clockPriceDiffPct: 1.0,
  clockStrictNegativeClose: true,
  marketLiquidityMinHemmat: 20,

  // تکنیکال
  stopLossMaPeriod: 14,
  stopLossFixedPct: 5.0,
  jetStabilizationDays: 3,
  fibStep1Level: 38.2,
  fibStep2Level: 61.8,
  hourglassWeeklyRsi: 7,
  thirdPeakWeeklyPct: 10,
  thirdPeakDailyPct: 5,

  // بنیادی
  minGrossMarginPct: 20,
  minMonthlySalesGrowthPct: 40,
  minFundScore: 4,
  excludePriceControlled: true,
  psAnnualMultiplier: 4,

  // مدیریت سرمایه
  exitHalfPct: 50,
  minRiskRewardRatio: 2.0,
  maxIndustryWeightPct: 20,
  singleStockMaxWeightPct: 3.5,
  hourglassLeverageMultiplier: 3.0,
  maxTotalPortfolioCapPct: 70,
  warConditionCapPct: 15,
};

const STORAGE_KEY = 'fts.strategy.custom_parameters.v2';

function loadPersistedParams(): StrategyParameters {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return { ...FTS_DEFAULT_PARAMS, ...parsed };
      }
    }
  } catch {
    // بازگشت به مقادیر پیش‌فرض
  }
  return { ...FTS_DEFAULT_PARAMS };
}

interface StrategyParamsStoreState {
  params: StrategyParameters;
  updateParam: <K extends keyof StrategyParameters>(key: K, value: StrategyParameters[K]) => void;
  resetParam: (key: keyof StrategyParameters) => void;
  resetAll: () => void;
}

export const useStrategyParamsStore = create<StrategyParamsStoreState>((set) => ({
  params: loadPersistedParams(),

  updateParam: (key, value) => {
    set((state) => {
      const next = { ...state.params, [key]: value };
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        }
      } catch {
        // نادیده گرفتن خطا
      }
      return { params: next };
    });
  },

  resetParam: (key) => {
    set((state) => {
      const next = { ...state.params, [key]: FTS_DEFAULT_PARAMS[key] };
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        }
      } catch {
        // نادیده گرفتن خطا
      }
      return { params: next };
    });
  },

  resetAll: () => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // نادیده گرفتن خطا
    }
    set({ params: { ...FTS_DEFAULT_PARAMS } });
  },
}));
