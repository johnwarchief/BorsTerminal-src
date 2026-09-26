// features/market/lib/tapeAlgorithms.ts -- موتور الگوریتم‌های پیشرفته فیلترهای تابلو
// پشتیبانی از شخصی‌سازی تایم‌فریم‌ها، آستانه‌های عددی و استراتژی‌های غربالگری پویا.
//
// قراردادی که این فایل قبلاً نقض می‌کرد: هر گیتِ عددی باید یا **رد** شود یا
// **قبول**؛ «داده نداشتن» هیچ‌وقت قبول نیست. قبلاً هر گیت به شکلِ
// `if (cfg.x > 0 && typeof r.y === 'number')` نوشته شده بود، یعنی با نبودنِ
// y بی‌صدا رد می‌شد و ردیف قبول. روی تابلوی واقعی همین باعث شد ۶۷۱ ردیف
// «جت» بخورد در حالی که فیلترِ جزوه ۱ ردیف می‌دهد. ریاضیاتِ مشترکِ این
// تصمیم در tapeMath.ts نشسته (همان‌جا که SuspiciousPanel هم می‌خواند).
import type { MarketRow } from '@shared/types/marketRow';
import {
  JET_LADDER,
  detectJetBreakout,
  detectSuspiciousVolume,
  volumeMultiple,
} from './tapeMath';

/** نقاطِ پلکانِ مقاومتِ جزوه — همان JET_LADDER، تا انتخابِ UI گم نشود. */
export type LookbackDays = (typeof JET_LADDER)[number];

export type TapeFilterConfig = {
  /** ۱. الگوی ساعت (Clock Pattern) */
  clock: {
    minDeltaPct: number;          // حداقل فاصله آخرین از پایانی (جزوه: ۲٫۰٪)
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
    /** بلندترین نقطهٔ پلکانی که باید شکسته شود؛ همهٔ نقاطِ کوتاه‌تر هم لازم‌اند. */
    lookbackDays: LookbackDays;
    minBuyerPower: number;        // حداقل نسبت قدرت خریدار به فروشنده
    minVolRatio: number;          // حداقل ضریب حجم
    requireLastAboveClose: boolean; // آخرین بالاتر از پایانی
    minChangePct: number;         // حداقل درصد تغییر قیمت
    // رأیِ مالک (۱۴۰۵-۰۷-۰۳): جت هیچ شرطِ «حداقل تعدادِ معامله» ندارد — نه
    // در جزوه و نه در چارت ۳ عددی برایِ آن هست. بازگرداندنش ممنوع است.
    // جزوه «۱ بار» را رویِ ۳× حجم می‌شمارد؛ minVolRatioِ زیر ۳ اثری ندارد
    // چون گیتِ خودِ جزوه همیشه برقرار است.
  };
  /** ۴. کف‌روبی و جمع‌آوری صف (Kef Roobi / Sweep) */
  roobi: {
    maxChangePct: number;         // سقف درصد افت قیمت (جزوه: -۱٫۰٪)
    minVolRatio: number;          // ۰ = بدون شرط (جزوه چنین گیتی ندارد)
    minBuyerPower: number;        // ۰ = بدون شرط
    minTradeCount: number;        // جای‌نشینِ qd1 (تعدادِ معاملاتِ نشستِ پیش منبعِ داده ندارد)
  };
  /** ۵. نقطه‌زنی و کف‌یابی (Sniper / Near Low) */
  noqteh: {
    maxDistPct: number;           // حداکثر فاصله از کف ۳۰ روزه (درصد)
    minTradeCount: number;        // حداقل تعداد معامله
    minVolRatio: number;          // تاییدیه حجم
  };
  /** ۶. جریان پول نخبگان (Elite Smart Money Flow) — خارج از جزوه، پنلِ خودی */
  smartFlow: {
    minBuyerPower: number;        // حداقل قدرت خریدار
    minVolRatio: number;          // حداقل ضریب حجم
  };
};

/**
 * پیش‌فرض‌ها = فرمول‌هایِ پنج‌گانۀِ جزوه، نه سلیقۀِ برنامه‌نویس.
 * هر عددی که اینجا تغییر کند باید اول درِ جزوه پیدا شود.
 */
export const DEFAULT_TAPE_FILTER_CONFIG: TapeFilterConfig = {
  clock: {
    minDeltaPct: 2.0,          // pl >= pc * 1.02
    requireGoldenHour: false,  // انتخابی، درِ جزوه نیست
    minVolRatio: 1.0,          // tvol > 1 * avg30
    minTradeCount: 30,         // tno > 30
  },
  suspiciousVolume: {
    timeframe: 'monthly_30d',
    minRatio: 3.0,             // tvol > 3 * avg30
    minTradeCount: 50,         // tno > 50
  },
  jet: {
    lookbackDays: 59,          // پلکانِ کاملِ [ih][2..59].PriceMax
    minBuyerPower: 1.5,        // خریدِ حقیقی >= ۱٫۵ × فروشِ حقیقی
    minVolRatio: 3.0,
    requireLastAboveClose: true,
    minChangePct: 0.0,         // plp > 0
  },
  roobi: {
    maxChangePct: -1.0,        // plp < -1
    minVolRatio: 0,            // جزوه گیتِ حجم ندارد
    minBuyerPower: 0,          // جزوه گیتِ قدرت خریدار ندارد
    minTradeCount: 100,        // qd1 > 100
  },
  noqteh: {
    maxDistPct: 3.0,           // فاصله از کفِ ۳۰ روزه < ۳٪
    minTradeCount: 5,          // tno > 5
    minVolRatio: 1.0,          // tvol > 1 * avg30
  },
  smartFlow: {
    minBuyerPower: 2.0,
    minVolRatio: 1.5,
  },
};

export type TapePresetKey = 'scalp' | 'jet_trend' | 'sniper' | 'smart_money';

/**
 * نزدیک‌ترین نقطۀِ معتبرِ پلکان به مقدارِ درخواستی (به بالا گِرد می‌کند).
 * کانفیگِ ذخیره‌شده در localStorage ممکن است از نسخه‌ای آمده باشد که
 * «۱ روزه» گزینه داشت؛ آن مقدار دیگر هیچ نقطۀِ پلکانی را پوشش نمی‌دهد و
 * بی‌صدا جت را برای همیشه خاموش می‌کند. این تابع همان را به ۲ می‌برد.
 */
export function coerceLookback(v: unknown): LookbackDays {
  const n = typeof v === 'number' && Number.isFinite(v) ? v : NaN;
  if (Number.isFinite(n)) {
    for (const k of JET_LADDER) if (k >= n) return k;
  }
  return DEFAULT_TAPE_FILTER_CONFIG.jet.lookbackDays;
}
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
//
// قانونِ مشترکِ همهٔ توابعِ این بخش: هر گیتِ فعالی که ورودی‌اش را ندارد،
// **رد** می‌کند. `gate(value, min)` تنها همان را می‌گوید.
// ─────────────────────────────────────────────────────────────────────────────

/** عددِ معتبر؛ بقیهٔ چیزها null است، از جمله NaN و بی‌نهایت. */
function num(v: number | null | undefined): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** گیتِ پایین‌حد: نداشتنِ داده یعنی رد، حتی اگر آستانه صفر باشد. */
function atLeast(value: number | null | undefined, min: number): boolean {
  const v = num(value);
  return v != null && v >= min;
}

/** گیتِ بالا‌حد: همان قاعده، در جهتِ مخالف. */
function atMost(value: number | null | undefined, max: number): boolean {
  const v = num(value);
  return v != null && v <= max;
}

/** ۱. الگوی ساعت — جزوه: ``pl >= pc*1.02 && tvol > avg30 && tno > 30`` */
export function matchClockPattern(r: MarketRow, cfg: TapeFilterConfig['clock']): boolean {
  const last = num(r.p_last);
  const close = num(r.p_closing);
  if (last == null || close == null || close <= 0) return false;

  const deltaPct = ((last - close) / close) * 100;
  if (deltaPct < cfg.minDeltaPct) return false;

  if (cfg.requireGoldenHour) {
    const yest = num(r.price_yesterday);
    if (yest == null || !(close < yest && last > yest)) return false;
  }

  if (cfg.minVolRatio > 0) {
    const mult = volumeMultiple(r.tvol, r.month_avg_vol);
    if (mult == null || mult <= cfg.minVolRatio) return false;
  }

  return atLeast(r.z_tot_tran, cfg.minTradeCount + 1);
}

/** ۲. حجم مشکوک — جزوه: ``tvol > 3*avg30 && tno > 50`` */
export function matchSuspiciousVolume(r: MarketRow, cfg: TapeFilterConfig['suspiciousVolume']): boolean {
  const hit = cfg.timeframe === 'prev_day_dod'
    ? atLeast(r.vol_dod, cfg.minRatio)
    : detectSuspiciousVolume({
        tvol: r.tvol,
        month_avg_vol: r.month_avg_vol,
        z_tot_tran: r.z_tot_tran,
      }).hit;
  if (!hit) return false;
  if (cfg.timeframe === 'prev_day_dod') return atLeast(r.z_tot_tran, cfg.minTradeCount + 1);
  return true;
}

/**
 * ۳. فیلتر جت FTS — جزوه:
 * ``tvol > 3*avg30 && خریدحقیقی/معامله >= 1.5 × فروشحقیقی/معامله
 *   && pl >= pc && plp > 0 && [ih][2..59].PriceMax < pl``
 * مقایسه با «آخرین» است، نه «پایانی»؛ و با همهٔ نقاطِ پلکان، نه یک نقطه.
 */
export function matchJetFilter(r: MarketRow, cfg: TapeFilterConfig['jet']): boolean {
  return detectJetBreakout(r, cfg.lookbackDays, cfg.minBuyerPower, cfg.minVolRatio,
                           cfg.requireLastAboveClose, cfg.minChangePct).hit;
}

/** ۴. کف‌روبی و جمع‌آوری صف — جزوه: ``pl == tmin && zd1 > 1 && plp < -1 && qd1 > 100`` */
export function matchRoobiFilter(r: MarketRow, cfg: TapeFilterConfig['roobi']): boolean {
  const last = num(r.p_last);
  const low = num(r.p_min);
  // «روی کفِ روز نشسته» — همین گیت، ستونِ اصلیِ کف‌روبی است و حذف‌شدنی نیست.
  if (last == null || low == null || last !== low) return false;
  if (!atLeast(r.prev_day_vol, 2)) return false;          // zd1 > 1
  if (!atMost(r.percent_change, cfg.maxChangePct)) return false;
  // قیدِ جزوه «>» است، پس آستانه +۰٫۰۰۱ نه؛ برایِ شمارۀِ صحیحِ معاملات همان +۱.
  if (!atLeast(r.z_tot_tran, cfg.minTradeCount + 1)) return false;

  if (cfg.minVolRatio > 0) {
    const mult = volumeMultiple(r.tvol, r.month_avg_vol);
    if (mult == null || mult <= cfg.minVolRatio) return false;
  }
  if (cfg.minBuyerPower > 0 && !atLeast(r.buyer_power, cfg.minBuyerPower)) return false;
  return true;
}

/** ۵. نقطه‌زنی و کف‌یابی — جزوه: ``round((pc-min29)/pc*100,2) < 3 && tvol > avg30 && tno > 5`` */
export function matchNoqtehFilter(r: MarketRow, cfg: TapeFilterConfig['noqteh']): boolean {
  const close = num(r.p_closing);
  const min30 = num(r.min30_low);
  if (close == null || close <= 0 || min30 == null || min30 <= 0) return false;

  const distPct = Math.round(((close - min30) / close) * 100 * 100) / 100;
  if (distPct < 0 || distPct >= cfg.maxDistPct) return false;

  if (cfg.minVolRatio > 0) {
    const mult = volumeMultiple(r.tvol, r.month_avg_vol);
    if (mult == null || mult <= cfg.minVolRatio) return false;
  }
  return atLeast(r.z_tot_tran, cfg.minTradeCount + 1);
}

/** ۶. جریان پول هوشمند نخبگان — پنلِ خودی، خارج از جزوه */
export function matchSmartFlowFilter(r: MarketRow, cfg: TapeFilterConfig['smartFlow']): boolean {
  if (!atLeast(r.buyer_power, cfg.minBuyerPower)) return false;
  const mult = volumeMultiple(r.tvol, r.month_avg_vol);
  return mult != null && mult >= cfg.minVolRatio;
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
