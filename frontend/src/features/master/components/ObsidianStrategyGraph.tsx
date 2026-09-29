// features/master/components/ObsidianStrategyGraph.tsx -- گراف شبکه‌ای بهینه‌شده، فوق‌العاده روان، تمیز به سبک ابسیدین
// یکپارچه‌سازی کامل ۴ صفحه چارت FTS با پشتیبانی جامع از تم روشن و تاریک، چینش اصیل راست‌به‌چپ (RTL)،
// جریان دوگانه مهندسی معکوس نوسان‌گیری (صفحه ۴ و ۱۹ جزوه) و جریان کلاسیک تحلیلی، همراه با قابلیت ویرایش زنده پارامترها
import React, { useState, useRef, useMemo } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useUiStore } from '@shared/stores/uiStore';
import { useStrategyParamsStore, type StrategyParameters } from '../stores/strategyParamsStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useTreeFlowStore, isFlowRunning } from '../stores/treeFlowStore';

export type GraphCategory = 'core' | 'fund' | 'tech' | 'tape' | 'money';
export type FlowDirection = 'reverse' | 'classic';

export interface StrategyGraphNode {
  id: string;
  label: string;
  fullTitle: string;
  category: GraphCategory;
  stage: number; // 0: Core, 1: Stage 1, 2: Stage 2, 3: Stage 3, 4: Stage 4
  stageName: string;
  page: string;
  description: string;
  ruleFormula: string;
  badge: string;
  color: string;
  radius: number;
  x: number;
  y: number;
  editableParamKeys?: (keyof StrategyParameters)[];
}

export interface StrategyGraphLink {
  id: string;
  source: string;
  target: string;
  presets: ('swing' | 'trend' | 'hourglass')[];
  flow?: FlowDirection; // اگر مشخص نشود، در هر دو جریان فعال است
}

// ساختار ۴۶ نود جامع — نسخهٔ تطبیق موبهمو با ۴ صفحه چارت (دور دوم: رفع متن‌های بی‌مرجع + ۱۲ گرهٔ جاافتاده)
function getGraphNodes(params: StrategyParameters, flow: FlowDirection): StrategyGraphNode[] {
  // در فرهنگ زبان فارسی، جهت مطالعه و جریان از راست به چپ (RTL) است:
  // X_CORE (راست‌ترین): 1350
  // X_COL1: 1080
  // X_COL2: 780
  // X_COL3: 480
  // X_COL4 (چپ‌ترین): 180

  const isReverse = flow === 'reverse';

  // تعیین مختصات ستون‌ها بر مبنای جهت جریان:
  // در مهندسی معکوس نوسان‌گیری: تابلوخوانی S (1080) ➔ تکنیکال T (780) ➔ ۵ شاخص بنیادی F (480) ➔ مدیریت سرمایه M (180)
  // در جریان کلاسیک روندی: بنیادی F (1080) ➔ تکنیکال T (780) ➔ تابلوخوانی S (480) ➔ مدیریت سرمایه M (180)
  const xTape = isReverse ? 1080 : 480;
  const xTech = 780;
  const xFund = isReverse ? 480 : 1080;
  const xMoney = 180;

  return [
    // ─── ستون راست (مبدأ جریان): هسته استراتژی جامع FTS ───
    {
      id: 'fts_core',
      label: isReverse ? '⚡ غربالگری نوسان‌گیری FTS' : '🌟 استراتژی جامع FTS',
      fullTitle: isReverse ? 'مهندسی معکوس نوسان‌گیری FTS (صفحه ۴ و ۱۹ جزوه)' : 'متدولوژی سه‌گانه FTS (عرفان نصرتی)',
      category: 'core',
      stage: 0,
      stageName: isReverse ? 'ورودی مهندسی معکوس' : 'هسته متدولوژی',
      page: 'صفحه ۱ تا ۴',
      description: isReverse
        ? 'طبق متد مهندسی معکوس FTS، ابتدا با تابلوخوانی و فیلترها سهام داغ اسکن می‌شوند، سپس تکنیکال دو زمانه تاییدیه می‌دهد، سپس ۵ فیلتر بنیادی بررسی شده و در نهایت مدیریت سرمایه اعمال می‌گردد.'
        : 'همگام‌سازی همزمان ۳ فیلتر: فیلتر ۵ شاخص بنیادی کدال (F)، تکنیکال دو زمانه (T)، و تابلوخوانی و زمان‌سنج ورود (S) همراه با مدیریت سرمایه و حد ضرر.',
      ruleFormula: isReverse ? 'تابلوخوانی (S) ➔ تکنیکال (T) ➔ بنیادی (F) ➔ مدیریت ریسک (M)' : 'F (بنیادی) + T (تکنیکال) + S (تابلو) + M (مدیریت سرمایه)',
      badge: isReverse ? 'مهندسی معکوس' : 'هسته مرکزی',
      color: '#38bdf8',
      radius: 28,
      x: 1350,
      y: 430,
    },

    // ─── رکن تابلوخوانی و غربالگری روزانه S (چارت صفحه ۳) ───
    {
      id: 'tape_volume',
      label: `🌊 حجم مشکوک (${toFaDigits(params.minVolumeRatio)}×)`,
      fullTitle: 'حجم مشکوک معاملات و ورود پول هوشمند',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: `بررسی حجم مشکوک: سه برابر میانگین ماهانه — volume, MA length=۲۱.`,
      ruleFormula: `حجم روز ≥ ${params.minVolumeRatio} × میانگین ماهانه (MA=۲۱)`,
      badge: 'پول هوشمند',
      color: '#06b6d4',
      radius: 20,
      x: xTape,
      y: 90,
      editableParamKeys: ['minVolumeRatio'],
    },
    {
      id: 'tape_clock',
      label: `⏰ الگوی ساعت (${toFaDigits(params.clockPriceDiffPct)}٪+)`,
      fullTitle: 'الگوی ساعت FTS: اختلاف قیمت آخرین از پایانی',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: `قیمت آخرین معامله بیش از ${toFaDigits(params.clockPriceDiffPct)}٪ بالاتر از قیمت پایانی؛ ایده‌آل: پایانی منفی و آخرین مثبت؛ هرچه اختلاف بیشتر، الگو قوی‌تر — در TRADER ARENA ستون «اختلاف آخرین و پایانی» را از زیاد به کم مرتب می‌کنیم.`,
      ruleFormula: `(آخرین - پایانی) / پایانی >= ${params.clockPriceDiffPct}٪ ${params.clockStrictNegativeClose ? '+ شرط پایانی منفی' : ''}`,
      badge: 'زمان‌سنج ورود',
      color: '#22c55e',
      radius: 20,
      x: xTape,
      y: 174,
      editableParamKeys: ['clockPriceDiffPct', 'clockStrictNegativeClose'],
    },
    {
      id: 'tape_breakout',
      label: '📦 خروج از باکس رنج',
      fullTitle: 'شکست سقف کانال تراکم قیمت در تابلو',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'در انتهای محدودهٔ رنج، رشد حجم معاملات و شکست باکس با یک کندل قوی به سمت بالا و ورود پول و الگوی ساعت؛ هرچه زمان باکس بیشتر باشد، حرکت صعودی قوی‌تر است.',
      ruleFormula: 'رشد حجم معاملات + شکست باکس با کندل قوی + ورود پول + الگوی ساعت',
      badge: 'آغاز شتاب',
      color: '#38bdf8',
      radius: 18,
      x: xTape,
      y: 258,
    },
    {
      id: 'tape_floor_sweep',
      label: '🧹 کف‌روبی و جمع‌آوری صف',
      fullTitle: 'بلعیدن صف فروش و خشک کردن عرضه در کف',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'سهم صف فروش است ولی اوردرهای قوی در حال خرید است و سهم را جمع می‌کند؛ خشک کردن عرضه.',
      ruleFormula: 'جمع‌آوری صف فروش با اردر سنگین در کف + پایان فشار عرضه',
      badge: 'کف‌روبی صف',
      color: '#a855f7',
      radius: 18,
      x: xTape,
      y: 342,
    },
    {
      id: 'tape_smart_money',
      label: '💳 ورود پول از درآمد ثابت به سهم',
      fullTitle: 'خروج نقدینگی از صندوق‌های فیکس و تزریق به سهام',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'جریان نقدینگی منفی در صندوق‌های درآمد ثابت همزمان با سرانه خرید پرقدرت در سهام برگزیده.',
      ruleFormula: 'خروج نقدینگی از فیکس ➔ تزریق مستقیم به لیدرهای صنعت',
      badge: 'جریان نقدینگی',
      color: '#10b981',
      radius: 17,
      x: xTape,
      y: 426,
    },
    {
      id: 'tape_market_liquidity',
      label: `🏛️ ارزش معاملات بازار سهام (>${toFaDigits(params.marketLiquidityMinHemmat)} همت)`,
      fullTitle: 'فیلتر رونق نقدینگی کل بازار خرد',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'صفحه ۳ و ۴',
      description: `بررسی وضعیت بازار در TRADERS ARENA: ارزش معاملات بازار سهام بالای ${toFaDigits(params.marketLiquidityMinHemmat)} همت ⇒ بازار مساعد؛ زیر ۱۰ همت ⇒ نامساعد.`,
      ruleFormula: `ارزش معاملات خرد روز >= ${params.marketLiquidityMinHemmat} همت ➔ مساعد · زیر ${toFaDigits(10)} همت ➔ نامساعد`,
      badge: 'نقدینگی کل',
      color: '#f59e0b',
      radius: 16,
      x: xTape,
      y: 510,
      editableParamKeys: ['marketLiquidityMinHemmat'],
    },
    {
      id: 'tape_breadth',
      label: '🧮 سهام مثبت و منفی (صف فروش)',
      fullTitle: 'بررسی تعداد و درصد سهام مثبت و منفی بازار',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'بررسی تعداد و درصد سهام مثبت و منفی (صف فروش)؛ زمانیکه ۸۰٪ بازار منفی است، هنوز فرصت ورود وجود دارد.',
      ruleFormula: 'تعداد و درصد مثبت/منفی + پایش صف‌های فروش | ۸۰٪ منفی = فرصت ورود',
      badge: 'نبض کلی بازار',
      color: '#f59e0b',
      radius: 17,
      x: xTape,
      y: 594,
    },
    {
      id: 'tape_flow_charts',
      label: '📉 نمودارهای جریان نقدینگی',
      fullTitle: 'پایش تصویری جریان نقدینگی بازار',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'نمودار ارزش سفارش‌های خرید و فروش؛ نمودار نمادهای مثبت و منفی؛ نمودار سرانه خرید و فروش معاملات خرد بازار؛ نمودار تعداد صف‌های خرید و فروش.',
      ruleFormula: 'ارزش سفارش‌ها · نمادهای مثبت/منفی · سرانه معاملات خرد · تعداد صف‌ها',
      badge: 'پایش تصویری',
      color: '#06b6d4',
      radius: 17,
      x: xTape,
      y: 678,
    },
    {
      id: 'tape_industries_picks',
      label: '🏭 صنایع و سهام برگزیده',
      fullTitle: 'بررسی صنایع و گزینش سهام برگزیده',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'بررسی صنایع: خلاصه معاملات صنایع بورس؛ سهام برگزیده: «درصد آخرین» و «ورود پول» را از بالا به پایین مرتب می‌کنیم.',
      ruleFormula: 'خلاصه معاملات صنایع + مرتب‌سازی برگزیده‌ها (درصد آخرین، ورود پول)',
      badge: 'انتخاب صنعت',
      color: '#10b981',
      radius: 17,
      x: xTape,
      y: 762,
    },
    {
      id: 'tape_volume_trend',
      label: '📦 حجم معاملات روندگیر',
      fullTitle: 'حجم معاملات در سبک روندگیری',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'روندگیر: بررسی حجم معاملات و ورود در قیمت ارزنده.',
      ruleFormula: 'حجم معاملات + ورود در قیمت ارزنده',
      badge: 'ورود ارزشی',
      color: '#a855f7',
      radius: 17,
      x: xTape,
      y: 846,
    },
    {
      id: 'tape_final_filters',
      label: '🧲 فیلترهای نهایی (خشک کردن)',
      fullTitle: 'فیلترهای نهایی نوسان‌گیر و روندگیر',
      category: 'tape',
      stage: isReverse ? 1 : 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'نوسان‌گیر: ساعت (عدد ۱ را می‌توان به ۳ یا ۵ تغییر داد؛ TVOL>۱)، جت، حجم مشکوک — روندگیر: کف‌روبی، نقطه‌زنی.',
      ruleFormula: 'نوسان‌گیر: ساعت/جت/حجم مشکوک · روندگیر: کف‌روبی/نقطه‌زنی',
      badge: 'فیلتر نهایی',
      color: '#eab308',
      radius: 17,
      x: xTape,
      y: 930,
    },


    // ─── رکن تکنیکال دو زمانه T (چارت صفحه ۲) ───
    {
      id: 'tech_weekly_up',
      label: '📈 تایم هفتگی صعودی',
      fullTitle: 'تاییدیه روند هفتگی (شرط لازم ورود FTS)',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'تایم هفتگی روند صعودی؛ فقط در این حالت بررسی ستاپ‌های تایم روزانه مجاز است.',
      ruleFormula: 'تایم هفتگی صعودی = صدور مجوز جستجوی ستاپ روزانه',
      badge: 'مجوز ورود',
      color: '#22c55e',
      radius: 20,
      x: xTech,
      y: 85,
    },
    {
      id: 'tech_weekly_reject',
      label: '⛔ ریجکت هفتگی (وتوی قطعی)',
      fullTitle: 'ریجکت صلب در صورت روند هفتگی نزولی یا رنج',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'تایم هفتگی نزولی ⇒ رد؛ تایم هفتگی خنثی ⇒ رد — ورود به سهم ممنوع است.',
      ruleFormula: 'هفتگی نزولی / رنج ➔ وتوی صلب کلیه ستاپ‌های روزانه',
      badge: 'وتوی قطعی',
      color: '#ef4444',
      radius: 17,
      x: xTech,
      y: 168,
    },
    {
      id: 'setup_jet',
      label: `🚀 ستاپ جت (مهلت ورود ${toFaDigits(params.jetStabilizationDays)} روز)`,
      fullTitle: 'استراتژی پرتاب جت و شکست مقاومت استاتیک',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: `بنیادی بودن + روند صعودیِ هفتگی و روزانه + شکستِ سطحِ استاتیک + کندلِ تثبیت. «${toFaDigits(params.jetStabilizationDays)} روز» تعدادِ روزهای تثبیت نیست، مهلتِ ورود است: بعد از شکست حداکثر تا ${toFaDigits(params.jetStabilizationDays)} روز روی تثبیت و پولبک مجاز به ورودی. (حکم ۱۷)`,
      ruleFormula: `بنیادی + هفتگی↑ و روزانه↑ + شکست استاتیک + کندل تثبیت | مهلت ورود <= ${params.jetStabilizationDays} روز`,
      badge: 'ستاپ پرتاب',
      color: '#06b6d4',
      radius: 19,
      x: xTech,
      y: 252,
      editableParamKeys: ['jetStabilizationDays'],
    },
    {
      id: 'setup_pullback',
      label: '↩️ ستاپ پولبک و بازآزمایی',
      fullTitle: 'پولبک آرام به سطح شکسته شده با حجم پایین',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'استراتژی پولبک؛ یکی از دو ستاپ مجاز تایم روزانهٔ صعودی.',
      ruleFormula: 'تایم روزانه صعودی ➔ ستاپ پولبک',
      badge: 'تاییدیه پولبک',
      color: '#10b981',
      radius: 18,
      x: xTech,
      y: 336,
    },
    {
      id: 'setup_fib',
      label: '📐 ستاپ فیبوناچی',
      fullTitle: 'پله‌های اصلاحی فیبوناچی در موج صعودی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: `چارتِ FTS فقط دو زون دارد: ۳۳ تا ۴۰٪ و ۶۱.۸ تا ۷۰٪ (به‌علاوهٔ مبنای ۱۰۰) — نه خطوطِ کلاسیکِ ۳۸.۲ و ۵۰. پلهٔ اول روی ${toFaDigits(params.fibStep1Level)}٪ و پلهٔ دوم روی ${toFaDigits(params.fibStep2Level)}٪ از موجِ صعودی انتخاب می‌شود.`,
      ruleFormula: `پله ۱: زون ۳۳–۴۰٪ (انتخابِ ${params.fibStep1Level}٪) | پله ۲: زون ۶۱.۸–۷۰٪ (انتخابِ ${params.fibStep2Level}٪)`,
      badge: 'پله‌های اصلاح',
      color: '#38bdf8',
      radius: 18,
      x: xTech,
      y: 420,
      editableParamKeys: ['fibStep1Level', 'fibStep2Level'],
    },
    {
      id: 'setup_choch',
      label: '🔄 تغییر ساختار CHoCH',
      fullTitle: 'ستاپ بازگشتی تغییر ساختار یا شکست خط گردن',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'شکست آخرین سقف در روند نزولی یا شکست آخرین کف در روند صعودی؛ سقف دوقلو و سر و شانه نیز مشابه CHoCH داوری می‌شوند.',
      ruleFormula: 'شکست آخرین سقف در نزولی / شکست آخرین کف در صعودی ➔ CHoCH',
      badge: 'الگوی بازگشتی',
      color: '#a855f7',
      radius: 18,
      x: xTech,
      y: 504,
    },
    {
      id: 'setup_point_hunt',
      label: '🎯 شکار نقطه حمایت (کف ۳ یا ۵)',
      fullTitle: 'نقطه‌زنی در کف سوم یا پنجم کانال صعودی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲ و ۳',
      description: 'واکنش دقیق قیمت به کف سوم یا پنجم کانال یا خط روند صعودی همزمان با تاییدیه کندل بازگشتی و کاهش عرضه.',
      ruleFormula: 'برخورد به کف کانال صعودی + کندل چکشی و پایان فشار فروش',
      badge: 'نقطه‌زنی کف',
      color: '#f59e0b',
      radius: 16,
      x: xTech,
      y: 588,
    },
    {
      id: 'tech_weekly_hourglass',
      label: `⏳ اشباع کف هفتگی (RSI(۵) < ${toFaDigits(params.hourglassWeeklyRsi)})`,
      fullTitle: 'اشباع فروش عمیق در کف تاریخی هفتگی (استراتژی ساعت شنی)',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'صفحه ۲ و ۴',
      description: `قیمت در تایم هفتگی زیر MA-52 و RSIِ پنج‌رفته زیر ${toFaDigits(params.hourglassWeeklyRsi)} (ناحیه اشباع فروش)؛ فرصت طلایی خرید سنگین پله‌ای به افق ۳ تا ۱۰ سال.`,
      ruleFormula: `هفتگی زیر MA=52 + RSI(دوره ${toFaDigits(5)}) <= ${params.hourglassWeeklyRsi}`,
      badge: 'اهرم کف تاریخ',
      color: '#eab308',
      radius: 19,
      x: xTech,
      y: 672,
      editableParamKeys: ['hourglassWeeklyRsi', 'hourglassLeverageMultiplier'],
    },
    {
      id: 'setup_last_low',
      label: '📍 ورود در آخرین کف یا سقف',
      fullTitle: 'ورود در آخرین کف روند صعودی یا آخرین سقف روند نزولی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'تایم روزانهٔ خنثی: ورود در آخرین کف روند صعودی یا آخرین سقف روند نزولی.',
      ruleFormula: 'روزانه خنثی ➔ ورود در آخرین کف/سقف روند',
      badge: 'ورود خنثی',
      color: '#22c55e',
      radius: 17,
      x: xTech,
      y: 756,
    },
    {
      id: 'setup_double_bottom',
      label: '🔁 کف دوقلو',
      fullTitle: 'کف دوقلو — شکست آخرین سقف به سمت بالا',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'کف دوقلو: زمانیکه آخرین سقف رو به بالا شکسته شود.',
      ruleFormula: 'شکست آخرین سقف به بالا (پس از کف دوقلو)',
      badge: 'ستاپ بازگشتی',
      color: '#38bdf8',
      radius: 17,
      x: xTech,
      y: 840,
    },
    {
      id: 'setup_double_top',
      label: '⛰️ سقف دوقلو و سر و شانه',
      fullTitle: 'سیگنال فروش: سقف دوقلو و سر و شانه (مشابه CHoCH)',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'سقف دوقلو و سر و شانه — مشابه CHoCH؛ سیگنال فروش.',
      ruleFormula: 'سقف دوقلو / سر و شانه ➔ مشابه CHoCH',
      badge: 'سیگنال فروش',
      color: '#ef4444',
      radius: 17,
      x: xTech,
      y: 924,
    },


    // ─── رکن ۵ شاخص بنیادی کدال F (چارت صفحه ۱) ───
    {
      id: 'fund_super',
      label: `💎 سوپربنیادی (رشد > ${toFaDigits(params.minMonthlySalesGrowthPct)}٪)`,
      fullTitle: 'نماد سوپربنیادی شاخص‌ساز (امتیاز ۵ از ۵ FTS)',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'رشد فروش ماهانه کدال بیش از ۴۰٪، سودآوری ۳ سالهٔ متوالی، حاشیه سود بالای ۳۰٪ (کف ۲۰٪)، چشم‌انداز خوب (دارویی، غذایی، سیمانی، فلزات، پتروشیمی، کانی‌فلزی، کاشی، شیشه)، نرخ‌گذاری دلاری/ریالی و فاقد نرخ دستوری.',
      ruleFormula: `رشد فروش > ${params.minMonthlySalesGrowthPct}٪ | EPS ۳ ساله | حاشیه > ۳۰٪ | بدون نرخ دستوری`,
      badge: '۵ از ۵ FTS',
      color: '#22c55e',
      radius: 20,
      x: xFund,
      y: 85,
      editableParamKeys: ['minMonthlySalesGrowthPct', 'excludePriceControlled'],
    },
    {
      id: 'fund_good',
      label: `بنیادی مطلوب (حاشیه > ${toFaDigits(params.minGrossMarginPct)}٪)`,
      fullTitle: 'بنیادی مطلوب با تایید ورود روندی (۴ از ۵)',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: `رشد فروش ماهانه و سودآوری ۳ ساله، حاشیه سود ناخالص بالای ${toFaDigits(params.minGrossMarginPct)}٪؛ مناسب سرمایه‌گذاری روندی بالای ۳ ماه.`,
      ruleFormula: `حاشیه سود ناخالص > ${params.minGrossMarginPct}٪ + فروش صعودی در کدال`,
      badge: 'تایید روندی',
      color: '#10b981',
      radius: 19,
      x: xFund,
      y: 175,
      editableParamKeys: ['minGrossMarginPct', 'minFundScore'],
    },
    {
      id: 'fund_medium',
      label: 'بنیادی متوسط (فقط نوسانی)',
      fullTitle: 'بنیادی متوسط؛ صرفاً مجاز برای نوسان‌گیری کوتاه‌مدت (۳ از ۵)',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'فاقد ۳ سال سود پیاپی اما بدون زیان انباشته؛ طبق چارت صفحه ۱ فقط و فقط مجاز برای نوسان‌گیری با ستاپ جت.',
      ruleFormula: 'امتیاز ۳ از ۵ | ورود روندی بلندمدت اکیداً ممنوع',
      badge: 'صرفاً نوسان‌گیر',
      color: '#eab308',
      radius: 18,
      x: xFund,
      y: 265,
      editableParamKeys: ['minFundScore'],
    },
    {
      id: 'fund_weak',
      label: '⛔ رد صلب بنیادی (وتوی قطعی)',
      fullTitle: 'رد بنیادی (صنایع قیمت دستوری خودرو یا حاشیه زیر ۲۰٪)',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'صنایع مشمول قیمت‌گذاری دستوری شدید نظیر خودرو و قطعات، شرکت‌های زیان‌ده ماده ۱۴۱؛ خرید اکیداً ممنوع و وتو است.',
      ruleFormula: 'حاشیه سود < ۲۰٪ یا نرخ دستوری شدید ➔ وتوی کامل',
      badge: 'توقف ورود',
      color: '#ef4444',
      radius: 18,
      x: xFund,
      y: 355,
      editableParamKeys: ['excludePriceControlled', 'minGrossMarginPct'],
    },
    {
      id: 'crit_sales_growth',
      label: `شاخص ۱: رشد فروش ماهانه (${toFaDigits(params.minMonthlySalesGrowthPct)}٪+)`,
      fullTitle: 'شاخص ۱: رشد فروش ماهانه کدال نسبت به دوره سال قبل',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'گزارش فعالیت ماهانه در سامانه کدال؛ رشد فروش تجمیعی نسبت به دوره مشابه سال قبل.',
      ruleFormula: `فروش ماهانه کدال >= ${params.minMonthlySalesGrowthPct}٪ رشد سالانه`,
      badge: 'شاخص ۱ · بلاکر',
      color: '#10b981',
      radius: 15,
      x: xFund,
      y: 445,
      editableParamKeys: ['minMonthlySalesGrowthPct'],
    },
    {
      id: 'crit_3y_eps',
      label: 'شاخص ۲: سودآوری مستمر ۳ ساله',
      fullTitle: 'شاخص ۲: سود خالص مثبت در ۳ سال گذشته بدون زیان',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'روند EPS شرکت در ۳ سال مالی گذشته صعودی و بدون سابقه زیان انباشته ماده ۱۴۱ باشد.',
      ruleFormula: 'EPS سال ۱ < سال ۲ < سال ۳ | سوددهی مستمر',
      badge: 'شاخص ۲ · بلاکر',
      color: '#10b981',
      radius: 15,
      x: xFund,
      y: 535,
    },
    {
      id: 'crit_gross_margin',
      label: 'شاخص ۳: حاشیه سود ناخالص',
      fullTitle: 'شاخص ۳: حاشیه سود ناخالص شرکت بالای ۲۰٪ (سوپر ۳۰٪)',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: `نسبت سود ناخالص به درآمد فروش شرکت حداقل ${toFaDigits(params.minGrossMarginPct)}٪ باشد تا در برابر تورم و تکانه‌های هزینه مصون بماند.`,
      ruleFormula: `(درآمد فروش - بهای تمام‌شده) / فروش >= ${params.minGrossMarginPct}٪`,
      badge: 'شاخص ۳ · بلاکر',
      color: '#10b981',
      radius: 15,
      x: xFund,
      y: 625,
      editableParamKeys: ['minGrossMarginPct'],
    },
    {
      id: 'crit_ps_ratio',
      label: 'شاخص ۴: فروش÷ارزش ≥ ۰٫۳۳',
      fullTitle: 'شاخص ۴: تخمین فروش دوازده‌ماهه تقسیم بر ارزش بازار',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'حکم ۴: قاعده «تخمین فروش ۱۲ ماهه ÷ ارزش بازار» است، نه نسبتِ معکوسش. «فروش ۳ ماهه × ۴» فقط مثالِ همان گزارشِ خرداد بود؛ تعمیمِ درست `تجمیعی × ۱۲ ÷ ماهِ گزارش` (فروردین ×۱۲، خرداد ×۴، شهریور ×۲). کفِ قبولی ۰٫۳۳ و حالتِ ایده‌آل ۱٫۰ — همان دو عددی که موتور در `sales_to_mcap_min` می‌سنجد.',
      ruleFormula: '(فروش تجمیعی × ۱۲ ÷ م) / ارزش روز بازار >= ۰٫۳۳ | ایده‌آل ۱٫۰',
      badge: 'شاخص ۴ · تعدیل‌گر',
      color: '#06b6d4',
      radius: 15,
      x: xFund,
      y: 715,
    },
    {
      id: 'crit_pricing_regime',
      label: 'شاخص ۵: نوع نرخ‌گذاری',
      fullTitle: 'شاخص ۵: حجم انبار و نوع نرخ‌گذاری — دستوری نباشد',
      category: 'fund',
      stage: isReverse ? 3 : 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'شاخص ۵: چشم‌انداز خوب (دارویی، غذایی، سیمانی، فلزات، پتروشیمی، کانی‌فلزی، کاشی، شیشه) + نرخ‌گذاری دلاری/ریالی، جهانی؛ نوع نرخ‌گذاری دستوری نباشد.',
      ruleFormula: 'نوع نرخ‌گذاری ≠ دستوری | آزاد / بورس‌کالا ✓ — دستوری ✗',
      badge: 'شاخص ۵ · تعدیل‌گر',
      color: '#a855f7',
      radius: 15,
      x: xFund,
      y: 800,
    },

    // ─── رکن مدیریت سرمایه، مهندسی معکوس و خروج M (چارت صفحه ۴) ───
    {
      id: 'stop_swing',
      label: '🛑 حد ضرر نوسان‌گیر',
      fullTitle: 'حد ضرر صلب نوسان‌گیر (استاپ تکنیکالی کوتاه‌مدت)',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `شخص نوسان‌گیر: تشکیل یک کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)}؛ حد ضرر عمومی ۵٪ زیر آخرین کف روند صعودی؛ خرید پله‌ای (معاملات ۲±۱ ماه).`,
      ruleFormula: `کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)} یا افت ۵٪ زیر آخرین کف روند صعودی ➔ خروج قطعی`,
      badge: 'استاپ تکنیکالی',
      color: '#ef4444',
      radius: 20,
      x: xMoney,
      y: 75,
      editableParamKeys: ['stopLossMaPeriod', 'stopLossFixedPct'],
    },
    {
      id: 'stop_trend',
      label: '🛡️ حد ضرر بنیادی روندگیر (کدال)',
      fullTitle: 'حد ضرر بنیادی روندگیر در گزارش‌های مالی کدال',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'شخص روندگیر: سرمایه‌گذاری بالای ۳ ماه، خرید پله‌ای دارد و حد ضرر تکنیکالی ندارد؛ حد ضرر آن بنیادی است — رصد گزارش فروش ماهانه و صورت‌های مالی فصلی/سالانه.',
      ruleFormula: `افت حاشیه سود < ${params.minGrossMarginPct}٪ یا توقف رشد فروش در کدال ➔ تعویض سهم`,
      badge: 'استاپ کدالی',
      color: '#22c55e',
      radius: 19,
      x: xMoney,
      y: 141,
      editableParamKeys: ['minGrossMarginPct', 'minMonthlySalesGrowthPct'],
    },
    {
      id: 'stop_hourglass',
      label: `⏳ اهرم ساعت شنی (${toFaDigits(params.hourglassLeverageMultiplier)}× پله کف)`,
      fullTitle: 'پله‌بندی سنگین اهرمی در کف تاریخی به افق ۳ تا ۱۰ سال',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `در اشباع کف تاریخی، حجم پله ${toFaDigits(params.hourglassLeverageMultiplier)} برابر حجم عادی افزایش می‌یابد؛ بدون حد ضرر کوتاه‌مدت.`,
      ruleFormula: `ضریب حجم ورود: ${params.hourglassLeverageMultiplier}× پله عادی | افق ۳ تا ۱۰ ساله`,
      badge: 'اهرم بلندمدت',
      color: '#eab308',
      radius: 18,
      x: xMoney,
      y: 207,
      editableParamKeys: ['hourglassLeverageMultiplier', 'hourglassWeeklyRsi'],
    },
    {
      id: 'exit_half',
      label: `💰 فروش ${toFaDigits(params.exitHalfPct)}٪ در اولین سقف`,
      fullTitle: 'سیگنال فروش: اولین سقف تشکیل شد — اصل پول نگه داشته می‌شود',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۲ و ۴',
      description: `جزوه فهرستِ «سیگنال فروش ٪۵۰» را می‌نویسد: «۱/ اولین سقف تشکیل شد … ۴/ سقف سوم (نمی‌تواند بالاتر بسازد)» و قاعده‌اش: «سود لایه لایه برویم و اصل پول را نگه داریم». ${toFaDigits(params.exitHalfPct)}٪ دستِ شماست؛ با نقدشدنِ همین لایه ریسکِ باقی‌مانده صفر می‌شود.`,
      ruleFormula: `اولین سقف ➔ فروش ${toFaDigits(params.exitHalfPct)}٪ و نگاه‌داشتنِ اصل پول`,
      badge: 'خروج اصل پول',
      color: '#38bdf8',
      radius: 19,
      x: xMoney,
      y: 273,
      editableParamKeys: ['exitHalfPct'],
    },
    {
      id: 'exit_third_peak',
      label: `🏔️ خروج در سقف سوم (${toFaDigits(params.thirdPeakWeeklyPct)}٪ و ${toFaDigits(params.thirdPeakDailyPct)}٪)`,
      fullTitle: 'خروج کامل در سقف سوم کانال صعودی طبق چارت صفحه ۴',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `برخورد قیمت به سقف سوم کانال صعودی یا خط روند ماژور با فاصله زیر ${toFaDigits(params.thirdPeakWeeklyPct)}٪ هفتگی و ${toFaDigits(params.thirdPeakDailyPct)}٪ روزانه؛ خروج کامل از سهم.`,
      ruleFormula: `فاصله تا خط روند هفتگی <= ${params.thirdPeakWeeklyPct}٪ یا روزانه <= ${params.thirdPeakDailyPct}٪ ➔ فروش ۱۰۰٪`,
      badge: 'خروج سقف ۳',
      color: '#f97316',
      radius: 18,
      x: xMoney,
      y: 339,
      editableParamKeys: ['thirdPeakWeeklyPct', 'thirdPeakDailyPct'],
    },
    {
      id: 'exit_rsi_div',
      label: '📉 واگرایی مقاومتی (RSI)',
      fullTitle: 'سیگنال اخطار واگرایی منفی قیمت و اندیکاتور RSI در سقف',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'واگرایی مقاومتی: در نمودار سقف بالاتر، ولی در RSI سقف پایین‌تر.',
      ruleFormula: 'قیمت: سقف بالاتر (HH) | شاخص RSI: سقف پایین‌تر (LH) ➔ خروج قطعی',
      badge: 'واگرایی منفی',
      color: '#ef4444',
      radius: 17,
      x: xMoney,
      y: 405,
    },
    {
      id: 'rule_rr',
      label: `⚖️ R/R کم ➔ ریسک بالا`,
      fullTitle: 'کم بودنِ R/R دلیلِ بی‌طلبیِ سهم است؛ آستانه دستِ شما',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `جزوه R/R را یک‌جا و به‌عنوانِ دلیلِ عدم ورود می‌آورد: «دلیلِ طلبِ سهم R/R کم است، ریسک بالاست». عددی برای آن نگفته؛ ${toFaDigits(params.minRiskRewardRatio)} برابر دستِ شماست: فاصله تا تارگت باید از فاصله تا حد ضرر بیشتر باشد.`,
      ruleFormula: `(تارگت سود - ورود) / (ورود - حد ضرر) >= ${toFaDigits(params.minRiskRewardRatio)}`,
      badge: 'ریسک به ریوارد',
      color: '#a855f7',
      radius: 16,
      x: xMoney,
      y: 471,
      editableParamKeys: ['minRiskRewardRatio'],
    },
    {
      id: 'rule_cap',
      label: `📊 سقف وزن صنعت (${toFaDigits(params.maxIndustryWeightPct)}٪)`,
      fullTitle: 'سقف سرمایه‌گذاری مجاز در یک صنعت و تک‌سهم',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `مجموع وزن تمام نمادهای یک صنعت نباید از ${toFaDigits(params.maxIndustryWeightPct)}٪ کل سبد و تک‌سهم نوسانی از ${toFaDigits(params.singleStockMaxWeightPct)}٪ تجاوز کند.`,
      ruleFormula: `سقف صنعت <= ${params.maxIndustryWeightPct}٪ | سقف تک‌سهم نوسانی <= ${params.singleStockMaxWeightPct}٪`,
      badge: 'سقف صنعت',
      color: '#10b981',
      radius: 16,
      x: xMoney,
      y: 537,
      editableParamKeys: ['maxIndustryWeightPct', 'singleStockMaxWeightPct'],
    },
    {
      id: 'm_weighting',
      label: '⚖️ وزن سبد و حداکثر ضرر',
      fullTitle: 'تعیین وزن سبد سهام با احتساب حداکثر ضرر ۲۰٪±۱۰٪',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'تعیین وزن سبد سهام با احتساب حداکثر ضرر ۲۰٪ ± ۱۰٪.',
      ruleFormula: 'وزن سبد با سقف ضرر ۲۰٪±۱۰٪',
      badge: 'وزن سبد',
      color: '#f59e0b',
      radius: 17,
      x: xMoney,
      y: 603,
    },
    {
      id: 'm_ladder',
      label: '🪜 ورود و خروج پله‌ای + ابزار کمکی',
      fullTitle: 'ورود و خروج پله‌ای و ابزارهای کمکی (RSI=۷ · MA=۱۰۰ · MA=۵۲)',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'ورود و خروج پله‌ای + ابزار کمکی: RSI=۷ سهام بنیادی و تایم هفتگی (ناحیه اشباع فروش)؛ تایم روزانه MA=۱۰۰؛ تایم هفتگی MA=۵۲.',
      ruleFormula: 'پله‌ای · RSI=۷ (هفتگی) · MA=۱۰۰ (روزانه) · MA=۵۲ (هفتگی)',
      badge: 'ابزار کمکی',
      color: '#06b6d4',
      radius: 17,
      x: xMoney,
      y: 669,
    },
    {
      id: 'm_review',
      label: '🔍 رصد مداوم پورتفو',
      fullTitle: 'رصد و تحلیل مداوم پورتفوی بورسی',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'هر ماه در کدال گزارش فروش، هر فصل صورت مالی، هر سال صورت مالی سالانه و مقایسه با سال قبل.',
      ruleFormula: 'ماهانه: گزارش فروش · فصلی: صورت مالی · سالانه: صورت مالی + مقایسه',
      badge: 'پایش دوره‌ای',
      color: '#10b981',
      radius: 17,
      x: xMoney,
      y: 735,
    },
    {
      id: 'm_principles',
      label: '🧺 اصول پورتفوی بهینه',
      fullTitle: 'اصول یک پورتفوی بهینه بورسی',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: 'سهام دلاری (سیمانی، فلزی، پتروشیمی، پالایشی، بانکی) و ریالی (غذایی، رایانه، لاستیک، حمل‌ونقل، بیمه)؛ شرکت‌های بزرگ (فملی و وبملت) و کوچک (سپیدار)؛ تولیدی و غیرتولیدی؛ صندوق‌های سرمایه‌گذاری؛ تناسب دیدگاه سرمایه‌گذاری با بورس ایران.',
      ruleFormula: 'دلاری/ریالی · بزرگ/کوچک · تولیدی/غیرتولیدی · صندوق‌ها',
      badge: 'چیدمان سبد',
      color: '#a855f7',
      radius: 17,
      x: xMoney,
      y: 801,
    },

    {
      id: 'rule_max_portfolio',
      label: '🏛️ سقف دارایی بورس',
      fullTitle: 'قانون طلایی سبد دارایی: سقف بورس در شرایط عادی و جنگی',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'صفحه ۴ جزوه',
      description: `حکم ۸: سقفِ ورودِ کلِ دارایی به بازارِ سرمایه در شرایط عادی ${toFaDigits(params.maxTotalPortfolioCapPct)}٪ است (تئوریِ جزوه ۷۰٪) و در شرایط جنگی ${toFaDigits(params.warConditionCapPct)}٪ ±۱۰٪. باقیِ دارایی طلا و درآمد ثابت است؛ عددِ جداگانه‌ای برایش در جزوه نیامده.`,
      ruleFormula: `سهام عادی <= ${params.maxTotalPortfolioCapPct}٪ کل دارایی | شرایط جنگی <= ${params.warConditionCapPct}٪`,
      badge: 'قانون سبد',
      color: '#f59e0b',
      radius: 17,
      x: xMoney,
      y: 867,
      editableParamKeys: ['maxTotalPortfolioCapPct', 'warConditionCapPct'],
    },
    {
      id: 'hedge_options_etf',
      label: '🛡️ صندوق‌ها و پوشش ریسک',
      fullTitle: 'پوشش ریسک سیستماتیک با صندوق طلای ETF و اختیار معامله',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'صفحه ۴ جزوه',
      description: 'صندوق‌های ETF طلا، اهرمی، ملکی، نقره و درآمد ثابت و فراصندوق‌هایی مثل خوشه یا تمشک؛ پوشش ریسک سبد با ابزارهای مشتقه (آپشن).',
      ruleFormula: 'سبد هج‌شده: سهام برگزیده + طلا + درآمد ثابت + بیمه سهام (Option)',
      badge: 'پوشش ریسک',
      color: '#06b6d4',
      radius: 16,
      x: xMoney,
      y: 933,
    },
  ];
}

// اتصالات پیوسته افقی از ستون به ستون با رعایت هر دو جریان
/** اتصالاتِ هر سبک — بیرون‌کشیده برایِ آزمونِ شاخه‌ها (قیف و درخت باید یک مسیر ببینند) */
export function getGraphLinks(flow: FlowDirection): StrategyGraphLink[] {
  if (flow === 'reverse') {
    // ─── جریان مهندسی معکوس نوسان‌گیری (صفحه ۴ و ۱۹ جزوه) ───
    // شروع از راست (هسته غربالگری نوسان‌گیری) ➔ فیلترهای تابلوخوانی ➔ تکنیکال دو زمانه ➔ ۵ شاخص بنیادی ➔ مدیریت سرمایه
    return [
      // ۱. اتصال هسته اسکن نوسان‌گیری به ورودی‌های تابلوخوانی S
      { id: 'rev_c_vol', source: 'fts_core', target: 'tape_volume', presets: ['swing', 'trend'] },
      { id: 'rev_c_clock', source: 'fts_core', target: 'tape_clock', presets: ['swing'] },
      { id: 'rev_c_box', source: 'fts_core', target: 'tape_breakout', presets: ['swing', 'trend'] },
      { id: 'rev_c_sweep', source: 'fts_core', target: 'tape_floor_sweep', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_c_smart', source: 'fts_core', target: 'tape_smart_money', presets: ['trend'] },
      { id: 'rev_c_macro', source: 'fts_core', target: 'tape_market_liquidity', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_c_breadth', source: 'fts_core', target: 'tape_breadth', presets: ['swing', 'trend'] },
      { id: 'rev_c_charts', source: 'fts_core', target: 'tape_flow_charts', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_c_ind', source: 'fts_core', target: 'tape_industries_picks', presets: ['trend'] },
      { id: 'rev_c_voltrend', source: 'fts_core', target: 'tape_volume_trend', presets: ['trend'] },
      { id: 'rev_c_filters', source: 'fts_core', target: 'tape_final_filters', presets: ['swing', 'trend'] },

      // ۲. تابلوخوانی S ➔ تاییدیه تکنیکال دو زمانه T
      { id: 'rev_s_vol_up', source: 'tape_volume', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
      { id: 'rev_s_clock_jet', source: 'tape_clock', target: 'setup_jet', presets: ['swing'] },
      { id: 'rev_s_clock_pull', source: 'tape_clock', target: 'setup_pullback', presets: ['swing'] },
      { id: 'rev_s_vol_fib', source: 'tape_volume', target: 'setup_fib', presets: ['swing', 'trend'] },
      { id: 'rev_s_box_jet', source: 'tape_breakout', target: 'setup_jet', presets: ['swing'] },
      { id: 'rev_s_sweep_hg', source: 'tape_floor_sweep', target: 'tech_weekly_hourglass', presets: ['hourglass'] },
      { id: 'rev_s_sweep_hunt', source: 'tape_floor_sweep', target: 'setup_point_hunt', presets: ['swing', 'trend'] },
      { id: 'rev_s_hunt_up', source: 'setup_point_hunt', target: 'tech_weekly_up', presets: ['trend'] },
      { id: 'rev_s_smart_choch', source: 'tape_smart_money', target: 'setup_choch', presets: ['trend'] },
      { id: 'rev_s_breadth_up', source: 'tape_breadth', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
      { id: 'rev_s_charts_up', source: 'tape_flow_charts', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
      { id: 'rev_s_ind_up', source: 'tape_industries_picks', target: 'tech_weekly_up', presets: ['trend'] },
      { id: 'rev_s_voltrend_hunt', source: 'tape_volume_trend', target: 'setup_point_hunt', presets: ['trend'] },
      { id: 'rev_s_filters_jet', source: 'tape_final_filters', target: 'setup_jet', presets: ['swing'] },
      { id: 'rev_s_filters_hunt', source: 'tape_final_filters', target: 'setup_point_hunt', presets: ['trend'] },
      { id: 'rev_t_up_lastlow', source: 'tech_weekly_up', target: 'setup_last_low', presets: ['swing', 'trend'] },
      { id: 'rev_t_up_dbottom', source: 'tech_weekly_up', target: 'setup_double_bottom', presets: ['swing', 'trend'] },
      { id: 'rev_t_up_dtop', source: 'tech_weekly_up', target: 'setup_double_top', presets: ['swing', 'trend'] },
      { id: 'rev_t_dtop_rsi', source: 'setup_double_top', target: 'exit_rsi_div', presets: ['swing', 'trend'] },

      // ۳. تکنیکال T ➔ ارزیابی ۵ شاخص بنیادی F
      { id: 'rev_t_up_super', source: 'tech_weekly_up', target: 'fund_super', presets: ['trend', 'hourglass'] },
      { id: 'rev_t_up_good', source: 'tech_weekly_up', target: 'fund_good', presets: ['swing', 'trend'] },
      { id: 'rev_t_jet_med', source: 'setup_jet', target: 'fund_medium', presets: ['swing'] },
      { id: 'rev_t_pull_good', source: 'setup_pullback', target: 'fund_good', presets: ['swing'] },
      { id: 'rev_t_rej_weak', source: 'tech_weekly_reject', target: 'fund_weak', presets: [] },
      { id: 'rev_t_fib_sales', source: 'setup_fib', target: 'crit_sales_growth', presets: ['trend'] },
      { id: 'rev_t_choch_eps', source: 'setup_choch', target: 'crit_3y_eps', presets: ['trend'] },
      { id: 'rev_t_hg_super', source: 'tech_weekly_hourglass', target: 'fund_super', presets: ['hourglass'] },

      // شاخص‌های فرعی بنیادی
      { id: 'rev_f_super_sales', source: 'fund_super', target: 'crit_sales_growth', presets: ['trend'] },
      { id: 'rev_f_super_eps', source: 'fund_super', target: 'crit_3y_eps', presets: ['trend', 'hourglass'] },
      { id: 'rev_f_good_margin', source: 'fund_good', target: 'crit_gross_margin', presets: ['swing', 'trend'] },
      { id: 'rev_f_super_ps', source: 'fund_super', target: 'crit_ps_ratio', presets: ['trend'] },
      { id: 'rev_f_good_regime', source: 'fund_good', target: 'crit_pricing_regime', presets: ['trend'] },

      // ۴. بنیادی F ➔ مدیریت سرمایه و خروج M
      { id: 'rev_f_med_stopswing', source: 'fund_medium', target: 'stop_swing', presets: ['swing'] },
      { id: 'rev_f_good_stopswing', source: 'fund_good', target: 'stop_swing', presets: ['swing'] },
      { id: 'rev_f_good_stoptrend', source: 'fund_good', target: 'stop_trend', presets: ['trend'] },
      { id: 'rev_f_super_stoptrend', source: 'fund_super', target: 'stop_trend', presets: ['trend'] },
      { id: 'rev_f_super_hg', source: 'fund_super', target: 'stop_hourglass', presets: ['hourglass'] },

      // اتصالات خروج و قوانین ریسک
      { id: 'rev_m_swing_exithalf', source: 'stop_swing', target: 'exit_half', presets: ['swing'] },
      { id: 'rev_m_exithalf_third', source: 'exit_half', target: 'exit_third_peak', presets: ['swing', 'trend'] },
      { id: 'rev_m_third_rsidiv', source: 'exit_third_peak', target: 'exit_rsi_div', presets: ['swing', 'trend'] },
      { id: 'rev_m_stoptrend_exithalf', source: 'stop_trend', target: 'exit_half', presets: ['trend'] },
      { id: 'rev_m_exithalf_rr', source: 'exit_half', target: 'rule_rr', presets: ['swing', 'trend'] },
      { id: 'rev_m_rr_cap', source: 'rule_rr', target: 'rule_cap', presets: ['swing', 'trend'] },
      { id: 'rev_m_cap_portcap', source: 'rule_cap', target: 'rule_max_portfolio', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_m_portcap_hedge', source: 'rule_max_portfolio', target: 'hedge_options_etf', presets: ['trend', 'hourglass'] },
      { id: 'rev_m_hg_portcap', source: 'stop_hourglass', target: 'rule_max_portfolio', presets: ['hourglass'] },
      { id: 'rev_m_portcap_weight', source: 'rule_max_portfolio', target: 'm_weighting', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_m_weight_ladder', source: 'm_weighting', target: 'm_ladder', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_m_ladder_review', source: 'm_ladder', target: 'm_review', presets: ['swing', 'trend', 'hourglass'] },
      { id: 'rev_m_review_principles', source: 'm_review', target: 'm_principles', presets: ['trend', 'hourglass'] },
      { id: 'rev_m_principles_hedge', source: 'm_principles', target: 'hedge_options_etf', presets: ['trend', 'hourglass'] },
    ];
  }

  // ─── جریان کلاسیک بنیادی به تابلوخوانی ───
  return [
    // هسته به شاخه‌های بنیادی
    { id: 'cls_c_super', source: 'fts_core', target: 'fund_super', presets: ['trend', 'hourglass'] },
    { id: 'cls_c_good', source: 'fts_core', target: 'fund_good', presets: ['swing', 'trend'] },
    { id: 'cls_c_medium', source: 'fts_core', target: 'fund_medium', presets: ['swing'] },
    { id: 'cls_c_weak', source: 'fts_core', target: 'fund_weak', presets: [] },

    // شاخص‌های بنیادی
    { id: 'cls_f_super_sales', source: 'fund_super', target: 'crit_sales_growth', presets: ['trend'] },
    { id: 'cls_f_super_eps', source: 'fund_super', target: 'crit_3y_eps', presets: ['trend', 'hourglass'] },
    { id: 'cls_f_good_margin', source: 'fund_good', target: 'crit_gross_margin', presets: ['swing', 'trend'] },
    { id: 'cls_f_super_ps', source: 'fund_super', target: 'crit_ps_ratio', presets: ['trend'] },
    { id: 'cls_f_good_regime', source: 'fund_good', target: 'crit_pricing_regime', presets: ['trend'] },

    // بنیادی F ➔ تکنیکال T
    { id: 'cls_f_super_up', source: 'fund_super', target: 'tech_weekly_up', presets: ['trend'] },
    { id: 'cls_f_super_hg', source: 'fund_super', target: 'tech_weekly_hourglass', presets: ['hourglass'] },
    { id: 'cls_f_good_up', source: 'fund_good', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
    { id: 'cls_f_med_up', source: 'fund_medium', target: 'tech_weekly_up', presets: ['swing'] },
    { id: 'cls_f_weak_rej', source: 'fund_weak', target: 'tech_weekly_reject', presets: [] },

    // تکنیکال هفتگی به ستاپ‌های روزانه
    { id: 'cls_t_up_jet', source: 'tech_weekly_up', target: 'setup_jet', presets: ['swing'] },
    { id: 'cls_t_up_pull', source: 'tech_weekly_up', target: 'setup_pullback', presets: ['swing'] },
    { id: 'cls_t_up_fib', source: 'tech_weekly_up', target: 'setup_fib', presets: ['swing', 'trend'] },
    { id: 'cls_t_up_choch', source: 'tech_weekly_up', target: 'setup_choch', presets: ['trend'] },
    { id: 'cls_t_up_hunt', source: 'tech_weekly_up', target: 'setup_point_hunt', presets: ['swing', 'trend'] },
    { id: 'cls_t_up_lastlow', source: 'tech_weekly_up', target: 'setup_last_low', presets: ['swing', 'trend'] },
    { id: 'cls_t_up_dbottom', source: 'tech_weekly_up', target: 'setup_double_bottom', presets: ['swing', 'trend'] },
    { id: 'cls_t_up_dtop', source: 'tech_weekly_up', target: 'setup_double_top', presets: ['swing', 'trend'] },

    // تکنیکال T ➔ تابلوخوانی S
    { id: 'cls_t_jet_clock', source: 'setup_jet', target: 'tape_clock', presets: ['swing'] },
    { id: 'cls_t_pull_clock', source: 'setup_pullback', target: 'tape_clock', presets: ['swing'] },
    { id: 'cls_t_fib_vol', source: 'setup_fib', target: 'tape_volume', presets: ['swing', 'trend'] },
    { id: 'cls_t_choch_smart', source: 'setup_choch', target: 'tape_smart_money', presets: ['trend'] },
    { id: 'cls_t_hunt_sweep', source: 'setup_point_hunt', target: 'tape_floor_sweep', presets: ['swing', 'trend'] },
    { id: 'cls_t_lastlow_breadth', source: 'setup_last_low', target: 'tape_breadth', presets: ['swing', 'trend'] },
    { id: 'cls_t_dbottom_charts', source: 'setup_double_bottom', target: 'tape_flow_charts', presets: ['swing', 'trend'] },
    { id: 'cls_t_dtop_charts', source: 'setup_double_top', target: 'tape_flow_charts', presets: ['swing', 'trend'] },
    { id: 'cls_t_dtop_rsi', source: 'setup_double_top', target: 'exit_rsi_div', presets: ['swing', 'trend'] },
    { id: 'cls_t_hg_sweep', source: 'tech_weekly_hourglass', target: 'tape_floor_sweep', presets: ['hourglass'] },

    // تابلوخوانی S ➔ مدیریت سرمایه M
    { id: 'cls_s_clock_stopswing', source: 'tape_clock', target: 'stop_swing', presets: ['swing'] },
    { id: 'cls_s_vol_stopswing', source: 'tape_volume', target: 'stop_swing', presets: ['swing'] },
    { id: 'cls_s_vol_stoptrend', source: 'tape_volume', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_smart_stoptrend', source: 'tape_smart_money', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_sweep_hg', source: 'tape_floor_sweep', target: 'stop_hourglass', presets: ['hourglass'] },
    { id: 'cls_s_sweep_stoptrend', source: 'tape_floor_sweep', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_voltrend_stoptrend', source: 'tape_volume_trend', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_breadth_stoptrend', source: 'tape_breadth', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_charts_stopswing', source: 'tape_flow_charts', target: 'stop_swing', presets: ['swing'] },
    { id: 'cls_s_ind_stoptrend', source: 'tape_industries_picks', target: 'stop_trend', presets: ['trend'] },
    { id: 'cls_s_filters_stopswing', source: 'tape_final_filters', target: 'stop_swing', presets: ['swing'] },
    { id: 'cls_s_filters_stoptrend', source: 'tape_final_filters', target: 'stop_trend', presets: ['trend'] },

    // مدیریت سرمایه و خروج
    { id: 'cls_m_swing_exithalf', source: 'stop_swing', target: 'exit_half', presets: ['swing'] },
    { id: 'cls_m_trend_exithalf', source: 'stop_trend', target: 'exit_half', presets: ['trend'] },
    { id: 'cls_m_exithalf_third', source: 'exit_half', target: 'exit_third_peak', presets: ['swing', 'trend'] },
    { id: 'cls_m_third_rsidiv', source: 'exit_third_peak', target: 'exit_rsi_div', presets: ['swing', 'trend'] },
    { id: 'cls_m_exithalf_rr', source: 'exit_half', target: 'rule_rr', presets: ['swing', 'trend'] },
    { id: 'cls_m_trend_cap', source: 'stop_trend', target: 'rule_cap', presets: ['trend'] },
    { id: 'cls_m_cap_portcap', source: 'rule_cap', target: 'rule_max_portfolio', presets: ['swing', 'trend', 'hourglass'] },
    { id: 'cls_m_portcap_hedge', source: 'rule_max_portfolio', target: 'hedge_options_etf', presets: ['trend', 'hourglass'] },
    { id: 'cls_m_hg_portcap', source: 'stop_hourglass', target: 'rule_max_portfolio', presets: ['hourglass'] },
    { id: 'cls_m_portcap_weight', source: 'rule_max_portfolio', target: 'm_weighting', presets: ['swing', 'trend', 'hourglass'] },
    { id: 'cls_m_weight_ladder', source: 'm_weighting', target: 'm_ladder', presets: ['swing', 'trend', 'hourglass'] },
    { id: 'cls_m_ladder_review', source: 'm_ladder', target: 'm_review', presets: ['swing', 'trend', 'hourglass'] },
    { id: 'cls_m_review_principles', source: 'm_review', target: 'm_principles', presets: ['trend', 'hourglass'] },
    { id: 'cls_m_principles_hedge', source: 'm_principles', target: 'hedge_options_etf', presets: ['trend', 'hourglass'] },
  ];
}

export interface ObsidianStrategyGraphProps {
  selectedPreset: 'swing' | 'trend' | 'hourglass' | 'custom';
  symbol?: string;
  activeCustomNodes?: string[];
  onToggleCustomNode?: (nodeId: string) => void;
  /** پلاک نماد (#222): وضعیتِ هر چهار فاز + سطوحِ ورود/خروجِ همان سهم، رویِ نقشه */
  symbolPhaseStatus?: { k: string; status: 'pass' | 'wait' | 'fail'; label: string }[];
  symbolLevels?: {
    price: number | null;
    entry: number | null;
    support: number | null;
    resistance: number | null;
    hardStop: number | null;
    exitVerdict?: string | null;
  };
}

/** جای دانه‌هایِ جاده رویِ منحنیِ بیزی و فاصلۀ تأخیرشان (چشم جهت را می‌خواند) */
const COMET_T = [0.3, 0.55, 0.8];
const COMET_STEP = 0.45;

function cubicAt(
  p0: { x: number; y: number },
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  p3: { x: number; y: number },
  t: number,
): { x: number; y: number } {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return {
    x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    y: a * p0.y + b * p1.y + c * p2.y + d * p3.y,
  };
}

export function ObsidianStrategyGraph({
  selectedPreset,
  symbol,
  activeCustomNodes = [],
  onToggleCustomNode,
  symbolPhaseStatus,
  symbolLevels,
}: ObsidianStrategyGraphProps) {
  // ۱. پشتیبانی کامل از تم روشن / تاریک
  const theme = useUiStore((s) => s.theme);
  const isLight = theme === 'light';

  // ۲. استور پارامترهای شخصی‌سازی استراتژی
  const { params, updateParam, resetParam, resetAll } = useStrategyParamsStore();

  // ۳. حالت جهت جریان (پیش‌فرض: مهندسی معکوس FTS)
  const [flowDirection, setFlowDirection] = useState<FlowDirection>('reverse');

  // ۴. تولید نودها و اتصالات بر اساس پارامترها و جریان جاری
  const nodes = useMemo(() => getGraphNodes(params, flowDirection), [params, flowDirection]);
  const links = useMemo(() => getGraphLinks(flowDirection), [flowDirection]);

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('tape_volume');
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  // حرکتِ رویِ مسیر با CSS انجام می‌شود. اینکه بدود یا نه را تنظیمِ
  // درون‌برنامه تعیین می‌کند (fts.tree.flow.v1، پیش‌فرض «همیشه»)، نه
  // ترجیعِ سیستم: پنجرۀ بومیِ برنامه آن ترجیع را از ویندوز می‌گیرد و
  // درخت را بی‌حرکت می‌کرد.
  const treeFlowMode = useTreeFlowStore((s) => s.mode);
  const systemReduce = useMediaQuery('(prefers-reduced-motion: reduce)');
  const flowOn = isFlowRunning(treeFlowMode, systemReduce);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const isDraggingRef = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const svgContainerRef = useRef<HTMLDivElement>(null);

  const nodeMap = useMemo(() => {
    const map = new Map<string, StrategyGraphNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  // چیدمانِ بصری: ستون‌هایی که هفت نود یا بیشتر روی هم دارند کمی به سمتِ
  // جریانِ راست‌به‌چپ خم می‌شوند تا «ستونِ صافِ بلند» دیده نشود. دامنهٔ خم ۱۶
  // واحد است چون پلاکِ نود ۲۳۶ واحد و فاصلهٔ دو ستون ۳۰۰ واحد — بیشتر از این،
  // پلاکِ دو ستونِ همسایه به هم می‌رسد.
  const layout = useMemo(() => {
    const byColumn = new Map<number, StrategyGraphNode[]>();
    nodes.forEach((n) => {
      const arr = byColumn.get(n.x);
      if (arr) arr.push(n);
      else byColumn.set(n.x, [n]);
    });
    const pos = new Map<string, { x: number; y: number }>();
    const bands = new Map<number, { top: number; bottom: number; bow: number }>();
    byColumn.forEach((arr, colX) => {
      const sorted = [...arr].sort((a, b) => a.y - b.y);
      const bow = sorted.length >= 7 ? 16 : 0;
      sorted.forEach((n, i) => {
        const t = sorted.length > 1 ? i / (sorted.length - 1) : 0.5;
        pos.set(n.id, { x: n.x - bow * Math.sin(Math.PI * t), y: n.y });
      });
      if (colX !== 1350) {
        bands.set(colX, { top: 74, bottom: sorted[sorted.length - 1].y + 73, bow });
      }
    });
    return { pos, bands };
  }, [nodes]);

  // نودهای فعال استراتژی جاری
  const activeNodeIds = useMemo(() => {
    if (selectedPreset === 'custom') {
      return new Set<string>(['fts_core', ...activeCustomNodes]);
    }
    const set = new Set<string>(['fts_core']);
    links.forEach((link) => {
      if (link.presets.includes(selectedPreset)) {
        set.add(link.source);
        set.add(link.target);
      }
    });
    return set;
  }, [selectedPreset, activeCustomNodes, links]);

  /**
   * جادۀ روان فقط ستونِ انتخاب است: مسیرِ ریشه تا گرهٔ برگزیده. پیش‌تر هر
   * پیوندِ فعالِ سبک خط‌چینِ متحرک و نقطهٔ روان داشت — بیست‌و‌سه مسیر، و در
   * اندازه‌گیریِ زنده (tools/tab_cost_probe.mts) دو هزار میلی‌ثانیه کارِ
   * رشتهٔ اصلی و ششصد لی‌اوت در هر دوازده ثانیه، در حالی که هر تبِ دیگر سی
   * میلی‌ثانیه و صفر لی‌اوت بود.
   */
  const spineLinkIds = useMemo(() => {
    const parents = new Map<string, { id: string; from: string }[]>();
    for (const l of links) {
      const arr = parents.get(l.target);
      if (arr) arr.push({ id: l.id, from: l.source });
      else parents.set(l.target, [{ id: l.id, from: l.source }]);
    }
    const set = new Set<string>();
    const seen = new Set<string>([selectedNodeId]);
    const stack = [selectedNodeId];
    while (stack.length) {
      const id = stack.pop() as string;
      for (const e of parents.get(id) ?? []) {
        set.add(e.id);
        if (!seen.has(e.from)) {
          seen.add(e.from);
          stack.push(e.from);
        }
      }
    }
    return set;
  }, [links, selectedNodeId]);

  // همسایگان نود هاور شده (Hover Focus)
  const hoveredNeighbors = useMemo(() => {
    if (!hoveredNodeId) return null;
    const set = new Set<string>([hoveredNodeId]);
    links.forEach((link) => {
      if (link.source === hoveredNodeId) set.add(link.target);
      if (link.target === hoveredNodeId) set.add(link.source);
    });
    return set;
  }, [hoveredNodeId, links]);

  // نود در حال بازرسی و ویرایش در پنل پایینی
  const inspectedNode = useMemo(() => {
    return nodeMap.get(selectedNodeId) || nodeMap.get('tape_volume') || nodes[0];
  }, [selectedNodeId, nodeMap, nodes]);

  // کنترل حرکت بوم با ماوس (Pan) بدون لرزش
  const handleMouseDown = (e: React.MouseEvent) => {
    if (
      (e.target as HTMLElement).tagName.toLowerCase() === 'input' ||
      (e.target as HTMLElement).tagName.toLowerCase() === 'button'
    ) {
      return;
    }
    isDraggingRef.current = true;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
    setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((z) => Math.min(Math.max(z * factor, 0.55), 1.9));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // سربرگ‌های ستون‌ها متناسب با تم و جهت جریان
  const columnHeaders = useMemo(() => {
    if (flowDirection === 'reverse') {
      return [
        { x: 1080, title: 'مرحله ۱: تابلوخوانی و فیلترها (S)', color: isLight ? '#0284c7' : '#38bdf8' },
        { x: 780, title: 'مرحله ۲: تکنیکال دو زمانه (T)', color: isLight ? '#059669' : '#10b981' },
        { x: 480, title: 'مرحله ۳: فیلتر ۵ شاخص بنیادی (F)', color: isLight ? '#d97706' : '#f59e0b' },
        { x: 180, title: 'مرحله ۴: مدیریت سرمایه و خروج (M)', color: isLight ? '#dc2626' : '#ef4444' },
      ];
    }
    return [
      { x: 1080, title: 'فاز ۱: فیلتر ۵ شاخص بنیادی (F)', color: isLight ? '#059669' : '#10b981' },
      { x: 780, title: 'فاز ۲: تکنیکال دو زمانه (T)', color: isLight ? '#0284c7' : '#38bdf8' },
      { x: 480, title: 'فاز ۳: تابلوخوانی و زمان‌سنج (S)', color: isLight ? '#d97706' : '#f59e0b' },
      { x: 180, title: 'فاز ۴: مدیریت سرمایه و خروج (M)', color: isLight ? '#dc2626' : '#ef4444' },
    ];
  }, [flowDirection, isLight]);

  return (
    <div
      className={`flex flex-col w-full rounded-2xl border transition-colors duration-200 overflow-hidden shadow-2xl ${
        isLight
          ? 'bg-slate-50 border-slate-300 text-slate-900 shadow-slate-200/80'
          : 'bg-[#070b16] border-border-c/80 text-text-primary shadow-black/60'
      }`}
    >
      {/* ۱. نوار ابزار کنترل استراتژی، جستجو و تغییر جهت جریان
          backdrop-blur حذف شد: بالای SVGِ همیشه‌متحرک، هر فریم را مجبور به
          re-blur می‌کرد و گرافیک را بی‌دلیل درگیر می‌نمود (#221). جایش یک
          پس‌زمینهٔ نیمه‌شفافِ جامد نشست که همان خوانایی را می‌دهد. */}
      <div
        className={`flex flex-wrap items-center justify-between gap-3 border-b px-4 py-2.5 transition-colors ${
          isLight ? 'bg-white border-slate-200' : 'bg-bg-card border-border-c/60'
        }`}
      >
        {/* سوییچ جهت جریان: مهندسی معکوس نوسان‌گیری vs جریان مستقیم
            (سوییچرِ پیش‌فرضِ بازی در خودِ صفحه هست و این‌جا تکرار نشد) */}
        <div className="flex items-center gap-2 flex-wrap">
          <div
            className={`flex items-center rounded-xl p-0.5 border text-2xs font-bold transition-colors ${
              isLight ? 'bg-slate-200/70 border-slate-300' : 'bg-bg-primary/80 border-border-c/70'
            }`}
          >
            <button
              type="button"
              onClick={() => setFlowDirection('reverse')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition-all ${
                flowDirection === 'reverse'
                  ? isLight
                    ? 'bg-white text-sky-700 font-black shadow-sm'
                    : 'bg-accent-blue/30 text-accent-blue font-black shadow-[0_0_8px_rgba(56,189,248,0.3)]'
                  : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-text-muted hover:text-text-primary'
              }`}
              title="مهندسی معکوس نوسان‌گیری طبق صفحه ۴ و ۱۹ جزوه: تابلوخوانی ➔ تکنیکال ➔ بنیادی ➔ خروج"
            >
              <span>🔄</span>
              <span>مهندسی معکوس (نوسان‌گیری)</span>
            </button>

            <button
              type="button"
              onClick={() => setFlowDirection('classic')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition-all ${
                flowDirection === 'classic'
                  ? isLight
                    ? 'bg-white text-emerald-700 font-black shadow-sm'
                    : 'bg-accent-green/30 text-accent-green font-black shadow-[0_0_8px_rgba(34,197,94,0.3)]'
                  : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-text-muted hover:text-text-primary'
              }`}
              title="جریان کلاسیک تحلیلی: بنیادی کدال ➔ تکنیکال ➔ تابلوخوانی ➔ مدیریت سرمایه"
            >
              <span>📑</span>
              <span>جریان مستقیم (کلاسیک)</span>
            </button>
          </div>

          {/* فیلد جستجو */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 جستجو در قوانین و نودها..."
              className={`w-36 sm:w-44 rounded-lg border px-2.5 py-1 text-2xs transition-colors focus:outline-none ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:border-sky-500'
                  : 'border-border-c/60 bg-bg-primary/70 text-text-primary placeholder:text-text-muted focus:border-accent-blue'
              }`}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute left-2 top-1 text-3xs text-text-muted hover:text-text-primary"
              >
                ✕
              </button>
            )}
          </div>

          {/* ابزارهای زوم و ریست */}
          <div className={`flex items-center gap-1 border-s ps-2 ${isLight ? 'border-slate-300' : 'border-border-c/50'}`}>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(z + 0.15, 1.9))}
              className={`h-6 w-6 rounded border text-xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="بزرگ‌نمایی"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.55))}
              className={`h-6 w-6 rounded border text-xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="کوچک‌نمایی"
            >
              −
            </button>
            <button
              type="button"
              onClick={handleResetView}
              className={`px-2 h-6 rounded border text-3xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="بازنشانی زاویه دید"
            >
              ⊙ نما
            </button>
          </div>

          {/* دکمه بازنشانی تمام پارامترها به مقادیر رسمی جزوه */}
          <button
            type="button"
            onClick={() => {
              if (window.confirm('آیا مایلید تمام پارامترها و فرمول‌ها به مقادیر مرجع جزوه FTS بازنشانی شوند؟')) {
                resetAll();
              }
            }}
            className={`rounded-lg border px-2.5 py-1 text-3xs font-bold transition-colors ${
              isLight
                ? 'border-amber-400 bg-amber-50 text-amber-700 hover:bg-amber-100'
                : 'border-border-c/60 bg-bg-primary/60 text-accent-yellow hover:bg-accent-yellow/15'
            }`}
            title="بازنشانی کلیه تنظیمات به مقادیر استاندارد جزوه نصرتی"
          >
            ⟲ مرجع جزوه
          </button>
        </div>
      </div>

      {/* پلاکِ نماد (#222): وضعیتِ چهار فاز F/T/S/M و سطوحِ ورود/خروج، درست
          بالایِ بوم — همان شماره‌های evaluateFtsPipeline و /api/fts، نه محاسبهٔ دوم. */}
      {symbol && symbolPhaseStatus && symbolPhaseStatus.length > 0 && (
        <div
          data-testid="graph-symbol-plaque"
          className={`flex flex-wrap items-center gap-2.5 border-b px-4 py-2 text-2xs font-bold transition-colors ${
            isLight ? 'bg-slate-100/90 border-slate-200' : 'bg-bg-primary/80 border-border-c/60'
          }`}
        >
          <span className="font-black text-text-primary">پلاکِ {symbol}:</span>
          {symbolPhaseStatus.map((p) => {
            const c = p.status === 'pass'
              ? 'border-accent-green/50 bg-accent-green/15 text-accent-green'
              : p.status === 'wait'
                ? 'border-accent-yellow/50 bg-accent-yellow/15 text-accent-yellow'
                : 'border-accent-red/50 bg-accent-red/15 text-accent-red';
            return (
              <span
                key={p.k}
                title={`${p.label} — ${p.status === 'pass' ? 'تایید' : p.status === 'wait' ? 'در انتظار' : 'رد / وتو'}`}
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${c}`}
              >
                <span className="font-black">{p.k}</span>
                <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
              </span>
            );
          })}
          {symbolLevels && (
            <span className={`ms-auto inline-flex flex-wrap items-center gap-2 rounded-lg border px-2.5 py-1 font-mono tabular-nums ${
              isLight ? 'border-slate-300 bg-white text-slate-800' : 'border-border-c/70 bg-bg-card text-text-primary'
            }`}>
              <span title="قیمت آخرین معامله">قیمت: {symbolLevels.price != null ? toFaDigits(symbolLevels.price) : '—'}</span>
              <span title="ورود: شکست مقاومت جت یا پولبک به تاز حمایتی">
                ورود: {symbolLevels.entry != null ? toFaDigits(symbolLevels.entry) : '—'}
              </span>
              <span title="حمایت (تاز فیبو ۳۳-۴۰٪)">حمایت: {symbolLevels.support != null ? toFaDigits(symbolLevels.support) : '—'}</span>
              <span title="مقاومت (سقف جت)">مقاومت: {symbolLevels.resistance != null ? toFaDigits(symbolLevels.resistance) : '—'}</span>
              <span title="حد ضررِ موتور خروج (hard stop)">حدضرر: {symbolLevels.hardStop != null ? toFaDigits(symbolLevels.hardStop) : '—'}</span>
              {symbolLevels.exitVerdict && (
                <span title="حکمِ موتور خروج سرور" className="rounded bg-bg-secondary px-1.5 py-0.5 text-3xs text-text-secondary">
                  خروج: {symbolLevels.exitVerdict}
                </span>
              )}
            </span>
          )}
        </div>
      )}

      {/* ۲. بوم نمودار ساختاریافته راست‌به‌چپ (RTL Obsidian Canvas) */}
      {/* بوم هیچ‌وقت کوچک‌تر از یک‌به‌یک نمی‌شود؛ تنگ‌جا اسکرول افقی می‌خورد،
          نه اینکه نوشته‌ها ریز شوند (بازخورد مالک: «تا نیاز به زوم نباشد»). */}
      <div className="w-full overflow-x-auto overflow-y-hidden">
      <div
        ref={svgContainerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        className="relative mx-auto w-full min-w-[1480px] max-w-[1954px] aspect-[1480/1040] overflow-hidden cursor-grab active:cursor-grabbing select-none"
      >
        <svg
          viewBox="0 0 1480 1040"
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
          data-testid="obsidian-strategy-canvas"
        >
          <defs>
            {/* الگوی بهینه‌شده شبکه ابسیدین جهت کارایی روان و مصرف کم در سیستم‌های معمولی */}
            <pattern id="gridPatternFts" width="60" height="60" patternUnits="userSpaceOnUse">
              <rect width="60" height="60" fill="none" stroke={isLight ? 'rgba(148, 163, 184, 0.18)' : 'rgba(51, 65, 85, 0.25)'} strokeWidth="0.5" />
            </pattern>
          </defs>

          {/* پس‌زمینه بوم متناسب با تم */}
          <rect width="1480" height="1040" fill={isLight ? '#f8fafc' : '#070b16'} />
          <rect width="1480" height="1040" fill="url(#gridPatternFts)" />

          {/* لایه متحرک و زوم‌پذیر */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} transform-origin="740 520">
            {/* فلش راهنما در بالای بوم جهت نشان دادن جریان راست به چپ (RTL) */}
            <g className="rtl-direction-banner pointer-events-none opacity-85">
              <rect
                x="590"
                y="10"
                width="300"
                height="24"
                rx="6"
                fill={isLight ? '#e2e8f0' : '#1e293b'}
                stroke={isLight ? '#cbd5e1' : '#334155'}
                strokeWidth="0.8"
              />
              <text
                x="720"
                y="26"
                textAnchor="middle"
                className={`text-[10px] font-black ${isLight ? 'fill-slate-700' : 'fill-slate-300'}`}
              >
                {flowDirection === 'reverse'
                  ? '⬅️ جریان مهندسی معکوس (RTL): شروع از تابلوخوانی ➔ خروج در چپ'
                  : '⬅️ جریان مستقیم تحلیلی (RTL): شروع از بنیادی ➔ خروج در چپ'}
              </text>
            </g>

            {/* مرحله‌گذاریِ ستون‌ها: هر فاز یک نوارِ عمودیِ رنگی. شمارهٔ درشتِ
                کمرنگِ پشتِ هر ستون حذف شد (رأیِ مالک: مزاحمِ دید است)؛ گروه‌بندی
                از همان نوارِ رنگی و سربرگِ عنوان خوانده می‌شود. */}
            <g className="column-headers pointer-events-none">
              {columnHeaders.map((col, idx) => {
                const band = layout.bands.get(col.x);
                return (
                <g key={idx}>
                  {band && (
                    <rect
                      x={col.x - 136 - band.bow}
                      y={band.top}
                      width={272 + band.bow}
                      height={band.bottom - band.top}
                      rx="20"
                      fill={col.color}
                      fillOpacity={isLight ? 0.07 : 0.05}
                      stroke={col.color}
                      strokeOpacity={isLight ? 0.42 : 0.3}
                      strokeWidth="1.2"
                      strokeDasharray="7 7"
                    />
                  )}
                  <rect
                    x={col.x - 136}
                    y="40"
                    width="272"
                    height="28"
                    rx="8"
                    fill={isLight ? '#ffffff' : '#1e293b'}
                    fillOpacity={isLight ? 0.95 : 0.65}
                    stroke={col.color}
                    strokeOpacity={isLight ? 0.55 : 0.45}
                    strokeWidth="1.2"
                  />
                  <text
                    x={col.x}
                    y="60"
                    textAnchor="middle"
                    fill={col.color}
                    className="text-[15px] font-black"
                  >
                    {col.title}
                  </text>
                </g>
                );
              })}

              {/* سربرگ ستون مبدأ در راست */}
              <rect
                x="1230"
                y="40"
                width="240"
                height="28"
                rx="8"
                fill={isLight ? '#e0f2fe' : '#1e293b'}
                stroke={isLight ? '#38bdf8' : '#0284c7'}
                strokeWidth="1"
              />
              <text
                x="1350"
                y="60"
                textAnchor="middle"
                fill={isLight ? '#0369a1' : '#38bdf8'}
                className="text-[15px] font-black"
              >
                {flowDirection === 'reverse' ? '🎯 ورودی غربالگری' : '🌟 هسته استراتژی'}
              </text>
            </g>

            {/* خطوط و یال‌های اتصالی منحنی (Smooth Cubic Bezier Rails) */}
            <g className="links-layer">
              {links.map((link) => {
                const src = nodeMap.get(link.source);
                const tgt = nodeMap.get(link.target);
                if (!src || !tgt) return null;

                const isPresetActive =
                  selectedPreset === 'custom'
                    ? activeNodeIds.has(link.source) && activeNodeIds.has(link.target)
                    : link.presets.includes(selectedPreset);

                const isHoverIsolated =
                  hoveredNeighbors && (!hoveredNeighbors.has(link.source) || !hoveredNeighbors.has(link.target));

                let strokeColor = isLight ? 'rgba(100, 116, 139, 0.40)' : 'rgba(148, 163, 184, 0.22)';
                let strokeWidth = 1.3;
                let strokeOpacity = isLight ? 0.45 : 0.28;

                if (isPresetActive) {
                  strokeColor = src.color;
                  strokeWidth = 2.4;
                  strokeOpacity = 0.95;
                }

                if (hoveredNeighbors?.has(link.source) && hoveredNeighbors?.has(link.target)) {
                  strokeColor = '#38bdf8';
                  strokeWidth = 3.2;
                  strokeOpacity = 1;
                } else if (isHoverIsolated) {
                  strokeOpacity = 0.08;
                }

                // محاسبه منحنی افقی نرم کوبیک بزیه — رویِ مختصاتِ چیدمان‌شده
                const sp = layout.pos.get(link.source) ?? { x: src.x, y: src.y };
                const tp = layout.pos.get(link.target) ?? { x: tgt.x, y: tgt.y };
                const dx = tp.x - sp.x;
                const ctrl1X = sp.x + dx * 0.45;
                const ctrl2X = tp.x - dx * 0.45;
                const pathData = `M ${sp.x} ${sp.y} C ${ctrl1X} ${sp.y}, ${ctrl2X} ${tp.y}, ${tp.x} ${tp.y}`;

                return (
                  <g key={link.id}>
                    <path
                      d={pathData}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      strokeOpacity={strokeOpacity}
                      className="transition-all duration-200"
                    />
                    {/* جادۀ بازِ ستونِ انتخاب: هالۀ نفس‌کشنده + سه دانهٔ پلکانی */}
                    {isPresetActive && !isHoverIsolated && spineLinkIds.has(link.id) && (
                      <>
                        <path
                          d={pathData}
                          fill="none"
                          stroke={strokeColor}
                          strokeWidth={strokeWidth + 2.6}
                          strokeOpacity={0.16}
                          className="fts-path-flow"
                        />
                        {/* سه دانه رویِ خودِ منحنی، با تأخیرِ پلکانی. حرکتِ
                            هندسی (خط‌چین یا motion-path) هر فریم کلِ SVG را
                            دوباره لی‌اوت می‌کرد؛ این فقط opacity را عوض می‌کند.
                            خاموش‌کردنش دو چیز است: تنظیمِ «جریانِ مسیر» (flowOn؛
                            پیش‌فرض «همیشه») و پنجرهٔ پنه (data-hidden)؛ بی‌حرکتیِ
                            موس نه — درخت همان تبی است که بی‌دست نگاهش می‌کنند
                            (استثنا در index.css). */}
                        {flowOn &&
                          COMET_T.map((t, i) => {
                            const q = cubicAt(sp, { x: ctrl1X, y: sp.y }, { x: ctrl2X, y: tp.y }, tp, t);
                            return (
                              <circle
                                key={t}
                                cx={q.x}
                                cy={q.y}
                                r="3.4"
                                fill={strokeColor}
                                className="fts-comet"
                                style={{ animationDelay: `${(-COMET_STEP * i).toFixed(2)}s` }}
                              />
                            );
                          })}
                      </>
                    )}
                  </g>
                );
              })}
            </g>

            {/* نودها (Nodes Layer) */}
            <g className="nodes-layer">
              {nodes.map((node) => {
                const isActive = activeNodeIds.has(node.id);
                const isSelected = selectedNodeId === node.id;
                const isMatched =
                  searchQuery.trim() !== '' &&
                  (node.label.includes(searchQuery) ||
                    node.fullTitle.includes(searchQuery) ||
                    node.description.includes(searchQuery) ||
                    node.ruleFormula.includes(searchQuery));

                let opacity = 1;
                if (hoveredNeighbors) {
                  opacity = hoveredNeighbors.has(node.id) ? 1 : 0.16;
                } else if (!isActive && selectedPreset !== 'custom') {
                  opacity = isLight ? 0.38 : 0.28; // کمرنگ شدن بقیه مسیرها طبق خواسته صریح کاربر
                }

                const p = layout.pos.get(node.id) ?? { x: node.x, y: node.y };

                return (
                  <g
                    key={node.id}
                    transform={`translate(${p.x}, ${p.y})`}
                    className="cursor-pointer transition-opacity duration-200"
                    style={{ opacity }}
                    onClick={() => {
                      setSelectedNodeId(node.id);
                      if (selectedPreset === 'custom' && onToggleCustomNode && node.stage > 0) {
                        onToggleCustomNode(node.id);
                      }
                    }}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                  >
                    {/* حلقه چرخان در دور نودهای انتخاب‌شده یا جستجوشده */}
                    {(isSelected || isMatched) && (
                      <circle
                        r={node.radius + 6}
                        fill="none"
                        stroke={node.color}
                        strokeWidth="2.5"
                        strokeDasharray="4 2"
                        className="animate-spin-slow"
                      />
                    )}

                    {/* دایره اصلی نود */}
                    <circle
                      r={node.radius}
                      fill={isActive ? node.color : isLight ? '#e2e8f0' : '#1e293b'}
                      fillOpacity={isActive ? (isLight ? 0.25 : 0.35) : 0.85}
                      stroke={node.color}
                      strokeWidth={isSelected ? 3 : 1.8}
                      className="transition-colors duration-200"
                    />

                    {/* مغز داخلی نود */}
                    <circle r={node.radius * 0.4} fill={node.color} />

                    {/* پلاک عنوان نود: فوق‌العاده خوانا، عریض‌تر با فونت درشت و پرکنتراست در هر دو تم روشن و تاریک */}
                    <g transform={`translate(0, ${node.radius + 16})`} pointerEvents="none">
                      <rect
                        x="-118"
                        y="-15"
                        width="236"
                        height="30"
                        rx="9"
                        fill={isLight ? '#ffffff' : '#0b1329'}
                        fillOpacity={isLight ? 0.98 : 0.94}
                        stroke={isSelected ? node.color : isLight ? '#cbd5e1' : 'rgba(71, 85, 105, 0.85)'}
                        strokeWidth={isSelected ? '2' : '1.2'}
                      />
                      <text
                        x="0"
                        y="5"
                        textAnchor="middle"
                        fill={isLight ? '#0f172a' : '#f8fafc'}
                        className="text-[16px] font-black"
                      >
                        {node.label}
                      </text>
                    </g>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>
      </div>
      </div>

      {/* ۳. پنل جامع ویرایشگر پارامترها و بازرسی نود انتخاب‌شده (Interactive Parameter Editor) */}
      <div
        className={`border-t p-4 sm:p-5 transition-colors ${
          isLight ? 'bg-white border-slate-200 text-slate-800' : 'bg-bg-card border-border-c/80 text-text-primary'
        }`}
      >
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          {/* سمت راست: مشخصات، فرمول و توضیحات نود */}
          <div className="flex items-start gap-3.5">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg font-black shadow-md"
              style={{
                backgroundColor: `${inspectedNode.color}22`,
                border: `1.5px solid ${inspectedNode.color}77`,
                color: inspectedNode.color,
              }}
            >
              {inspectedNode.category === 'fund'
                ? 'F'
                : inspectedNode.category === 'tech'
                  ? 'T'
                  : inspectedNode.category === 'tape'
                    ? 'S'
                    : inspectedNode.category === 'money'
                      ? 'M'
                      : '★'}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className={`text-sm sm:text-base font-black ${isLight ? 'text-slate-900' : 'text-text-primary'}`}>
                  {inspectedNode.fullTitle}
                </h3>
                <span
                  className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                    isLight
                      ? 'bg-sky-50 text-sky-700 border-sky-200'
                      : 'bg-bg-primary text-accent-blue border-border-c'
                  }`}
                >
                  {inspectedNode.page}
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                    isLight
                      ? 'bg-slate-100 text-slate-600 border-slate-200'
                      : 'bg-bg-primary text-text-muted border-border-c'
                  }`}
                >
                  رکن: {inspectedNode.stageName}
                </span>
                {symbol && (
                  <span
                    className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                      isLight
                        ? 'bg-cyan-50 text-cyan-700 border-cyan-200'
                        : 'bg-bg-primary text-accent-cyan border-border-c'
                    }`}
                  >
                    نماد فعال: {symbol}
                  </span>
                )}
              </div>
              <p
                className={`text-xs max-w-3xl leading-relaxed font-medium ${
                  isLight ? 'text-slate-700' : 'text-text-secondary'
                }`}
              >
                {inspectedNode.description}
              </p>
              <div className="text-xs font-mono flex items-center gap-1.5 pt-0.5">
                <span className={`font-sans font-bold text-xs ${isLight ? 'text-slate-500' : 'text-text-muted'}`}>
                  فرمول و شرط قانون:
                </span>
                <span className={`font-bold ${isLight ? 'text-slate-900' : 'text-accent-blue'}`}>
                  {inspectedNode.ruleFormula}
                </span>
              </div>
            </div>
          </div>

          {/* سمت چپ: دکمه‌های اقدام سریع */}
          <div className="flex items-center gap-2 self-end lg:self-center shrink-0">
            {inspectedNode.editableParamKeys && inspectedNode.editableParamKeys.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  inspectedNode.editableParamKeys?.forEach((k) => resetParam(k));
                }}
                className={`rounded-xl border px-3 py-1.5 text-2xs font-bold transition-all ${
                  isLight
                    ? 'border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100'
                    : 'border-border-c/70 bg-bg-primary text-accent-yellow hover:bg-accent-yellow/15'
                }`}
                title="بازنشانی پارامترهای این نود به مقدار اصلی جزوه FTS"
              >
                ⟲ بازنشانی به جزوه
              </button>
            )}

            {selectedPreset === 'custom' && inspectedNode.stage > 0 && onToggleCustomNode && (
              <button
                type="button"
                onClick={() => onToggleCustomNode(inspectedNode.id)}
                className={`rounded-xl px-3.5 py-1.5 text-2xs font-bold transition-all ${
                  activeCustomNodes.includes(inspectedNode.id)
                    ? isLight
                      ? 'bg-rose-100 border border-rose-500 text-rose-700'
                      : 'bg-accent-red/20 border border-accent-red text-accent-red'
                    : isLight
                      ? 'bg-emerald-100 border border-emerald-500 text-emerald-700'
                      : 'bg-accent-green/20 border border-accent-green text-accent-green'
                }`}
              >
                {activeCustomNodes.includes(inspectedNode.id) ? '✕ حذف از مسیر من' : '＋ فعال در مسیر من'}
              </button>
            )}
          </div>
        </div>

        {/* ۴. کنترل‌های تعاملی تغییر مقادیر و اعداد استراتژی (Live Parameter Sliders & Inputs) */}
        {inspectedNode.editableParamKeys && inspectedNode.editableParamKeys.length > 0 && (
          <div
            className={`mt-4 pt-3.5 border-t grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 ${
              isLight ? 'border-slate-200' : 'border-border-c/60'
            }`}
          >
            {/* ۱. ضریب حجم مشکوک */}
            {inspectedNode.editableParamKeys.includes('minVolumeRatio') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ضریب حجم مشکوک:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.minVolumeRatio)} برابر
                  </span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="5.0"
                  step="0.1"
                  value={params.minVolumeRatio}
                  onChange={(e) => updateParam('minVolumeRatio', parseFloat(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵×</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۳.۰×</span>
                  <span>۵.۰×</span>
                </div>
              </div>
            )}

            {/* ۲. حداقل قدرت خریدار به فروشنده */}
            {inspectedNode.editableParamKeys.includes('minBuyerPower') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل قدرت خریدار:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.minBuyerPower)}
                  </span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="2.5"
                  step="0.05"
                  value={params.minBuyerPower}
                  onChange={(e) => updateParam('minBuyerPower', parseFloat(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۰</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱.۲</span>
                  <span>۲.۵</span>
                </div>
              </div>
            )}

            {/* ۳. حداقل درصد اختلاف الگوی ساعت */}
            {inspectedNode.editableParamKeys.includes('clockPriceDiffPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل اختلاف ساعت:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.clockPriceDiffPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="3.0"
                  step="0.1"
                  value={params.clockPriceDiffPct}
                  onChange={(e) => updateParam('clockPriceDiffPct', parseFloat(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۰.۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱.۰٪</span>
                  <span>۳.۰٪</span>
                </div>
              </div>
            )}

            {/* ۴. حداقل ارزش معاملات خرد بازار مساعد (همت) */}
            {inspectedNode.editableParamKeys.includes('marketLiquidityMinHemmat') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ارزش معاملات خرد بازار مساعد:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.marketLiquidityMinHemmat)} همت
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="40"
                  step="1"
                  value={params.marketLiquidityMinHemmat}
                  onChange={(e) => updateParam('marketLiquidityMinHemmat', parseInt(e.target.value, 10))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۵ همت</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰ همت</span>
                  <span>۴۰ همت</span>
                </div>
              </div>
            )}

            {/* ۵. دوره میانگین متحرک استاپ نوسان‌گیر */}
            {inspectedNode.editableParamKeys.includes('stopLossMaPeriod') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    دوره میانگین متحرک استاپ:
                  </span>
                  <span className="text-xs font-black text-rose-600 dark:text-accent-red font-mono">
                    MA-{toFaDigits(params.stopLossMaPeriod)}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[10, 14, 20].map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => updateParam('stopLossMaPeriod', period)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.stopLossMaPeriod === period
                          ? isLight
                            ? 'bg-rose-100 border border-rose-500 text-rose-700'
                            : 'bg-accent-red/20 border border-accent-red text-accent-red'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      MA-{toFaDigits(period)} {period === 14 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۶. درصد حد ضرر ثابت از قیمت ورود */}
            {inspectedNode.editableParamKeys.includes('stopLossFixedPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    درصد حد ضرر ثابت:
                  </span>
                  <span className="text-xs font-black text-rose-600 dark:text-accent-red font-mono">
                    {toFaDigits(params.stopLossFixedPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="2.0"
                  max="10.0"
                  step="0.5"
                  value={params.stopLossFixedPct}
                  onChange={(e) => updateParam('stopLossFixedPct', parseFloat(e.target.value))}
                  className="w-full accent-rose-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۲٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۵٪</span>
                  <span>۱۰٪</span>
                </div>
              </div>
            )}

            {/* ۷. حداقل حاشیه سود ناخالص کدال */}
            {inspectedNode.editableParamKeys.includes('minGrossMarginPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل حاشیه سود ناخالص:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.minGrossMarginPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="40"
                  step="1"
                  value={params.minGrossMarginPct}
                  onChange={(e) => updateParam('minGrossMarginPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰٪ (سوپر ۳۰٪)</span>
                  <span>۴۰٪</span>
                </div>
              </div>
            )}

            {/* ۸. حداقل درصد رشد فروش ماهانه کدال */}
            {inspectedNode.editableParamKeys.includes('minMonthlySalesGrowthPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل رشد فروش ماهانه:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.minMonthlySalesGrowthPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="60"
                  step="5"
                  value={params.minMonthlySalesGrowthPct}
                  onChange={(e) => updateParam('minMonthlySalesGrowthPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۴۰٪</span>
                  <span>۶۰٪</span>
                </div>
              </div>
            )}

            {/* ۹. درصدِ فروش در اولین سقف — جزوه: «سیگنال فروش ٪۵۰» */}
            {inspectedNode.editableParamKeys.includes('exitHalfPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    درصد فروش در اولین سقف:
                  </span>
                  <span className="text-xs font-black text-sky-600 dark:text-accent-blue font-mono">
                    {toFaDigits(params.exitHalfPct)}٪
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5">
                  {[30, 50, 70, 100].map((pct) => (
                    <button
                      key={pct}
                      type="button"
                      onClick={() => updateParam('exitHalfPct', pct)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.exitHalfPct === pct
                          ? isLight
                            ? 'bg-sky-100 border border-sky-500 text-sky-700'
                            : 'bg-accent-blue/20 border border-accent-blue text-accent-blue'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(pct)}٪ {pct === 50 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۱۰. آستانه سقف سوم خروج (هفتگی ۱۰٪ و روزانه ۵٪) */}
            {inspectedNode.editableParamKeys.includes('thirdPeakWeeklyPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    فاصله تا خط روند در سقف ۳:
                  </span>
                  <span className="text-xs font-black text-orange-600 dark:text-orange-400 font-mono">
                    هفتگی {toFaDigits(params.thirdPeakWeeklyPct)}٪ | روزانه {toFaDigits(params.thirdPeakDailyPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="20"
                  step="1"
                  value={params.thirdPeakWeeklyPct}
                  onChange={(e) => updateParam('thirdPeakWeeklyPct', parseInt(e.target.value, 10))}
                  className="w-full accent-orange-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱۰٪ هفتگی</span>
                  <span>۲۰٪</span>
                </div>
              </div>
            )}

            {/* ۱۱. سقف کل دارایی در بورس و شرایط جنگی */}
            {inspectedNode.editableParamKeys.includes('maxTotalPortfolioCapPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    سقف بورس عادی / جنگی:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.maxTotalPortfolioCapPct)}٪ / {toFaDigits(params.warConditionCapPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="40"
                  max="90"
                  step="5"
                  value={params.maxTotalPortfolioCapPct}
                  onChange={(e) => updateParam('maxTotalPortfolioCapPct', parseInt(e.target.value, 10))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۴۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۷۰٪ بورس (۱۵٪ جنگی)</span>
                  <span>۹۰٪</span>
                </div>
              </div>
            )}

            {/* ۱۲. حداقل نسبت ریسک به ریوارد */}
            {inspectedNode.editableParamKeys.includes('minRiskRewardRatio') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل نسبت سود به ریسک:
                  </span>
                  <span className="text-xs font-black text-purple-600 dark:text-purple-400 font-mono">
                    {toFaDigits(params.minRiskRewardRatio)}
                  </span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="3.5"
                  step="0.1"
                  value={params.minRiskRewardRatio}
                  onChange={(e) => updateParam('minRiskRewardRatio', parseFloat(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">پیش‌فرضِ برنامه: ۲.۰</span>
                  <span>۳.۵</span>
                </div>
              </div>
            )}

            {/* ۱۳. سقف وزن سرمایه‌گذاری در هر صنعت */}
            {inspectedNode.editableParamKeys.includes('maxIndustryWeightPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    سقف سرمایه‌گذاری در صنعت:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.maxIndustryWeightPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="35"
                  step="5"
                  value={params.maxIndustryWeightPct}
                  onChange={(e) => updateParam('maxIndustryWeightPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰٪</span>
                  <span>۳۵٪</span>
                </div>
              </div>
            )}

            {/* ۱۴. ضریب اهرم خرید کف ساعت شنی */}
            {inspectedNode.editableParamKeys.includes('hourglassLeverageMultiplier') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ضریب اهرم خرید در کف:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.hourglassLeverageMultiplier)} برابر
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[2.0, 3.0, 4.0].map((mul) => (
                    <button
                      key={mul}
                      type="button"
                      onClick={() => updateParam('hourglassLeverageMultiplier', mul)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.hourglassLeverageMultiplier === mul
                          ? isLight
                            ? 'bg-amber-100 border border-amber-500 text-amber-700'
                            : 'bg-accent-yellow/20 border border-accent-yellow text-accent-yellow'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(mul)}× {mul === 3.0 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۱۵. فرصت روزهای تثبیت ستاپ جت */}
            {inspectedNode.editableParamKeys.includes('jetStabilizationDays') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    فرصت تثبیت ستاپ جت:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.jetStabilizationDays)} روز
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[1, 3, 5].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => updateParam('jetStabilizationDays', d)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.jetStabilizationDays === d
                          ? isLight
                            ? 'bg-cyan-100 border border-cyan-500 text-cyan-700'
                            : 'bg-neon-cyan/20 border border-neon-cyan text-neon-cyan'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(d)} روز {d === 3 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
