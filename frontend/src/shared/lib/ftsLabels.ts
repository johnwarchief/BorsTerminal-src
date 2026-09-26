// shared/lib/ftsLabels.ts -- نامِ یکتای پنج شاخص FTS
// لایهٔ shared: این نام‌ها واژگانِ مشترکِ کلِ برنامه‌اند — جدولِ غربالگری، کارت،
// پنلِ جزئیات و قیفِ نبض بازار همه همین را می‌خوانند (فیچرها حقِ importِ
// فیچرِ دیگر را ندارند؛ مرزِ FSD در eslint.config.js).
// هر پنج شاخص پیش‌تر در کارت، جدول، پنلِ جزئیات و کشوی تنظیمات هرکدام جدا
// نام‌گذاری می‌شدند و سه نام مختلف برای یک محور سرِ هم درآمده بود.

/** برچسبِ کوتاهِ ستون/کارت */
export const FTS_LABEL: Record<string, string> = {
  '1_growth': '۱. رشد فروش کدال',
  '2_eps_trend': '۲. سودآوری ۳ ساله',
  '3_gross_margin': '۳. حاشیه سود ناخالص',
  '4_sales_to_mcap': '۴. پتانسیل سود تا آخر سال',
  '5_industry': '۵. رژیم صنعت',
};

/** برچسبِ کوتاهِ سرستونِ جدول (بدونِ شمارهٔ تکراری در عنوانِ ترکیبی) */
export const FTS_COLUMN_LABEL: Record<string, string> = {
  gross_margin: '۳ — حاشیه سود ناخالص',
  profit_potential: '۴ — پتانسیل سود تا آخر سال',
  industry: '۵ — صنعت',
  score: 'امتیاز',
};

/** عنوانِ پنلِ جزئیات */
export const FTS_PANEL_TITLE: Record<string, string> = {
  '1': 'شاخص ۱ — رشد فروش و درآمد',
  '2': 'شاخص ۲ — سابقه عملکرد سودسازی ۳ ساله',
  '3': 'شاخص ۳ — حاشیه سود ناخالص',
  '4': 'شاخص ۴ — پتانسیل سود تا آخر سال',
  '5': 'شاخص ۵ — چشم‌انداز صنعت و نرخ‌گذاری',
};

/** محورِ ارزیابیِ درآمدِ ارزی — در پنلِ شاخص ۵ */
export const FTS_FX_TITLE = 'پتانسیل ارزی';

/**
 * قیفِ پنج‌محوریِ جزوه — ترتیب + کلیدِ ستونِ pass در payload اسکرینر + نامِ
 * یکپارچه. یک‌جا تعریف می‌شود تا نمودارِ قیفِ نبض بازار و جدولِ غربالگری دو
 * ترتیبِ مختلف به کاربر نشان ندهند.
 */
export const FTS_FUNNEL: { axis: string; column: string; label: string; short: string }[] = [
  { axis: '1', column: 'i1_pass', label: FTS_LABEL['1_growth'], short: 'رشد فروش' },
  { axis: '2', column: 'i2_pass', label: FTS_LABEL['2_eps_trend'], short: 'روند EPS' },
  { axis: '3', column: 'i3_pass', label: FTS_LABEL['3_gross_margin'], short: 'حاشیه سود' },
  { axis: '4', column: 'i4_pass', label: FTS_LABEL['4_sales_to_mcap'], short: 'پتانسیل سود' },
  { axis: '5', column: 'i5_pass', label: FTS_LABEL['5_industry'], short: 'رژیم صنعت' },
];
