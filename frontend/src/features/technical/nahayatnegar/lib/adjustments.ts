import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

/**
 * رویداد تعدیل. سرور (api/chart.py) برای هر رویداد فقط یک عدد می‌دهد:
 * نسبتِ گسستِ «قیمت پایه» در روزِ بازگشایی = اثرِ **ترکیبیِ** افزایش سرمایه و سود نقدی.
 * تفکیکِ سهمِ هر کدام از این یک عدد ممکن نیست (یک معادله، دو مجهول)، پس حالت‌های
 * جداگانهٔ «سود نقدی» و «افزایش سرمایه» دادهٔ پشتیبان ندارند.
 */
export interface CorporateAction {
  timestamp: number;
  dateStr: string;
  ratio: number;
}

/**
 * سه مفهومِ جدا — یکی نکن، جای یکی را به دیگری ندِه:
 *   none        — قیمتِ خامِ تابلو (محور ریال)
 *   combined    — ضریبِ تجمعیِ گسستِ «قیمت پایه» روی کندل‌هایِ ماقبلِ رویداد (محور ریال)
 *   performance — **نمایِ بازدهی (شاخصِ ۱۰۰)**: همان سریِ combined تقسیم بر نخستین
 *                 پایانی × ۱۰۰. مقدارِ `performance` درِ این فایل و درِ stateِ ذخیره‌شده
 *                 فقط نامِ سیمِ رابط است (نمایه‌هایِ چارت با همین رشته ذخیره شده‌اند)؛
 *                 معنایش شاخصِ بازدهی است، **نه** Functional Adjustment.
 *
 * «تعدیل عملکردیِ واقعی» (ره‌آورد/نهایات‌نگر) سودِ نقدی را **سرمایه‌گذاریِ دوباره**
 * می‌کند (history را تا ده برابر پایین‌تر می‌کشند — docs/CHART-PARITY-REFERENCE.md §۸)
 * و به DPSِ تفکیکیِ هر رویداد، آورده/حق‌تقدم، افزایشِ سرمایه و تاریخِ معافیت نیاز دارد.
 * سرور از این دور همان الزامات را از داده می‌خواند (`_functional_state` درِ
 * api/chart.py) و `functionalAvailable` را **محاسبه** می‌کند؛ هر مانع هم با عددِ
 * همان نماد درِ `functionalBlockers` می‌آید. مرورگر دیگر خودش تصمیم نمی‌گیرد که
 * تعدیلِ عملکردی هست یا نه، و هیچ عددِ حدسی جای ضریبِ سرور نمی‌نشیند.
 */
export type AdjustmentMode = 'none' | 'combined' | 'performance';

/** پایهٔ نمایِ بازدهی — همان چیزی که رویِ محورِ عمودی خوانده می‌شود */
export const PERFORMANCE_BASE = 100;

/**
 * موتورِ دوم (FFC) کرکرۀ «نوع تعدیل قیمت» را ندارد — آن کرکره درِ نوارِ ابزارِ
 * KLineCharts است. سریِ این موتور همیشه همین مبنای واحد است، و برچسبِ رویِ صحنه
 * از همین دو ثابت ساخته می‌شود: اعلامِ UI و داده‌ای که رسم می‌شود یک منبع دارند،
 * پس «موتورِ دوم خام نشان می‌دهد در حالی که عملکردی می‌گوید» ممکن نیست.
 */
export const FFC_ADJUSTMENT_MODE: AdjustmentMode = 'combined';
export const FFC_ADJUSTMENT_BASIS_LABEL = 'عملکردی (خام × ضریبِ سرور) — این موتور کرکرۀ تعدیل ندارد';

/**
 * ضریبِ هر کندل آن‌طور که سرور محاسبه کرده است (`factors=[{time,factor}]`).
 * از این دور این آرایه **تنها** ورودیِ مقیاسِ قیمت درِ مرورگر است: حلقۀِ محلیِ
 * «دوباره ضرب‌کردنِ رویدادها» حذف شد، چون سنجشِ قدمِ ۵ نشان داد دو مسیر یکی نیستند —
 * مرورگر نسبتِ بیرونِ بازۀِ باورپذیر را دور می‌انداخت (فیلترِ ۰٫۰۲ تا ۵۰ درِ
 * `mapBackendAdjustEvents`) در حالی که حلقۀِ CDN همان را می‌ضرب کرد.
 */
export interface AdjustFactor {
  time: string;
  factor: number;
}

/** آنچه سرور دربارهٔ تواناییِ تعدیل اعلام می‌کند (api/chart.py::_adjust_capability) */
export interface AdjustmentCapability {
  /** منبعِ داوری: base-price-discontinuity · no-adjustment-event · local-cache ·
   *  base-not-anchored · local-db-unseen · … */
  source: string;
  /** مجموعهٔ رویدادِ کاننیکال در دسترس است ⇒ `combined` معنایِ واقعی دارد */
  combinedAvailable: boolean;
  /** تعدیلِ عملکردیِ واقعی (DPSِ سرمایه‌گذاری‌شده) — محاسبه‌شده از الزاماتِ همین نماد */
  functionalAvailable: boolean;
  /** دلیلِ human-readableِ نبودِ تعدیلِ عملکردی (متنِ سرور، بی‌بازنویسی) */
  functionalReason: string;
  /** موانعِ شمارشیِ همین نماد، هر کدام با عددِ خودش (بی‌سکوت درِ پاسخ) */
  functionalBlockers: string[];
  /** `false` = رویدادِ ناقص درِ زنجیره، `null` = سرور اعلام نکرده است */
  chainComplete: boolean | null;
  /** پوششِ دفترِ رسمیِ همین ابزار (ردیف‌ها، بی‌همتاها، کندل‌هایِ پیشِ پوشش) */
  coverage: Record<string, unknown> | null;
}

const UNKNOWN_CAPABILITY: AdjustmentCapability = {
  source: 'unreported',
  combinedAvailable: false,
  functionalAvailable: false,
  functionalReason: 'پاسخِ سرور بلوکِ تواناییِ تعدیل ندارد؛ تعدیلِ رویداد تأیید نشده است.',
  functionalBlockers: ['unreported:سرور بلوکِ توانایی را نفرستاد'],
  chainComplete: null,
  coverage: null,
};

/**
 * خواندنِ `adjustCapability` از پاسخِ سرور. نبودِ بلوک = «تأیید نشده»، نه «هست».
 * بی‌این، پاسخِ قدیمی/جایگزین با `adjustEvents: []` خودش را «رویدادی نیست» جا می‌زد.
 */
export function readAdjustmentCapability(raw: unknown): AdjustmentCapability {
  const c = (raw as { adjustCapability?: Record<string, unknown> } | null | undefined)?.adjustCapability;
  if (!c || typeof c !== 'object') {
    return { ...UNKNOWN_CAPABILITY, source: String((raw as { adjustSource?: unknown } | null)?.adjustSource ?? 'unreported') };
  }
  return {
    source: String(c.source ?? 'unreported'),
    combinedAvailable: c.combined_available === true,
    functionalAvailable: c.functional_available === true,
    functionalReason: String(c.functional_reason ?? UNKNOWN_CAPABILITY.functionalReason),
    functionalBlockers: Array.isArray(c.functional_blockers)
      ? (c.functional_blockers as unknown[]).map(String) : [],
    chainComplete: typeof c.chain_complete === 'boolean' ? c.chain_complete : null,
    coverage: (c.coverage && typeof c.coverage === 'object')
      ? (c.coverage as Record<string, unknown>) : null,
  };
}

/**
 * هشدارِ صادقِ همان حالت — نه «داده نیست» کلی، بلکه علتِ همان محور.
 * فقط وقتی آتش می‌زند که مجموعهٔ رویداد در دسترس نباشد؛ آن‌وقت هر عددی که
 * `combined` یا «نمایِ بازدهی» خوانده می‌شود در واقع ریالِ خام است.
 */
export function adjustmentGapNote(mode: AdjustmentMode, cap: AdjustmentCapability): string | null {
  if (mode === 'none') return null;
  if (cap.combinedAvailable) return null;
  return mode === 'performance'
    ? `نمایِ بازدهی رویِ قیمتِ خام (تعدیلِ رویداد در دسترس نیست — منبع: ${cap.source}).`
    : `تعدیلِ ترکیبی در دسترس نیست (منبع: ${cap.source})؛ اعدادِ محور خام‌اند.`;
}

/**
 * آنچه سرور دربارهٔ تعدیلِ عملکردیِ واقعی می‌گوید، به زبانِ همان نماد.
 * «عملکردی» درِ رهاورد یعنی سرمایه‌گذاریِ دوبلۀِ سود و با «تعدیلِ ترکیبی» یکی
 * نیست؛ تا پیش از این، رابط هیچ‌جا این تفاوت را به کاربر نمی‌گفت (متنِ سرور
 * خوانده می‌شد ولی هیچ‌جا نمایش داده نمی‌شد). نبودِ ادعایِ فعال = نمایشِ مانع،
 * با همان شمارۀِ اعلام‌شدۀِ سرور — نه یک «داده نیست» کلی.
 */
export function functionalGapNote(cap: AdjustmentCapability): string | null {
  if (cap.functionalAvailable) return null;
  const first = (cap.functionalBlockers ?? []).slice(0, 2).join('، ');
  return `تعدیلِ عملکردیِ واقعی با دادهٔ همین نماد اثبات نشده‌است${first ? ` (${first})` : ''} — `
    + 'محور، سریِ تعدیلِ ترکیبی است.';
}

/** ده‌دقیقه‌ایِ ممیز برای عددِ بازدهی؛ قیمتِ ریالی گردِ صحیح می‌ماند */
function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

export function getAdjustmentFactor(action: CorporateAction): number {
  return action.ratio > 0 ? Math.min(Math.max(action.ratio, 0.0001), 50) : 1.0;
}

/**
 * تبدیلِ سریِ قیمت به شاخصِ بازدهی: هر کندل ÷ پایانیِ نخستین کندل × ۱۰۰.
 * این **فقط یک مقیاس‌کردن است** — هیچ رویدادِ شرکتی در آن لحاظ نمی‌شود، پس
 * «تعدیل» نامیده نمی‌شود مگر رویِ سریِ از پیش `combined`.
 *
 * حجم و گردشِ ارزش **دست‌نخورده** می‌مانند — آن‌ها قیمت نیستند که مقیاس شوند.
 * سریِ بی‌پایه (نخستین close صفر یا تهی) بدونِ تغییر برمی‌گردد: تقسیمِ بر صفر
 * یعنی بی‌نهایتِ سبزِ جعلی رویِ محور، نه «۰٪».
 */
export function toIndexedSeries(candles: KLineData[]): KLineData[] {
  const base = candles.length ? Number(candles[0].close) : 0;
  if (!(base > 0)) return candles.map(c => ({ ...c }));
  return candles.map(c => ({
    ...c,
    open: round2(Number(c.open) / base * PERFORMANCE_BASE),
    high: round2(Number(c.high) / base * PERFORMANCE_BASE),
    low: round2(Number(c.low) / base * PERFORMANCE_BASE),
    close: round2(Number(c.close) / base * PERFORMANCE_BASE),
  }));
}

/** دقتِ محورِ قیمت برای هر حالت — نمایِ بازدهی بدونِ دو رقمِ ممیز خوانده نمی‌شود */
export function pricePrecisionFor(mode: AdjustmentMode): number {
  return mode === 'performance' ? 2 : 0;
}

/**
 * تنها نقطۀ ضربِ ضریبِ تعدیل درِ کلِ مرورگر. هیچ مصرف‌کننده‌ای (چارت، تجمیعِ
 * هفتگی/ماهانه، FFC، موتورِ دوم، سریِ مقایسه) نباید دوباره این را بنویسد یا
 * خروجیِ این را یک‌بارِ دیگر ضرب کند — «تعدیلِ دوباره» تاریخِ گذشته را دو‌بار
 * مقیاس می‌کند.
 *
 * ضریب‌ها از سرور می‌آیند (`api/chart.py::_canonical_adjustment` ⇒ `AE.chain_factors`).
 * پیش از این دور همین فایل از `adjustEvents` یک زنجیرۀِ *دوم* می‌ساخت و با سریِ سرور
 * واگرا می‌شد: فیلترِ نسبتِ بیرونِ (۰٫۰۲،۵۰) درِ `mapBackendAdjustEvents` رویدادها را کم
 * می‌کرد، در حالی که حلقۀِ سرور همان‌ها را نگه می‌داشت — دو مقیاسِ متفاوت برایِ یک
 * نماد درِ یک صفحه. حالا یک محاسبه هست و مرورگر فقط همان را اعمال می‌کند.
 *
 * اعمالِ ضریب: قیمت‌ها ×k و حجم ÷k تا ارزشِ معامله ثابت بماند. کندلی که سرور برایش
 * ضریبی نفرستاده (سریِ محلیِ بی‌factors، کندلِ تزریق‌شدۀِ محلی) ضریبِ ۱ می‌گیرد —
 * «بی‌اثر»، نه حذفِ کندل و نه عددِ ساخته‌شده.
 */
export function applyAdjustmentToCandles(
  rawCandles: KLineData[],
  factors: AdjustFactor[],
  mode: AdjustmentMode
): KLineData[] {
  if (mode === 'none' || !rawCandles || rawCandles.length === 0) {
    return mode === 'performance' ? toIndexedSeries(rawCandles.map(c => ({ ...c })))
                                  : rawCandles.map(c => ({ ...c }));
  }

  const byDate = new Map<string, number>();
  for (const f of factors ?? []) {
    const d = String(f?.time ?? '').slice(0, 10);
    const v = Number(f?.factor ?? NaN);
    if (d && Number.isFinite(v) && v > 0) byDate.set(d, v);
  }

  const scaled = rawCandles.map(candle => {
    // سرور ضریب را با کلیدِ تاریخِ ISO می‌فرستد و کندل‌ها از همان تاریخِ UTC-نیمه‌شب
    // ساخته شده‌اند (`Date.parse(time + 'T00:00:00Z')` / `Date.UTC(...)` درِ
    // `parseCandleTimestamp`)، پس این بازگشتِ روز بی‌جابه‌جایی است.
    const key = new Date(candle.timestamp).toISOString().slice(0, 10);
    const factor = byDate.get(key) ?? 1.0;
    return {
      timestamp: candle.timestamp,
      open: Math.round(candle.open * factor),
      high: Math.round(candle.high * factor),
      low: Math.round(candle.low * factor),
      close: Math.round(candle.close * factor),
      volume: candle.volume !== undefined ? Math.round(candle.volume / factor) : undefined,
      turnover: candle.turnover
    };
  });

  // نمایِ بازدهی رویِ همان سریِ تعدیل‌شده می‌نشیند؛ بی‌ضریبِ قیمتی، درصدِ بازدهی
  return mode === 'performance' ? toIndexedSeries(scaled) : scaled;
}

/**
 * نگاشت رویدادهای خام بک‌اند adjustEvents ([{date,ratio}]) به CorporateAction
 *
 * رویدادِ بی‌تاریخ حذف می‌شود، نه «الان»: اگر timestamp به امروز بیفتد، حلقهٔ
 * applyAdjustmentToCandles هر کندلِ موجود را زیرِ آن تاریخ می‌بیند و کلِ سری را
 * یک‌جا مقیاس می‌کند. نسبتِ بیرونِ بازهٔ باورپذیر هم حذف می‌شود.
 */
export function mapBackendAdjustEvents(
  rawEvents: Array<{ timestamp?: number | null; time?: number | null; date?: string | null;
                    dateStr?: string | null; ratio?: number | null }>
): CorporateAction[] {
  if (!Array.isArray(rawEvents)) return [];

  return rawEvents
    .map(e => ({
      timestamp: parseCandleTimestamp(e.timestamp ?? e.time ?? e.dateStr ?? e.date),
      dateStr: e.dateStr || e.date || '',
      ratio: Number(e.ratio ?? 0)
    }))
    .filter(a => Number.isFinite(a.timestamp) && a.timestamp > 0 &&
                 a.ratio > 0.02 && a.ratio < 50);
}
