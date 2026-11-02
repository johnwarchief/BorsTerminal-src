/**
 * frontend-v2/src/features/technical/model/drawingCatalog.ts
 *
 * کاتالوگ جامع و دسته‌بندی‌شده ابزارهای رسم تکنیکال با نام‌های استاندارد فارسی،
 * آیکون‌های برداری و نگاشت به نام اورلی‌های KLineCharts v10.
 */

import type { DrawingCategory, DrawingToolItem, DrawingToolType } from './types';

export interface DrawingCategoryMeta {
  id: DrawingCategory;
  titleFa: string;
  descriptionFa: string;
}

export const DRAWING_CATEGORIES: DrawingCategoryMeta[] = [
  {
    id: 'lines',
    titleFa: 'ابزارهای خطی',
    descriptionFa: 'خطوط روند، کانال‌ها، سطوح افقی و رگرسیون برای تشخیص جهت حرکت قیمت',
  },
  {
    id: 'fibonacci',
    titleFa: 'ابزارهای فیبوناچی و هندسی',
    descriptionFa: 'نسبت‌های طلایی فیبوناچی، بادبزن‌ها، چنگال اندروز و هندسه گن',
  },
  {
    id: 'shapes',
    titleFa: 'زون‌ها و اشکال',
    descriptionFa: 'مستطیل‌های نقدینگی و عرضه/تقاضا، محدوده‌های قیمتی و برآورد ریسک به ریوارد',
  },
];

export const DRAWING_TOOLS_CATALOG: DrawingToolItem[] = [
  // --------------------------------------------------------------------------
  // ۱. ابزارهای خطی (Lines & Channels)
  // --------------------------------------------------------------------------
  {
    id: 'trendLine',
    nameFa: 'خط روند',
    nameEn: 'Trend Line',
    category: 'lines',
    icon: 'M4 20L20 4',
    overlayName: 'segment',
    descriptionFa: 'ترسیم پاره‌خط دو نقطه‌ای برای اتصال کف‌ها یا سقف‌های متوالی روند',
  },
  {
    id: 'horizontalLine',
    nameFa: 'خط افقی',
    nameEn: 'Horizontal Line',
    category: 'lines',
    icon: 'M3 12h18',
    overlayName: 'horizontalStraightLine',
    descriptionFa: 'خط افقی سراسری برای مشخص کردن ترازهای کلیدی حمایت، مقاومت و پیوت‌ها',
  },
  {
    id: 'horizontalRay',
    nameFa: 'نیم‌خط افقی',
    nameEn: 'Horizontal Ray',
    category: 'lines',
    icon: 'M4 12h16m-4-4l4 4-4 4',
    overlayName: 'horizontalRayLine',
    descriptionFa: 'نیم‌خط افقی امتدادیافته به سمت راست از نقطه شروع شکست یا قله',
  },
  {
    id: 'rayLine',
    nameFa: 'نیم‌خط امتدادیافته',
    nameEn: 'Ray',
    category: 'lines',
    icon: 'M4 20L18 6m-5 0h5v5',
    overlayName: 'rayLine',
    descriptionFa: 'نیم‌خط با امتداد نامحدود از نقطه دوم به آینده',
  },
  {
    id: 'verticalLine',
    nameFa: 'خط عمودی',
    nameEn: 'Vertical Line',
    category: 'lines',
    icon: 'M12 3v18',
    overlayName: 'verticalStraightLine',
    descriptionFa: 'خط عمودی برای علامت‌گذاری زمان مجامع، گزارش‌های کدال یا سررسیدهای زمانی',
  },
  {
    id: 'parallelChannel',
    nameFa: 'کانال موازی',
    nameEn: 'Parallel Channel',
    category: 'lines',
    icon: 'M4 18L18 4M6 20L20 6',
    overlayName: 'parallelStraightLine',
    descriptionFa: 'ترسیم کانال موازی بر پایه دو کف و یک سقف یا بالعکس',
  },
  {
    id: 'regressionChannel',
    nameFa: 'کانال رگرسیون',
    nameEn: 'Regression Channel',
    category: 'lines',
    icon: 'M3 17l6-6 4 4 8-8M3 13l6-6 4 4 8-8M3 21l6-6 4 4 8-8',
    overlayName: 'regressionChannel',
    descriptionFa: 'کانال رگرسیون خطی استاندارد با باندهای انحراف معیار',
  },

  // --------------------------------------------------------------------------
  // ۲. ابزارهای فیبوناچی و هندسی (Fibonacci & Geometric)
  // --------------------------------------------------------------------------
  {
    id: 'fibonacciRetracement',
    nameFa: 'فیبوناچی اصلاحی',
    nameEn: 'Fibonacci Retracement',
    category: 'fibonacci',
    icon: 'M3 5h18M3 9h18M3 13h18M3 17h18M3 21h18',
    overlayName: 'fibonacciLine',
    descriptionFa: 'سطوح استاندارد اصلاحی ۲۳٫۶٪، ۳۸٫۲٪، ۵۰٪، ۶۱٫۸٪ و ۷۸٫۶٪ موج',
  },
  {
    id: 'fibonacciExtension',
    nameFa: 'فیبوناچی گسترشی',
    nameEn: 'Fibonacci Extension',
    category: 'fibonacci',
    icon: 'M4 19L10 13L16 16L20 5',
    overlayName: 'fibonacciExtension',
    descriptionFa: 'برآورد ترازهای تارگت ۱۰۰٪، ۱۲۷٫۲٪ و ۱۶۱٫۸٪ بر مبنای حرکت سه‌نقطه‌ای',
  },
  {
    id: 'fibonacciFan',
    nameFa: 'بادبزن فیبوناچی',
    nameEn: 'Fibonacci Fan',
    category: 'fibonacci',
    icon: 'M3 21L21 3M3 21L21 9M3 21L21 15',
    overlayName: 'fibonacciFan',
    descriptionFa: 'پرتوهای زاویه‌ای فیبوناچی برای تشخیص نقاط برخورد زمانی و قیمتی',
  },
  {
    id: 'andrewsPitchfork',
    nameFa: 'چنگال اندروز',
    nameEn: 'Andrews Pitchfork',
    category: 'fibonacci',
    icon: 'M4 12L12 4M12 4v16M4 12L12 20M12 4h8M12 12h8M12 20h8',
    overlayName: 'andrewsPitchfork',
    descriptionFa: 'خط میانه و بال‌های موازی بر اساس سه پیوت اصلی زیگزاگ',
  },
  {
    id: 'gannBox',
    nameFa: 'باکس گن',
    nameEn: 'Gann Box',
    category: 'fibonacci',
    icon: 'M3 3h18v18H3zM3 3l18 18M3 21L21 3',
    overlayName: 'gannBox',
    descriptionFa: 'مربع هندسی تعادل زمان و قیمت بر پایه چرخه‌های مربع گن',
  },

  // --------------------------------------------------------------------------
  // ۳. زون‌ها و اشکال (Zones & Shapes)
  // --------------------------------------------------------------------------
  {
    id: 'rectZone',
    nameFa: 'مستطیل عرضه و تقاضا',
    nameEn: 'Supply/Demand Zone',
    category: 'shapes',
    icon: 'M4 6h16v12H4z',
    overlayName: 'rect',
    descriptionFa: 'کادر مستطیلی برای تعیین زون‌های تجمیع نقدینگی، FVG و اردر بلاک',
  },
  {
    id: 'priceRange',
    nameFa: 'محدوده قیمت و درصد',
    nameEn: 'Price Range',
    category: 'shapes',
    icon: 'M12 3v18m-4-4l4 4 4-4m-8-10l4-4 4 4',
    overlayName: 'priceRange',
    descriptionFa: 'محاسبه درصد سود/زیان و تعداد کندل‌های طی شده بین دو نقطه',
  },
  {
    id: 'riskReward',
    nameFa: 'زون هدف و ریسک',
    nameEn: 'Risk / Reward Ratio',
    category: 'shapes',
    icon: 'M4 4h16v6H4zm0 8h16v8H4z',
    overlayName: 'riskReward',
    descriptionFa: 'ترسیم خودکار محدوده حد سود (TP) و حد ضرر (SL) با نسبت R:R',
  },
];

export function getDrawingToolById(id: DrawingToolType | null | undefined): DrawingToolItem | undefined {
  if (!id) return undefined;
  return DRAWING_TOOLS_CATALOG.find((tool) => tool.id === id);
}

export function getDrawingToolsByCategory(category: DrawingCategory): DrawingToolItem[] {
  return DRAWING_TOOLS_CATALOG.filter((tool) => tool.category === category);
}
