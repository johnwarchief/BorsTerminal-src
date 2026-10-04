// features/technical/lib/levels.ts -- واژه‌نامهٔ فارسیِ ترازها و حد ضرر (سایدبار تب ۳)
// هیچ عددی اینجا محاسبه نمی‌شود: حد ضرر و لایه‌های خروج در موتور سرور (api/chart.py)
// ساخته می‌شوند و این فایل فقط کلیدهای انگلیسی‌شان را به فارسیِ جزوه برگرد می‌اندازد.

export const SETUP_FA: Record<string, string> = {
  breakout: 'جت (شکست سقف)',
  pullback: 'پولبک',
  choch: 'CHoCH',
  bearish_div: 'واگرایی منفی',
  range: 'رنج',
  trend: 'روند',
};

/** واژه‌نامۀ «زمینه»ها — این‌ها ستاپ/سیگنالِ ورود نیستند (taxonomyِ دورِ J) */
export const CONTEXT_FA: Record<string, string> = {
  fib_zone_33_40: 'موقعیت: کمربند ۳۳–۴۰٪',
  fib_zone_618_70: 'موقعیت: کمربند ۶۱.۸–۷۰٪',
};

/** منشأِ حد ضرر سخت از موتور خروج — `stop_basis` در لایهٔ ۱ */
export const STOP_BASIS_FA: Record<string, string> = {
  entry: 'زیرِ قیمتِ خریدِ ثبت‌شده در سبد',
  swing_low: 'زیرِ کف ۲۰ نشستِ اخیر (قیمت خریدی در سبد ثبت نشده)',
};

/** لایه‌های فعالِ موتور خروج — کلیدهای `exit_engine.signals` */
export const EXIT_SIGNAL_FA: Record<string, string> = {
  stop_hard: 'حد ضرر خورد شد',
  ma14_trail: 'خروج MA(14)',
  ma14_watch: 'نزدیکِ خروج MA(14)',
  choch_break: 'شکست ساختار (CHoCH)',
  channel_break: 'شکست کف کانال',
  third_peak: 'سقف سوم',
  double_top: 'سقف دوقلو',
  hs_break: 'شکست سر و شانه',
  rsi_divergence: 'واگرایی منفی RSI',
  rsi_rollover: 'چرخش RSI از اشباع',
};
