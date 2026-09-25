// features/market/lib/tapeAlgorithms.ts -- موتور الگوریتم‌های پیشرفته فیلترهای تابلو
// پشتیبانی از شخصی‌سازی تایم‌فریم‌ها، آستانه‌های عددی و استراتژی‌های غربالگری پویا.
import type { MarketRow } from '@shared/types/marketRow';

export type LookbackDays = 1 | 5 | 9 | 19 | 29 | 39 | 49 | 59;

export type TapeFilterConfig = {
  /** ۱. الگوی ساعت (Clock Pattern) */
  clock: {
    minDeltaPct: number;          // حداقل فاصله آخرین از پایانی (پیش‌فرض: ۱.۰٪)
    requireGoldenHour: boolean;   // شرط ساعت طلایی (پایانی منفی و آخرین مثبت)
    minVolRatio: number;          // حداقل نسبت به میانگین حجم ۳۰ روزه
    minTradeCount: number;        // حداقل تعداد معاملات
  };
  /** ۲. حجم مشکوک (Suspicious Volume) */
  suspiciousVolume: {
    timeframe: 'monthly_30d' | 'prev_day_dod'; // تایم‌فریم مرجع حجم (۳۰ روزه یا روز قبل)
    minRatio: number;             // آستانه ضریب حجم (پیش‌فرض: ۳.۰×)
    minTradeCount: number;        // حداقل تعداد معاملات
  };
  /** ۳. فیلتر جت FTS (Jet Breakout) */
  jet: {
    lookbackDays: LookbackDays;   // تایم‌فریم شکست سقف تاریخی (۱، ۵، ۹، ۱۹، ۲۹، ۳۹، ۴۹ یا ۵۹ روزه)
    minBuyerPower: number;        // حداقل نسبت قدرت خریدار به فروشنده
    minVolRatio: number;          // حداقل ضریب حجم
    requireLastAboveClose: boolean; // آخرین بالاتر از پایانی
    minChangePct: number;         // حداقل درصد تغییر قیمت
    // رأیِ مالک (۱۴۰۵-۰۷-۰۳): جت هیچ شرطِ «حداقل تعدادِ معامله» ندارد — نه
    // در جزوه و نه در چارت ۳ عددی برایِ آن هست. بازگرداندنش ممنوع است.
  };
  /** ۴. کف‌روبی و جمع‌آوری صف (Kef Roobi / Sweep) */
  roobi: {
    maxChangePct: number;         // سقف درصد افت قیمت (مثلاً -۱.۰٪)
    minVolRatio: number;          // ضریب حجم جمع‌آوری
    minBuyerPower: number;        // قدرت خریدار جمع‌کننده
    minTradeCount: number;        // حداقل تعداد معاملات (>۲۰۰ طبق جزوه)
  };
  /** ۵. نقطه‌زنی و کف‌یابی (Sniper / Near Low) */
  noqteh: {
    maxDistPct: number;           // حداکثر فاصله از کف ۳۰ روزه (درصد)
    minTradeCount: number;        // حداقل تعداد معامله
    minVolRatio: number;          // تاییدیه حجم
  };
  /** ۶. جریان پول نخبگان (Elite Smart Money Flow) */
  smartFlow: {
    minBuyerPower: number;        // حداقل قدرت خریدار
    minVolRatio: number;          // حداقل ضریب حجم
  };
};

export const DEFAULT_TAPE_FILTER_CONFIG: TapeFilterConfig = {
  clock: {
    minDeltaPct: 1.0,
    requireGoldenHour: false,
    minVolRatio: 1.0,
    minTradeCount: 30,
  },
  suspiciousVolume: {
    timeframe: 'monthly_30d',
    minRatio: 3.0,
    minTradeCount: 50,
  },
  jet: {
    lookbackDays: 59,
    minBuyerPower: 1.5,
    minVolRatio: 3.0,
    requireLastAboveClose: true,
    minChangePct: 0.0,
  },
  roobi: {
    maxChangePct: -1.0,
    minVolRatio: 2.0,
    minBuyerPower: 1.2,
    minTradeCount: 200,
  },
  noqteh: {
    maxDistPct: 3.0,
    minTradeCount: 5,
    minVolRatio: 1.0,
  },
  smartFlow: {
    minBuyerPower: 2.0,
    minVolRatio: 1.5,
  },
};

export type TapePresetKey = 'scalp' | 'jet_trend' | 'sniper' | 'smart_money';

export const TAPE_PRESETS: Record<TapePresetKey, { label: string; desc: string; config: TapeFilterConfig }> = {
  scalp: {
    label: 'نوسان‌گیری سریع و ساعت قوی',
    desc: 'دلتای ساعت ۱.۵٪ + شکست سقف کوتاه‌مدت ۵ روزه با حجم ۲×',
    config: {
      ...DEFAULT_TAPE_FILTER_CONFIG,
      clock: { ...DEFAULT_TAPE_FILTER_CONFIG.clock, minDeltaPct: 1.5, requireGoldenHour: false,
               minVolRatio: 1.2, minTradeCount: 40 },
      jet: { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 5, minBuyerPower: 1.3,
             minVolRatio: 2.0, requireLastAboveClose: true, minChangePct: 1.0 },
      suspiciousVolume: { ...DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume,
                          timeframe: 'prev_day_dod', minRatio: 2.0, minTradeCount: 30 },
    },
  },
  jet_trend: {
    label: 'سوئینگ و شکست سقف روندی',
    desc: 'شکست سقف ۳۰ روزه + قدرت خریدار ۲× و حجم مشکوک ۳×',
    config: {
      ...DEFAULT_TAPE_FILTER_CONFIG,
      jet: { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 29, minBuyerPower: 2.0,
             minVolRatio: 3.0, requireLastAboveClose: true, minChangePct: 2.0 },
      suspiciousVolume: { ...DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume,
                          timeframe: 'monthly_30d', minRatio: 3.0, minTradeCount: 50 },
    },
  },
  sniper: {
    label: 'کف‌نشینی کم‌ریسک (Sniper)',
    desc: 'فاصله زیر ۲٪ از کف ۳۰ روزه با خریدار قوی و حجم کنترل‌شده',
    config: {
      ...DEFAULT_TAPE_FILTER_CONFIG,
      noqteh: { ...DEFAULT_TAPE_FILTER_CONFIG.noqteh, maxDistPct: 2.0, minTradeCount: 10,
                minVolRatio: 1.2 },
      roobi: { ...DEFAULT_TAPE_FILTER_CONFIG.roobi, maxChangePct: -2.0, minVolRatio: 2.5,
               minBuyerPower: 1.5 },
    },
  },
  smart_money: {
    label: 'ورود سنگین پول هوشمند',
    desc: 'قدرت خریدار بالای ۲.۵× و حجم معاملات بالای ۳ برابر میانگین',
    config: {
      ...DEFAULT_TAPE_FILTER_CONFIG,
      smartFlow: { ...DEFAULT_TAPE_FILTER_CONFIG.smartFlow, minBuyerPower: 2.5,
                   minVolRatio: 3.0 },
      suspiciousVolume: { ...DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume,
                          timeframe: 'monthly_30d', minRatio: 3.0, minTradeCount: 60 },
      jet: { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 19, minBuyerPower: 2.2,
             minVolRatio: 3.0, requireLastAboveClose: true, minChangePct: 1.0 },
    },
  },
};

/** آیا کانفیگ با پیش‌فرض تفاوت دارد؟ */
export function isConfigCustomized(cfg: TapeFilterConfig): boolean {
  return JSON.stringify(cfg) !== JSON.stringify(DEFAULT_TAPE_FILTER_CONFIG);
}

// ─────────────────────────────────────────────────────────────────────────────
// الگوریتم‌های ارزیابی ردیف
// ─────────────────────────────────────────────────────────────────────────────

/** ۱. الگوی ساعت */
export function matchClockPattern(r: MarketRow, cfg: TapeFilterConfig['clock']): boolean {
  const last = r.p_last;
  const close = r.p_closing;
  const yest = r.price_yesterday;
  if (typeof last !== 'number' || typeof close !== 'number' || close <= 0) return false;

  const deltaPct = ((last - close) / close) * 100;
  if (deltaPct < cfg.minDeltaPct) return false;

  if (cfg.requireGoldenHour) {
    if (typeof yest !== 'number' || !(close < yest && last > yest)) return false;
  }

  if (cfg.minVolRatio > 0 && typeof r.vol_ratio === 'number') {
    if (r.vol_ratio < cfg.minVolRatio) return false;
  }

  if (cfg.minTradeCount > 0 && typeof r.z_tot_tran === 'number') {
    if (r.z_tot_tran < cfg.minTradeCount) return false;
  }

  return true;
}

/** ۲. حجم مشکوک */
export function matchSuspiciousVolume(r: MarketRow, cfg: TapeFilterConfig['suspiciousVolume']): boolean {
  const ratio = cfg.timeframe === 'prev_day_dod' ? r.vol_dod : r.vol_ratio;
  if (typeof ratio !== 'number' || !Number.isFinite(ratio)) return false;
  if (ratio < cfg.minRatio) return false;

  if (cfg.minTradeCount > 0 && typeof r.z_tot_tran === 'number') {
    if (r.z_tot_tran < cfg.minTradeCount) return false;
  }

  return true;
}

/** ۳. فیلتر جت FTS */
export function matchJetFilter(r: MarketRow, cfg: TapeFilterConfig['jet']): boolean {
  const close = r.p_closing;
  const last = r.p_last;
  if (typeof close !== 'number' || close <= 0) return false;

  if (cfg.requireLastAboveClose) {
    if (typeof last !== 'number' || last < close) return false;
  }

  if (typeof r.percent_change === 'number' && r.percent_change < cfg.minChangePct) {
    return false;
  }

  if (typeof r.buyer_power === 'number' && r.buyer_power < cfg.minBuyerPower) {
    return false;
  }

  if (typeof r.vol_ratio === 'number' && r.vol_ratio < cfg.minVolRatio) {
    return false;
  }

  // شکست سقف تایم‌فریم مشخص‌شده
  const highMap: Record<LookbackDays, number | null | undefined> = {
    1: r.h1_max,
    5: r.h5_max,
    9: r.h9_max,
    19: r.h19_max,
    29: r.h29_max,
    39: r.h39_max,
    49: r.h49_max,
    59: r.h59_max,
  };
  const targetHigh = highMap[cfg.lookbackDays];
  if (typeof targetHigh === 'number' && targetHigh > 0) {
    if (close <= targetHigh) return false;
  }

  // تعدادِ معامله اینجا عمداً شرط نیست (رأیِ مالک ۱۴۰۵-۰۷-۰۳).

  return true;
}

/** ۴. کف‌روبی و جمع‌آوری صف */
export function matchRoobiFilter(r: MarketRow, cfg: TapeFilterConfig['roobi']): boolean {
  if (typeof r.percent_change === 'number' && r.percent_change > cfg.maxChangePct) {
    return false;
  }

  if (typeof r.vol_ratio === 'number' && r.vol_ratio < cfg.minVolRatio) {
    return false;
  }

  if (typeof r.buyer_power === 'number' && r.buyer_power < cfg.minBuyerPower) {
    return false;
  }

  // تاییدیه کف قیمتی روز (نزدیک به کف روزانه)
  if (typeof r.p_min === 'number' && typeof r.p_closing === 'number') {
    if (r.p_closing > r.p_min * 1.025) return false;
  }

  if (cfg.minTradeCount > 0 && typeof r.z_tot_tran === 'number') {
    if (r.z_tot_tran < cfg.minTradeCount) return false;
  }

  return true;
}

/** ۵. نقطه‌زنی و کف‌یابی */
export function matchNoqtehFilter(r: MarketRow, cfg: TapeFilterConfig['noqteh']): boolean {
  const close = r.p_closing;
  const min30 = r.min30_low;
  if (typeof close !== 'number' || close <= 0 || typeof min30 !== 'number' || min30 <= 0) return false;

  const distPct = ((close - min30) / close) * 100;
  if (distPct < 0 || distPct > cfg.maxDistPct) return false;

  if (cfg.minVolRatio > 0 && typeof r.vol_ratio === 'number') {
    if (r.vol_ratio < cfg.minVolRatio) return false;
  }

  if (cfg.minTradeCount > 0 && typeof r.z_tot_tran === 'number') {
    if (r.z_tot_tran < cfg.minTradeCount) return false;
  }

  return true;
}

/** ۶. جریان پول هوشمند نخبگان */
export function matchSmartFlowFilter(r: MarketRow, cfg: TapeFilterConfig['smartFlow']): boolean {
  if (typeof r.buyer_power === 'number' && r.buyer_power < cfg.minBuyerPower) {
    return false;
  }
  if (typeof r.vol_ratio === 'number' && r.vol_ratio < cfg.minVolRatio) {
    return false;
  }
  return true;
}

/**
 * ارزیابی فیلتر سریع بر اساس الگوریتم‌های پویا
 */
export function evaluateDynamicQuickFilter(
  r: MarketRow,
  filterKey: string,
  cfg: TapeFilterConfig,
): boolean {
  switch (filterKey) {
    case 'f_clock':
      return matchClockPattern(r, cfg.clock);
    case 'f_susp':
      return matchSuspiciousVolume(r, cfg.suspiciousVolume);
    case 'f_jet':
      return matchJetFilter(r, cfg.jet);
    case 'f_roobi':
      return matchRoobiFilter(r, cfg.roobi);
    case 'f_noqteh':
      return matchNoqtehFilter(r, cfg.noqteh);
    case 'f_smart_flow':
      return matchSmartFlowFilter(r, cfg.smartFlow);
    default:
      return Boolean((r as unknown as Record<string, unknown>)[filterKey]);
  }
}
