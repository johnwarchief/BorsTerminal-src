// features/master/lib/strategyGraphModel.ts
// مدل گراف کانونی نقشه راه استراتژی FTS (Canonical FTS Roadmap Graph Model)
// استخراج‌شده مو‌به‌مو از چارت ۴ صفحه‌ای FTS و جزوه عرفان نصرتی:
//   صفحه ۳: S — تابلوخوانی و انتخاب (Selection)
//   صفحه ۲: T — تکنیکال دو زمانه (Technical)
//   صفحه ۱: F — بنیادی ۵ شاخصه کدال (Fundamental)
//   صفحه ۴: تحویل (Delivery)، مدیریت سرمایه و استراتژی‌های ورود (Capital & Entry Strategies)

import { toFaDigits } from '@shared/lib/fmt';
import type { StrategyParameters } from '../stores/strategyParamsStore';
import type { PipelineStep } from './ftsPipelineEvaluator';

export type StrategyNodeType =
  | 'root'
  | 'stage'
  | 'branch'
  | 'decision'
  | 'condition'
  | 'pattern'
  | 'result'
  | 'action'
  | 'reject'
  | 'pending'
  | 'unknown';

export type StrategyNodeStatus = 'pass' | 'wait' | 'fail' | 'active' | 'inactive';

/** ۵ مرحله اصلی نقشه راه FTS متناظر با ۴ صفحه چارت رسمی */
export type StrategyStageKey = 'selection' | 'technical' | 'fundamental' | 'delivery' | 'capital';

export interface StrategyGraphNode {
  id: string;
  type: StrategyNodeType;
  stage: StrategyStageKey;
  page: string; // چارت صفحه ۱ تا ۴
  label: string;
  subLabel?: string;
  description: string;
  formula?: string;
  badge?: string;
  depth: number;
  parentId: string | null;
  childrenIds: string[];
  refs?: string[];
  status: StrategyNodeStatus;
  evidence?: string[];
  editableParamKeys?: (keyof StrategyParameters)[];
  weight?: number;
  valueDisplay?: string;
}

export interface StrategyGraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'hierarchy' | 'cross_ref' | 'active_flow';
  label?: string;
  status: StrategyNodeStatus;
}

export interface CanonicalStrategyGraph {
  nodes: StrategyGraphNode[];
  edges: StrategyGraphEdge[];
  nodeMap: Map<string, StrategyGraphNode>;
  stageRoots: Record<StrategyStageKey, string>;
  rootId: string;
  activePathNodeIds: Set<string>;
  activePathEdgeIds: Set<string>;
}

export interface GraphBuildOptions {
  params: StrategyParameters;
  selectedPreset: 'swing' | 'trend' | 'hourglass' | 'custom';
  steps?: PipelineStep[];
  activeCustomNodeIds?: string[];
  symbol?: string;
  searchQuery?: string;
}

/**
 * ایجاد گراف کانونی FTS کاملاً منطبق بر چارت ۴ صفحه‌ای:
 * ترتیب اجرا: سبک معامله -> S (تابلوخوانی) -> T (تکنیکال) -> F (بنیادی) -> Delivery -> تصمیم کاربر و مدیریت سرمایه
 */
export function buildCanonicalStrategyGraph(options: GraphBuildOptions): CanonicalStrategyGraph {
  const { params, selectedPreset, steps = [], symbol } = options;

  const nodeMap = new Map<string, StrategyGraphNode>();
  const nodes: StrategyGraphNode[] = [];
  const edges: StrategyGraphEdge[] = [];

  const isSwing = selectedPreset === 'swing';
  const isTrend = selectedPreset === 'trend';
  const isHourglass = selectedPreset === 'hourglass';

  // نگاشت وضعیت مراحل ارزیابی از روی نماد جاری
  const stepStatusMap: Record<string, StrategyNodeStatus> = {
    selection: 'inactive',
    technical: 'inactive',
    fundamental: 'inactive',
    delivery: 'inactive',
    capital: 'inactive',
  };

  const stepEvidenceMap: Record<string, string[]> = {
    selection: [],
    technical: [],
    fundamental: [],
    delivery: [],
    capital: [],
  };

  for (const s of steps) {
    if (s.id === 'tape') {
      stepStatusMap.selection = s.status;
      stepEvidenceMap.selection = s.evidence;
    } else if (s.id === 'technical') {
      stepStatusMap.technical = s.status;
      stepEvidenceMap.technical = s.evidence;
    } else if (s.id === 'fundamental') {
      stepStatusMap.fundamental = s.status;
      stepEvidenceMap.fundamental = s.evidence;
    } else if (s.id === 'master') {
      stepStatusMap.delivery = s.status;
      stepEvidenceMap.delivery = s.evidence;
      stepStatusMap.capital = s.status === 'pass' ? 'active' : 'inactive';
    }
  }

  const addNode = (n: Omit<StrategyGraphNode, 'childrenIds'>): StrategyGraphNode => {
    const fullNode: StrategyGraphNode = { ...n, childrenIds: [] };
    nodes.push(fullNode);
    nodeMap.set(fullNode.id, fullNode);
    return fullNode;
  };

  // -------------------------------------------------------------
  // ۰. ریشه کلان نقشه راه FTS
  // -------------------------------------------------------------
  addNode({
    id: 'fts_root',
    type: 'root',
    stage: 'selection',
    page: 'نقشه جامع',
    label: 'نقشه راه تصمیم‌گیری FTS',
    subLabel: isSwing ? 'سبک نوسان‌گیر (زیر ۳ ماه)' : isTrend ? 'سبک روندگیر (بالای ۳ ماه)' : isHourglass ? 'استراتژی ساعت شنی (۳ تا ۱۰ سال)' : 'مسیر سفارشی FTS',
    description: 'خط لوله مهندسی معکوس FTS: انتخاب سبک -> تابلوخوانی (S) -> تکنیکال (T) -> بنیادی (F) -> تحویل -> مدیریت سرمایه (صفحه ۴)',
    depth: 0,
    parentId: null,
    status: 'active',
    badge: 'FTS v2.1',
  });

  // -------------------------------------------------------------
  // ۱. فاز S: انتخاب و تابلوخوانی (Selection) — چارت صفحه ۳
  // -------------------------------------------------------------
  addNode({
    id: 'stage_selection',
    type: 'stage',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'S: انتخاب و تابلوخوانی',
    subLabel: 'صفحه ۳ چارت FTS',
    description: 'انتخاب سبک، رصد جریان نقدینگی در TRADERS ARENA، بررسی صنایع، حجم معاملات، الگوهای تابلوخوانی و فیلتر خشک کردن',
    formula: 'ورود پول هوشمند + حجم مشکوک + الگوی ساعت یا کف‌روبی',
    depth: 1,
    parentId: 'fts_root',
    status: symbol ? stepStatusMap.selection : 'active',
    evidence: stepEvidenceMap.selection,
    badge: 'صفحه ۳',
  });

  // شاخه‌های S
  addNode({
    id: 's_style_branch',
    type: 'branch',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'انتخاب سبک معامله',
    subLabel: isSwing ? 'نوسان‌گیر (فعال)' : isTrend ? 'روندگیر (فعال)' : isHourglass ? 'ساعت شنی (فعال)' : 'سفارشی',
    description: 'نوسان‌گیر: ۱ تا ۲ ماه، بررسی ساعت و حجم مشکوک | روندگیر: بالای ۳ ماه، کف‌روبی و خرید پله‌ای',
    depth: 2,
    parentId: 'stage_selection',
    status: 'active',
    badge: 'سبک',
  });

  addNode({
    id: 's_liquidity_branch',
    type: 'branch',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'رصد جریان نقدینگی و TRADERS ARENA',
    subLabel: 'ارزش معاملات و نبض بازار',
    description: 'ارزش معاملات >۲۰ همت مساعد، <۱۰ همت نامساعد؛ تا زمانی که ۸۰٪ بازار منفی باشد هنوز فرصت ورود است؛ خروج پول از درآمد ثابت و ورود به سهام',
    formula: 'ارزش معاملات > ۱۰ همت | صف فروش < ۸۰٪',
    depth: 2,
    parentId: 'stage_selection',
    status: 'active',
    badge: 'جریان نقدینگی',
  });

  addNode({
    id: 's_volume_branch',
    type: 'branch',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'حجم معاملات (مشکوک / روند)',
    subLabel: isTrend ? 'بررسی حجم و قیمت ارزنده' : `حجم مشکوک ۳ برابر MA(volume, 21)`,
    description: 'نوسان‌گیر: بررسی حجم مشکوک ۳ برابر میانگین ماهانه MA21؛ روندگیر: بررسی حجم معاملات و ورود در قیمت ارزنده',
    formula: `حجم >= ${toFaDigits(params.minVolumeRatio)}× MA21`,
    depth: 2,
    parentId: 'stage_selection',
    status: 'active',
    badge: 'حجم',
    editableParamKeys: ['minVolumeRatio'],
  });

  addNode({
    id: 's_patterns_branch',
    type: 'branch',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'الگوهای تابلوخوانی',
    subLabel: isTrend ? 'کف‌روبی صف فروش' : 'الگوی ساعت + خروج از باکس رنج',
    description: 'نوسان‌گیر: الگوی ساعت (آخرین > پایانی بیش از ۱٪)، خروج از باکس رنج با کندل قوی و ورود پول؛ روندگیر: کف‌روبی (صف فروش با اردرهای خرید قوی)',
    formula: 'آخرین > پایانی * ۱٫۰۱ یا کف‌روبی',
    depth: 2,
    parentId: 'stage_selection',
    status: 'active',
    badge: 'الگو',
    editableParamKeys: ['clockPriceDiffPct'],
  });

  addNode({
    id: 's_dry_filter',
    type: 'condition',
    stage: 'selection',
    page: 'چارت صفحه ۳',
    label: 'فیلتر خشک کردن',
    subLabel: isTrend ? 'کف‌روبی + نقطه‌زنی' : 'ساعت + جت + حجم مشکوک',
    description: 'فیلتر نهایی صفحه ۳ چارت FTS برای استخراج نمادهای واجد شرایط جهت ارسال به مرحله تکنیکال',
    formula: isTrend ? 'کف‌روبی صف فروش' : 'ساعت + حجم مشکوک + شکست مقاومت',
    depth: 2,
    parentId: 'stage_selection',
    status: 'active',
    badge: 'فیلتر خشک کردن',
  });

  // -------------------------------------------------------------
  // ۲. فاز T: تحلیل تکنیکال دو زمانه (Technical) — چارت صفحه ۲
  // -------------------------------------------------------------
  addNode({
    id: 'stage_technical',
    type: 'stage',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'T: تحلیل تکنیکال دو زمانه',
    subLabel: 'صفحه ۲ چارت FTS',
    description: 'گیت روند هفتگی، شاخه‌های روزانه صعودی/نزولی/خنثی، ستاپ‌های ورود، الگوهای فروش و تعیین حد ضرر',
    formula: 'هفتگی صعودی (اجباری) + ستاپ روزانه معتبر',
    depth: 1,
    parentId: 'stage_selection',
    status: symbol ? stepStatusMap.technical : 'active',
    evidence: stepEvidenceMap.technical,
    badge: 'صفحه ۲',
  });

  // گیت هفتگی: ۳ حالت
  addNode({
    id: 'tech_weekly_gate',
    type: 'decision',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'گیت روند ماژور هفتگی (Weekly Gate)',
    subLabel: 'صعودی (ادامه) | نزولی/خنثی (رد صلب)',
    description: 'هفتگی صعودی شرط الزامی است. هفتگی نزولی یا خنثی منجر به وتو و Reject قطعی نماد می‌شود',
    formula: 'هفتگی صعودی = PASS | هفتگی نزولی/خنثی = REJECT صلب',
    depth: 2,
    parentId: 'stage_technical',
    status: 'active',
    badge: 'گیت ماژور',
  });

  addNode({
    id: 'tech_weekly_reject',
    type: 'reject',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'هفتگی نزولی یا خنثی → REJECT',
    subLabel: 'وتوی قطعی FTS',
    description: 'طبق چارت صفحه ۲: در صورت نزولی یا خنثی بودن تایم‌فریم هفتگی، نماد بدون استثنا Reject و از چرخه حذف می‌شود',
    formula: 'Weekly Trend in (Down, Neutral) => REJECT',
    depth: 3,
    parentId: 'tech_weekly_gate',
    status: symbol && stepStatusMap.technical === 'fail' ? 'fail' : 'inactive',
    badge: 'رد صلب',
  });

  addNode({
    id: 'tech_weekly_pass',
    type: 'condition',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'تایم هفتگی روند صعودی → PASS',
    subLabel: 'مجوز ورود به تایم روزانه',
    description: 'تایید روند صعودی هفتگی؛ اجازه ورود به بررسی شاخه‌های روزانه داده می‌شود',
    formula: 'Weekly Trend == Uptrend => Continue to Daily',
    depth: 3,
    parentId: 'tech_weekly_gate',
    status: symbol && stepStatusMap.technical === 'pass' ? 'pass' : 'active',
    badge: 'تایید هفتگی',
  });

  // شاخه‌های روزانه زیرِ هفتگی صعودی
  addNode({
    id: 't_daily_bullish',
    type: 'branch',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'تایم روزانه صعودی (پولبک / جت)',
    subLabel: 'ستاپ پولبک یا جت',
    description: 'استراتژی پولبک به سقف شکسته‌شده یا ستاپ جت (عبور از سقف تاریخی/مقاومت استاتیک با کندل تثبیت)',
    formula: 'Daily Bullish: Pullback / Jet Breakout',
    depth: 2,
    parentId: 'stage_technical',
    status: 'active',
    badge: 'روزانه صعودی',
    editableParamKeys: ['jetStabilizationDays'],
  });

  addNode({
    id: 't_daily_bearish',
    type: 'branch',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'تایم روزانه نزولی (فیبوناچی / CHoCH)',
    subLabel: 'تراز ۳۳-۴۰ و ۶۱.۸-۷۰ یا تغییر ساختار',
    description: 'اصلاح در روند نزولی مینور: بازگشت از ترازهای فیبوناچی لگاریتمی (زون ۳۳-۴۰٪ یا ۶۱.۸-۷۰٪) یا تغییر ساختار CHoCH',
    formula: 'Daily Bearish: Log Fib 33-40% / 61.8-70% / CHoCH',
    depth: 2,
    parentId: 'stage_technical',
    status: 'active',
    badge: 'روزانه نزولی',
  });

  addNode({
    id: 't_daily_neutral',
    type: 'branch',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'تایم روزانه خنثی (کف/سقف یا کف دوقلو)',
    subLabel: 'آخرین کف صعودی یا آخرین سقف نزولی',
    description: 'ورود در آخرین کف روند صعودی یا آخرین سقف روند نزولی؛ شکست آخرین سقف در کف دوقلو',
    formula: 'Daily Neutral: Last Low Uptrend / Double Bottom',
    depth: 2,
    parentId: 'stage_technical',
    status: 'active',
    badge: 'روزانه خنثی',
  });

  addNode({
    id: 't_stop_logic',
    type: 'decision',
    stage: 'technical',
    page: 'چارت صفحه ۲',
    label: 'قوانین حد ضرر و خروج',
    subLabel: isTrend ? 'روندگیر: حد ضرر بنیادی (بدون استاپ قیمتی)' : `نوسان‌گیر: کندل کامل زیر MA14 یا ۵٪ زیر کف`,
    description: '۵٪ زیر آخرین کف روند صعودی؛ نوسان‌گیر: MA14 یک کندل کامل زیر خط؛ روندگیر: خرید پله‌ای و حد ضرر بنیادی با تغییر گزارش کدال',
    formula: isTrend ? 'خروج صرفاً با تغییر منفی گزارش فصلی کدال' : '۵٪ زیر کف ماژور صعودی یا خروج با کندل زیر MA14',
    depth: 2,
    parentId: 'stage_technical',
    status: 'active',
    badge: 'حد ضرر',
    editableParamKeys: ['stopLossMaPeriod', 'stopLossFixedPct'],
  });

  // -------------------------------------------------------------
  // ۳. فاز F: ارزیابی بنیادی ۵ شاخصه کدال (Fundamental) — چارت صفحه ۱
  // -------------------------------------------------------------
  addNode({
    id: 'stage_fundamental',
    type: 'stage',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: 'F: ارزیابی بنیادی ۵ شاخصه',
    subLabel: 'صفحه ۱ چارت FTS',
    description: 'پنج شاخص رسمی کدال: رشد فروش ماهانه، سودآوری ۳ ساله EPS، حاشیه سود ناخالص، فروش به ارزش بازار، چشم‌انداز ۸ صنعت و نرخ‌گذاری',
    formula: `کسب حداقل ${toFaDigits(params.minFundScore)} از ۵ امتیاز بنیادی`,
    depth: 1,
    parentId: 'stage_technical',
    status: symbol ? stepStatusMap.fundamental : 'active',
    evidence: stepEvidenceMap.fundamental,
    badge: 'صفحه ۱',
    editableParamKeys: ['minFundScore'],
  });

  // ۵ شاخصه رسمی کدال
  addNode({
    id: 'f_ind_1_sales',
    type: 'condition',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: `شاخص ۱: رشد فروش ماهانه کدال (کف ۴۰٪، هدف ۶۰٪)`,
    subLabel: 'گزارش فعالیت ماهانه نسبت به سال قبل',
    description: 'درآمد و فروش از ابتدای سال تا کنون در مقایسه با سال گذشته: ((فروش امسال ÷ فروش پارسال) × ۱۰۰) - ۱۰۰ > ۴۰٪ با تایید تولید و نرخ',
    formula: `رشد فروش >= ${toFaDigits(params.minMonthlySalesGrowthPct)}٪ سالانه`,
    depth: 2,
    parentId: 'stage_fundamental',
    status: 'active',
    badge: 'شاخص ۱',
    editableParamKeys: ['minMonthlySalesGrowthPct'],
  });

  addNode({
    id: 'f_ind_2_eps',
    type: 'condition',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: 'شاخص ۲: سودآوری مستمر ۳ ساله EPS',
    subLabel: 'روند صعودی EPS در ۳ سال مالی گذشته',
    description: 'بررسی صورت سود و زیان سالانه در کدال: سود هر سهم در ۳ سال اخیر باید مثبت، صعودی و فاقد زیان انباشته ماده ۱۴۱ باشد',
    formula: 'EPS سال ۱ < سال ۲ < سال ۳ (سودآوری پایدار)',
    depth: 2,
    parentId: 'stage_fundamental',
    status: 'active',
    badge: 'شاخص ۲',
  });

  addNode({
    id: 'f_ind_3_margin',
    type: 'condition',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: `شاخص ۳: حاشیه سود ناخالص (کف ۲۰٪، استاندارد ۳۰٪)`,
    subLabel: 'صورت مالی سالانه و میان‌دوره‌ای',
    description: 'نسبت سود ناخالص به درآمد عملیاتی شرکت: (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰ > ۳۰٪ (کف بحرانی ۲۰٪)',
    formula: `حاشیه سود ناخالص >= ${toFaDigits(params.minGrossMarginPct)}٪`,
    depth: 2,
    parentId: 'stage_fundamental',
    status: 'active',
    badge: 'شاخص ۳',
    editableParamKeys: ['minGrossMarginPct'],
  });

  addNode({
    id: 'f_ind_4_sales_mcap',
    type: 'condition',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: 'شاخص ۴: نسبت فروش به ارزش بازار (کف ۰٫۳۳، ایده‌آل ۱٫۰)',
    subLabel: 'تخمین فروش ۱۲ ماهه ÷ ارزش بازار',
    description: 'تخمین فروش دوازده‌ماهه (فروش تجمیعی × ۱۲ ÷ ماه گزارش) تقسیم بر ارزش روز بازار در TSETMC. حداقل ۰٫۳۳ و ایده‌آل ۱٫۰',
    formula: '(فروش تجمیعی × ۱۲ ÷ ماه) / ارزش بازار >= ۰٫۳۳',
    depth: 2,
    parentId: 'stage_fundamental',
    status: 'active',
    badge: 'شاخص ۴',
  });

  addNode({
    id: 'f_ind_5_outlook',
    type: 'condition',
    stage: 'fundamental',
    page: 'چارت صفحه ۱',
    label: 'شاخص ۵: چشم‌انداز ۸ صنعت و نرخ‌گذاری',
    subLabel: 'نرخ‌گذاری دلاری/ریالی بدون قیمت دستوری',
    description: 'چشم‌انداز خوب در ۸ صنعت: دارویی، غذایی، سیمانی، فلزات، پتروشیمی، کانی‌فلزی، کاشی، شیشه + نرخ‌گذاری بورس کالا/آزاد و عدم شمول قیمت دستوری',
    formula: 'صنعت مجاز + نرخ‌گذاری آزاد / بورس‌کالا',
    depth: 2,
    parentId: 'stage_fundamental',
    status: 'active',
    badge: 'شاخص ۵',
  });

  // -------------------------------------------------------------
  // ۴. فاز تحویل به کاربر (Delivery) — پایان غربالگری
  // -------------------------------------------------------------
  addNode({
    id: 'stage_delivery',
    type: 'stage',
    stage: 'delivery',
    page: 'پایان غربالگری',
    label: 'تحویل نهایی به معامله‌گر (Delivery)',
    subLabel: 'کاندیداهای نهایی عبور کرده از FTS',
    description: 'فقط نمادهایی که از هر ۳ فیلتر تابلو (S)، تکنیکال (T) و بنیادی (F) عبور کرده‌اند و مجمع پیش‌رو ندارند',
    formula: 'S (Pass) + T (Pass) + F (Pass) + عدم وتوی مجمع',
    depth: 1,
    parentId: 'stage_fundamental',
    status: symbol ? stepStatusMap.delivery : 'active',
    evidence: stepEvidenceMap.delivery,
    badge: 'تحویل',
  });

  addNode({
    id: 'delivery_verdict_pass',
    type: 'result',
    stage: 'delivery',
    page: 'پایان غربالگری',
    label: 'تایید نهایی: وضعیت PASS',
    subLabel: 'آماده تخصیص سبد و معامله',
    description: 'نماد با موفقیت تمامی گیت‌ها را پشت سر گذاشته و برای تصمیم‌گیری نهایی و پله‌بندی به معامله‌گر تحویل می‌شود',
    formula: 'Status == PASS',
    depth: 2,
    parentId: 'stage_delivery',
    status: symbol && stepStatusMap.delivery === 'pass' ? 'pass' : 'active',
    badge: 'PASS',
  });

  addNode({
    id: 'delivery_assembly_check',
    type: 'condition',
    stage: 'delivery',
    page: 'پایان غربالگری',
    label: 'کنترل وتوی مجمع عمومی (۱۴ روز)',
    subLabel: 'توقف ورود قبل از مجامع سالانه',
    description: 'در صورت وجود مجمع عمومی تا ۱۴ روز آینده، ورود به سهم موقتاً به تعویق می‌افتد تا ریسک بسته‌شدن نماد مدیریت شود',
    formula: 'فاصله تا مجمع عمومی > ۱۴ روز کاری',
    depth: 2,
    parentId: 'stage_delivery',
    status: 'active',
    badge: 'مجمع',
  });

  // -------------------------------------------------------------
  // ۵. فاز مدیریت سرمایه و استراتژی‌های ورود (Page 4 — Capital & Strategies)
  // -------------------------------------------------------------
  addNode({
    id: 'stage_capital',
    type: 'stage',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'تصمیم کاربر و مدیریت سرمایه',
    subLabel: 'صفحه ۴ چارت FTS',
    description: 'اقدامات پس از غربالگری: اصول سبدچینی، سقف دارایی، ابزارهای پوشش ریسک و انتخاب استراتژی ورود (ساعت شنی، جت، نقطه‌زنی)',
    formula: 'حداکثر ۷۰٪ کل دارایی در بورس + سبد ۵ تا ۷ سهم',
    depth: 1,
    parentId: 'stage_delivery',
    status: symbol ? stepStatusMap.capital : 'active',
    badge: 'صفحه ۴',
  });

  // مدیریت سرمایه
  addNode({
    id: 'm_rules_cap',
    type: 'branch',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'اصول مدیریت سرمایه و سبدچینی',
    subLabel: 'سقف بازار، وزن سبد و پوشش ریسک',
    description: 'سقف ۷۰٪ کل دارایی در بازار سهام (در شرایط جنگی ۱۰٪ تا ۲۰٪)، سبد ۵ تا ۷ نماد بهینه، پوشش ریسک با صندوق‌های طلا، اهرمی و آپشن',
    formula: `سقف تک‌سهم ${toFaDigits(params.singleStockMaxWeightPct)}٪ | سبد ۵ تا ۷ نماد`,
    depth: 2,
    parentId: 'stage_capital',
    status: 'active',
    badge: 'سرمایه',
    editableParamKeys: ['singleStockMaxWeightPct', 'maxTotalPortfolioCapPct'],
  });

  addNode({
    id: 'm_ladder_entry',
    type: 'condition',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'ورود و خروج پله‌ای + حفظ ۵۰٪ بنیادی',
    subLabel: 'پله‌بندی خرید و سیو سود در سقف‌ها',
    description: 'نوسان‌گیر: ۲ پله (زون ۳۳-۴۰ و ۶۱-۷۰)؛ روندگیر: ۴-۵ پله خرید میانگین‌کم‌کردن؛ در سقف‌ها خروج اصل سرمایه و نگهداری ۵۰٪ برای مجمع',
    formula: 'خروج اصل سرمایه در مقاومت + نگهداری ۵۰٪ تا تایید صورت‌های مالی',
    depth: 2,
    parentId: 'stage_capital',
    status: 'active',
    badge: 'پله‌بندی',
    editableParamKeys: ['exitHalfPct'],
  });

  // استراتژی‌های ورود (Entry Strategies)
  addNode({
    id: 'm_strat_hourglass',
    type: 'pattern',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'استراتژی ساعت شنی (بلندمدت / بازنشستگی)',
    subLabel: 'سهام بزرگ بنیادی، هفتگی بالای MA52 و RSI5 اشباع',
    description: 'سهام لیدر و سوپربنیادی در تایم هفتگی؛ قیمت بالای میانگین MA52 و RSI دوره ۵ یا ۷ در اشباع فروش (زیر ۳۰ یا ۲۰)؛ ضریب خرید ۲ تا ۴ برابر',
    formula: 'Weekly Close > MA52 & Weekly RSI(5) <= 30',
    depth: 2,
    parentId: 'stage_capital',
    status: isHourglass ? 'active' : 'inactive',
    badge: 'ساعت شنی',
  });

  addNode({
    id: 'm_strat_jet',
    type: 'pattern',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'استراتژی جت FTS',
    subLabel: 'شکست سقف تاریخی با کندل تثبیت و مهلت ۳ روز',
    description: 'یک نماد بنیادی از سقف تاریخی یا مقاومت استاتیک افقی عبور کند و کندل تثبیت بزند؛ معامله‌گر تا ۳ روز کاری مهلت ورود دارد',
    formula: 'Static Resistance Breakout + Confirmation Candle',
    depth: 2,
    parentId: 'stage_capital',
    status: isSwing ? 'active' : 'inactive',
    badge: 'ستاپ جت',
  });

  addNode({
    id: 'm_strat_point_hunt',
    type: 'pattern',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'استراتژی نقطه‌زنی (Point Hunt)',
    subLabel: 'ورود در کف سوم یا پنجم خط روند نزولی',
    description: 'رسم خط روند متصل‌کننده ۲ کف اول در روند نزولی؛ سیگنال خرید در واکنش به کف سوم (کم‌ریسک) یا کف پنجم (الگوهای دیامتریک/سیمتریکال)',
    formula: 'Rebound at 3rd or 5th Trendline Bottom',
    depth: 2,
    parentId: 'stage_capital',
    status: isTrend ? 'active' : 'inactive',
    badge: 'نقطه‌زنی',
  });

  addNode({
    id: 'm_user_actions',
    type: 'action',
    stage: 'capital',
    page: 'چارت صفحه ۴',
    label: 'اقدام معامله‌گر (سبد / واچ‌لیست)',
    subLabel: 'افزودن به دیده‌بان یا ثبت خرید در پورتفوی',
    description: 'تصمیم نهایی با خود کاربر است؛ سیستم خرید خودکار انجام نمی‌دهد. نماد را به واچ‌لیست یا سبد دارایی اضافه کنید',
    formula: 'ثبت در سبد دارایی یا پایش در دیده‌بان',
    depth: 2,
    parentId: 'stage_capital',
    status: 'active',
    badge: 'اقدام',
  });

  // ساختن رابطه فرزندان (childrenIds) و یال‌های درختی
  for (const node of nodes) {
    if (node.parentId) {
      const parent = nodeMap.get(node.parentId);
      if (parent) {
        parent.childrenIds.push(node.id);
        edges.push({
          id: `edge_${node.parentId}_${node.id}`,
          source: node.parentId,
          target: node.id,
          type: 'hierarchy',
          status: node.status,
        });
      }
    }
  }

  // یال‌های اتصالی بین مراحل اصلی جریان نقشه راه:
  // S -> T -> F -> Delivery -> Capital
  const stageSequence: StrategyStageKey[] = ['selection', 'technical', 'fundamental', 'delivery', 'capital'];
  const stageRootIds: Record<StrategyStageKey, string> = {
    selection: 'stage_selection',
    technical: 'stage_technical',
    fundamental: 'stage_fundamental',
    delivery: 'stage_delivery',
    capital: 'stage_capital',
  };

  for (let i = 0; i < stageSequence.length - 1; i++) {
    const sCurrent = stageRootIds[stageSequence[i]];
    const sNext = stageRootIds[stageSequence[i + 1]];
    edges.push({
      id: `flow_edge_${sCurrent}_${sNext}`,
      source: sCurrent,
      target: sNext,
      type: 'active_flow',
      label: `گام ${toFaDigits(i + 1)} به ${toFaDigits(i + 2)}`,
      status: 'active',
    });
  }

  // محاسبه مسیر فعال بر اساس نماد و سبک انتخابی
  const activePathNodeIds = new Set<string>();
  const activePathEdgeIds = new Set<string>();

  // همیشه ریشه و مراحل اصلی فعال هستند
  activePathNodeIds.add('fts_root');
  activePathNodeIds.add('stage_selection');
  activePathNodeIds.add('stage_technical');
  activePathNodeIds.add('stage_fundamental');
  activePathNodeIds.add('stage_delivery');
  activePathNodeIds.add('stage_capital');

  // شاخه‌های متناسب با سبک
  activePathNodeIds.add('s_style_branch');
  activePathNodeIds.add('s_liquidity_branch');
  activePathNodeIds.add('s_volume_branch');
  activePathNodeIds.add('s_patterns_branch');
  activePathNodeIds.add('s_dry_filter');

  activePathNodeIds.add('tech_weekly_gate');
  activePathNodeIds.add('tech_weekly_pass');
  if (isSwing) {
    activePathNodeIds.add('t_daily_bullish');
    activePathNodeIds.add('m_strat_jet');
  } else if (isTrend) {
    activePathNodeIds.add('t_daily_bearish');
    activePathNodeIds.add('m_strat_point_hunt');
  } else if (isHourglass) {
    activePathNodeIds.add('m_strat_hourglass');
  }
  activePathNodeIds.add('t_stop_logic');

  activePathNodeIds.add('f_ind_1_sales');
  activePathNodeIds.add('f_ind_2_eps');
  activePathNodeIds.add('f_ind_3_margin');
  activePathNodeIds.add('f_ind_4_sales_mcap');
  activePathNodeIds.add('f_ind_5_outlook');

  activePathNodeIds.add('delivery_verdict_pass');
  activePathNodeIds.add('delivery_assembly_check');

  activePathNodeIds.add('m_rules_cap');
  activePathNodeIds.add('m_ladder_entry');
  activePathNodeIds.add('m_user_actions');

  // علامت‌گذاری یال‌های فعال
  for (const edge of edges) {
    if (activePathNodeIds.has(edge.source) && activePathNodeIds.has(edge.target)) {
      activePathEdgeIds.add(edge.id);
    }
  }

  return {
    nodes,
    edges,
    nodeMap,
    stageRoots: stageRootIds,
    rootId: 'fts_root',
    activePathNodeIds,
    activePathEdgeIds,
  };
}
