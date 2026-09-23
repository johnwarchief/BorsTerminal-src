// shared/lib/marketHours.ts — ساعت معاملات و ریتمِ تازه‌سازیِ وابسته به آن
//
// دلیلِ وجودش: پولینگِ ۵ ثانیه‌ایِ کلِ تابلو (پاسخِ ~۴ مگابایتی) وقتی بازار
// بسته است هیچ داده‌ای عوض نمی‌کند، ولی رندرر را بیدار و GPU را مشغول نگه
// می‌دارد. اندازه‌گیریِ واقعی: در ساعتِ بسته، پنجرهٔ باز ~۷۵٪ یک هسته CPU و
// ۲۵٪ موتورِ ۳بعدی را می‌خورد؛ همین پنجره در حالتِ minimize ‏۰.۹٪ و ۰٪.
// این فایل در shared است چون هم ویژگیِ بازار به آن نیاز دارد و هم واچ‌لیستِ
// تکنیکال؛ importِ cross-feature در FSD ممنوع است.

export const MARKET_OPEN_MIN = 8 * 60 + 45;
export const MARKET_CLOSE_MIN = 12 * 60 + 30;

/** ریتمِ تازه‌سازی وقتی تابلو بسته است. */
export const CLOSED_POLL_MS = 5 * 60_000;

/** شنبه تا چهارشنبه ۰۸:۴۵ تا ۱۲:۳۰ — پنجشنبه و جمعه تعطیل. */
export function isMarketOpen(d: Date = new Date()): boolean {
  const wd = d.getDay(); // 0=Sun … 6=Sat
  if (wd === 4 || wd === 5) return false;
  const mins = d.getHours() * 60 + d.getMinutes();
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
