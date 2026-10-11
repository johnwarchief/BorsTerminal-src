// features/technical/lib/ftsIndicatorCatalog.ts -- کاتالوگِ یکتای اندیکاتورهای FTS
// مرحله ۴-۵ مأموریت: هر داوری که `/api/fts` منتشر می‌کند اینجا یک شناسه، نام
// فارسی/انگلیسی، گروه، نوع نمایش، دهانۀ payload، نام قاعده در
// `docs/FTS-RULE-ALGORITHM-MAP.md` و وضعیتِ رسم در هر دو موتور دارد.
// این فایل هیچ محاسبه‌ای نمی‌کند و هیچ آستانه‌ای نمی‌سازد — رجیستریِ توصیفی است؛
// مرجعیتِ داوری همان api/chart.py می‌ماند (§۵ طرح مأموریت).
// صداقت: `engines` یعنی «امروز واقعاً رسم می‌شود» — نه آرزو. لایه‌ای که در یک
// موتور رسم نمی‌شود false می‌خورد و در گزارشِ نهایی به همان شکل مستند می‌شود.
import type { PatternKind } from './patternOverlays';

export type IndicatorGroupId =
  | 'trend'
  | 'structure'
  | 'fibonacci'
  | 'entry-setup'
  | 'exit-risk'
  | 'history-events';

export type DisplayKind = 'level' | 'band' | 'segment' | 'marker' | 'panel';

/** سوییچِ مستقلِ لایه: کلیدِ PatternPrefs یا flagِ نوارِ ابزار؛ null یعنی
 *  لایه همیشه با موتور می‌آید (پنلِ وضعیت) و توسلِ جدا ندارد. */
export type LayerToggle = PatternKind | 'showFibLevels' | 'showHistoryEvents' | 'showCorporateActions' | null;

export type FtsIndicatorEntry = {
  /** شناسهٔ پایدار — در legend، شواهدِ کلیک و لاگ‌ها همین خوانده می‌شود */
  id: string;
  fa: string;
  en: string;
  group: IndicatorGroupId;
  display: DisplayKind[];
  /** دهانۀ payloadِ `/api/fts` (نقطه‌access از ریشۀ FtsAnalysis) */
  source: string;
  /** نامِ سطرِ قاعده در docs/FTS-RULE-ALGORITHM-MAP.md — زنجیرۀ ردپا */
  rule: string;
  toggle: LayerToggle;
  engines: { klinecharts: boolean; ffc: boolean };
};

export const CATALOG_GROUPS: Record<IndicatorGroupId, { fa: string; order: number }> = {
  trend: { fa: 'روند و گیت', order: 0 },
  structure: { fa: 'ساختار (پیوت‌ها)', order: 1 },
  fibonacci: { fa: 'فیبوناچی', order: 2 },
  'entry-setup': { fa: 'ستاپ‌های ورود', order: 3 },
  'exit-risk': { fa: 'خروج و ریسک', order: 4 },
  'history-events': { fa: 'رویدادهای تاریخی', order: 5 },
};

export const FTS_INDICATOR_CATALOG: readonly FtsIndicatorEntry[] = [
  {
    id: 'trend-daily', fa: 'روند ساختاری روزانه', en: 'Daily structural trend',
    group: 'trend', display: ['panel'], source: 'trend.D',
    rule: 'روند ساختاری صعودی/نزولی/خنثی', toggle: null,
    engines: { klinecharts: false, ffc: false },
  },
  {
    id: 'trend-weekly-gate', fa: 'وتوی روند هفتگی', en: 'Weekly trend gate',
    group: 'trend', display: ['panel'], source: 'trend.matrix',
    rule: 'فیلتر روند هفتگی (ماژور)', toggle: null,
    engines: { klinecharts: false, ffc: false },
  },
  {
    id: 'structure-points', fa: 'نقاط ساختار (HH/HL/LH/LL)', en: 'Structure pivot points',
    group: 'structure', display: ['marker'], source: 'structure_points.D',
    rule: 'روند ساختاری صعودی/نزولی/خنثی', toggle: 'structure',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'fib-belt-33-40', fa: 'پل اول فیبو ۳۳–۴۰٪', en: 'Fibonacci first bridge',
    group: 'fibonacci', display: ['band'], source: 'fib.zone_33_40',
    rule: 'فیبوناچی (کمربندها/پل)', toggle: 'showFibLevels',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'fib-belt-618-70', fa: 'کمربند طلایی ۶۱.۸–۷۰٪', en: 'Fibonacci golden belt',
    group: 'fibonacci', display: ['band'], source: 'fib.zone_618_70',
    rule: 'فیبوناچی (کمربندها/پل)', toggle: 'showFibLevels',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'fib-levels', fa: 'سطوح کامل فیبو (۰ تا ۱)', en: 'Fibonacci levels',
    group: 'fibonacci', display: ['level'], source: 'fib.levels',
    rule: 'فیبوناچی (کمربندها/پل)', toggle: 'showFibLevels',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'jet', fa: 'جت — شکست مقاومت استاتیک', en: 'Jet breakout',
    group: 'entry-setup', display: ['segment', 'level'], source: 'jet.resistance',
    rule: 'جت (استراتژی)', toggle: 'jet',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'pullback', fa: 'پولبک به آخرین سقف', en: 'Pullback to last high',
    group: 'entry-setup', display: ['level', 'marker'], source: 'pullback',
    rule: 'پولبک', toggle: 'pullback',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'choch', fa: 'تغییر ساختار (CHoCH)', en: 'Change of character',
    group: 'entry-setup', display: ['level'], source: 'choch.level',
    rule: 'CHoCH / تغییر ساختار', toggle: 'choch',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'double-bottom', fa: 'خط گردن کف دوقلو', en: 'Double-bottom neckline',
    group: 'entry-setup', display: ['level'], source: 'double_bottom.neckline',
    rule: 'کف دوقلو', toggle: 'double',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'point-hunt', fa: 'تریگر نقطه‌زنی کف‌ها', en: 'Floor point-hunt trigger',
    group: 'entry-setup', display: ['marker'], source: 'point_hunt',
    rule: 'نقطه‌زنی (کف سوم/پنجم)', toggle: 'pointhunt',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'current-trigger', fa: 'تریگرِ فعلیِ موتور', en: 'Current engine trigger',
    group: 'entry-setup', display: ['marker'], source: 'status.trigger',
    rule: 'مسیریابی شاخۀ روزانه (مینور)', toggle: null,
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'third-peak', fa: 'منطقه پرریسک سقف سوم', en: 'Third-peak risk zone',
    group: 'exit-risk', display: ['band', 'level'], source: 'exit_engine.l3',
    rule: 'سقف سوم', toggle: 'thirdpeak',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'hourglass', fa: 'ساعت شنی (MA52 هفتگی)', en: 'Hourglass MA52 band',
    group: 'exit-risk', display: ['band', 'level'], source: 'hourglass',
    rule: 'ساعت شنی (استراتژی)', toggle: 'hourglass',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'ma14-exit', fa: 'خروج زیر MA14', en: 'MA14 exit',
    group: 'exit-risk', display: ['level', 'marker'], source: 'exit_engine.l1',
    rule: 'خروج MA14', toggle: 'ma14exit',
    engines: { klinecharts: true, ffc: true },
  },
  {
    id: 'hard-stop', fa: 'حد ضرر (آخرین کف)', en: 'Hard stop',
    group: 'exit-risk', display: ['level'], source: 'exit_engine.l1.hard_stop',
    rule: 'حد ضرر نوسانگیر', toggle: null,
    // در klinecharts حدِ ضرر درِ پنلِ وضعیت/برنامه خوانده می‌شود، نه روی محور؛
    // در FFC خطِ dashed دارد. صداقتِ رجیستری: همین است، نه آرزو.
    engines: { klinecharts: false, ffc: true },
  },
  {
    id: 'setup-history', fa: 'رویدادهای تاریخی ستاپ‌ها', en: 'Historical setup events',
    group: 'history-events', display: ['marker'], source: 'setups',
    rule: 'مسیریابی شاخۀ روزانه (مینور)', toggle: 'showHistoryEvents',
    engines: { klinecharts: true, ffc: false },
  },
  {
    id: 'corp-actions', fa: 'رویدادهای شرکتی (تعدیل)', en: 'Corporate actions',
    group: 'history-events', display: ['marker'], source: '(feed adjustEvents)',
    rule: '— خارج از قواعد جزوه؛ منبعش خوراک TSETMC است', toggle: 'showCorporateActions',
    engines: { klinecharts: true, ffc: true },
  },
];

/** جست‌وجویِ شناسه — بی‌یافته undefined، صفرِ ساختگی نیست */
export function catalogEntry(id: string): FtsIndicatorEntry | undefined {
  return FTS_INDICATOR_CATALOG.find((e) => e.id === id);
}

/** entriesِ یک گروه، به همان ترتیبِ کاتالوگ — برای legend/پنلِ مرحله ۶ */
export function catalogForGroup(group: IndicatorGroupId): FtsIndicatorEntry[] {
  return FTS_INDICATOR_CATALOG.filter((e) => e.group === group);
}
