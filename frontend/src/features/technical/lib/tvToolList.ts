// features/technical/lib/tvToolList.ts -- لیست سبک ابزارهای پیشرفتهٔ TV (بدون import سنگین)
// جدا نگه داشته شد تا کاتالوگ تولبار به بستهٔ react-klinecharts-ui وابسته نشود؛
// ثبت تمپلیت‌ها به‌صورت lazy در tvTools.ts انجام می‌شود.

export type TvOverlayTool = { name: string; label: string; hint?: string };

/** زیرمجموعهٔ منتخب (پوشش شکاف‌های T-03: گن/الیوت/هارمونیک/پوزیشن/اندازه‌گیری) */
export const TV_OVERLAY_TOOLS: TvOverlayTool[] = [
  { name: 'measure', label: 'اندازه‌گیری (Range)', hint: 'تغییر قیمت/درصد و تعداد کندل' },
  { name: 'longPosition', label: 'پوزیشن لانگ' },
  { name: 'shortPosition', label: 'پوزیشن شورت' },
  { name: 'parallelChannel', label: 'کانال موازی (پیشرفته)' },
  { name: 'gannBox', label: 'جعبهٔ گن' },
  { name: 'gannFan', label: 'بادبزن گن' },
  { name: 'xabcd', label: 'الگوی XABCD' },
  { name: 'elliottWave', label: 'موج الیوت' },
  { name: 'fibonacciExtension', label: 'فیبوی گسترش' },
  { name: 'fibonacciSpeedResistanceFan', label: 'بادبزن فیبو' },
  { name: 'rect', label: 'مستطیل' },
  { name: 'triangle', label: 'مثلث' },
  { name: 'ray', label: 'رای (پیشرفته)' },
  { name: 'arrow', label: 'فلش' },
];

/** نام‌های ابزارهای TV در کاتالوگ ما */
export const TV_TOOL_NAMES: string[] = TV_OVERLAY_TOOLS.map((t) => t.name);
