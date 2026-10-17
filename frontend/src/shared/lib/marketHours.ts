// shared/lib/marketHours.ts — ساعت معاملات و ریتمِ تازه‌سازیِ وابسته به آن
//
// دلیلِ وجودش: پولینگِ ۵ ثانیه‌ایِ کلِ تابلو (پاسخِ ~۴ مگابایتی) وقتی بازار
// بسته است هیچ داده‌ای عوض نمی‌کند، ولی رندرر را بیدار و GPU را مشغول نگه
// می‌دارد. اندازه‌گیریِ واقعی: در ساعتِ بسته، پنجرهٔ باز ~۷۵٪ یک هسته CPU و
// ۲۵٪ موتورِ ۳بعدی را می‌خورد؛ همین پنجره در حالتِ minimize ‏۰.۹٪ و ۰٪.
// این فایل در shared است چون هم ویژگیِ بازار به آن نیاز دارد و هم واچ‌لیستِ
// تکنیکال؛ importِ cross-feature در FSD ممنوع است.
//
// قاعدۀ تاریخ/ساعتِ بازار: تابلوی TSETMC با تقویم و ساعتِ *تهران* باز/بسته
// می‌شود. نسخۀ پیشین با getDay()/getHours()ِ ساعتِ *دستگاه* می‌ساخت؛ گوشیِ با
// timezone غیرِ تهران (سفر، تنظیمِ اشتباه، ROM کارگزاری) درِ بازارِ واقعیِ باز
// «بازار بسته» می‌گفت و پولینگِ ۵ ثانیه را به ۵ دقیقه می‌انداخت — یعنی تابلو
// عملاً می‌ایستاد بی‌آنکه کاربر سرنخی ببیند. حالا ساعتِ دیواریِ تهران مستقیماً
// از Intl خوانده می‌شود؛ رویِ دستگاهِ تهرانی نتیجه بیت‌به‌بیت همانِ پیشین است.

export const MARKET_OPEN_MIN = 8 * 60 + 45;
export const MARKET_CLOSE_MIN = 12 * 60 + 30;

/** ریتمِ تازه‌سازی وقتی تابلو بسته است. */
export const CLOSED_POLL_MS = 5 * 60_000;

// موتورِ ساعتِ تهران — weekdayِ شماره‌دار برایِ پارسِ مطمئن (انگلیسیِ en-US
// همیشه عددِ رقمی می‌دهد، نه نامِ روز). fmt یک‌بار ساخته می‌شود؛ callsِ بعدی
// (پولینگ ۵ ثانیه) فقط formatToPartsِ ارزان‌اند.
const TEHRAN_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Tehran', hourCycle: 'h23', weekday: 'short',
  hour: '2-digit', minute: '2-digit',
});
const WEEKDAY_NUM: Record<string, number> = {
  Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6,
};

/** روزِ هفته و دقیقۀ دیواریِ تهران برایِ یکِ لحظه (clock-safe، بی‌قید به TZِ دستگاه). */
function tehranFilterWhereSafe(d: Date): { wd: number; mins: number } {
  const parts = TEHRAN_FMT.formatToParts(d);
  const g = (t: Intl.DateTimeFormatPartTypes): string =>
    parts.find((p) => p.type === t)?.value ?? '';
  const wd = WEEKDAY_NUM[g('weekday')] ?? new Date().getDay();
  const mins = Number(g('hour')) * 60 + Number(g('minute'));
  return { wd, mins };
}

/** آفستِ تهران نسبت به UTC (میلی‌ثانیه) درِ یکِ لحظه — ۳:۳۰+ بدونِ DST.
 *  مصرف‌کننده: تبدیلِ مُهرهایِ «ساعتِ دیواریِ تهران» (مثلِ meta.last_sync از
 *  بک‌اند، بی‌Z) به epoch. موتورِ خاب ⇒ همان ۱۳٫۵ ساعت صریح. */
export function tehranOffsetMs(now: number = Date.now()): number {
  try {
    const f = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Tehran', hourCycle: 'h23',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    const p = f.formatToParts(new Date(now));
    const g = (t: Intl.DateTimeFormatPartTypes): number =>
      Number(p.find((x) => x.type === t)?.value ?? 0);
    const wall = Date.UTC(g('year'), g('month') - 1, g('day'), g('hour'), g('minute'), g('second'));
    return wall - Math.floor(now / 1000) * 1000;
  } catch {
    return 3.5 * 3_600_000; // +۳:۳۰ = ۱۲٬۶۰۰٬۰۰۰ میلی‌ثانیه
  }
}

/** شنبه تا چهارشنبه ۰۸:۴۵ تا ۱۲:۳۰ به وقت تهران — پنجشنبه و جمعه تعطیل. */
export function isMarketOpen(d: Date = new Date()): boolean {
  const { wd, mins } = tehranFilterWhereSafe(d);
  if (wd === 4 || wd === 5) return false;
  return mins >= MARKET_OPEN_MIN && mins <= MARKET_CLOSE_MIN;
}

/**
 * بازهٔ عملیِ پولینگ: هر چه کاربر انتخاب کرده، ولی در ساعتِ تعطیل دستِ‌کم
 * به ریتمِ بسته می‌رسد. انتخابِ صریحِ کاربر (۱۵ ثانیه ↔ ۵ دقیقه) محترم می‌ماند
 * و فقط در بازهٔ باز سریع می‌شود.
 */
export function effectivePollMs(userMs: number, d: Date = new Date()): number {
  return isMarketOpen(d) ? userMs : Math.max(userMs, CLOSED_POLL_MS);
}

/**
 * ریتمِ پنل‌هایِ نشست‌محور (نبض بازار، صنایع داغ، مینی‌چارتِ جریان حجم،
 * تریگرهای درون‌روزه). این‌ها انتخابِ کاربر نیستند — خودشان در ساعتِ بازار
 * نفس می‌کشند و بیرونِ آن به ریتمِ آرامِ تابلو می‌نشینند تا عددِ پنل با
 * عددِ جدولِ نهایی یکی بماند (#173: تا پیش از این فقط جدول تازه می‌شد و
 * نمودارهایِ نبض تا بستنِ صفحه در جای خودشان می‌ماندند).
 */
export function sessionPollMs(openMs: number, d: Date = new Date()): number {
  return isMarketOpen(d) ? openMs : CLOSED_POLL_MS;
}
