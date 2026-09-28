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
  LOW_BASE_SESSIONS,
  ROOBI_ZD1_MIN,
  detectJetBreakout,
  filterVolumeRatio,
  filterVolumeRatioWithToday,
} from './tapeMath';

/** نقاطِ پلکانِ مقاومتِ جزوه — همان JET_LADDER، تا انتخابِ UI گم نشود. */
export type LookbackDays = (typeof JET_LADDER)[number];

/**
 * پنج فیلترِ فایل دربارهٔ **همین نشست** حرف می‌زنند. ردیفی که رویِ تابلویِ امروز
 * نیست (`is_live === false` — اختیارِ سررسیدشده، نمادِ متوقف) از نشستِ خودشِ
 * قدیمی داوری می‌شود و «حجمِ امروزِ من سه برابرِ مبناءست» را دروغ می‌گوید:
 * اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵ — «حجم مشکوک» ۷۴ ردیف، فیلترنویس ۱۹ ردیف، و ۵۵ تای
 * ما فسیل بودند. نبودنِ ستون یعنی زنده (پنل‌هایِ قدیمی آن را نمی‌فرستند).
 */
export function isLiveBoardRow(r: MarketRow): boolean {
  return r.is_live !== false;
}

export type TapeFilterConfig = {
  /** ۱. الگوی ساعت (Clock Pattern) */
  clock: {
    minDeltaPct: number;          // حداقل فاصله آخرین از پایانی (جزوه: ۲٫۰٪)
    requireGoldenHour: boolean;   // شرط ساعت طلایی (پایانی منفی و آخرین مثبت)
    minVolRatio: number;          // حداقل نسبت حجم به مبنای فایل (Σ[ih][0..29]/30)
    minTradeCount: number;        // حداقل تعداد معاملات
  };
  /** ۲. حجم مشکوک (Suspicious Volume) */
  suspiciousVolume: {
    timeframe: 'monthly_30d' | 'prev_day_dod'; // تایم‌فریم مرجع حجم (مبنای فایل یا روز قبل)
    minRatio: number;             // آستانه ضریب حجم (پیش‌فرض: ۳.۰×)
    minTradeCount: number;        // حداقل تعداد معاملات
  };
  /** ۳. فیلتر جت FTS (Jet Breakout) */
  jet: {
    /** بلندترین نقطهٔ پلکانی که باید شکسته شود؛ همهٔ نقاطِ کوتاه‌تر هم لازم‌اند. */
    lookbackDays: LookbackDays;
    minBuyerPower: number;        // حداقل نسبت قدرت خریدار به فروشنده
    minVolRatio: number;          // حداقل ضریب حجم (مبنای فایل)
    requireLastAboveClose: boolean; // آخرین بالاتر از پایانی
    minChangePct: number;         // حداقل درصد تغییر قیمت
    // ``tno > 100`` عینِ فایل. رأیِ ۱۷ (۱۴۰۵-۰۷-۰۳) آن را از جتِ *استراتژیک*
    // بیرون گذاشت؛ رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴) همان را به **فیلترِ تابلو** برگرداند،
    // چون مالک می‌خواهد نشانِ «جت» همان چیزی باشد که فیلترنویسِ TSETMC می‌دهد.
    minTradeCount: number;
  };
  /** ۴. کف‌روبی و جمع‌آوری صف (Kef Roobi / Sweep) */
  roobi: {
    maxChangePct: number;         // سقف درصد افت قیمت (فایل: -۱٫۰٪)
    minVolRatio: number;          // ۰ = بدون شرط (فایل چنین گیتی ندارد)
    minBuyerPower: number;        // ۰ = بدون شرط
    minTradeCount: number;        // قیدِ چهارمِ فایل: ``qd1 > 100`` — حجمِ
                                  // سفارشِ **سطرِ اولِ صفِ خرید** (buy_q1_vol)
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
  /**
   * ۷. مبنایِ داوری (#226) — دو دستگیره، فقط درِ ارزیابِ فرانت؛ بک‌اند و
   * نشانه‌هایِ خامِ ستون‌ها دست‌نخورده‌اند.
   */
  basis: {
    /** (الف) «امروز داخلِ مبنایِ میانگین» — حجمِ همین نشست درِ Σ[ih][0..29]/۳۰
     *  یک واحدِ سی‌ام share می‌گیرد: مبناء ÷ ۳۱ با امروز. پیش‌فرض خاموش = عینِ فایل. */
    includeTodayInVolumeBase: boolean;
    /** (ب) «دروازۀ ۲۹-نشستِ تاریخچه» — روشن = کمینۀِ نقطه‌زنی فقط با آرایۀِ
     *  کاملِ فایل سنجیده می‌شود (رفتارِ فعلی/جزوه). خاموش = نمادهایِ کم‌سابقه
     *  با کمینۀِ موجود سنجیده می‌شوند (ستونِ نمایشِ min30_low، بدونِ روزهایِ صفر). */
    requireLowBaseHistory: boolean;
  };
};

/**
 * پیش‌فرض‌ها = خودِ پنج فایلِ مالک، نه سلیقۀِ برنامه‌نویس.
 * هر عددی که اینجا تغییر کند باید اول درِ فایلِ فیلترنویسی پیدا شود.
 * مبناءِ همهٔ گیت‌هایِ حجمی Σ[ih][0..29]/۳۰ است (ستونِ vol_ratio_file).
 */
export const DEFAULT_TAPE_FILTER_CONFIG: TapeFilterConfig = {
  clock: {
    minDeltaPct: 2.0,          // pl >= pc * 1.02
    requireGoldenHour: false,  // انتخابی، درِ فایل نیست
    minVolRatio: 1.0,          // tvol > 1 * Σ[ih][0..29]/30
    minTradeCount: 30,         // tno > 30
  },
  suspiciousVolume: {
    timeframe: 'monthly_30d',
    minRatio: 3.0,             // tvol > 3 * Σ[ih][0..29]/30
    minTradeCount: 50,         // tno > 50
  },
  jet: {
    lookbackDays: 59,          // پلکانِ کاملِ [ih][2..59].PriceMax
    minBuyerPower: 1.5,        // خریدِ حقیقی >= ۱٫۵ × فروشِ حقیقی
    minVolRatio: 3.0,
    requireLastAboveClose: true,
    minChangePct: 0.0,         // plp > 0
    minTradeCount: 100,        // tno > 100 — عینِ فایل (رأیِ ۱۸)
  },
  roobi: {
    maxChangePct: -1.0,        // plp < -1
    minVolRatio: 0,            // فایل گیتِ حجم ندارد
    minBuyerPower: 0,          // فایل گیتِ قدرت خریدار ندارد
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
  basis: {
    includeTodayInVolumeBase: false,  // عینِ فایل: Σ[ih][0..29] بی‌امروز
    requireLowBaseHistory: true,      // عینِ فایل: کمینۀ سی‌نشستِ کامل
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

/** گیتِ «اکیداً بیشتر» — فایل هر جا `>` نوشته، نه `>=`. */
function above(value: number | null | undefined, bound: number): boolean {
  const v = num(value);
  return v != null && v > bound;
}

/** گیتِ «اکیداً کمتر»: همان قاعده، در جهتِ مخالف. */
function below(value: number | null | undefined, bound: number): boolean {
  const v = num(value);
  return v != null && v < bound;
}

/** گیتِ حجمیِ پنج فیلتر — مبناءِ فایل، و نبودنش **رد** است نه بی‌صدا قبول.
 *  دستگیرۀ #226-الف (`basis.includeTodayInVolumeBase`) تنها وزنِ امروز را درِ
 *  همان مبناء عوض می‌کند؛ آستانه و قاعدۀ «نسنجیده = مردود» همان می‌ماند. */
function volumeGate(r: MarketRow, minRatio: number, basis?: TapeFilterConfig['basis']): boolean {
  if (!(minRatio > 0)) return true;              // آستانهٔ صفر = گیتِ خاموش
  const mult = basis?.includeTodayInVolumeBase ? filterVolumeRatioWithToday(r) : filterVolumeRatio(r);
  return mult != null && mult > minRatio;
}

/** پنجرۀِ فایل: سی **نشستِ** آخر (`[ih][0..29]`). امروز تا پیش از نهایه داخلِ
 *  این آرایه نیست — بک‌اند شمارۀِ نشست را در `hist_sessions` می‌شمارد، نه
 *  شمارۀِ ردیفِ ذخیره‌شده را (کوئری همین کار را می‌کند؛ `srn`). */
function knownSessions(r: MarketRow): number | null {
  return num(r.hist_sessions);
}

/** کمینۀ فایل: ``min([ih][0..28].PriceMin)`` — صفر **معتبر** است، چون فایل
 *  `MinPriceOfMonth() != 0` را صریحاً می‌خواهد؛ نشستِ بی‌معامله کفِ صفر
 *  می‌گیرد و کلِ ردیف را رد می‌کند. بک‌اند پنجرۀِ ناقص را خودش صفر می‌کند
 *  (`min_low_29`)، این‌جا فقط همان کفِ ۲۹ نشستیِ بک‌اند برگردانده می‌شود
 *  (`tape_flags.LOW_BASE_SESSIONS`).
 *
 *  دستگیرۀ #226-ب (`basis.requireLowBaseHistory=false`) همین دربِ «۲۹ نشستِ
 *  تاریخچه» را باز می‌کند: نمادهایِ کم‌سابقه با کمینۀِ **موجود** (ستونِ
 *  نمایشیِ `min30_low`، که مثلِ فایل روزهایِ صفر را بیرون می‌گذارد) سنجیده
 *  می‌شوند. با دربِ بسته (پیش‌فرض) رفتارِ جزوه مو به مو محفوظ است. */
function fileLow(r: MarketRow, basis?: TapeFilterConfig['basis']): number | null {
  const exact = num(r.min_low_29);
  const sessions = knownSessions(r);
  if (basis?.requireLowBaseHistory === false) {
    if (exact != null && exact > 0 && sessions != null && sessions >= LOW_BASE_SESSIONS) return exact;
    const avail = num(r.min30_low);
    return avail != null && avail > 0 ? avail : null;
  }
  if (sessions == null || sessions < LOW_BASE_SESSIONS) return null;
  return exact;
}

/** ۱. الگوی ساعت — فایل: ``pl >= pc*1.02 && tvol > Σ[ih][0..29]/30 && tno > 30`` */
export function matchClockPattern(r: MarketRow, cfg: TapeFilterConfig['clock'], basis?: TapeFilterConfig['basis']): boolean {
  const last = num(r.p_last);
  const close = num(r.p_closing);
  if (last == null || close == null || close <= 0) return false;

  const deltaPct = ((last - close) / close) * 100;
  if (deltaPct < cfg.minDeltaPct) return false;

  if (cfg.requireGoldenHour) {
    const yest = num(r.price_yesterday);
    if (yest == null || !(close < yest && last > yest)) return false;
  }

  if (!volumeGate(r, cfg.minVolRatio, basis)) return false;
  return above(r.z_tot_tran, cfg.minTradeCount);
}

/** ۲. حجم مشکوک — فایل: ``tvol > 3*Σ[ih][0..29]/30 && tno > 50`` */
export function matchSuspiciousVolume(r: MarketRow, cfg: TapeFilterConfig['suspiciousVolume'], basis?: TapeFilterConfig['basis']): boolean {
  if (!above(r.z_tot_tran, cfg.minTradeCount)) return false;
  if (cfg.timeframe === 'prev_day_dod') return above(r.vol_dod, cfg.minRatio);
  return volumeGate(r, cfg.minRatio, basis);
}

/**
 * ۳. فیلتر جت FTS — فایل:
 * ``tvol > 3*Σ[ih][0..29]/30 && خریدحقیقی/معامله >= 1.5 × فروشحقیقی/معامله
 *   && pl >= pc && plp > 0 && [ih][2..59].PriceMax < pl && tno > 1 && tno > 100``
 * مقایسه با «آخرین» است، نه «پایانی»؛ و با همهٔ نقاطِ پلکان، نه یک نقطه.
 */
export function matchJetFilter(r: MarketRow, cfg: TapeFilterConfig['jet']): boolean {
  return detectJetBreakout(r, cfg).hit;
}

/** ۴. کف‌روبی و جمع‌آوری صف — فایل: ``pl == tmin && zd1 > 1 && plp < -1 && qd1 > 100``
 *
 * هر چهار واژه از `ExecFilter` خودِ tsetmc.com گرفته شده‌اند:
 *   tmin = آستانۀ مجاز پایین (نه کفِ همین نشست)، plp = درصدِ **آخرین** نسبت به
 *   دیروز (نه پایانی)، zd1/qd1 = تعداد و حجمِ سفارشِ **سطرِ اولِ صفِ خرید**.
 * یعنی: رویِ کفِ مجاز چسبیده، بیش از یک درصد پایین، و خریدار در صفِ اول نشسته.
 * نبودنِ هر قید = رد (درِ خودِ سایت هم ExecFilter را با try/catch رد می‌کند).
 */
export function matchRoobiFilter(r: MarketRow, cfg: TapeFilterConfig['roobi'], basis?: TapeFilterConfig['basis']): boolean {
  const last = num(r.p_last);
  const floor = num(r.tmin);
  if (last == null || floor == null || floor <= 0 || last !== floor) return false;
  const zd1 = num(r.buy_q1_cnt);
  if (zd1 == null || zd1 <= ROOBI_ZD1_MIN) return false;                 // zd1 > 1
  if (!below(r.percent_last, cfg.maxChangePct)) return false;            // plp < -1
  const qd1 = num(r.buy_q1_vol);
  if (qd1 == null || qd1 <= cfg.minTradeCount) return false;              // qd1 > 100

  if (!volumeGate(r, cfg.minVolRatio, basis)) return false;
  if (cfg.minBuyerPower > 0 && !atLeast(r.buyer_power, cfg.minBuyerPower)) return false;
  return true;
}

/** ۵. نقطه‌زنی و کف‌یابی — فایل: ``round((pc-min)/pc*100*100)/100 < 3 && tvol > Σ[ih][0..29]/30 && tno > 5``
 *  ``min`` کفِ [ih][0..28] است، نه ستونِ نمایشیِ min30_low (که دیروزها را می‌شمرد).
 */
export function matchNoqtehFilter(r: MarketRow, cfg: TapeFilterConfig['noqteh'], basis?: TapeFilterConfig['basis']): boolean {
  const close = num(r.p_closing);
  const minLow = fileLow(r, basis);
  if (close == null || close <= 0 || minLow == null || minLow <= 0) return false;

  const distPct = Math.round(((close - minLow) / close) * 100 * 100) / 100;
  if (distPct < 0 || distPct >= cfg.maxDistPct) return false;

  if (!volumeGate(r, cfg.minVolRatio, basis)) return false;
  return above(r.z_tot_tran, cfg.minTradeCount);
}

/** ۶. جریان پول هوشمند نخبگان — پنلِ خودی، خارج از فایل */
export function matchSmartFlowFilter(r: MarketRow, cfg: TapeFilterConfig['smartFlow']): boolean {
  if (!atLeast(r.buyer_power, cfg.minBuyerPower)) return false;
  const mult = filterVolumeRatio(r);
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
  // ردیفِ بیرونِ تابلویِ امروز هیچ‌کدام از پنج فیلترِ فایل را رد/قبول نمی‌کند
  // (عددش مربوط به نشستِ خودش است)؛ جریانِ پولِ نخبگان پنلِ خودی است و آزاد.
  if (filterKey !== 'f_smart_flow' && !isLiveBoardRow(r)) return false;
  switch (filterKey) {
    case 'f_clock':
      return matchClockPattern(r, cfg.clock, cfg.basis);
    case 'f_susp':
      return matchSuspiciousVolume(r, cfg.suspiciousVolume, cfg.basis);
    case 'f_jet':
      return matchJetFilter(r, cfg.jet);
    case 'f_roobi':
      return matchRoobiFilter(r, cfg.roobi, cfg.basis);
    case 'f_noqteh':
      return matchNoqtehFilter(r, cfg.noqteh, cfg.basis);
    case 'f_smart_flow':
      return matchSmartFlowFilter(r, cfg.smartFlow);
    default:
      return Boolean((r as unknown as Record<string, unknown>)[filterKey]);
  }
}
