// features/master/lib/ftsChartModel.ts -- مدلِ «چهار صفحۀ FTS در یک نقشه»
// این فایل فقط **داده** است: هیچ SVG، هیچ مختصاتِ دستی و هیچ قاعدۀ تشخیصی درِ آن
// نیست. چهار Zone دقیقاً چهار صفحۀ چاپیِ چارت‌اند (F=۱ بنیادی، T=۲ تکنیکال،
// S=۳ انتخاب، M=۴ مهندسی معکوس/مدیریت سرمایه/استراتژی) و parent/child هر Zone
// همان سطرهایِ خودِ چارت است (`docs/fts-notes/FTS_CHART3_extracted_text.txt`،
// حسابرسیِ خط‌به‌خط: `docs/CHART-FOUR-PAGES-PARITY.md`).
//
// سه قیدِ این مدل:
//  ۱) متن/قاعده/آستانۀ گره‌ها از جدولِ پیشینِ `ObsidianStrategyGraph.tsx` عیناً
//     منتقل شده (تولیدِ مکانیکی: `_audit/gen_fts_chart_model.py`) تا ظاهرِ تازه،
//     معنا را عوض نکند.
//  ۲) چیزی که درِ چارت سطر ندارد `origin: 'program'` می‌خورد (طبقه‌هایِ امتیاز،
//     R/R، سقفِ وزنِ صنعت، فروشِ درصدی در اولین سقف) تا نقشه، برنامه را وعدهٔ
//     جزوه نزند.
//  ۳) مفهومی که درِ چند صفحه تکرار شده یکِ گره می‌ماند و با `refs` به آن صفحه‌ها
//     وصل می‌شود — خط‌چینِ «هم‌نام»، نه نسخۀ دوم و نه رابطۀ ساختاریِ جعلی.
//
// Source of Truth منطق همچنان بک‌اند/پایتون است؛ این مدل هیچ داوری‌ای نمی‌کند.
// GENERATED از `_audit/strategy_graph_dump.json` + جدولِ parentِ همان اسکریپت.

import { toFaDigits } from '@shared/lib/fmt';
import type { StrategyParameters } from '../stores/strategyParamsStore';

export type FtsZone = 'F' | 'T' | 'S' | 'M';
export type FtsPreset = 'swing' | 'trend' | 'hourglass' | 'custom';
/** جهتِ ریل: مهندسی معکوسِ جزوه (S→T→F→M) یا جریانِ کلاسیکِ تحلیلی (F→T→S→M).
 *  فقط ترتیبِ روشن‌شدن و فلشِ ریل را عوض می‌کند — هیچ گره، هیچ parent و هیچ
 *  جایگاهِ Zone را جابه‌جا نمی‌کند (قیدِ مالک: جهت، توپولوژی را نسازد). */
export type FlowDirection = 'reverse' | 'classic';

export interface FtsZoneMeta {
  key: FtsZone;
  page: number;
  /** سربرگِ Zone رویِ نقشه */
  title: string;
  sub: string;
  /** همان «رکن: …» که پنلِ جزئیات نشان می‌داد (متنِ پیشین) */
  stageName: string;
  /** رنگِ تمِ Zone، دو حالتِ روشن/تاریک */
  accentLight: string;
  accentDark: string;
}

export const ZONES: FtsZoneMeta[] = [
  { key: 'F', page: 1, title: '۱ · F بنیادی', sub: 'پنج‌شاخص کدال', stageName: 'بنیادی F', accentLight: '#059669', accentDark: '#10b981' },
  { key: 'T', page: 2, title: '۲ · T تکنیکال', sub: 'سیگنال دو زمانه', stageName: 'تکنیکال T', accentLight: '#0284c7', accentDark: '#38bdf8' },
  { key: 'S', page: 3, title: '۳ · S انتخاب', sub: 'تابلوخوانی', stageName: 'تابلوخوانی S', accentLight: '#d97706', accentDark: '#f59e0b' },
  { key: 'M', page: 4, title: '۴ · M داوری و سرمایه', sub: 'مهندسی معکوس و سرمایه', stageName: 'مدیریت سرمایه M', accentLight: '#dc2626', accentDark: '#ef4444' },
];

export const ZONE_BY_KEY: Record<FtsZone, FtsZoneMeta> = Object.fromEntries(
  ZONES.map((z) => [z.key, z]),
) as Record<FtsZone, FtsZoneMeta>;

export interface FtsChartNode {
  id: string;
  /** صفحۀ اصلیِ گره — همان Zone که درِ آن رسم می‌شود */
  zone: FtsZone;
  /** سرِ شاخۀ واقعی درِ همان صفحه؛ null یعنی ریشۀ همان Zone */
  parent: string | null;
  /** ترتیبِ خواندنِ چارت درِ همان شاخه (۰ = اول) */
  order: number;
  /** 'chart' = سطرِ خودِ جزوه، 'program' = افزونۀ منطقِ برنامه */
  origin: 'chart' | 'program';
  /** 'head' = سرِ شاخه (نقلِ سطرِ چارت)، 'leaf' = گره برچسب‌دار */
  kind: 'head' | 'leaf';
  label: string;
  fullTitle: string;
  /** برچسبِ «چارت صفحۀ …» که درِ پنلِ جزئیات دیده می‌شود — متنِ پیشین */
  page: string;
  description: string;
  ruleFormula: string;
  badge: string;
  color: string;
  /** هم‌نام‌هایِ این مفهوم درِ صفحه‌های دیگر (خط‌چین، نه یالِ ساختاری) */
  refs: string[];
  editableParamKeys?: (keyof StrategyParameters)[];
}

export interface FtsChartModel {
  nodes: FtsChartNode[];
  byId: Map<string, FtsChartNode>;
  childrenOf: Map<string, string[]>;
  roots: Record<FtsZone, string>;
  byZone: Record<FtsZone, FtsChartNode[]>;
}

/** سرِ شاخه‌ها و ریشه‌ها — متن‌ها عینِ سطرهایِ خودِ چارت است */
const CHART_HEADS: FtsChartNode[] = [
  {
    id: 'f_root',
    zone: 'F',
    parent: null,
    order: 0,
    origin: 'chart',
    kind: 'head',
    label: 'F: بنیادی',
    fullTitle: 'صفحۀ ۱ چارت FTS — غربالگری بنیادی پنج‌شاخصه',
    page: 'چارت صفحه ۱',
    description: 'ریشۀ صفحۀ اول: پنج سطرِ شاخصِ کدال. هیچ شاخصی درِ اینجا محاسبه نمی‌شود؛ داوری از `api/fundamental.py::evaluate_v10` می‌آید.',
    ruleFormula: '۵ شاخص ← امتیاز ۱ تا ۵',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'f_tiers',
    zone: 'F',
    parent: 'f_root',
    order: 6,
    origin: 'program',
    kind: 'head',
    label: 'طبقه‌بندی امتیاز',
    fullTitle: 'طبقه‌بندیِ چهارگانهٔ امتیازِ بنیادی',
    page: 'چارت صفحه ۱',
    description: 'درِ جزوه این چهار طبقه سطر ندارد؛ از منطقِ برنامه است (سوپر/مطلوب/متوسط/رد صلب) و رأی‌اش از موتورِ بنیادی سرور می‌آید.',
    ruleFormula: 'برنامۀ FTS، نه سطرِ چارت',
    badge: 'سرِ شاخۀ برنامه',
    color: '',
    refs: [],
  },
  {
    id: 't_root',
    zone: 'T',
    parent: null,
    order: 0,
    origin: 'chart',
    kind: 'head',
    label: 'T: تکنیکال',
    fullTitle: 'صفحۀ ۲ چارت FTS — سیگنال خرید و فروشِ دو زمانه',
    page: 'چارت صفحه ۲',
    description: 'ریشۀ صفحۀ دوم. روند و ستاپ‌ها از موتورِ `api/chart.py` خوانده می‌شوند؛ این نقشه چیزی را دوباره حساب نمی‌کند.',
    ruleFormula: 'هفتگی ⇒ روزانه ⇒ ستاپ',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_buy',
    zone: 'T',
    parent: 't_root',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'سیگنال خرید',
    fullTitle: 'سرِ شاخۀ سیگنالِ خرید در چارت',
    page: 'چارت صفحه ۲',
    description: 'چارت اول روندِ هفتگی را می‌پرسد: نزولی reject، خنثی reject، صعودی باز می‌شود.',
    ruleFormula: 'ریجکت هفتگی = وتوی قطعی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_daily_up',
    zone: 'T',
    parent: 'tech_weekly_up',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'تایم روزانه صعودی',
    fullTitle: 'شاخۀ روزانۀ صعودیِ زیرِ هفتگیِ صعودی',
    page: 'چارت صفحه ۲',
    description: 'سطرِ «تایم روزانه صعودی» در چارت: استراتژی پولبک و استراتژی جت.',
    ruleFormula: 'هفتگی صعودی + روزانه صعودی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_daily_down',
    zone: 'T',
    parent: 'tech_weekly_up',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'تایم روزانه نزولی',
    fullTitle: 'شاخۀ روزانۀ نزولیِ زیرِ هفتگیِ صعودی',
    page: 'چارت صفحه ۲',
    description: 'سطرِ «تایم روزانه نزولی» در چارت: استراتژی فیبوناتچی و CHOOCH.',
    ruleFormula: 'هفتگی صعودی + روزانه نزولی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_daily_neutral',
    zone: 'T',
    parent: 'tech_weekly_up',
    order: 3,
    origin: 'chart',
    kind: 'head',
    label: 'تایم روزانه خنثی',
    fullTitle: 'شاخۀ روزانۀ خنثیِ زیرِ هفتگیِ صعودی',
    page: 'چارت صفحه ۲',
    description: 'سطرِ «تایم روزانه خنثی» در چارت: ورود در آخرین کفِ روند صعودی یا آخرین سقفِ روند نزولی.',
    ruleFormula: 'هفتگی صعودی + روزانه خنثی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_sell',
    zone: 'T',
    parent: 't_root',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'سیگنال فروش',
    fullTitle: 'بخشِ فروشِ صفحۀ دوم چارت',
    page: 'چارت صفحه ۲',
    description: 'سرِ شاخۀ فروش در چارت: کف دوقلو، سقف دوقلو، سر و شانه، سقف سوم و واگراییِ مقاومتی. هیچ‌کدام درِ فرانت داوری نمی‌شوند؛ رأی از `exit_engine`ِ سرور است.',
    ruleFormula: 'ساختارِ فروش',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 't_stop',
    zone: 'T',
    parent: 't_root',
    order: 3,
    origin: 'chart',
    kind: 'head',
    label: 'حد ضرر',
    fullTitle: 'بخشِ حد ضررِ صفحۀ دوم چارت',
    page: 'چارت صفحه ۲',
    description: 'سطرهایِ «حد ضرر» در چارت: ۵٪ زیر آخرین کفِ روند صعودی، نوسانگیر MA=14 با یک کندلِ کامل زیر MA، و روندگیر با خریدِ پله‌ای و ۵٪ زیر نقطۀ ورود. عددها را همان گره‌هایِ صفحۀ ۴ نگه می‌دارند (خط‌چینِ هم‌نام) — نسخهٔ دوم ساخته نشده.',
    ruleFormula: '۵٪ · MA=14 · پله‌ای',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['stop_swing', 'stop_trend'],
  },
  {
    id: 's_root',
    zone: 'S',
    parent: null,
    order: 0,
    origin: 'chart',
    kind: 'head',
    label: 'S: SELECTION',
    fullTitle: 'صفحۀ ۳ چارت FTS — انتخاب و غربالگری تابلوخوانی',
    page: 'چارت صفحه ۳',
    description: 'ریشۀ صفحۀ سوم: سبکِ معامله، رصدِ جریان نقدینگی، بررسیِ صنایع، حجمِ معاملات، الگوهایِ تابلوخوانی و خشک کردن.',
    ruleFormula: 'تابلو قبل از تکنیکال (مهندسی معکوس)',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_style',
    zone: 'S',
    parent: 's_root',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'انتخاب سبک معامله',
    fullTitle: 'سرِ شاخۀ سبکِ معامله در چارت',
    page: 'چارت صفحه ۳',
    description: 'چارت دو سبک را می‌شمارد: نوسانگیر و روندگیر. همین دو، همان دو پرستِ برنامه‌اند؛ شاخه‌ها جابه‌جا نمی‌شوند، فقط روشن می‌شوند.',
    ruleFormula: 'نوسانگیر / روندگیر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_style_swing',
    zone: 'S',
    parent: 's_style',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'نوسانگیر',
    fullTitle: 'سبکِ نوسان‌گیری (۱ تا ۲ ماه)',
    page: 'چارت صفحه ۳',
    description: 'سرِ شاخۀ نوسانگیر در چند بخشِ صفحۀ سوم؛ پرستِ `swing` همین شاخه‌ها را روشن می‌کند.',
    ruleFormula: 'پرست: swing',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_style_trend',
    zone: 'S',
    parent: 's_style',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'روندگیر',
    fullTitle: 'سبکِ روندی (بالای ۳ ماه)',
    page: 'چارت صفحه ۳',
    description: 'سرِ شاخۀ روندگیر در چند بخشِ صفحۀ سوم؛ پرستِ `trend` همین شاخه‌ها را روشن می‌کند.',
    ruleFormula: 'پرست: trend',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_liquidity',
    zone: 'S',
    parent: 's_root',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'رصد جریان نقدینگی',
    fullTitle: 'سرِ شاخۀ نقدینگی در چارت',
    page: 'چارت صفحه ۳',
    description: 'وضعیتِ کل بازار: TRADERS ARENA، نمودارهایِ جریانِ پول و ورود/خروجِ پول.',
    ruleFormula: 'مساعد / نامساعد',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_arena',
    zone: 'S',
    parent: 's_liquidity',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'وضعیت بازار در TRADERS ARENA',
    fullTitle: 'بررسی وضعیت بازار در TRADERS ARENA',
    page: 'چارت صفحه ۳',
    description: 'سطرِ چارت: ارزشِ معاملاتِ بازارِ سهام و شمارِ سهامِ مثبت/منفی. داوریِ عددی درِ `mstat_engine` و `/api/live-stats` است، نه این نقشه.',
    ruleFormula: 'ارزش معاملات · سهام مثبت/منفی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_industries',
    zone: 'S',
    parent: 's_root',
    order: 3,
    origin: 'chart',
    kind: 'head',
    label: 'بررسی صنایع',
    fullTitle: 'خلاصه معاملات صنایع و سهام برگزیده',
    page: 'چارت صفحه ۳',
    description: 'سطرِ «بررسی صنایع: خلاصه معاملات صنایع بورس» و «سهام برگزیده» (صدِ آخرین و ورودِ پول را از بالا به پایین مرتب می‌کنیم).',
    ruleFormula: 'خلاصه صنایع · سهام برگزیده',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_volume',
    zone: 'S',
    parent: 's_root',
    order: 4,
    origin: 'chart',
    kind: 'head',
    label: 'حجم معاملات',
    fullTitle: 'سرِ شاخۀ حجمِ معاملات در چارت',
    page: 'چارت صفحه ۳',
    description: 'چارت برایِ هر دو سبک یک شرطِ حجمی می‌گذارد: نوسانگیر حجمِ مشکوک (سه برابر میانگینِ ماهانۀ MA=21)، روندگیر حجمِ معاملات و ورود در قیمتِ ارزنده.',
    ruleFormula: 'حجم مشکوک / حجم روند',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_volume_swing',
    zone: 'S',
    parent: 's_volume',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'نوسانگیر',
    fullTitle: 'حجم معاملات — شاخۀ نوسانگیر',
    page: 'چارت صفحه ۳',
    description: 'سطرِ «نوسانگیر: بررسی حجم مشکوک (سه برابر میانگین ماهانه) volume, MA length=21».',
    ruleFormula: 'سبک: نوسانگیر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_volume_trend',
    zone: 'S',
    parent: 's_volume',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'روندگیر',
    fullTitle: 'حجم معاملات — شاخۀ روندگیر',
    page: 'چارت صفحه ۳',
    description: 'سطرِ «روندگیر: بررسی حجم معاملات و ورود در قیمتِ ارزنده».',
    ruleFormula: 'سبک: روندگیر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_patterns',
    zone: 'S',
    parent: 's_root',
    order: 5,
    origin: 'chart',
    kind: 'head',
    label: 'الگوهای تابلوخوانی',
    fullTitle: 'سرِ شاخۀ الگوهایِ تابلوخوانی در چارت',
    page: 'چارت صفحه ۳',
    description: 'الگوی ساعت و خروج از باکسِ رنج برایِ نوسانگیر؛ کف‌روبی برایِ روندگیر.',
    ruleFormula: 'ساعت / باکس رنج / کف‌روبی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_patterns_swing',
    zone: 'S',
    parent: 's_patterns',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'نوسانگیر',
    fullTitle: 'الگوها — شاخۀ نوسانگیر',
    page: 'چارت صفحه ۳',
    description: 'سرِ شاخۀ «نوسانگیر: الگوی ساعت، خروج از باکس رنج» در چارت.',
    ruleFormula: 'سبک: نوسانگیر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_patterns_trend',
    zone: 'S',
    parent: 's_patterns',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'روندگیر',
    fullTitle: 'الگوها — شاخۀ روندگیر',
    page: 'چارت صفحه ۳',
    description: 'سطرِ «روندگیر: کف روبی — سهم صف فروش است ولی اوردرهایِ قوی در حال خریدِ سهم هستند».',
    ruleFormula: 'سبک: روندگیر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 's_dry',
    zone: 'S',
    parent: 's_root',
    order: 6,
    origin: 'chart',
    kind: 'head',
    label: 'خشک کردن (فیلتر)',
    fullTitle: 'فیلترِ نهاییِ صفحۀ سوم',
    page: 'چارت صفحه ۳',
    description: 'سطرِ «خشک کردن / فیلتر» در چارت: برایِ نوسانگیر ساعت، جت و حجمِ مشکوک؛ برایِ روندگیر کف‌روبی و نقطه‌زنی. شمارشِ نمادهایِ عبوری درِ `lib/strictGates.ts` است.',
    ruleFormula: 'خشک کردنِ فهرست',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_root',
    zone: 'M',
    parent: null,
    order: 0,
    origin: 'chart',
    kind: 'head',
    label: 'مهندسی معکوس + مدیریت سرمایه',
    fullTitle: 'صفحۀ ۴ چارت FTS — داوری، سرمایه و استراتژی',
    page: 'چارت صفحه ۴',
    description: 'ریشۀ صفحۀ چهارم: ترتیبِ مهندسی معکوس، مدیریتِ سرمایه، رصدِ پورتفو، اصولِ پورتفوی بهینه و استراتژی‌ها.',
    ruleFormula: '۱ تابلو ۲ تکنیکال ۳ بنیادی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_reverse',
    zone: 'M',
    parent: 'm_root',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: 'مهندسی معکوس',
    fullTitle: 'ترتیبِ مهندسی معکوسِ چارت',
    page: 'چارت صفحه ۴',
    description: 'سطرهایِ «۱-تابلو خوانی، ۲-تکنیکال، ۳-بنیادی». همین ترتیب، همان جریانِ `reverse` است — جهتِ ریل، نه جایِ صفحه‌ها.',
    ruleFormula: 'تابلو ← تکنیکال ← بنیادی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_reverse_tape',
    zone: 'M',
    parent: 'm_reverse',
    order: 1,
    origin: 'chart',
    kind: 'head',
    label: '۱- تابلو خوانی',
    fullTitle: 'پیلارِ اولِ مهندسی معکوس',
    page: 'چارت صفحه ۴',
    description: 'چارت زیرِ این سطر سه مورد می‌شمارد: فیلتر حجم مشکوک، الگوی ساعت، کف روبی — همان سه گره درِ صفحۀ ۳؛ پیوندِ خط‌چین به همان‌ها می‌رود، نسخۀ دوم ساخته نمی‌شود.',
    ruleFormula: 'حجم مشکوک · ساعت · کف‌روبی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['tape_volume', 'tape_clock', 'tape_floor_sweep'],
  },
  {
    id: 'm_reverse_tech',
    zone: 'M',
    parent: 'm_reverse',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: '۲- تکنیکال',
    fullTitle: 'پیلارِ دومِ مهندسی معکوس',
    page: 'چارت صفحه ۴',
    description: 'ارجاع به صفحۀ ۲. داوریِ روند از موتورِ FTS است.',
    ruleFormula: '→ صفحۀ ۲',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['t_root'],
  },
  {
    id: 'm_reverse_fund',
    zone: 'M',
    parent: 'm_reverse',
    order: 3,
    origin: 'chart',
    kind: 'head',
    label: '۳- بنیادی',
    fullTitle: 'پیلارِ سومِ مهندسی معکوس',
    page: 'چارت صفحه ۴',
    description: 'ارجاع به صفحۀ ۱. امتیاز از `/api/fundamental` می‌آید.',
    ruleFormula: '→ صفحۀ ۱',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['f_root'],
  },
  {
    id: 'm_money',
    zone: 'M',
    parent: 'm_root',
    order: 2,
    origin: 'chart',
    kind: 'head',
    label: 'مدیریت سرمایه',
    fullTitle: 'سرِ شاخۀ مدیریتِ سرمایه در چارت',
    page: 'چارت صفحه ۴',
    description: 'حداکثر ۷۰٪ کل دارایی در بازارِ سرمایه (در شرایطِ جنگی ۲۰±۱۰٪)، وزنِ سبد با احتسابِ حداکثرِ ضرر، صندوق‌ها و پوششِ ریسک، نوعِ حدِ ضرر و ورود/خروجِ پله‌ای.',
    ruleFormula: 'سقف · وزن · پوشش · حدضرر',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_stop_kind',
    zone: 'M',
    parent: 'm_money',
    order: 4,
    origin: 'chart',
    kind: 'head',
    label: 'نوع حد ضرر (نوسانی و روندی)',
    fullTitle: 'توجه به نوع حد ضرر در معاملات نوسانی و روندی',
    page: 'چارت صفحه ۴',
    description: 'سطرِ چارت: نوسانگیر حد ضرر دارد و خریدِ پله‌ای (۱ تا ۲ ماه+)؛ روندگیر بالای ۳ ماه، خریدِ پله‌ای دارد و حد ضررش بنیادی است نه تکنیکالی (حکمِ ۸ مالک).',
    ruleFormula: 'نوسانگیر: تکنیکالی · روندگیر: بنیادی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['t_stop'],
  },
  {
    id: 'm_monitor',
    zone: 'M',
    parent: 'm_root',
    order: 3,
    origin: 'chart',
    kind: 'head',
    label: 'رصد و تحلیل مداوم پورتفوی',
    fullTitle: 'سرِ شاخۀ رصدِ مداوم در چارت',
    page: 'چارت صفحه ۴',
    description: 'سطرِ چارت: هر ماه گزارشِ فروش، هر فصل صورتِ مالی، هر سال صورتِ مالی سالانه و مقایسه با سال قبل. تقویمِ گزارش‌ها از `codal_periods` است.',
    ruleFormula: 'ماهانه · فصلی · سالانه',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_fit',
    zone: 'M',
    parent: 'm_root',
    order: 4,
    origin: 'chart',
    kind: 'head',
    label: 'تناسب دیدگاه با بورس ایران',
    fullTitle: 'تناسب دیدگاه سرمایه‌گذاری با بورس ایران',
    page: 'چارت صفحه ۴',
    description: 'سرِ شاخۀ اصولِ پورتفوی بهینه در چارت: سهام دلاری/ریالی، بزرگ و کوچک، تولیدی و غیرتولیدی، صندوق‌های سرمایه‌گذاری.',
    ruleFormula: 'دلاری · ریالی · بزرگ/کوچک',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: [],
  },
  {
    id: 'm_strategy',
    zone: 'M',
    parent: 'm_root',
    order: 5,
    origin: 'chart',
    kind: 'head',
    label: 'استراتژی',
    fullTitle: 'سرِ شاخۀ استراتژی‌های صفحۀ چهارم',
    page: 'چارت صفحه ۴',
    description: 'چارت اینجا سه استراتژی را نام می‌برد: ساعت شنی، جت، نقطه‌زنی. هر سه گره‌شان درِ صفحۀ ۲ و ۳ ساخته شده، پس این سر با خط‌چین به همان‌ها وصل می‌شود.',
    ruleFormula: 'ساعت شنی · جت · نقطه‌زنی',
    badge: 'سرِ شاخۀ چارت',
    color: '',
    refs: ['stop_hourglass', 'setup_jet', 'setup_point_hunt'],
  },
];

/** گره‌هایِ برچسب‌دارِ نقشه — متن/قاعده/آستانه عیناً از جدولِ پیشین. تابع است چون
 *  برچسبِ چند گره آستانۀ زندۀ `strategyParamsStore` را درِ خودش نشان می‌دهد. */
export function chartLeaves(params: StrategyParameters): FtsChartNode[] {
  return [
  {
    id: 'crit_sales_growth',
    zone: 'F',
    parent: 'f_root',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: `شاخص ۱: رشد فروش ماهانه (${toFaDigits(params.minMonthlySalesGrowthPct)}٪+)`,
    fullTitle: 'شاخص ۱: رشد فروش ماهانه کدال نسبت به دوره سال قبل',
    page: 'چارت صفحه ۱',
    description: 'گزارش فعالیت ماهانه در سامانه کدال؛ رشد فروش تجمیعی نسبت به دوره مشابه سال قبل.',
    ruleFormula: `فروش ماهانه کدال >= ${params.minMonthlySalesGrowthPct}٪ رشد سالانه`,
    badge: 'شاخص ۱ · بلاکر',
    color: '#10b981',
    refs: [],
    editableParamKeys: ['minMonthlySalesGrowthPct'],
  },
  {
    id: 'crit_3y_eps',
    zone: 'F',
    parent: 'f_root',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: 'شاخص ۲: سودآوری مستمر ۳ ساله',
    fullTitle: 'شاخص ۲: سود خالص مثبت در ۳ سال گذشته بدون زیان',
    page: 'چارت صفحه ۱',
    description: 'روند EPS شرکت در ۳ سال مالی گذشته صعودی و بدون سابقه زیان انباشته ماده ۱۴۱ باشد.',
    ruleFormula: 'EPS سال ۱ < سال ۲ < سال ۳ | سوددهی مستمر',
    badge: 'شاخص ۲ · بلاکر',
    color: '#10b981',
    refs: [],
  },
  {
    id: 'crit_gross_margin',
    zone: 'F',
    parent: 'f_root',
    order: 3,
    origin: 'chart',
    kind: 'leaf',
    label: 'شاخص ۳: حاشیه سود ناخالص',
    fullTitle: 'شاخص ۳: حاشیه سود ناخالص شرکت بالای ۲۰٪ (سوپر ۳۰٪)',
    page: 'چارت صفحه ۱',
    description: `نسبت سود ناخالص به درآمد فروش شرکت حداقل ${toFaDigits(params.minGrossMarginPct)}٪ باشد تا در برابر تورم و تکانه‌های هزینه مصون بماند.`,
    ruleFormula: `(درآمد فروش - بهای تمام‌شده) / فروش >= ${params.minGrossMarginPct}٪`,
    badge: 'شاخص ۳ · بلاکر',
    color: '#10b981',
    refs: [],
    editableParamKeys: ['minGrossMarginPct'],
  },
  {
    id: 'crit_ps_ratio',
    zone: 'F',
    parent: 'f_root',
    order: 4,
    origin: 'chart',
    kind: 'leaf',
    label: 'شاخص ۴: فروش÷ارزش ≥ ۰٫۳۳',
    fullTitle: 'شاخص ۴: تخمین فروش دوازده‌ماهه تقسیم بر ارزش بازار',
    page: 'چارت صفحه ۱',
    description: 'حکم ۴: قاعده «تخمین فروش ۱۲ ماهه ÷ ارزش بازار» است، نه نسبتِ معکوسش. «فروش ۳ ماهه × ۴» فقط مثالِ همان گزارشِ خرداد بود؛ تعمیمِ درست `تجمیعی × ۱۲ ÷ ماهِ گزارش` (فروردین ×۱۲، خرداد ×۴، شهریور ×۲). کفِ قبولی ۰٫۳۳ و حالتِ ایده‌آل ۱٫۰ — همان دو عددی که موتور در `sales_to_mcap_min` می‌سنجد.',
    ruleFormula: '(فروش تجمیعی × ۱۲ ÷ م) / ارزش روز بازار >= ۰٫۳۳ | ایده‌آل ۱٫۰',
    badge: 'شاخص ۴ · تعدیل‌گر',
    color: '#06b6d4',
    refs: [],
  },
  {
    id: 'crit_pricing_regime',
    zone: 'F',
    parent: 'f_root',
    order: 5,
    origin: 'chart',
    kind: 'leaf',
    label: 'شاخص ۵: نوع نرخ‌گذاری',
    fullTitle: 'شاخص ۵: حجم انبار و نوع نرخ‌گذاری — دستوری نباشد',
    page: 'چارت صفحه ۱',
    description: 'شاخص ۵: چشم‌انداز خوب (دارویی، غذایی، سیمانی، فلزات، پتروشیمی، کانی‌فلزی، کاشی، شیشه) + نرخ‌گذاری دلاری/ریالی، جهانی؛ نوع نرخ‌گذاری دستوری نباشد.',
    ruleFormula: 'نوع نرخ‌گذاری ≠ دستوری | آزاد / بورس‌کالا ✓ — دستوری ✗',
    badge: 'شاخص ۵ · تعدیل‌گر',
    color: '#a855f7',
    refs: [],
  },
  {
    id: 'fund_super',
    zone: 'F',
    parent: 'f_tiers',
    order: 1,
    origin: 'program',
    kind: 'leaf',
    label: `💎 سوپربنیادی (رشد > ${toFaDigits(params.minMonthlySalesGrowthPct)}٪)`,
    fullTitle: 'نماد سوپربنیادی شاخص‌ساز (امتیاز ۵ از ۵ FTS)',
    page: 'چارت صفحه ۱',
    description: 'رشد فروش ماهانه کدال بیش از ۴۰٪، سودآوری ۳ سالهٔ متوالی، حاشیه سود بالای ۳۰٪ (کف ۲۰٪)، چشم‌انداز خوب (دارویی، غذایی، سیمانی، فلزات، پتروشیمی، کانی‌فلزی، کاشی، شیشه)، نرخ‌گذاری دلاری/ریالی و فاقد نرخ دستوری.',
    ruleFormula: `رشد فروش > ${params.minMonthlySalesGrowthPct}٪ | EPS ۳ ساله | حاشیه > ۳۰٪ | بدون نرخ دستوری`,
    badge: '۵ از ۵ FTS',
    color: '#22c55e',
    refs: [],
    editableParamKeys: ['minMonthlySalesGrowthPct', 'excludePriceControlled'],
  },
  {
    id: 'fund_good',
    zone: 'F',
    parent: 'f_tiers',
    order: 2,
    origin: 'program',
    kind: 'leaf',
    label: `بنیادی مطلوب (حاشیه > ${toFaDigits(params.minGrossMarginPct)}٪)`,
    fullTitle: 'بنیادی مطلوب با تایید ورود روندی (۴ از ۵)',
    page: 'چارت صفحه ۱',
    description: `رشد فروش ماهانه و سودآوری ۳ ساله، حاشیه سود ناخالص بالای ${toFaDigits(params.minGrossMarginPct)}٪؛ مناسب سرمایه‌گذاری روندی بالای ۳ ماه.`,
    ruleFormula: `حاشیه سود ناخالص > ${params.minGrossMarginPct}٪ + فروش صعودی در کدال`,
    badge: 'تایید روندی',
    color: '#10b981',
    refs: [],
    editableParamKeys: ['minGrossMarginPct', 'minFundScore'],
  },
  {
    id: 'fund_medium',
    zone: 'F',
    parent: 'f_tiers',
    order: 3,
    origin: 'program',
    kind: 'leaf',
    label: 'بنیادی متوسط (فقط نوسانی)',
    fullTitle: 'بنیادی متوسط؛ صرفاً مجاز برای نوسان‌گیری کوتاه‌مدت (۳ از ۵)',
    page: 'چارت صفحه ۱',
    description: 'فاقد ۳ سال سود پیاپی اما بدون زیان انباشته؛ طبق چارت صفحه ۱ فقط و فقط مجاز برای نوسان‌گیری با ستاپ جت.',
    ruleFormula: 'امتیاز ۳ از ۵ | ورود روندی بلندمدت اکیداً ممنوع',
    badge: 'صرفاً نوسان‌گیر',
    color: '#eab308',
    refs: [],
    editableParamKeys: ['minFundScore'],
  },
  {
    id: 'fund_weak',
    zone: 'F',
    parent: 'f_tiers',
    order: 4,
    origin: 'program',
    kind: 'leaf',
    label: '⛔ رد صلب بنیادی (وتوی قطعی)',
    fullTitle: 'رد بنیادی (صنایع قیمت دستوری خودرو یا حاشیه زیر ۲۰٪)',
    page: 'چارت صفحه ۱',
    description: 'صنایع مشمول قیمت‌گذاری دستوری شدید نظیر خودرو و قطعات، شرکت‌های زیان‌ده ماده ۱۴۱؛ خرید اکیداً ممنوع و وتو است.',
    ruleFormula: 'حاشیه سود < ۲۰٪ یا نرخ دستوری شدید ➔ وتوی کامل',
    badge: 'توقف ورود',
    color: '#ef4444',
    refs: [],
    editableParamKeys: ['excludePriceControlled', 'minGrossMarginPct'],
  },
  {
    id: 'm_principles',
    zone: 'M',
    parent: 'm_fit',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🧺 اصول پورتفوی بهینه',
    fullTitle: 'اصول یک پورتفوی بهینه بورسی',
    page: 'چارت صفحه ۴',
    description: 'سهام دلاری (سیمانی، فلزی، پتروشیمی، پالایشی، بانکی) و ریالی (غذایی، رایانه، لاستیک، حمل‌ونقل، بیمه)؛ شرکت‌های بزرگ (فملی و وبملت) و کوچک (سپیدار)؛ تولیدی و غیرتولیدی؛ صندوق‌های سرمایه‌گذاری؛ تناسب دیدگاه سرمایه‌گذاری با بورس ایران.',
    ruleFormula: 'دلاری/ریالی · بزرگ/کوچک · تولیدی/غیرتولیدی · صندوق‌ها',
    badge: 'چیدمان سبد',
    color: '#a855f7',
    refs: [],
  },
  {
    id: 'tech_weekly_hourglass',
    zone: 'M',
    parent: 'm_ladder',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: `⏳ اشباع کف هفتگی (RSI(۵) < ${toFaDigits(params.hourglassWeeklyRsi)})`,
    fullTitle: 'اشباع فروش عمیق در کف تاریخی هفتگی (استراتژی ساعت شنی)',
    page: 'صفحه ۲ و ۴',
    description: `قیمت در تایم هفتگی زیر MA-52 و RSIِ پنج‌رفته زیر ${toFaDigits(params.hourglassWeeklyRsi)} (ناحیه اشباع فروش)؛ فرصت طلایی خرید سنگین پله‌ای به افق ۳ تا ۱۰ سال.`,
    ruleFormula: `هفتگی زیر MA=52 + RSI(دوره ${toFaDigits(5)}) <= ${params.hourglassWeeklyRsi}`,
    badge: 'اهرم کف تاریخ',
    color: '#eab308',
    refs: ['m_strategy'],
    editableParamKeys: ['hourglassWeeklyRsi', 'hourglassLeverageMultiplier'],
  },
  {
    id: 'stop_hourglass',
    zone: 'M',
    parent: 'm_ladder',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: `⏳ اهرم ساعت شنی (${toFaDigits(params.hourglassLeverageMultiplier)}× پله کف)`,
    fullTitle: 'پله‌بندی سنگین اهرمی در کف تاریخی به افق ۳ تا ۱۰ سال',
    page: 'چارت صفحه ۴',
    description: `در اشباع کف تاریخی، حجم پله ${toFaDigits(params.hourglassLeverageMultiplier)} برابر حجم عادی افزایش می‌یابد؛ بدون حد ضرر کوتاه‌مدت.`,
    ruleFormula: `ضریب حجم ورود: ${params.hourglassLeverageMultiplier}× پله عادی | افق ۳ تا ۱۰ ساله`,
    badge: 'اهرم بلندمدت',
    color: '#eab308',
    refs: ['m_strategy'],
    editableParamKeys: ['hourglassLeverageMultiplier', 'hourglassWeeklyRsi'],
  },
  {
    id: 'exit_half',
    zone: 'M',
    parent: 'm_ladder',
    order: 3,
    origin: 'program',
    kind: 'leaf',
    label: `💰 فروش ${toFaDigits(params.exitHalfPct)}٪ در اولین سقف`,
    fullTitle: 'سیگنال فروش: اولین سقف تشکیل شد — اصل پول نگه داشته می‌شود',
    page: 'چارت صفحه ۲ و ۴',
    description: `جزوه فهرستِ «سیگنال فروش ٪۵۰» را می‌نویسد: «۱/ اولین سقف تشکیل شد … ۴/ سقف سوم (نمی‌تواند بالاتر بسازد)» و قاعده‌اش: «سود لایه لایه برویم و اصل پول را نگه داریم». ${toFaDigits(params.exitHalfPct)}٪ دستِ شماست؛ با نقدشدنِ همین لایه ریسکِ باقی‌مانده صفر می‌شود.`,
    ruleFormula: `اولین سقف ➔ فروش ${toFaDigits(params.exitHalfPct)}٪ و نگاه‌داشتنِ اصل پول`,
    badge: 'خروج اصل پول',
    color: '#38bdf8',
    refs: [],
    editableParamKeys: ['exitHalfPct'],
  },
  {
    id: 'rule_max_portfolio',
    zone: 'M',
    parent: 'm_money',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🏛️ سقف دارایی بورس',
    fullTitle: 'قانون طلایی سبد دارایی: سقف بورس در شرایط عادی و جنگی',
    page: 'صفحه ۴ جزوه',
    description: `حکم ۸: سقفِ ورودِ کلِ دارایی به بازارِ سرمایه در شرایط عادی ${toFaDigits(params.maxTotalPortfolioCapPct)}٪ است (تئوریِ جزوه ۷۰٪) و در شرایط جنگی ${toFaDigits(params.warConditionCapPct)}٪ ±۱۰٪. باقیِ دارایی طلا و درآمد ثابت است؛ عددِ جداگانه‌ای برایش در جزوه نیامده.`,
    ruleFormula: `سهام عادی <= ${params.maxTotalPortfolioCapPct}٪ کل دارایی | شرایط جنگی <= ${params.warConditionCapPct}٪`,
    badge: 'قانون سبد',
    color: '#f59e0b',
    refs: [],
    editableParamKeys: ['maxTotalPortfolioCapPct', 'warConditionCapPct'],
  },
  {
    id: 'm_weighting',
    zone: 'M',
    parent: 'm_money',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '⚖️ وزن سبد و حداکثر ضرر',
    fullTitle: 'تعیین وزن سبد سهام با احتساب حداکثر ضرر ۲۰٪±۱۰٪',
    page: 'چارت صفحه ۴',
    description: 'تعیین وزن سبد سهام با احتساب حداکثر ضرر ۲۰٪ ± ۱۰٪.',
    ruleFormula: 'وزن سبد با سقف ضرر ۲۰٪±۱۰٪',
    badge: 'وزن سبد',
    color: '#f59e0b',
    refs: [],
  },
  {
    id: 'hedge_options_etf',
    zone: 'M',
    parent: 'm_money',
    order: 3,
    origin: 'chart',
    kind: 'leaf',
    label: '🛡️ صندوق‌ها و پوشش ریسک',
    fullTitle: 'پوشش ریسک سیستماتیک با صندوق طلای ETF و اختیار معامله',
    page: 'صفحه ۴ جزوه',
    description: 'صندوق‌های ETF طلا، اهرمی، ملکی، نقره و درآمد ثابت و فراصندوق‌هایی مثل خوشه یا تمشک؛ پوشش ریسک سبد با ابزارهای مشتقه (آپشن).',
    ruleFormula: 'سبد هج‌شده: سهام برگزیده + طلا + درآمد ثابت + بیمه سهام (Option)',
    badge: 'پوشش ریسک',
    color: '#06b6d4',
    refs: [],
  },
  {
    id: 'm_ladder',
    zone: 'M',
    parent: 'm_money',
    order: 4,
    origin: 'chart',
    kind: 'leaf',
    label: '🪜 ورود و خروج پله‌ای + ابزار کمکی',
    fullTitle: 'ورود و خروج پله‌ای و ابزارهای کمکی (RSI=۷ · MA=۱۰۰ · MA=۵۲)',
    page: 'چارت صفحه ۴',
    description: 'ورود و خروج پله‌ای + ابزار کمکی: RSI=۷ سهام بنیادی و تایم هفتگی (ناحیه اشباع فروش)؛ تایم روزانه MA=۱۰۰؛ تایم هفتگی MA=۵۲.',
    ruleFormula: 'پله‌ای · RSI=۷ (هفتگی) · MA=۱۰۰ (روزانه) · MA=۵۲ (هفتگی)',
    badge: 'ابزار کمکی',
    color: '#06b6d4',
    refs: [],
  },
  {
    id: 'rule_cap',
    zone: 'M',
    parent: 'm_money',
    order: 5,
    origin: 'program',
    kind: 'leaf',
    label: `📊 سقف وزن صنعت (${toFaDigits(params.maxIndustryWeightPct)}٪)`,
    fullTitle: 'سقف سرمایه‌گذاری مجاز در یک صنعت و تک‌سهم',
    page: 'چارت صفحه ۴',
    description: `مجموع وزن تمام نمادهای یک صنعت نباید از ${toFaDigits(params.maxIndustryWeightPct)}٪ کل سبد و تک‌سهم نوسانی از ${toFaDigits(params.singleStockMaxWeightPct)}٪ تجاوز کند.`,
    ruleFormula: `سقف صنعت <= ${params.maxIndustryWeightPct}٪ | سقف تک‌سهم نوسانی <= ${params.singleStockMaxWeightPct}٪`,
    badge: 'سقف صنعت',
    color: '#10b981',
    refs: [],
    editableParamKeys: ['maxIndustryWeightPct', 'singleStockMaxWeightPct'],
  },
  {
    id: 'rule_rr',
    zone: 'M',
    parent: 'm_money',
    order: 6,
    origin: 'program',
    kind: 'leaf',
    label: `⚖️ R/R کم ➔ ریسک بالا`,
    fullTitle: 'کم بودنِ R/R دلیلِ بی‌طلبیِ سهم است؛ آستانه دستِ شما',
    page: 'چارت صفحه ۴',
    description: `جزوه R/R را یک‌جا و به‌عنوانِ دلیلِ عدم ورود می‌آورد: «دلیلِ طلبِ سهم R/R کم است، ریسک بالاست». عددی برای آن نگفته؛ ${toFaDigits(params.minRiskRewardRatio)} برابر دستِ شماست: فاصله تا تارگت باید از فاصله تا حد ضرر بیشتر باشد.`,
    ruleFormula: `(تارگت سود - ورود) / (ورود - حد ضرر) >= ${toFaDigits(params.minRiskRewardRatio)}`,
    badge: 'ریسک به ریوارد',
    color: '#a855f7',
    refs: [],
    editableParamKeys: ['minRiskRewardRatio'],
  },
  {
    id: 'm_review',
    zone: 'M',
    parent: 'm_monitor',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🔍 رصد مداوم پورتفو',
    fullTitle: 'رصد و تحلیل مداوم پورتفوی بورسی',
    page: 'چارت صفحه ۴',
    description: 'هر ماه در کدال گزارش فروش، هر فصل صورت مالی، هر سال صورت مالی سالانه و مقایسه با سال قبل.',
    ruleFormula: 'ماهانه: گزارش فروش · فصلی: صورت مالی · سالانه: صورت مالی + مقایسه',
    badge: 'پایش دوره‌ای',
    color: '#10b981',
    refs: [],
  },
  {
    id: 'stop_swing',
    zone: 'M',
    parent: 'm_stop_kind',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🛑 حد ضرر نوسان‌گیر',
    fullTitle: 'حد ضرر صلب نوسان‌گیر (استاپ تکنیکالی کوتاه‌مدت)',
    page: 'چارت صفحه ۴',
    description: `شخص نوسان‌گیر: تشکیل یک کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)}؛ حد ضرر عمومی ۵٪ زیر آخرین کف روند صعودی؛ خرید پله‌ای (معاملات ۲±۱ ماه).`,
    ruleFormula: `کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)} یا افت ۵٪ زیر آخرین کف روند صعودی ➔ خروج قطعی`,
    badge: 'استاپ تکنیکالی',
    color: '#ef4444',
    refs: ['t_stop'],
    editableParamKeys: ['stopLossMaPeriod', 'stopLossFixedPct'],
  },
  {
    id: 'stop_trend',
    zone: 'M',
    parent: 'm_stop_kind',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '🛡️ حد ضرر بنیادی روندگیر (کدال)',
    fullTitle: 'حد ضرر بنیادی روندگیر در گزارش‌های مالی کدال',
    page: 'چارت صفحه ۴',
    description: 'شخص روندگیر: سرمایه‌گذاری بالای ۳ ماه، خرید پله‌ای دارد و حد ضرر تکنیکالی ندارد؛ حد ضرر آن بنیادی است — رصد گزارش فروش ماهانه و صورت‌های مالی فصلی/سالانه.',
    ruleFormula: `افت حاشیه سود < ${params.minGrossMarginPct}٪ یا توقف رشد فروش در کدال ➔ تعویض سهم`,
    badge: 'استاپ کدالی',
    color: '#22c55e',
    refs: ['t_stop'],
    editableParamKeys: ['minGrossMarginPct', 'minMonthlySalesGrowthPct'],
  },
  {
    id: 'tape_market_liquidity',
    zone: 'S',
    parent: 's_arena',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: `🏛️ ارزش معاملات بازار سهام (>${toFaDigits(params.marketLiquidityMinHemmat)} همت)`,
    fullTitle: 'فیلتر رونق نقدینگی کل بازار خرد',
    page: 'صفحه ۳ و ۴',
    description: `بررسی وضعیت بازار در TRADERS ARENA: ارزش معاملات بازار سهام بالای ${toFaDigits(params.marketLiquidityMinHemmat)} همت ⇒ بازار مساعد؛ زیر ۱۰ همت ⇒ نامساعد.`,
    ruleFormula: `ارزش معاملات خرد روز >= ${params.marketLiquidityMinHemmat} همت ➔ مساعد · زیر ${toFaDigits(10)} همت ➔ نامساعد`,
    badge: 'نقدینگی کل',
    color: '#f59e0b',
    refs: [],
    editableParamKeys: ['marketLiquidityMinHemmat'],
  },
  {
    id: 'tape_breadth',
    zone: 'S',
    parent: 's_arena',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '🧮 سهام مثبت و منفی (صف فروش)',
    fullTitle: 'بررسی تعداد و درصد سهام مثبت و منفی بازار',
    page: 'چارت صفحه ۳',
    description: 'بررسی تعداد و درصد سهام مثبت و منفی (صف فروش)؛ زمانیکه ۸۰٪ بازار منفی است، هنوز فرصت ورود وجود دارد.',
    ruleFormula: 'تعداد و درصد مثبت/منفی + پایش صف‌های فروش | ۸۰٪ منفی = فرصت ورود',
    badge: 'نبض کلی بازار',
    color: '#f59e0b',
    refs: [],
  },
  {
    id: 'tape_final_filters',
    zone: 'S',
    parent: 's_dry',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🧲 فیلترهای نهایی (خشک کردن)',
    fullTitle: 'فیلترهای نهایی نوسان‌گیر و روندگیر',
    page: 'چارت صفحه ۳',
    description: 'نوسان‌گیر: ساعت (عدد ۱ را می‌توان به ۳ یا ۵ تغییر داد؛ TVOL>۱)، جت، حجم مشکوک — روندگیر: کف‌روبی، نقطه‌زنی.',
    ruleFormula: 'نوسان‌گیر: ساعت/جت/حجم مشکوک · روندگیر: کف‌روبی/نقطه‌زنی',
    badge: 'فیلتر نهایی',
    color: '#eab308',
    refs: ['tape_clock', 'setup_jet', 'tape_volume', 'tape_floor_sweep'],
  },
  {
    id: 'setup_point_hunt',
    zone: 'S',
    parent: 's_dry',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '🎯 شکار نقطه حمایت (کف ۳ یا ۵)',
    fullTitle: 'نقطه‌زنی در کف سوم یا پنجم کانال صعودی',
    page: 'چارت صفحه ۲ و ۳',
    description: 'واکنش دقیق قیمت به کف سوم یا پنجم کانال یا خط روند صعودی همزمان با تاییدیه کندل بازگشتی و کاهش عرضه.',
    ruleFormula: 'برخورد به کف کانال صعودی + کندل چکشی و پایان فشار فروش',
    badge: 'نقطه‌زنی کف',
    color: '#f59e0b',
    refs: ['m_strategy'],
  },
  {
    id: 'tape_industries_picks',
    zone: 'S',
    parent: 's_industries',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🏭 صنایع و سهام برگزیده',
    fullTitle: 'بررسی صنایع و گزینش سهام برگزیده',
    page: 'چارت صفحه ۳',
    description: 'بررسی صنایع: خلاصه معاملات صنایع بورس؛ سهام برگزیده: «درصد آخرین» و «ورود پول» را از بالا به پایین مرتب می‌کنیم.',
    ruleFormula: 'خلاصه معاملات صنایع + مرتب‌سازی برگزیده‌ها (درصد آخرین، ورود پول)',
    badge: 'انتخاب صنعت',
    color: '#10b981',
    refs: [],
  },
  {
    id: 'tape_flow_charts',
    zone: 'S',
    parent: 's_liquidity',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '📉 نمودارهای جریان نقدینگی',
    fullTitle: 'پایش تصویری جریان نقدینگی بازار',
    page: 'چارت صفحه ۳',
    description: 'نمودار ارزش سفارش‌های خرید و فروش؛ نمودار نمادهای مثبت و منفی؛ نمودار سرانه خرید و فروش معاملات خرد بازار؛ نمودار تعداد صف‌های خرید و فروش.',
    ruleFormula: 'ارزش سفارش‌ها · نمادهای مثبت/منفی · سرانه معاملات خرد · تعداد صف‌ها',
    badge: 'پایش تصویری',
    color: '#06b6d4',
    refs: [],
  },
  {
    id: 'tape_smart_money',
    zone: 'S',
    parent: 's_liquidity',
    order: 3,
    origin: 'chart',
    kind: 'leaf',
    label: '💳 ورود پول از درآمد ثابت به سهم',
    fullTitle: 'خروج نقدینگی از صندوق‌های فیکس و تزریق به سهام',
    page: 'چارت صفحه ۳',
    description: 'جریان نقدینگی منفی در صندوق‌های درآمد ثابت همزمان با سرانه خرید پرقدرت در سهام برگزیده.',
    ruleFormula: 'خروج نقدینگی از فیکس ➔ تزریق مستقیم به لیدرهای صنعت',
    badge: 'جریان نقدینگی',
    color: '#10b981',
    refs: [],
  },
  {
    id: 'tape_clock',
    zone: 'S',
    parent: 's_patterns_swing',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: `⏰ الگوی ساعت (${toFaDigits(params.clockPriceDiffPct)}٪+)`,
    fullTitle: 'الگوی ساعت FTS: اختلاف قیمت آخرین از پایانی',
    page: 'چارت صفحه ۳',
    description: `قیمت آخرین معامله بیش از ${toFaDigits(params.clockPriceDiffPct)}٪ بالاتر از قیمت پایانی؛ ایده‌آل: پایانی منفی و آخرین مثبت؛ هرچه اختلاف بیشتر، الگو قوی‌تر — در TRADER ARENA ستون «اختلاف آخرین و پایانی» را از زیاد به کم مرتب می‌کنیم.`,
    ruleFormula: `(آخرین - پایانی) / پایانی >= ${params.clockPriceDiffPct}٪ ${params.clockStrictNegativeClose ? '+ شرط پایانی منفی' : ''}`,
    badge: 'زمان‌سنج ورود',
    color: '#22c55e',
    refs: ['m_reverse_tape'],
    editableParamKeys: ['clockPriceDiffPct', 'clockStrictNegativeClose'],
  },
  {
    id: 'tape_breakout',
    zone: 'S',
    parent: 's_patterns_swing',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '📦 خروج از باکس رنج',
    fullTitle: 'شکست سقف کانال تراکم قیمت در تابلو',
    page: 'چارت صفحه ۳',
    description: 'در انتهای محدودهٔ رنج، رشد حجم معاملات و شکست باکس با یک کندل قوی به سمت بالا و ورود پول و الگوی ساعت؛ هرچه زمان باکس بیشتر باشد، حرکت صعودی قوی‌تر است.',
    ruleFormula: 'رشد حجم معاملات + شکست باکس با کندل قوی + ورود پول + الگوی ساعت',
    badge: 'آغاز شتاب',
    color: '#38bdf8',
    refs: [],
  },
  {
    id: 'tape_floor_sweep',
    zone: 'S',
    parent: 's_patterns_trend',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🧹 کف‌روبی و جمع‌آوری صف',
    fullTitle: 'بلعیدن صف فروش و خشک کردن عرضه در کف',
    page: 'چارت صفحه ۳',
    description: 'سهم صف فروش است ولی اوردرهای قوی در حال خرید است و سهم را جمع می‌کند؛ خشک کردن عرضه.',
    ruleFormula: 'جمع‌آوری صف فروش با اردر سنگین در کف + پایان فشار عرضه',
    badge: 'کف‌روبی صف',
    color: '#a855f7',
    refs: ['m_reverse_tape'],
  },
  {
    id: 'tape_volume',
    zone: 'S',
    parent: 's_volume_swing',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: `🌊 حجم مشکوک (${toFaDigits(params.minVolumeRatio)}×)`,
    fullTitle: 'حجم مشکوک معاملات و ورود پول هوشمند',
    page: 'چارت صفحه ۳',
    description: `بررسی حجم مشکوک: سه برابر میانگین ماهانه — volume, MA length=۲۱.`,
    ruleFormula: `حجم روز ≥ ${params.minVolumeRatio} × میانگین ماهانه (MA=۲۱)`,
    badge: 'پول هوشمند',
    color: '#06b6d4',
    refs: ['m_reverse_tape'],
    editableParamKeys: ['minVolumeRatio'],
  },
  {
    id: 'tape_volume_trend',
    zone: 'S',
    parent: 's_volume_trend',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '📦 حجم معاملات روندگیر',
    fullTitle: 'حجم معاملات در سبک روندگیری',
    page: 'چارت صفحه ۳',
    description: 'روندگیر: بررسی حجم معاملات و ورود در قیمت ارزنده.',
    ruleFormula: 'حجم معاملات + ورود در قیمت ارزنده',
    badge: 'ورود ارزشی',
    color: '#a855f7',
    refs: [],
  },
  {
    id: 'tech_weekly_reject',
    zone: 'T',
    parent: 't_buy',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '⛔ ریجکت هفتگی (وتوی قطعی)',
    fullTitle: 'ریجکت صلب در صورت روند هفتگی نزولی یا رنج',
    page: 'چارت صفحه ۲',
    description: 'تایم هفتگی نزولی ⇒ رد؛ تایم هفتگی خنثی ⇒ رد — ورود به سهم ممنوع است.',
    ruleFormula: 'هفتگی نزولی / رنج ➔ وتوی صلب کلیه ستاپ‌های روزانه',
    badge: 'وتوی قطعی',
    color: '#ef4444',
    refs: [],
  },
  {
    id: 'tech_weekly_up',
    zone: 'T',
    parent: 't_buy',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '📈 تایم هفتگی صعودی',
    fullTitle: 'تاییدیه روند هفتگی (شرط لازم ورود FTS)',
    page: 'چارت صفحه ۲',
    description: 'تایم هفتگی روند صعودی؛ فقط در این حالت بررسی ستاپ‌های تایم روزانه مجاز است.',
    ruleFormula: 'تایم هفتگی صعودی = صدور مجوز جستجوی ستاپ روزانه',
    badge: 'مجوز ورود',
    color: '#22c55e',
    refs: [],
  },
  {
    id: 'setup_fib',
    zone: 'T',
    parent: 't_daily_down',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '📐 ستاپ فیبوناچی',
    fullTitle: 'پله‌های اصلاحی فیبوناچی در موج صعودی',
    page: 'چارت صفحه ۲',
    description: `چارتِ FTS فقط دو زون دارد: ۳۳ تا ۴۰٪ و ۶۱.۸ تا ۷۰٪ (به‌علاوهٔ مبنای ۱۰۰) — نه خطوطِ کلاسیکِ ۳۸.۲ و ۵۰. پلهٔ اول روی ${toFaDigits(params.fibStep1Level)}٪ و پلهٔ دوم روی ${toFaDigits(params.fibStep2Level)}٪ از موجِ صعودی انتخاب می‌شود.`,
    ruleFormula: `پله ۱: زون ۳۳–۴۰٪ (انتخابِ ${params.fibStep1Level}٪) | پله ۲: زون ۶۱.۸–۷۰٪ (انتخابِ ${params.fibStep2Level}٪)`,
    badge: 'پله‌های اصلاح',
    color: '#38bdf8',
    refs: [],
    editableParamKeys: ['fibStep1Level', 'fibStep2Level'],
  },
  {
    id: 'setup_choch',
    zone: 'T',
    parent: 't_daily_down',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '🔄 تغییر ساختار CHoCH',
    fullTitle: 'ستاپ بازگشتی تغییر ساختار یا شکست خط گردن',
    page: 'چارت صفحه ۲',
    description: 'شکست آخرین سقف در روند نزولی یا شکست آخرین کف در روند صعودی؛ سقف دوقلو و سر و شانه نیز مشابه CHoCH داوری می‌شوند.',
    ruleFormula: 'شکست آخرین سقف در نزولی / شکست آخرین کف در صعودی ➔ CHoCH',
    badge: 'الگوی بازگشتی',
    color: '#a855f7',
    refs: [],
  },
  {
    id: 'setup_last_low',
    zone: 'T',
    parent: 't_daily_neutral',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '📍 ورود در آخرین کف یا سقف',
    fullTitle: 'ورود در آخرین کف روند صعودی یا آخرین سقف روند نزولی',
    page: 'چارت صفحه ۲',
    description: 'تایم روزانهٔ خنثی: ورود در آخرین کف روند صعودی یا آخرین سقف روند نزولی.',
    ruleFormula: 'روزانه خنثی ➔ ورود در آخرین کف/سقف روند',
    badge: 'ورود خنثی',
    color: '#22c55e',
    refs: [],
  },
  {
    id: 'setup_pullback',
    zone: 'T',
    parent: 't_daily_up',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '↩️ ستاپ پولبک و بازآزمایی',
    fullTitle: 'پولبک آرام به سطح شکسته شده با حجم پایین',
    page: 'چارت صفحه ۲',
    description: 'استراتژی پولبک؛ یکی از دو ستاپ مجاز تایم روزانهٔ صعودی.',
    ruleFormula: 'تایم روزانه صعودی ➔ ستاپ پولبک',
    badge: 'تاییدیه پولبک',
    color: '#10b981',
    refs: ['m_strategy'],
  },
  {
    id: 'setup_jet',
    zone: 'T',
    parent: 't_daily_up',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: `🚀 ستاپ جت (مهلت ورود ${toFaDigits(params.jetStabilizationDays)} روز)`,
    fullTitle: 'استراتژی پرتاب جت و شکست مقاومت استاتیک',
    page: 'چارت صفحه ۲',
    description: `بنیادی بودن + روند صعودیِ هفتگی و روزانه + شکستِ سطحِ استاتیک + کندلِ تثبیت. «${toFaDigits(params.jetStabilizationDays)} روز» تعدادِ روزهای تثبیت نیست، مهلتِ ورود است: بعد از شکست حداکثر تا ${toFaDigits(params.jetStabilizationDays)} روز روی تثبیت و پولبک مجاز به ورودی. (حکم ۱۷)`,
    ruleFormula: `بنیادی + هفتگی↑ و روزانه↑ + شکست استاتیک + کندل تثبیت | مهلت ورود <= ${params.jetStabilizationDays} روز`,
    badge: 'ستاپ پرتاب',
    color: '#06b6d4',
    refs: ['m_strategy'],
    editableParamKeys: ['jetStabilizationDays'],
  },
  {
    id: 'setup_double_bottom',
    zone: 'T',
    parent: 't_sell',
    order: 1,
    origin: 'chart',
    kind: 'leaf',
    label: '🔁 کف دوقلو',
    fullTitle: 'کف دوقلو — شکست آخرین سقف به سمت بالا',
    page: 'چارت صفحه ۲',
    description: 'کف دوقلو: زمانیکه آخرین سقف رو به بالا شکسته شود.',
    ruleFormula: 'شکست آخرین سقف به بالا (پس از کف دوقلو)',
    badge: 'ستاپ بازگشتی',
    color: '#38bdf8',
    refs: [],
  },
  {
    id: 'setup_double_top',
    zone: 'T',
    parent: 't_sell',
    order: 2,
    origin: 'chart',
    kind: 'leaf',
    label: '⛰️ سقف دوقلو و سر و شانه',
    fullTitle: 'سیگنال فروش: سقف دوقلو و سر و شانه (مشابه CHoCH)',
    page: 'چارت صفحه ۲',
    description: 'سقف دوقلو و سر و شانه — مشابه CHoCH؛ سیگنال فروش.',
    ruleFormula: 'سقف دوقلو / سر و شانه ➔ مشابه CHoCH',
    badge: 'سیگنال فروش',
    color: '#ef4444',
    refs: [],
  },
  {
    id: 'exit_third_peak',
    zone: 'T',
    parent: 't_sell',
    order: 3,
    origin: 'chart',
    kind: 'leaf',
    label: `🏔️ خروج در سقف سوم (${toFaDigits(params.thirdPeakWeeklyPct)}٪ و ${toFaDigits(params.thirdPeakDailyPct)}٪)`,
    fullTitle: 'خروج کامل در سقف سوم کانال صعودی طبق چارت صفحه ۴',
    page: 'چارت صفحه ۴',
    description: `برخورد قیمت به سقف سوم کانال صعودی یا خط روند ماژور با فاصله زیر ${toFaDigits(params.thirdPeakWeeklyPct)}٪ هفتگی و ${toFaDigits(params.thirdPeakDailyPct)}٪ روزانه؛ خروج کامل از سهم.`,
    ruleFormula: `فاصله تا خط روند هفتگی <= ${params.thirdPeakWeeklyPct}٪ یا روزانه <= ${params.thirdPeakDailyPct}٪ ➔ فروش ۱۰۰٪`,
    badge: 'خروج سقف ۳',
    color: '#f97316',
    refs: ['m_stop_kind'],
    editableParamKeys: ['thirdPeakWeeklyPct', 'thirdPeakDailyPct'],
  },
  {
    id: 'exit_rsi_div',
    zone: 'T',
    parent: 't_sell',
    order: 4,
    origin: 'chart',
    kind: 'leaf',
    label: '📉 واگرایی مقاومتی (RSI)',
    fullTitle: 'سیگنال اخطار واگرایی منفی قیمت و اندیکاتور RSI در سقف',
    page: 'چارت صفحه ۴',
    description: 'واگرایی مقاومتی: در نمودار سقف بالاتر، ولی در RSI سقف پایین‌تر.',
    ruleFormula: 'قیمت: سقف بالاتر (HH) | شاخص RSI: سقف پایین‌تر (LH) ➔ خروج قطعی',
    badge: 'واگرایی منفی',
    color: '#ef4444',
    refs: ['m_stop_kind'],
  },
  ];
}

/** تنها درختِ نقشه: یال‌هایِ parent→child درِ همان Zone. بی‌تأثیر از پرست و جهت. */
export function treeEdges(model: FtsChartNode[]): { id: string; source: string; target: string }[] {
  return model
    .filter((n) => n.parent)
    .map((n) => ({ id: 'tr_' + (n.parent as string) + '_' + n.id, source: n.parent as string, target: n.id }));
}

/** وابستگی‌هایِ بین‌صفحه‌ای که خودِ چارت اعلام می‌کند: ترتیبِ مهندسی معکوسِ صفحۀ ۴
 *  (۱ تابلو ۲ تکنیکال ۳ بنیادی) و داوریِ نهایی که به مدیریتِ سرمایه می‌رسد.
 *  ستون‌ها جایِ ثابت دارند؛ فقط `flow` جهتِ فلشِ همین سه رابطۀ ثابت را می‌خواند. */
export const ZONE_LINKS: { id: string; from: FtsZone; to: FtsZone }[] = [
  { id: 'zl_s_t', from: 'S', to: 'T' },
  { id: 'zl_t_f', from: 'T', to: 'F' },
  { id: 'zl_f_m', from: 'F', to: 'M' },
];

/** ترتیبِ ریل برایِ جهتِ انتخابی — همان چهار Zone، فقط با اولویتِ خواندن.
 *  توپولوژیِ درخت این عدد را نمی‌شناسد (`ZONE_LINKS` ثابت است). */
export function railOrder(flow: FlowDirection): FtsZone[] {
  return flow === 'reverse' ? ['S', 'T', 'F', 'M'] : ['F', 'T', 'S', 'M'];
}

/** پرست ⇒ گره‌هایِ روشن. این جدول عینِ `activeNodes` درِ `StrategyTreePage.tsx` است
 *  و تنها جایِ نگهداری‌اش به مدلِ داده منتقل شده (تکلیفِ پرست از خودِ برنامه).
 *
 *  چارت ۳ (S: SELECTION): روندگیر = کف‌روبی + نقطه‌زنی، و نقطه‌زنی
 *  «ورود در کف سوم یا پنجم» است (چارت ۴). گرهٔ setup_point_hunt درِ
 *  نقشه ساخته شده، پس اینجا هم باید باشد — وگرنه درختِ روندگیر همان
 *  گره‌ای را خاموش نشان می‌دهد که قیف برایش نماد می‌گیرد.
 *
 *  رأیِ مالک (بند ۸): سهامدارِ روندگیر در سهم بنیادی حد ضررِ قیمتی
 *  ندارد و با گزارشِ فصلی کدال خارج می‌شود — هیچ گره «خروج»ی برایش
 *  روشن نمی‌شود، و این خالی‌بودن عمدی است نه فراموشی.
 *
 *  ساعت شنی ستاپِ مستقل ندارد؛ خودِ همان اشباعِ هفتگی (MA=52 + RSI)
 *  در ستونِ هفتگی روشن می‌شود. */
export const PRESET_ACTIVE: Record<'swing' | 'trend' | 'hourglass', string[]> = {
  swing: ['fund_good', 'fund_medium', 'tech_weekly_up', 'setup_jet', 'setup_fib', 'tape_clock', 'tape_volume', 'stop_swing', 'exit_half'],
  trend: ['fund_super', 'fund_good', 'tech_weekly_up', 'setup_fib', 'setup_choch', 'setup_jet', 'setup_point_hunt', 'tape_floor_sweep', 'stop_trend'],
  hourglass: ['fund_super', 'tech_weekly_hourglass', 'tape_floor_sweep', 'tape_clock', 'stop_hourglass'],
};

/** پرست ⇒ گره‌هایِ روشن + جدّهایِ مسیرشان، تا ریل رویِ نقشه بُرش نداشته باشد. */
export function activeIdsForPreset(
  preset: FtsPreset,
  model: FtsChartModel,
  customIds: string[] = [],
): Set<string> {
  const base = preset === 'custom' ? customIds : PRESET_ACTIVE[preset];
  const set = new Set<string>();
  for (const id of base) {
    if (!model.byId.has(id)) continue;
    for (const a of ancestorsOf(model, id)) set.add(a);
  }
  return set;
}

export function buildFtsChartModel(params: StrategyParameters): FtsChartModel {
  const nodes: FtsChartNode[] = [...CHART_HEADS, ...chartLeaves(params)];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<string, string[]>();
  for (const n of nodes) {
    if (!n.parent) continue;
    const arr = childrenOf.get(n.parent);
    if (arr) arr.push(n.id);
    else childrenOf.set(n.parent, [n.id]);
  }
  childrenOf.forEach((arr) => arr.sort((a, b) => (byId.get(a)?.order ?? 0) - (byId.get(b)?.order ?? 0)));
  const roots = {} as Record<FtsZone, string>;
  const byZone = {} as Record<FtsZone, FtsChartNode[]>;
  for (const z of ZONES) {
    const root = nodes.find((n) => n.zone === z.key && !n.parent);
    roots[z.key] = root ? root.id : '';
    byZone[z.key] = nodes
      .filter((n) => n.zone === z.key)
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  }
  return { nodes, byId, childrenOf, roots, byZone };
}

/** همهٔ جدّهایِ یک گره، ریشه تا خودِ گره — برایِ «روشن‌شدنِ کل مسیر» درِ جست‌وجو. */
export function ancestorsOf(model: FtsChartModel, id: string): string[] {
  const out: string[] = [];
  let cur: string | null | undefined = id;
  while (cur) {
    out.push(cur);
    cur = model.byId.get(cur)?.parent;
  }
  return out;
}

/** همهٔ فرزندانِ یک گره (بی‌_ordered) — برایِ جمع‌کردنِ شاخه و جست‌وجو. */
export function descendantsOf(model: FtsChartModel, id: string): string[] {
  const out: string[] = [];
  const stack = [id];
  while (stack.length) {
    const k = stack.pop() as string;
    for (const c of model.childrenOf.get(k) ?? []) {
      out.push(c);
      stack.push(c);
    }
  }
  return out;
}

/** سازۀ «هم‌نام»ها: هر رابطۀ بین‌صفحه‌ای که گونۀ دومِ یک مفهوم است، خط‌چین می‌شود
 *  و هیچ‌وقت یالِ ساختاری. جهتِ تعریف رویِ نمایش اثر ندارد؛ نمایش از refs می‌آید. */
export interface FtsRefEdge {
  id: string;
  source: string;
  target: string;
  kind: 'ref';
}

export function refEdges(model: FtsChartModel): FtsRefEdge[] {
  const seen = new Set<string>();
  const out: FtsRefEdge[] = [];
  for (const n of model.nodes) {
    for (const r of n.refs) {
      if (!model.byId.has(r)) continue;
      const key = [n.id, r].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ id: 'rf_' + key.replace('|', '_'), source: n.id, target: r, kind: 'ref' });
    }
  }
  return out;
}

/** سازۀ یال‌ها برایِ مصرف‌کننده‌هایِ پیشین (`getGraphLinks` درِ کامپوننت).
 *  توپولوژیِ درخت ثابت است؛ `flow` فقط ترتیبِ ریل را تعیین می‌کند. */
export interface FtsCompatLink {
  id: string;
  source: string;
  target: string;
  presets: ('swing' | 'trend' | 'hourglass')[];
  flow: FlowDirection;
}

/** یال‌هایِ درختِ ثابتِ نقشه: [parent, child]. متنِ گره‌ها اینجا نمی‌آید تا
 *  سازۀ یال‌ها به `strategyParamsStore` وابسته نشود. */
const TREE_PAIRS: [string, string][] = [
  ['f_root', 'f_tiers'],
  ['t_root', 't_buy'],
  ['tech_weekly_up', 't_daily_up'],
  ['tech_weekly_up', 't_daily_down'],
  ['tech_weekly_up', 't_daily_neutral'],
  ['t_root', 't_sell'],
  ['t_root', 't_stop'],
  ['s_root', 's_style'],
  ['s_style', 's_style_swing'],
  ['s_style', 's_style_trend'],
  ['s_root', 's_liquidity'],
  ['s_liquidity', 's_arena'],
  ['s_root', 's_industries'],
  ['s_root', 's_volume'],
  ['s_volume', 's_volume_swing'],
  ['s_volume', 's_volume_trend'],
  ['s_root', 's_patterns'],
  ['s_patterns', 's_patterns_swing'],
  ['s_patterns', 's_patterns_trend'],
  ['s_root', 's_dry'],
  ['m_root', 'm_reverse'],
  ['m_reverse', 'm_reverse_tape'],
  ['m_reverse', 'm_reverse_tech'],
  ['m_reverse', 'm_reverse_fund'],
  ['m_root', 'm_money'],
  ['m_money', 'm_stop_kind'],
  ['m_root', 'm_monitor'],
  ['m_root', 'm_fit'],
  ['m_root', 'm_strategy'],
  ['f_root', 'crit_sales_growth'],
  ['f_root', 'crit_3y_eps'],
  ['f_root', 'crit_gross_margin'],
  ['f_root', 'crit_ps_ratio'],
  ['f_root', 'crit_pricing_regime'],
  ['f_tiers', 'fund_super'],
  ['f_tiers', 'fund_good'],
  ['f_tiers', 'fund_medium'],
  ['f_tiers', 'fund_weak'],
  ['t_buy', 'tech_weekly_reject'],
  ['t_buy', 'tech_weekly_up'],
  ['t_daily_up', 'setup_pullback'],
  ['t_daily_up', 'setup_jet'],
  ['t_daily_down', 'setup_fib'],
  ['t_daily_down', 'setup_choch'],
  ['t_daily_neutral', 'setup_last_low'],
  ['t_sell', 'setup_double_bottom'],
  ['t_sell', 'setup_double_top'],
  ['t_sell', 'exit_third_peak'],
  ['t_sell', 'exit_rsi_div'],
  ['s_arena', 'tape_market_liquidity'],
  ['s_arena', 'tape_breadth'],
  ['s_liquidity', 'tape_flow_charts'],
  ['s_liquidity', 'tape_smart_money'],
  ['s_industries', 'tape_industries_picks'],
  ['s_volume_swing', 'tape_volume'],
  ['s_volume_trend', 'tape_volume_trend'],
  ['s_patterns_swing', 'tape_clock'],
  ['s_patterns_swing', 'tape_breakout'],
  ['s_patterns_trend', 'tape_floor_sweep'],
  ['s_dry', 'tape_final_filters'],
  ['s_dry', 'setup_point_hunt'],
  ['m_money', 'rule_max_portfolio'],
  ['m_money', 'm_weighting'],
  ['m_money', 'hedge_options_etf'],
  ['m_stop_kind', 'stop_swing'],
  ['m_stop_kind', 'stop_trend'],
  ['m_money', 'm_ladder'],
  ['m_ladder', 'tech_weekly_hourglass'],
  ['m_ladder', 'stop_hourglass'],
  ['m_ladder', 'exit_half'],
  ['m_money', 'rule_cap'],
  ['m_money', 'rule_rr'],
  ['m_monitor', 'm_review'],
  ['m_fit', 'm_principles']
];

const CHILD_OF: Map<string, string[]> = (() => {
  const m = new Map<string, string[]>();
  for (const [p, c] of TREE_PAIRS) {
    const arr = m.get(p);
    if (arr) arr.push(c);
    else m.set(p, [c]);
  }
  return m;
})();

/** پرست‌هایِ یک گره: برگ‌ها از `PRESET_ACTIVE` و سرِ شاخه‌ها از uniteِ فرزندان. */
export function presetsOfNode(id: string): ('swing' | 'trend' | 'hourglass')[] {
  const direct = (Object.keys(PRESET_ACTIVE) as ('swing' | 'trend' | 'hourglass')[]).filter(
    (p) => PRESET_ACTIVE[p].includes(id),
  );
  if (direct.length) return direct;
  const kids = CHILD_OF.get(id);
  if (!kids || !kids.length) return [];
  const acc = new Set<string>();
  for (const k of kids) for (const p of presetsOfNode(k)) acc.add(p);
  return [...acc] as ('swing' | 'trend' | 'hourglass')[];
}

export function getGraphLinks(flow: FlowDirection): FtsCompatLink[] {
  const out: FtsCompatLink[] = TREE_PAIRS.map(([p, c]) => ({
    id: 'tr_' + p + '_' + c,
    source: p,
    target: c,
    presets: presetsOfNode(c),
    flow,
  }));
  // سه رابطۀ بین‌صفحه‌ای که خودِ چارت اعلام می‌کند (ترتیبِ مهندسی معکوسِ صفحۀ ۴).
  // سرِ این سه یال ریشۀ Zone است، نه یک گره؛ و جهتِ توپولوژی ثابت می‌ماند —
  // `flow` فقط فلشِ ریل را برعکس می‌کشد.
  const roots = zoneRoots();
  for (const zl of ZONE_LINKS) {
    out.push({
      id: zl.id,
      source: roots[zl.from],
      target: roots[zl.to],
      presets: ['swing', 'trend', 'hourglass'],
      flow,
    });
  }
  return out;
}

/** ریشۀ هر Zone — همان چهار صفحۀ چاپی، جایِ ثابت رویِ نقشه */
export function zoneRoots(): Record<FtsZone, string> {
  return { F: 'f_root', T: 't_root', S: 's_root', M: 'm_root' };
}
