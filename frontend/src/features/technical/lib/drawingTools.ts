// features/technical/lib/drawingTools.ts -- کاتالوگ ابزارهای ترسیم و نگاشت بر klinecharts v10
// ابزارهای vendor از getSupportedOverlays فیلتر می‌شوند؛ ابزارهای سفارشی FTS
// (فیبو با سطوح ۳۳/۴۰/۶۱.۸/۷۰/۱۰۰، اندازه‌گیری، پوزیشن) همیشه نمایش داده می‌شوند
// چون خودمان ثبتشان می‌کنیم. گروه‌بندی بر مبنای docs/CHART-PARITY-REFERENCE.md §۲.

export type DrawingTool = { name: string; label: string; custom?: boolean; hint?: string };
export type DrawingGroup = { label: string; glyph: string; tools: DrawingTool[] };

export const DRAWING_CATALOG: DrawingGroup[] = [
  {
    label: 'خطوط',
    glyph: '／',
    tools: [
      { name: 'straightLine', label: 'خط روند' },
      { name: 'segment', label: 'پاره‌خط' },
      { name: 'rayLine', label: 'رای' },
      { name: 'horizontalStraightLine', label: 'خط افقی' },
      { name: 'verticalStraightLine', label: 'خط عمودی' },
      { name: 'horizontalRayLine', label: 'رای افقی' },
      { name: 'verticalRayLine', label: 'رای عمودی' },
      { name: 'priceLine', label: 'خط قیمت' },
    ],
  },
  {
    label: 'کانال',
    glyph: '∥',
    tools: [
      { name: 'parallelStraightLine', label: 'کانال موازی' },
      { name: 'priceChannelLine', label: 'کانال قیمت' },
    ],
  },
  {
    label: 'فیبوناچی',
    glyph: 'ف',
    tools: [
      { name: 'ftsFib', label: 'فیبوی بازگشتی FTS', custom: true, hint: 'سطوح ۳۳/۴۰/۶۱.۸/۷۰/۱۰۰ لگاریتمی (FTS_SPEC بند ۳)' },
      { name: 'fibonacciLine', label: 'فیبوی استاندارد' },
    ],
  },
  {
    label: 'اندازه‌گیری / پوزیشن',
    glyph: 'م',
    tools: [
      { name: 'ftsMeasure', label: 'اندازه‌گیری (۲ نقطه)', custom: true, hint: 'تغییر قیمت، درصد و تعداد کندل' },
      { name: 'ftsPosition', label: 'پوزیشن لانگ/شورت', custom: true, hint: 'ورود/حد ضرر/هدف + R/R' },
    ],
  },
  {
    label: 'حاشیه‌نویسی',
    glyph: 'ت',
    tools: [
      { name: 'simpleAnnotation', label: 'یادداشت' },
      { name: 'simpleTag', label: 'برچسب' },
      { name: 'brush', label: 'قلم' },
    ],
  },
];

/** ابزارهای vendor پشتیبانی‌شده + ابزارهای سفارشی FTS؛ گروه خالی حذف می‌شود */
export function buildDrawingGroups(supported: string[]): DrawingGroup[] {
  const set = new Set(supported);
  return DRAWING_CATALOG.map((g) => ({ ...g, tools: g.tools.filter((t) => t.custom === true || set.has(t.name)) })).filter(
    (g) => g.tools.length > 0,
  );
}

/** نگاشت نام ابزار به برچسب فارسی (برای پنل تنظیمات ابزار) */
export function toolLabel(name: string): string {
  for (const g of DRAWING_CATALOG) {
    const t = g.tools.find((x) => x.name === name);
    if (t) return t.label;
  }
  return name;
}
