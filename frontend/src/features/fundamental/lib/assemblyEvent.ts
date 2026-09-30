// features/fundamental/lib/assemblyEvent.ts -- برچسب «مجمع نزدیک» از رویدادهای تقویم
// منبع داده: `events` در /api/ma/{symbol} — خروجی `_cal_events_for` بک‌اند با
// ساختار {date:'YYYY-MM-DD', ts, title, cat} و cat طبق `_cal_classify`
// (assembly | assemblyChange | assemblyExtra | dividend | …).
// قاعده‌ها:
//   • نزدیک‌ترین رویداد مجمع پیش‌رو (date ≥ امروز) با فاصلهٔ ≤۱۴ روز ⇒
//     «مجمع نزدیک — X روز دیگر (تاریخ جلالی)».
//   • اگر نزدیک‌ترین رویداد پیش‌رو از نوع assemblyChange بود (لغو/تعویق/انتقال)
//     برچسبِ صادقانهٔ تغییر می‌آید — نه تاریخ قدیمیِ مجمع.
//   • اگر رویداد پیش‌رو نیست ولی آخرین رویدادِ گذشته تغییر مجمع بود ⇒ همان
//     برچسب تغییر (مجمعِ برنامه‌ریزی‌شده عقب افتاده).
//   • بدون رویداد مجمع ⇒ هیچ badge (بدون دادهٔ ساختگی).
import { toFaDigits } from '@shared/lib/fmt';

/** آستانهٔ «نزدیک» (روز) — ثابت کافی است؛ تابع پارامتر هم می‌پذیرد */
export const ASSEMBLY_NEAR_DAYS = 14;

const ASSEMBLY_FAMILY = new Set(['assembly', 'assemblyChange', 'assemblyExtra']);

export interface CalEvent {
  /** ISO میلادی YYYY-MM-DD — روز رویداد در تقویم کدال */
  date: string;
  title?: string | null;
  cat?: string | null;
}

export interface AssemblyBadgeInfo {
  kind: 'near' | 'change';
  /** فاصله تا مجمع به روز — فقط برای near (۰ = امروز) */
  days: number;
  /** تاریخ ISO رویداد */
  date: string;
  /** تاریخ جلالی رویداد */
  jalali: string;
  /** متن برچسب */
  label: string;
  /** عنوان کامل رویداد کدال برای tooltip */
  detail: string;
  testId: 'assembly-near-badge' | 'assembly-change-badge';
}

const FA_TZ = 'Asia/Tehran';
const gregFmt = new Intl.DateTimeFormat('en-CA', { timeZone: FA_TZ, year: 'numeric', month: '2-digit', day: '2-digit' });
const jalaliFmt = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { timeZone: FA_TZ, year: 'numeric', month: '2-digit', day: '2-digit' });

/** امروز به وقت تهران به شکل YYYY-MM-DD */
export function todayIsoInTehran(now: Date = new Date()): string {
  try {
    return gregFmt.format(now);
  } catch {
    return now.toISOString().slice(0, 10);
  }
}

/** تاریخ جلالی یک روز ISO — با Intl تقویم فارسی؛ خطا ⇒ همان ISO */
export function jalaliOf(iso: string): string {
  try {
    return jalaliFmt.format(new Date(`${iso}T12:00:00Z`));
  } catch {
    return iso;
  }
}

/** فاصلهٔ دو روز ISO به روز (to − from) */
export function dayDiff(fromIso: string, toIso: string): number {
  const a = Date.parse(`${fromIso}T00:00:00Z`);
  const b = Date.parse(`${toIso}T00:00:00Z`);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return Number.NaN;
  return Math.round((b - a) / 86_400_000);
}

/** نرمال‌سازی حروف عربی/نیم‌فاصله برای تطبیق عنوان (همان کاری که بک‌اند می‌کند) */
const normTitle = (t: string | null | undefined): string =>
  String(t ?? '').replace(/\u200c/g, '').replace(/\u064a/g, '\u06cc').replace(/\u0643/g, '\u06a9');

/** برچسب صادقانهٔ تغییر مجمع از روی عنوان اطلاعیه */
export function assemblyChangeLabel(title: string | null | undefined): string {
  const t = normTitle(title);
  if (/لغو|عدم برگزاری/.test(t)) return 'مجمع لغو شد';
  if (/تعویق/.test(t)) return 'مجمع به تعویق افتاد';
  if (/انتقال مجمع|تغییر زمان|موافقت با تغییر/.test(t)) return 'زمان مجمع تغییر کرد';
  return 'مجمع به تعویق افتاد';
}

function isFamily(cat: string | null | undefined): boolean {
  return cat != null && ASSEMBLY_FAMILY.has(cat);
}

export function pickAssemblyBadge(
  events: readonly CalEvent[] | null | undefined,
  now: Date = new Date(),
  nearDays: number = ASSEMBLY_NEAR_DAYS,
): AssemblyBadgeInfo | null {
  const list = (Array.isArray(events) ? events : [])
    .filter((e): e is CalEvent => typeof e?.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(e.date))
    .filter((e) => isFamily(e.cat));
  if (list.length === 0) return null;

  const todayIso = todayIsoInTehran(now);
  const sorted = [...list].sort((a, b) => a.date.localeCompare(b.date));
  const upcoming = sorted.filter((e) => dayDiff(todayIso, e.date) >= 0);
  const pastDesc = sorted.filter((e) => dayDiff(todayIso, e.date) < 0).reverse();

  const mk = (kind: 'near' | 'change', ev: CalEvent, days: number, label: string): AssemblyBadgeInfo => ({
    kind,
    days,
    date: ev.date,
    jalali: jalaliOf(ev.date),
    label,
    detail: String(ev.title ?? ''),
    testId: kind === 'near' ? 'assembly-near-badge' : 'assembly-change-badge',
  });

  const next = upcoming[0] ?? null;
  if (next != null) {
    if (next.cat === 'assemblyChange') {
      // آخرین خبرِ پیش‌رو تغییر مجمع است — تاریخ قدیمِ مجمع معتبر نیست
      return mk('change', next, 0, assemblyChangeLabel(next.title));
    }
    const days = dayDiff(todayIso, next.date);
    if (days > nearDays) return null;
    const daysText = days === 0 ? 'امروز' : days === 1 ? 'فردا' : `${toFaDigits(days)} روز دیگر`;
    const head = next.cat === 'assemblyExtra' ? 'مجمع فوق‌العاده نزدیک' : 'مجمع نزدیک';
    return mk('near', next, days, `${head} — ${daysText} (${jalaliOf(next.date)})`);
  }

  const lastPast = pastDesc[0];
  if (lastPast != null && lastPast.cat === 'assemblyChange') {
    return mk('change', lastPast, 0, assemblyChangeLabel(lastPast.title));
  }
  return null;
}

export interface CapitalIncreaseBadge {
  date: string;
  jalali: string;
  /** فاصله تا اطلاعیه — ۰ یعنی همین امروز */
  days: number;
  label: string;
  detail: string;
  testId: 'capital-increase-badge';
}

/** برچسب «افزایش سرمایه» — هشدارِ زمان‌بندی است، نه حکم: هیچ وتویی از آن نمی‌سازد
 *  (رأیِ pilot روی #53). بیرونِ افقِ همان «مجمع نزدیک» چیزی نشان داده نمی‌شود.
 *  عنوان‌محور است، چون یک اطلاعیه می‌تواند هم «دعوت به مجمع» باشد هم «افزایش
 *  سرمایه»؛ آن‌جا `cat` مجمع می‌ماند (تا وتو نَبَد) و این فهرست همان ردیف را از
 *  عنوان می‌شناسد — عینِ `_CAP_RE` در api/chart.py. */
const CAPITAL_RE = /افزايش\s*سرمايه|افزایش\s*سرمایه|افزایشسرمايه|افزايشسرمايه/;

export function isCapitalIncreaseEvent(e: CalEvent): boolean {
  if (e.cat === 'capitalIncrease') return true;
  const t = normTitle(String(e.title ?? '')).replace(/\u064a/g, '\u06cc').replace(/\u0643/g, '\u06a9');
  return CAPITAL_RE.test(t);
}

export function pickCapitalBadge(
  events: readonly CalEvent[] | null | undefined,
  now: Date = new Date(),
  nearDays: number = ASSEMBLY_NEAR_DAYS,
): CapitalIncreaseBadge | null {
  const todayIso = todayIsoInTehran(now);
  const upcoming = (Array.isArray(events) ? events : [])
    .filter((e): e is CalEvent => typeof e?.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(e.date))
    .filter((e) => isCapitalIncreaseEvent(e) && dayDiff(todayIso, e.date) >= 0)
    .sort((a, b) => a.date.localeCompare(b.date));
  const next = upcoming[0];
  if (!next) return null;
  const days = dayDiff(todayIso, next.date);
  if (days > nearDays) return null;
  const daysText = days === 0 ? 'امروز' : days === 1 ? 'فردا' : `${toFaDigits(days)} روز دیگر`;
  return {
    date: next.date,
    jalali: jalaliOf(next.date),
    days,
    label: `افزایش سرمایه — ${daysText} (${jalaliOf(next.date)})`,
    detail: String(next.title ?? ''),
    testId: 'capital-increase-badge',
  };
}
