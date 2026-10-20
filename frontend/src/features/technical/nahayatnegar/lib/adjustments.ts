import type { KLineData } from 'klinecharts';
import { parseCandleTimestamp } from '../../lib/jalaliDate';
import { toFaDigits } from '@shared/lib/fmt';

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
 * دو حالتِ سریِ قیمت — و فقط همین دو (رأیِ مالک، دورِ ممیزیِ کلِ نمادها):
 *   none      — قیمتِ خامِ تابلو (محور ریال)
 *   combined  — عملکردی: ضریبِ تجمعیِ گسستِ «قیمت پایه» روی کندل‌هایِ ماقبلِ رویداد (ریال)
 *
 * «نمایِ بازدهی (شاخصِ ۱۰۰)» که با نامِ `performance` درِ این فایل و درِ stateِ
 * ذخیره‌شده بود حذف شد. آن حالت *نوعِ سریِ قیمت نبود*: یک مقیاس‌کردنِ نمایشی رویِ
 * همان سریِ combined (÷ نخستینِ پایانی × ۱۰۰) بود، و نامش دقیقاً همان چیزی است که
 * درِ رأیِ ۲۰۲۶-۰۹-۲۴ از UI و کد بیرون رفت — چون کاربر آن را «تعدیلِ عملکردی» می‌خواند
 * و چارت را با محورِ ۶۵٬۰۰۰ تا ۱۶۶٬۰۰۰ برای فولادی باز می‌کرد که آخرین کندلش ۴٬۴۱۰ است.
 * امروز آن مقیاسِ نمایشی همان «محور درصدی» درِ تنظیماتِ مقیاس‌ها است (نوعِ نمایش، نه
 * نوعِ سری) و همان‌جا می‌ماند.
 *
 * «تعدیل عملکردیِ واقعی» (ره‌آورد/نهایات‌نگر) سودِ نقدی را **سرمایه‌گذاریِ دوباره**
 * می‌کند (history را تا ده برابر پایین‌تر می‌کشند — docs/CHART-PARITY-REFERENCE.md §۸)
 * و به DPSِ تفکیکیِ هر رویداد، آورده/حق‌تقدم، افزایشِ سرمایه و تاریخِ معافیت نیاز دارد.
 * سرور از این دور همان الزامات را از داده می‌خواند (`_functional_state` درِ
 * api/chart.py) و `functionalAvailable` را **محاسبه** می‌کند؛ هر مانع هم با عددِ
 * همان نماد درِ `functionalBlockers` می‌آید. مرورگر دیگر خودش تصمیم نمی‌گیرد که
 * تعدیلِ عملکردی هست یا نه، و هیچ عددِ حدسی جای ضریبِ سرور نمی‌نشیند.
 */
export type AdjustmentMode = 'none' | 'combined';

/** هر حالتِ دیگری که درِ تنظیمِ قدیمی پیدا شود، به این دو کوچکت می‌شود */
const LEGACY_MODE_TARGETS: Record<string, AdjustmentMode> = {
  none: 'none',
  combined: 'combined',
  // نمایِ بازدهی رویِ سریِ تعدیل‌شده می‌نشست، پس نزدیک‌ترین معنایِ ریالیِ همان عدد
  performance: 'combined',
  // دو حالتی که هرگز دادهٔ پشتیبان نداشتند و درِ UI غیرفعال بودند
  capital: 'combined',
  cash: 'combined',
};

/**
 * خواندنِ یکِ مبنایِ ذخیره‌شده — از قالبِ چارت یا stateِ کهنه.
 * سازگاریِ داخلی، نه یکِ حالتِ سومِ رابط: رشته‌ای که نمی‌شناسیم `null` می‌ماند تا
 * فراخوانِ خودش پیش‌فرضِ جاری را نگه دارد (بی‌ساختنِ حالت از رویِ حدس).
 */
export function migrateAdjustmentMode(stored: unknown): AdjustmentMode | null {
  if (typeof stored !== 'string') return null;
  return LEGACY_MODE_TARGETS[stored] ?? null;
}

/**
 * مبنایِ پیش‌فرضِ چارت. «عملکردی» درِ رهاورد محورِ **ریالی** را نگه می‌دارد
 * (برچسبِ همان صفحه: O 4,410 H 4,410 …)، پس پیش‌فرضِ چارتِ خودی هم باید سریِ
 * ریالیِ تعدیل‌شده باشد، نه شاخصِ ۱۰۰.
 *
 * پیش از این، `KLineChartWrapper` با همان نیتِ مالک («تعدیل عملکردی») رویِ
 * `performance` باز می‌شد و محورِ فولاد ۶۵٬۰۰۰ تا ۱۶۶٬۰۰۰ نشان می‌داد در حالی که
 * آخرین کندلِ همان پاسخِ API ۴٬۴۱۰ بود (سنجشِ ۱۴۰۵-۰۷-۲۷، `_audit/chart_axis_stages.json`:
 * `axisValues.candle = {topValue: 166820.57, bottomValue: 65106.08}` در برابرِ
 * `api.lastClose = 4410`). سرجایش همین‌جا بسته می‌شود تا دو حالتِ واگرا نسازد.
 */
export const DEFAULT_ADJUSTMENT_MODE: AdjustmentMode = 'combined';

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
 * درِ حالتِ «عملکردی» خوانده می‌شود در واقع ریالِ خام است.
 */
export function adjustmentGapNote(mode: AdjustmentMode, cap: AdjustmentCapability): string | null {
  if (mode === 'none') return null;
  if (cap.combinedAvailable) return null;
  return `تعدیلِ رویداد در دسترس نیست (منبع: ${cap.source})؛ اعدادِ محور خام‌اند.`;
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

export interface FunctionalStatusNote {
  summary: string;
  details: string[];
}

/** متنِ کوتاهِ فارسی برای هشدارِ عملکردی + جزئیاتِ بازشونده.
 *
 * همهٔ عددها از `functionalBlockers` همان پاسخ می‌آیند؛ هیچ عددی در این فایل
 * hard-code نیست. اگر وضعیت کامل باشد (functionalAvailable) هشدار برمی‌گردد null.
 * کدهایِ خامِ انگلیسی فقط در جزئیات می‌مانند تا کاربر متنِ فارسی کوتاه ببیند.
 */
export function functionalStatusNote(cap: AdjustmentCapability): FunctionalStatusNote | null {
  if (cap.functionalAvailable) return null;
  const parse = (raw: string): { key: string; n: number | null } => {
    const i = raw.indexOf(':');
    if (i <= 0) return { key: raw, n: null };
    const tail = raw.slice(i + 1);
    return /^\d+$/.test(tail)
      ? { key: raw.slice(0, i), n: Number(tail) }
      : { key: raw.slice(0, i), n: null };
  };
  const blockers = (cap.functionalBlockers ?? []).map(parse);
  const count = (key: string): number | null => {
    const hit = blockers.find(b => b.key === key);
    return hit ? hit.n : null;
  };
  const nEvent = count('event-type-unresolved');
  const nPre = count('candles-before-ledger-coverage');
  const nUnmatched = count('ledger-rows-unmatched-by-price-series');
  const short: string[] = [];
  if (nEvent) short.push(`${toFaDigits(nEvent)} رویداد حل‌نشده`);
  if (nPre) short.push(`${toFaDigits(nPre)} کندل پیش از پوشش مرجع`);
  if (!short.length && nUnmatched) short.push(`${toFaDigits(nUnmatched)} ردیف دفتر بی‌تطبیق`);
  if (!short.length) {
    const has = (key: string) => blockers.some(b => b.key === key);
    if (has('no-official-rows-for-instrument')) short.push('هیچ ردیف رسمیِ تعدیل در بانک نیست');
    else if (has('ledger-unavailable')) short.push('دفتر تعدیل در دسترس نیست');
    else if (has('unmeasured')) short.push('وضعیت تعدیل سنجیده نشده است');
    else if (has('unreported')) short.push('سرور وضعیت تعدیل را نفرستاد');
    else short.push('دلیلِ دقیق در جزئیات آمده است');
  }
  const summary = `تعدیل عملکردی این نماد کامل تأیید نشده است؛ ${short.join(' و ')}.`;

  const label = (b: { key: string; n: number | null }): string => {
    const n = b.n;
    switch (b.key) {
      case 'event-type-unresolved': return `${toFaDigits(n ?? 0)} رویداد با نوعِ حل‌نشده`;
      case 'candles-before-ledger-coverage': return `${toFaDigits(n ?? 0)} کندل پیش از پوشش دفتر رسمی`;
      case 'ledger-rows-unmatched-by-price-series': return `${toFaDigits(n ?? 0)} ردیف دفتر بی‌تطبیق با سری قیمت`;
      case 'offer-price-missing': return `${toFaDigits(n ?? 0)} رویداد بدون قیمت پذیره`;
      case 'ledger-rows-rejected': return `${toFaDigits(n ?? 0)} ردیف دفتر ردشده`;
      case 'chain-incomplete': return `${toFaDigits(n ?? 0)} رویداد با زنجیرهٔ ناقص`;
      case 'ledger-flow-truncated-at-cap': return `دفتر تعدیل در سقف ${toFaDigits(n ?? 0)} ردیف بریده شده است`;
      case 'no-official-rows-for-instrument': return 'هیچ ردیف رسمیِ تعدیل در بانک نیست';
      case 'ledger-unavailable': return 'دفتر تعدیل در دسترس نیست';
      case 'unmeasured': return 'وضعیت تعدیل سنجیده نشده است';
      case 'unreported': return 'سرور وضعیت تعدیل را نفرستاد';
      default: return b.key;
    }
  };
  const details = blockers.map(label);
  if (!details.length) details.push('سرور دلیلی برای تأییدنشدن اعلام نکرده است.');
  return { summary, details };
}

/**
 * گردکردنِ قیمتِ تعدیل‌شده. صحیح‌گردانیِ بی‌قید اینجا خطایِ بزرگی می‌سازد: ضریبِ تجمعیِ فولاد در
 * ۲۰۰۷-۰۳-۱۱ برابر ۰٫۰۰۱۶۷۴۸۹۷۸ است و پایانیِ خام ۱٬۹۰۰ ⇒ ۳٫۱۸۲۳. صحیح‌گردانی آن را
 * به ۳ می‌اندازد (۵٫۷٪ خطا) و آن خطا به ارتفاعِ همهٔ کندل‌هایِ کهنه و به هر عددی که
 * از همان سری حساب می‌شود سرایت می‌کند. پس چهار رقمِ ممیز می‌ماند؛ خوانا‌بودنِ محور
 * تنظیمِ جدا است (`pricePrecision` درِ ftsConfigStore) — نه تحریفِ داده.
 */
function roundAdjustedPrice(v: number): number {
  return Math.round(v * 1e4) / 1e4;
}

export function getAdjustmentFactor(action: CorporateAction): number {
  return action.ratio > 0 ? Math.min(Math.max(action.ratio, 0.0001), 50) : 1.0;
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
 * اعمالِ ضریب: فقط قیمت‌ها ×k. حجم و گردشِ ارزش دست‌نخورده می‌مانند — مرجعِ ره‌آورد
 * هم درِ هر دو_seriesِ خام و تعدیل‌شده همان حجم را می‌رسمد (سنجشِ بالا)، و تقسیمِ حجم
 * بر ضریبِ کهنه (۰٫۰۰۱۶) محورِ حجم را تا صدبرابرِ منبع بالا می‌برد.
 * کندلی که سرور برایش ضریبی نفرستاده (سریِ محلیِ بی‌factors، کندلِ تزریق‌شدۀِ محلی)
 * ضریبِ ۱ می‌گیرد — «بی‌اثر»، نه حذفِ کندل و نه عددِ ساخته‌شده.
 */
export function applyAdjustmentToCandles(
  rawCandles: KLineData[],
  factors: AdjustFactor[],
  mode: AdjustmentMode
): KLineData[] {
  if (mode === 'none' || !rawCandles || rawCandles.length === 0) {
    return rawCandles ? rawCandles.map(c => ({ ...c })) : [];
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
      open: roundAdjustedPrice(candle.open * factor),
      high: roundAdjustedPrice(candle.high * factor),
      low: roundAdjustedPrice(candle.low * factor),
      close: roundAdjustedPrice(candle.close * factor),
      // حجم دست‌نخورده می‌ماند. تقسیمِ حجم بر ضریب («تا ارزشِ ثابت بماند») با
      // مرجعِ measured نمی‌خواند: درِ سنجشِ ۱۴۰۵-۰۷-۲۷ از ۶۰۱ تاریخِ مشترکِ فولاد،
      // سریِ حجمِ خام (type0) و سریِ حجمِ تعدیل‌شدهٔ رهاورد (type7) در ۶۰۱ از ۶۰۱
      // تاریخ *یکسان* بودند (`_audit/ra365_ref_bars.json`). تقسیم، محورِ حجم را در
      // نمایِ کاملِ تاریخچه ۱۷۶ برابرِ منبع می‌کرد (۲٫۲۹e۱۲ به‌جای ۱٫۳e۱۰،
      // `_audit/chart_axis_stages.json`).
      volume: candle.volume,
      turnover: candle.turnover
    };
  });

  return scaled;
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
