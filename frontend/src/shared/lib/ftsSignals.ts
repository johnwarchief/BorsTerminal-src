// shared/lib/ftsSignals.ts — نامِ فارسیِ ستاپ‌های تکنیکال، یک منبع
//
// کلیدهای `tech_*` نامِ ستونِ بانک‌اند و درِ پاسخِ سرور هم همان می‌آید؛ آنچه
// کاربر باید ببیند واژۀ جزوه است. تا پیش از این دو مصرف‌کننده داشتیم و یکی
// بی‌نام می‌ماند: برچسب‌هایِ تب تکنیکال این واژه‌ها را می‌ساختند (`ftsSignalTags`)
// ولی خانۀ «شواهد» درِ غربالگری کلیدِ خام را می‌داد
// («tech_double_bottom + tech_range_break» — سنجشِ زنده، ۲۱۴ پیکسل درِ ۱۵۰).
// پس نگاشت این‌جا می‌نشیند چون هم ویژگیِ تکنیکال و هم ویژگیِ مستر به آن نیاز
// دارند و importِ cross-feature درِ FSD ممنوع است.
export const FTS_SIGNAL_LABEL: Record<string, string> = {
  tech_hourglass_active: 'ساعت شنی (۲x-۴x)',
  tech_jet: 'جت',
  tech_choch_bull: 'CHoCH صعودی',
  tech_choch_bear: 'CHoCH نزولی',
  tech_double_bottom: 'کف دوقلو',
  tech_range_break: 'خروج از انباشت',
};

/** کلیدِ ناشناس را بی‌تغییر برمی‌گرداند — چیزی را بی‌نام نمی‌گذاریم و چیزی را
 *  اختراع نمی‌کنیم؛ اگر کلیدِ تازه‌ای آمد، همان درِ رابط دیده می‌شود و درِ
 *  همین فایل باید برچسبش اضافه شود. */
export const ftsSignalLabel = (key: string): string => FTS_SIGNAL_LABEL[key] ?? key;

/** فهرستِ کلیدهایِ شاهد (همان ترتیبِ پاسخِ سرور) به متنِ خوانا */
export const ftsSignalListText = (keys: readonly string[], sep = ' + '): string =>
  keys.map(ftsSignalLabel).join(sep);
