// features/technical/lib/drawingTools.ts -- کاتالوگ ابزارهای ترسیم و نگاشت بر klinecharts v10
// ابزارهای vendor از getSupportedOverlays فیلتر می‌شوند؛ ابزارهای سفارشی FTS
// (فیبو با سطوح ۳۳/۴۰/۶۱.۸/۷۰/۱۰۰، اندازه‌گیری، پوزیشن) همیشه نمایش داده می‌شوند
// چون خودمان ثبتشان می‌کنیم. گروه‌بندی بر مبنای docs/CHART-PARITY-REFERENCE.md §۲.

export type DrawingTool = { name: string; label: string; custom?: boolean; hint?: string };
export type DrawingGroup = { label: string; glyph: string; tools: DrawingTool[] };

import { FTS_FIB_LOG_OVERLAY, FTS_FIB_OVERLAY, FTS_MEASURE_OVERLAY, FTS_POSITION_OVERLAY } from './ftsOverlays';

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
      { name: FTS_FIB_OVERLAY, label: 'فیبوی بازگشتی FTS', custom: true, hint: 'سطوح ۳۳/۴۰/۶۱.۸/۷۰/۱۰۰ (خطی)' },
      { name: FTS_FIB_LOG_OVERLAY, label: 'فیبوی لگاریتمی FTS', custom: true, hint: 'همان سطوح، محاسبه روی ln قیمت (FTS_SPEC بند ۳)' },
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

export type ToolDefault = { styles?: Record<string, unknown>; extendData?: Record<string, unknown> };

const SAVED_KEY = '***';

/** پیشفرض‌های ذخیره‌شدهٔ کاربر برای هر ابزار (localStorage) */
export function savedToolDefaults(): Record<string, ToolDefault> {
  try {
    const raw = localStorage.getItem(SAVED_KEY);
    return raw ? (JSON.parse(raw) as Record<string, ToolDefault>) : {};
  } catch {
    return {};
  }
}

/** ذخیرهٔ استایل فعلی به‌عنوان پیشفرض همان ابزار */
export function saveToolDefault(name: string, patch: ToolDefault): void {
  try {
    const all = savedToolDefaults();
    const prev = all[name] ?? {};
    all[name] = {
      styles: { ...(prev.styles ?? {}), ...(patch.styles ?? {}) },
      extendData: { ...(prev.extendData ?? {}), ...(patch.extendData ?? {}) },
    };
    localStorage.setItem(SAVED_KEY, JSON.stringify(all));
  } catch {
    // حافظه در دسترس نیست
  }
}

/** پیشفرض نهایی هر ابزار = پیشفرض کاتالوگ + پیشفرض ذخیره‌شدهٔ کاربر */
export function defaultFor(name: string): ToolDefault {
  const base = toolDefaults(name);
  const saved = savedToolDefaults()[name];
  if (!saved) return base;
  return {
    styles: { ...(base.styles ?? {}), ...(saved.styles ?? {}) },
    extendData: { ...(base.extendData ?? {}), ...(saved.extendData ?? {}) },
  };
}

const line = (color: string, size = 1.5): ToolDefault => ({ styles: { color, size, style: 'solid' } });

/**
 * پیش‌فرض هر ابزار ترسیم (رنگ/ضخامت/نوع خط/متن) — هنگام ساخت اورلی اعمال می‌شود
 * تا هر ابزار ظاهر معنادار پیشفرض داشته باشد (رنگ/ضخامت/امتداد/برچسب قیمت).
 */
export function toolDefaults(name: string): ToolDefault {
  switch (name) {
    case 'straightLine':
    case 'segment':
    case 'rayLine':
      return line('#38bdf8');
    case 'horizontalStraightLine':
      return line('#10b981', 1.2);
    case 'verticalStraightLine':
      return line('#a78bfa', 1.2);
    case 'horizontalRayLine':
    case 'verticalRayLine':
      return line('#38bdf8', 1.2);
    case 'priceLine':
      return line('#10b981', 1.2);
    case 'parallelStraightLine':
    case 'priceChannelLine':
      return line('#22d3ee', 1.4);
    case 'fibonacciLine':
      return { styles: { color: '#fbbf24', size: 1.2 } };
    case FTS_FIB_OVERLAY:
      return { styles: { color: '#22d3ee' } };
    case FTS_FIB_LOG_OVERLAY:
      return { styles: { color: '#a78bfa' } };
    case FTS_MEASURE_OVERLAY:
      return { styles: { color: '#10b981' } };
    case FTS_POSITION_OVERLAY:
      return { styles: { color: '#38bdf8' } };
    case 'simpleAnnotation':
      return { styles: { color: '#fbbf24' }, extendData: { text: 'یادداشت' } };
    case 'simpleTag':
      return { styles: { color: '#fbbf24' }, extendData: { text: 'برچسب' } };
    case 'brush':
      return line('#fbbf24', 2);
    default:
      return {};
  }
}
