// features/master/components/ObsidianStrategyGraph.tsx -- گراف شبکه‌ای بهینه‌شده، روان و مرتب سبک ابسیدین
// یکپارچه‌سازی ۴ صفحه چارت FTS با قابلیت ویرایش زنده مقادیر و پارامترهای استراتژی
import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useStrategyParamsStore, type StrategyParameters, FTS_DEFAULT_PARAMS } from '../stores/strategyParamsStore';

export type GraphCategory = 'core' | 'fund' | 'tech' | 'tape' | 'money';

export interface StrategyGraphNode {
  id: string;
  label: string;
  fullTitle: string;
  category: GraphCategory;
  stage: number; // 0: Core, 1: Fundamental, 2: Technical, 3: Tape, 4: Money
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
  isCross?: boolean;
}

// ساختار ۲۶ نود در ۵ ستون منظم، خوانا و بدون هیچ‌گونه تداخل متنی
function getBaseNodes(params: StrategyParameters): StrategyGraphNode[] {
  return [
    // ─── ستون ۰: هسته استراتژی FTS ───
    {
      id: 'fts_core',
      label: '🌟 استراتژی جامع FTS',
      fullTitle: 'متدولوژی سه‌گانه FTS (عرفان نصرتی)',
      category: 'core',
      stage: 0,
      stageName: 'هسته متدولوژی',
      page: 'صفحه ۱ تا ۴',
      description: 'هماهنگی همزمان ۳ فیلتر: بنیادی کدال (F)، تکنیکال دو زمانه (T)، و تابلوخوانی و زمان‌سنج ورود (S) به همراه مدیریت سرمایه.',
      ruleFormula: 'F (Fundamental) + T (Technical) + S (Selection) + Risk Management',
      badge: 'هسته مرکزی',
      color: '#38bdf8',
      radius: 28,
      x: 90,
      y: 390,
    },

    // ─── ستون ۱: فاز بنیادی F (صفحه ۱ جزوه) ───
    {
      id: 'fund_super',
      label: `💎 سوپربنیادی (رشد > ${toFaDigits(params.minMonthlySalesGrowthPct)}٪)`,
      fullTitle: 'نماد سوپربنیادی شاخص‌ساز (امتیاز ۵ از ۵)',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: `رشد فروش ماهانه کدال بیش از ${toFaDigits(params.minMonthlySalesGrowthPct)}٪، سودآوری ۳ ساله متوالی، حاشیه سود > ۳۰٪، بدون نرخ دستوری.`,
      ruleFormula: `فروش > ${params.minMonthlySalesGrowthPct}٪ | EPS ۳ ساله | حاشیه > ۳۰٪ | بدون قیمت‌گذاری دستوری`,
      badge: '۵ از ۵ FTS',
      color: '#22c55e',
      radius: 20,
      x: 350,
      y: 150,
      editableParamKeys: ['minMonthlySalesGrowthPct', 'excludePriceControlled'],
    },
    {
      id: 'fund_good',
      label: `بنیادی مطلوب (حاشیه > ${toFaDigits(params.minGrossMarginPct)}٪)`,
      fullTitle: 'بنیادی مطلوب و تایید ورود روندی (۴ از ۵)',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: `رشد فروش ماهانه و سودآوری ۳ ساله، حاشیه سود ناخالص بالای ${toFaDigits(params.minGrossMarginPct)}٪؛ مناسب سرمایه‌گذاری بالای ۳ ماه.`,
      ruleFormula: `حاشیه سود > ${params.minGrossMarginPct}٪ + رشد فروش کدال`,
      badge: 'تایید روندی',
      color: '#10b981',
      radius: 19,
      x: 350,
      y: 280,
      editableParamKeys: ['minGrossMarginPct', 'minFundScore'],
    },
    {
      id: 'fund_medium',
      label: 'بنیادی متوسط (فقط نوسانی)',
      fullTitle: 'بنیادی متوسط؛ صرفاً مجاز برای نوسان‌گیری (۳ از ۵)',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'فاقد سودآوری ۳ ساله اما دارای رشد فروش فصلی؛ طبق صفحه ۱ جزوه صرفاً نوسان‌گیری با ستاپ جت مجاز است.',
      ruleFormula: 'امتیاز ۳ از ۵ | ورود روندی بلندمدت اکیداً ممنوع',
      badge: 'صرفاً نوسان‌گیر',
      color: '#eab308',
      radius: 18,
      x: 350,
      y: 420,
      editableParamKeys: ['minFundScore'],
    },
    {
      id: 'fund_weak',
      label: '⛔ رد صلب بنیادی (وتو)',
      fullTitle: 'رد بنیادی (صنایع دستوری یا حاشیه سود زیر ۲۰٪)',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'چارت صفحه ۱',
      description: 'صنایع مشمول قیمت‌گذاری دستوری شدید (خودرو/قطعات)، زیان‌ده یا حاشیه سود زیر ۲۰٪؛ معامله اکیداً ممنوع.',
      ruleFormula: 'حاشیه سود < ۲۰٪ یا نرخ دستوری شدید -> وتوی قطعی',
      badge: 'توقف ورود',
      color: '#ef4444',
      radius: 18,
      x: 350,
      y: 560,
      editableParamKeys: ['excludePriceControlled', 'minGrossMarginPct'],
    },
    {
      id: 'crit_sales_growth',
      label: `رشد ماهانه کدال (${toFaDigits(params.minMonthlySalesGrowthPct)}٪+)`,
      fullTitle: 'شاخص ۱: رشد فروش ماهانه نسبت به سال قبل',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'صفحه ۱',
      description: 'گزارش فعالیت ماهانه در سامانه کدال؛ رشد فروش تجمیعی نسبت به دوره مشابه سال قبل.',
      ruleFormula: `رشد فروش کدال >= ${params.minMonthlySalesGrowthPct}٪`,
      badge: 'شاخص ۱',
      color: '#10b981',
      radius: 14,
      x: 480,
      y: 200,
      editableParamKeys: ['minMonthlySalesGrowthPct'],
    },
    {
      id: 'crit_3y_eps',
      label: 'سودآوری مستمر ۳ ساله',
      fullTitle: 'شاخص ۲: سودآوری ۳ ساله بدون زیان انباشته',
      category: 'fund',
      stage: 1,
      stageName: 'بنیادی F',
      page: 'صفحه ۱',
      description: 'روند سود خالص (EPS) شرکت در ۳ سال گذشته صعودی و پایدار بوده و فاقد زیان انباشته باشد.',
      ruleFormula: 'EPS سال ۱ < سال ۲ < سال ۳ | سوددهی مستمر',
      badge: 'شاخص ۲',
      color: '#10b981',
      radius: 14,
      x: 480,
      y: 350,
    },

    // ─── ستون ۲: فاز تکنیکال دو زمانه T (صفحه ۲ جزوه) ───
    {
      id: 'tech_weekly_up',
      label: '📈 تایم هفتگی صعودی (تایید ماژور)',
      fullTitle: 'تاییدیه روند ماژور هفتگی (شرط لازم ورود)',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'سقف‌ها و کف‌های بالاتر در تایم هفتگی؛ کندل‌ها بالای میانگین متحرک هفتگی (EMA20) و مکدی صعودی.',
      ruleFormula: 'هفتگی صعودی = مجوز ورود به ستاپ‌های روزانه',
      badge: 'مجوز ورود',
      color: '#22c55e',
      radius: 20,
      x: 680,
      y: 130,
    },
    {
      id: 'tech_weekly_reject',
      label: '⛔ ریجکت هفتگی (وتوی قطعی)',
      fullTitle: 'ریجکت صلب در روند هفتگی نزولی یا خنثی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'طبق صفحه ۲ جزوه، در صورت نزولی یا خنثی بودن تایم هفتگی، ورود به سهم اکیداً وتو و ممنوع است.',
      ruleFormula: 'هفتگی نزولی -> وتوی صلب کلیه ستاپ‌های روزانه',
      badge: 'وتوی قطعی',
      color: '#ef4444',
      radius: 17,
      x: 680,
      y: 230,
    },
    {
      id: 'tech_weekly_hourglass',
      label: `⏳ کف هفتگی ساعت شنی (RSI < ${toFaDigits(params.hourglassWeeklyRsi)})`,
      fullTitle: 'اشباع فروش عمیق در کف تاریخی هفتگی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'صفحه ۲ و ۴',
      description: `قیمت در تایم هفتگی زیر MA-52 و شاخص RSI زیر ${toFaDigits(params.hourglassWeeklyRsi)}؛ موقعیت خرید سنگین به دید ۳ تا ۱۰ سال.`,
      ruleFormula: `هفتگی زیر MA=52 + شاخص RSI <= ${params.hourglassWeeklyRsi}`,
      badge: 'اهرم خرید کف',
      color: '#eab308',
      radius: 18,
      x: 680,
      y: 330,
      editableParamKeys: ['hourglassWeeklyRsi', 'hourglassLeverageMultiplier'],
    },
    {
      id: 'setup_jet',
      label: `🚀 ستاپ جت (تثبیت ${toFaDigits(params.jetStabilizationDays)} روزه)`,
      fullTitle: 'استراتژی پرتاب جت و شکست مقاومت استاتیک',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: `عبور از سقف تاریخی با کندل ماروبوزو؛ تا ${toFaDigits(params.jetStabilizationDays)} روز فرصت ورود پله‌ای روی پولبک و تثبیت وجود دارد.`,
      ruleFormula: `شکست سقف تاریخی/استاتیک + تثبیت ${params.jetStabilizationDays} روزه`,
      badge: 'ستاپ پرتاب',
      color: '#06b6d4',
      radius: 19,
      x: 680,
      y: 440,
      editableParamKeys: ['jetStabilizationDays'],
    },
    {
      id: 'setup_fib',
      label: `📐 ستاپ فیبوناچی (${toFaDigits(params.fibStep1Level)}٪ و ${toFaDigits(params.fibStep2Level)}٪)`,
      fullTitle: 'پله‌های اصلاحی فیبوناچی در روند صعودی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: `پله اول در تراز ${toFaDigits(params.fibStep1Level)}٪ و پله دوم در تراز ${toFaDigits(params.fibStep2Level)}٪؛ اصلاح سالم بدون شکست روند صعودی.`,
      ruleFormula: `پله ۱: تراز ${params.fibStep1Level}٪ | پله ۲: تراز ${params.fibStep2Level}٪`,
      badge: 'پله‌های ورود',
      color: '#38bdf8',
      radius: 18,
      x: 680,
      y: 550,
      editableParamKeys: ['fibStep1Level', 'fibStep2Level'],
    },
    {
      id: 'setup_choch',
      label: '🔄 تغییر ساختار CHoCH / کف دوقلو',
      fullTitle: 'ستاپ بازگشتی تغییر ساختار یا الگوی کف دوقلو',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'چارت صفحه ۲',
      description: 'شکست آخرین سقف در روند نزولی مینور (Change of Character) یا شکست خط گردن الگوی کف دوقلو.',
      ruleFormula: 'شکست آخرین سقف نزولی (CHoCH) + پولبک تاییدکننده',
      badge: 'الگوی بازگشتی',
      color: '#a855f7',
      radius: 18,
      x: 680,
      y: 650,
    },
    {
      id: 'setup_point_hunt',
      label: '🎯 ستاپ شکار نقطه حمایت',
      fullTitle: 'نقطه‌زنی در کف سوم یا پنجم کانال صعودی',
      category: 'tech',
      stage: 2,
      stageName: 'تکنیکال T',
      page: 'صفحه ۲ و ۳',
      description: 'واکنش دقیق قیمت به کف سوم یا پنجم کانال یا خط روند ماژور همزمان با کاهش فشار عرضه.',
      ruleFormula: 'برخورد به کف کانال + کندل چکشی یا تاییدیه برگشت',
      badge: 'نقطه‌زنی',
      color: '#38bdf8',
      radius: 15,
      x: 680,
      y: 740,
    },

    // ─── ستون ۳: فاز تابلوخوانی و زمان‌سنج S (صفحه ۳ جزوه) ───
    {
      id: 'tape_clock',
      label: `⏰ الگوی ساعت (${toFaDigits(params.clockPriceDiffPct)}٪+)`,
      fullTitle: 'الگوی ساعت FTS: اختلاف قیمت آخرین از پایانی',
      category: 'tape',
      stage: 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: `قیمت آخرین معامله حداقل ${toFaDigits(params.clockPriceDiffPct)}٪ بالاتر از پایانی (بهترین حالت: پایانی منفی و آخرین مثبت)؛ زمان‌سنج ورود قطعی.`,
      ruleFormula: `(آخرین - پایانی) / پایانی >= ${params.clockPriceDiffPct}٪`,
      badge: 'زمان‌سنج ورود',
      color: '#22c55e',
      radius: 20,
      x: 990,
      y: 160,
      editableParamKeys: ['clockPriceDiffPct', 'clockStrictNegativeClose'],
    },
    {
      id: 'tape_volume',
      label: `🌊 حجم مشکوک (${toFaDigits(params.minVolumeRatio)}×)`,
      fullTitle: 'حجم مشکوک معاملات و ورود پول هوشمند',
      category: 'tape',
      stage: 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: `حجم روزانه حداقل ${toFaDigits(params.minVolumeRatio)} برابر میانگین ۲۱ روزه + قدرت خریدار حقیقی بالای ${toFaDigits(params.minBuyerPower)}.`,
      ruleFormula: `حجم روز >= ${params.minVolumeRatio} × میانگین ۲۱ روزه + قدرت خریدار > ${params.minBuyerPower}`,
      badge: 'پول هوشمند',
      color: '#06b6d4',
      radius: 19,
      x: 990,
      y: 290,
      editableParamKeys: ['minVolumeRatio', 'minBuyerPower'],
    },
    {
      id: 'tape_breakout',
      label: '📦 خروج از باکس رنج (Breakout)',
      fullTitle: 'شکست سقف کانال تراکم قیمت در تابلو',
      category: 'tape',
      stage: 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'شکست سقف تراکم با کندل پرقدرت و پر شدن حجم مبنا + ورود پرقدرت پول حقیقی.',
      ruleFormula: 'شکست سقف باکس رنج + جهش ارزش معاملات خرد',
      badge: 'آغاز شتاب',
      color: '#38bdf8',
      radius: 18,
      x: 990,
      y: 420,
    },
    {
      id: 'tape_floor_sweep',
      label: '🧹 کف‌روبی و جمع‌آوری صف',
      fullTitle: 'بلعیدن صف فروش و خشک کردن عرضه',
      category: 'tape',
      stage: 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'صف فروش توسط کدهای درشت بلعیده می‌شود؛ یا حجم فروشنده‌ها کاملاً به صفر میل کرده است.',
      ruleFormula: 'جمع‌آوری صف فروش با اردرهای سنگین یا خشک شدن فروشنده',
      badge: 'جمع‌آوری صف',
      color: '#a855f7',
      radius: 17,
      x: 990,
      y: 550,
    },
    {
      id: 'tape_smart_money',
      label: '💳 ورود پول از فیکس به سهام',
      fullTitle: 'خروج نقدینگی از صندوق‌های درآمد ثابت به سهم',
      category: 'tape',
      stage: 3,
      stageName: 'تابلوخوانی S',
      page: 'چارت صفحه ۳',
      description: 'جریان نقدینگی منفی صندوق‌های حامی/فیکس و تزریق سرمایه به سهام برگزیده و پیشرو.',
      ruleFormula: 'خروج پول از صندوق درآمد ثابت + ورود مستقیم به سهم',
      badge: 'جریان نقدینگی',
      color: '#10b981',
      radius: 15,
      x: 990,
      y: 670,
    },

    // ─── ستون ۴: فاز مدیریت سرمایه و خروج M (صفحه ۴ جزوه) ───
    {
      id: 'stop_swing',
      label: `🛑 حد ضرر نوسان‌گیر (MA-${toFaDigits(params.stopLossMaPeriod)} یا ${toFaDigits(params.stopLossFixedPct)}٪)`,
      fullTitle: 'حد ضرر صلب نوسان‌گیر (استاپ تکنیکالی)',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)} یا افت ${toFaDigits(params.stopLossFixedPct)}٪ زیر قیمت ورود؛ خروج قطعی و بدون درنگ.`,
      ruleFormula: `کندل زیر MA=${params.stopLossMaPeriod} یا افت ${params.stopLossFixedPct}٪ -> خروج فوری`,
      badge: 'استاپ تکنیکالی',
      color: '#ef4444',
      radius: 20,
      x: 1290,
      y: 160,
      editableParamKeys: ['stopLossMaPeriod', 'stopLossFixedPct'],
    },
    {
      id: 'stop_trend',
      label: `🛡️ حد ضرر بنیادی روندگیر (کدال)`,
      fullTitle: 'حد ضرر بنیادی روندگیر در صورت‌های مالی',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `روندگیر حد ضرر تکنیکالی ندارد؛ حد ضرر در کدال است: افت حاشیه سود به زیر ${toFaDigits(params.minGrossMarginPct)}٪ یا توقف رشد فروش ماهانه.`,
      ruleFormula: `افت حاشیه سود < ${params.minGrossMarginPct}٪ یا توقف رشد فروش کدال -> تعویض سهم`,
      badge: 'استاپ کدالی',
      color: '#22c55e',
      radius: 20,
      x: 1290,
      y: 290,
      editableParamKeys: ['minGrossMarginPct', 'minMonthlySalesGrowthPct'],
    },
    {
      id: 'stop_hourglass',
      label: `⏳ اهرم ساعت شنی (${toFaDigits(params.hourglassLeverageMultiplier)}× کف)`,
      fullTitle: 'پله‌بندی سنگین اهرمی در کف تاریخی به دید ۳ تا ۱۰ سال',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `در اشباع کف تاریخی، حجم پله ${toFaDigits(params.hourglassLeverageMultiplier)} برابر حجم عادی افزایش می‌یابد؛ بدون حد ضرر کوتاه‌مدت.`,
      ruleFormula: `ضریب حجم ورود: ${params.hourglassLeverageMultiplier}× پله عادی | افق ۳ تا ۱۰ ساله`,
      badge: 'اهرم بلندمدت',
      color: '#eab308',
      radius: 18,
      x: 1290,
      y: 420,
      editableParamKeys: ['hourglassLeverageMultiplier', 'hourglassWeeklyRsi'],
    },
    {
      id: 'exit_half',
      label: `💰 ذخیره سود ${toFaDigits(params.exitHalfPct)}٪ FTS`,
      fullTitle: 'فروش ۵۰٪ در مقاومت اول R1 جهت بدون ریسک شدن',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۲ و ۴',
      description: `در برخورد با مقاومت اول R1، دقیقاً ${toFaDigits(params.exitHalfPct)}٪ سهم فروخته می‌شود تا اصل پول آزاد و معامله بدون ریسک شود.`,
      ruleFormula: `رسیدن به مقاومت R1 -> فروش دقیق ${params.exitHalfPct}٪ دارایی سهم`,
      badge: 'خروج اصل پول',
      color: '#38bdf8',
      radius: 19,
      x: 1290,
      y: 540,
      editableParamKeys: ['exitHalfPct'],
    },
    {
      id: 'rule_rr',
      label: `⚖️ ریسک به ریوارد (R/R > ${toFaDigits(params.minRiskRewardRatio)})`,
      fullTitle: 'الزام نسبت سود به ریسک حداقل ۱ به ۲',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `فاصله تا تارگت سود باید حداقل ${toFaDigits(params.minRiskRewardRatio)} برابر فاصله تا حد ضرر باشد.`,
      ruleFormula: `(تارگت سود - ورود) / (ورود - حد ضرر) >= ${params.minRiskRewardRatio}`,
      badge: 'ریسک به ریوارد',
      color: '#a855f7',
      radius: 16,
      x: 1290,
      y: 650,
      editableParamKeys: ['minRiskRewardRatio'],
    },
    {
      id: 'rule_cap',
      label: `📊 سقف وزن صنعت (${toFaDigits(params.maxIndustryWeightPct)}٪)`,
      fullTitle: 'سقف سرمایه‌گذاری مجاز در یک صنعت',
      category: 'money',
      stage: 4,
      stageName: 'مدیریت سرمایه M',
      page: 'چارت صفحه ۴',
      description: `مجموع وزن تمام نمادهای یک صنعت نباید از ${toFaDigits(params.maxIndustryWeightPct)}٪ کل سبد دارایی تجاوز کند.`,
      ruleFormula: `مجموع سرمایه در صنعت <= ${params.maxIndustryWeightPct}٪ کل سبد`,
      badge: 'سقف صنعت',
      color: '#10b981',
      radius: 15,
      x: 1290,
      y: 740,
      editableParamKeys: ['maxIndustryWeightPct', 'singleStockMaxWeightPct'],
    },
  ];
}

// اتصالات پیوسته افقی از ستون به ستون (بدون درهم‌تنیدگی)
const LINKS: StrategyGraphLink[] = [
  // اتصال هسته مرکزی به شاخه‌های فاز ۱ (بنیادی)
  { id: 'l_core_super', source: 'fts_core', target: 'fund_super', presets: ['trend', 'hourglass'] },
  { id: 'l_core_good', source: 'fts_core', target: 'fund_good', presets: ['swing', 'trend'] },
  { id: 'l_core_medium', source: 'fts_core', target: 'fund_medium', presets: ['swing'] },
  { id: 'l_core_weak', source: 'fts_core', target: 'fund_weak', presets: [] },

  // زیرشاخه‌های بنیادی
  { id: 'l_super_sales', source: 'fund_super', target: 'crit_sales_growth', presets: ['trend'] },
  { id: 'l_super_eps', source: 'fund_super', target: 'crit_3y_eps', presets: ['trend', 'hourglass'] },
  { id: 'l_good_sales', source: 'fund_good', target: 'crit_sales_growth', presets: ['trend'] },

  // فاز ۱ (بنیادی) ➔ فاز ۲ (تکنیکال)
  { id: 'l_f_super_tech', source: 'fund_super', target: 'tech_weekly_up', presets: ['trend'] },
  { id: 'l_f_super_hg', source: 'fund_super', target: 'tech_weekly_hourglass', presets: ['hourglass'] },
  { id: 'l_f_good_tech', source: 'fund_good', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
  { id: 'l_f_med_tech', source: 'fund_medium', target: 'tech_weekly_up', presets: ['swing'] },
  { id: 'l_f_weak_reject', source: 'fund_weak', target: 'tech_weekly_reject', presets: [] },

  // فاز ۲: هفتگی صعودی به ستاپ‌های روزانه
  { id: 'l_t_up_jet', source: 'tech_weekly_up', target: 'setup_jet', presets: ['swing'] },
  { id: 'l_t_up_fib', source: 'tech_weekly_up', target: 'setup_fib', presets: ['swing', 'trend'] },
  { id: 'l_t_up_choch', source: 'tech_weekly_up', target: 'setup_choch', presets: ['trend'] },
  { id: 'l_t_up_hunt', source: 'tech_weekly_up', target: 'setup_point_hunt', presets: ['swing'] },

  // فاز ۲ (تکنیکال) ➔ فاز ۳ (تابلوخوانی)
  { id: 'l_t_jet_clock', source: 'setup_jet', target: 'tape_clock', presets: ['swing'] },
  { id: 'l_t_jet_vol', source: 'setup_jet', target: 'tape_volume', presets: ['swing'] },
  { id: 'l_t_fib_clock', source: 'setup_fib', target: 'tape_clock', presets: ['swing', 'trend'] },
  { id: 'l_t_fib_box', source: 'setup_fib', target: 'tape_breakout', presets: ['trend'] },
  { id: 'l_t_choch_vol', source: 'setup_choch', target: 'tape_volume', presets: ['trend'] },
  { id: 'l_t_choch_smart', source: 'setup_choch', target: 'tape_smart_money', presets: ['trend'] },
  { id: 'l_t_hg_sweep', source: 'tech_weekly_hourglass', target: 'tape_floor_sweep', presets: ['hourglass'] },
  { id: 'l_t_hunt_sweep', source: 'setup_point_hunt', target: 'tape_floor_sweep', presets: ['swing'] },

  // فاز ۳ (تابلوخوانی) ➔ فاز ۴ (مدیریت سرمایه و خروج)
  { id: 'l_s_clock_stopswing', source: 'tape_clock', target: 'stop_swing', presets: ['swing'] },
  { id: 'l_s_vol_stopswing', source: 'tape_volume', target: 'stop_swing', presets: ['swing'] },
  { id: 'l_s_vol_stoptrend', source: 'tape_volume', target: 'stop_trend', presets: ['trend'] },
  { id: 'l_s_box_stoptrend', source: 'tape_breakout', target: 'stop_trend', presets: ['trend'] },
  { id: 'l_s_sweep_hg', source: 'tape_floor_sweep', target: 'stop_hourglass', presets: ['hourglass'] },
  { id: 'l_s_smart_stoptrend', source: 'tape_smart_money', target: 'stop_trend', presets: ['trend'] },

  // اتصالات خروج و مدیریت ریسک
  { id: 'l_m_swing_exit', source: 'stop_swing', target: 'exit_half', presets: ['swing'] },
  { id: 'l_m_trend_exit', source: 'stop_trend', target: 'exit_half', presets: ['trend'] },
  { id: 'l_m_exit_rr', source: 'exit_half', target: 'rule_rr', presets: ['swing', 'trend'] },
  { id: 'l_m_trend_cap', source: 'stop_trend', target: 'rule_cap', presets: ['trend'] },
  { id: 'l_m_hg_cap', source: 'stop_hourglass', target: 'rule_cap', presets: ['hourglass'] },
];

export interface ObsidianStrategyGraphProps {
  selectedPreset: 'swing' | 'trend' | 'hourglass' | 'custom';
  onSelectPreset: (preset: 'swing' | 'trend' | 'hourglass' | 'custom') => void;
  symbol?: string;
  activeCustomNodes?: string[];
  onToggleCustomNode?: (nodeId: string) => void;
}

export function ObsidianStrategyGraph({
  selectedPreset,
  onSelectPreset,
  symbol,
  activeCustomNodes = [],
  onToggleCustomNode,
}: ObsidianStrategyGraphProps) {
  const { params, updateParam, resetParam, resetAll } = useStrategyParamsStore();
  const nodes = useMemo(() => getBaseNodes(params), [params]);

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('tape_volume');
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const isDraggingRef = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const svgContainerRef = useRef<HTMLDivElement>(null);

  const nodeMap = useMemo(() => {
    const map = new Map<string, StrategyGraphNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  // نودهای فعال استراتژی جاری
  const activeNodeIds = useMemo(() => {
    if (selectedPreset === 'custom') {
      return new Set<string>(['fts_core', ...activeCustomNodes]);
    }
    const set = new Set<string>(['fts_core']);
    LINKS.forEach((link) => {
      if (link.presets.includes(selectedPreset)) {
        set.add(link.source);
        set.add(link.target);
      }
    });
    return set;
  }, [selectedPreset, activeCustomNodes]);

  // همسایگان نود هاور شده (Hover Focus)
  const hoveredNeighbors = useMemo(() => {
    if (!hoveredNodeId) return null;
    const set = new Set<string>([hoveredNodeId]);
    LINKS.forEach((link) => {
      if (link.source === hoveredNodeId) set.add(link.target);
      if (link.target === hoveredNodeId) set.add(link.source);
    });
    return set;
  }, [hoveredNodeId]);

  // نود در حال بازرسی و ویرایش
  const inspectedNode = useMemo(() => {
    return nodeMap.get(selectedNodeId) || nodeMap.get('tape_volume') || nodes[0];
  }, [selectedNodeId, nodeMap, nodes]);

  // مدیریت حرکت روان Pan بدون لرزش و پرش با Mouse Down / Move روی کانتینر
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).tagName.toLowerCase() === 'input' || (e.target as HTMLElement).tagName.toLowerCase() === 'button') {
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
    setZoom((z) => Math.min(Math.max(z * factor, 0.6), 1.8));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="flex flex-col w-full rounded-2xl border border-border-c/80 bg-[#080d1a] shadow-2xl overflow-hidden">
      {/* ۱. نوار ابزار کنترل استراتژی و جستجو */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-c/60 bg-bg-card/70 px-4 py-2.5 backdrop-blur-md">
        {/* پری‌ست‌ها و حالت بازی */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-2xs font-bold text-text-muted ms-1 hidden sm:inline">مسیر استراتژی:</span>
          <button
            type="button"
            onClick={() => onSelectPreset('swing')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'swing'
                ? 'bg-accent-blue/25 border border-accent-blue text-accent-blue shadow-[0_0_8px_rgba(56,189,248,0.25)]'
                : 'border border-border-c/60 bg-bg-primary/50 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>⚡</span>
            <span>نوسان‌گیر (زیر ۳ ماه)</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectPreset('trend')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'trend'
                ? 'bg-accent-green/25 border border-accent-green text-accent-green shadow-[0_0_8px_rgba(34,197,94,0.25)]'
                : 'border border-border-c/60 bg-bg-primary/50 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>📈</span>
            <span>روندگیر (بالای ۳ ماه)</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectPreset('hourglass')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'hourglass'
                ? 'bg-accent-yellow/25 border border-accent-yellow text-accent-yellow shadow-[0_0_8px_rgba(234,179,8,0.25)]'
                : 'border border-border-c/60 bg-bg-primary/50 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>⏳</span>
            <span>ساعت شنی (۳ تا ۱۰ ساله)</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectPreset('custom')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'custom'
                ? 'bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_8px_rgba(6,182,212,0.25)]'
                : 'border border-border-c/60 bg-bg-primary/50 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>🛠</span>
            <span>مسیر من (سفارشی)</span>
          </button>
        </div>

        {/* دکمه‌های زوم، ریست و جستجو */}
        <div className="flex items-center gap-2 ms-auto flex-wrap">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 جستجو در نودها..."
              className="w-32 sm:w-40 rounded-lg border border-border-c/60 bg-bg-primary/70 px-2.5 py-1 text-2xs text-text-primary placeholder:text-text-muted focus:border-accent-blue focus:outline-none"
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

          <div className="flex items-center gap-1 border-s border-border-c/50 ps-2">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(z + 0.15, 1.8))}
              className="h-6 w-6 rounded border border-border-c/60 bg-bg-primary text-xs font-bold text-text-secondary hover:text-text-primary"
              title="بزرگ‌نمایی"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.6))}
              className="h-6 w-6 rounded border border-border-c/60 bg-bg-primary text-xs font-bold text-text-secondary hover:text-text-primary"
              title="کوچک‌نمایی"
            >
              −
            </button>
            <button
              type="button"
              onClick={handleResetView}
              className="px-2 h-6 rounded border border-border-c/60 bg-bg-primary text-3xs font-bold text-text-secondary hover:text-text-primary"
              title="ریست زاویه دید"
            >
              ⊙ نما
            </button>
          </div>

          {/* دکمه ریست کل پارامترها */}
          <button
            type="button"
            onClick={() => {
              if (window.confirm('آیا مایلید تمام تنظیمات و پارامترها به مقادیر اصلی جزوه FTS بازنشانی شوند؟')) {
                resetAll();
              }
            }}
            className="rounded-lg border border-border-c/60 bg-bg-primary/60 px-2.5 py-1 text-3xs font-bold text-accent-yellow hover:bg-accent-yellow/15 transition-colors"
            title="بازنشانی تمام پارامترها به مقادیر پیش‌فرض جزوه"
          >
            ⟲ پیش‌فرض جزوه
          </button>
        </div>
      </div>

      {/* ۲. بوم نمودار ساختاریافته سبک ابسیدین (Smooth 60FPS Pipeline Canvas) */}
      <div
        ref={svgContainerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        className="relative w-full h-[540px] sm:h-[580px] lg:h-[620px] overflow-hidden cursor-grab active:cursor-grabbing select-none"
      >
        <svg
          viewBox="0 0 1440 820"
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
          data-testid="obsidian-strategy-canvas"
        >
          <defs>
            {/* الگوی پس‌زمینه ستاره‌ای شبکه ابسیدین */}
            <pattern id="gridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="20" cy="20" r="0.8" fill="rgba(148, 163, 184, 0.14)" />
            </pattern>
          </defs>

          {/* پس‌زمینه تیره کهکشانی */}
          <rect width="1440" height="820" fill="#070b16" />
          <rect width="1440" height="820" fill="url(#gridPattern)" />

          {/* سربرگ‌های ستون‌های ۴ فاز در بالای بوم */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} transform-origin="720 410">
            {/* راهنما و ستون‌های ۵ مرحله‌ای */}
            <g className="column-headers opacity-75 pointer-events-none">
              <rect x="250" y="30" width="200" height="30" rx="8" fill="#1e293b" fillOpacity="0.5" stroke="#334155" />
              <text x="350" y="50" textAnchor="middle" className="fill-accent-green text-[12px] font-black">
                فاز ۱: فیلتر بنیادی (کدال)
              </text>

              <rect x="580" y="30" width="200" height="30" rx="8" fill="#1e293b" fillOpacity="0.5" stroke="#334155" />
              <text x="680" y="50" textAnchor="middle" className="fill-neon-cyan text-[12px] font-black">
                فاز ۲: تکنیکال دو زمانه (T)
              </text>

              <rect x="890" y="30" width="200" height="30" rx="8" fill="#1e293b" fillOpacity="0.5" stroke="#334155" />
              <text x="990" y="50" textAnchor="middle" className="fill-accent-yellow text-[12px] font-black">
                فاز ۳: تابلوخوانی و زمان‌سنج (S)
              </text>

              <rect x="1190" y="30" width="200" height="30" rx="8" fill="#1e293b" fillOpacity="0.5" stroke="#334155" />
              <text x="1290" y="50" textAnchor="middle" className="fill-accent-blue text-[12px] font-black">
                فاز ۴: مدیریت سرمایه و خروج (M)
              </text>
            </g>

            {/* خطوط و یال‌های اتصالی منحنی (Smooth Cubic Bezier Rails) */}
            <g className="links-layer">
              {LINKS.map((link) => {
                const src = nodeMap.get(link.source);
                const tgt = nodeMap.get(link.target);
                if (!src || !tgt) return null;

                const isPresetActive =
                  selectedPreset === 'custom'
                    ? activeNodeIds.has(link.source) && activeNodeIds.has(link.target)
                    : link.presets.includes(selectedPreset);

                const isHoverIsolated =
                  hoveredNeighbors && (!hoveredNeighbors.has(link.source) || !hoveredNeighbors.has(link.target));

                let strokeColor = 'rgba(148, 163, 184, 0.22)';
                let strokeWidth = 1.3;
                let strokeOpacity = 0.28;

                if (isPresetActive) {
                  strokeColor = src.color;
                  strokeWidth = 2.4;
                  strokeOpacity = 0.95;
                }

                if (hoveredNeighbors?.has(link.source) && hoveredNeighbors?.has(link.target)) {
                  strokeColor = '#38bdf8';
                  strokeWidth = 3;
                  strokeOpacity = 1;
                } else if (isHoverIsolated) {
                  strokeOpacity = 0.08;
                }

                // محاسبه منحنی افقی نرم کوبیک بزیه
                const dx = tgt.x - src.x;
                const ctrl1X = src.x + dx * 0.45;
                const ctrl2X = tgt.x - dx * 0.45;
                const pathData = `M ${src.x} ${src.y} C ${ctrl1X} ${src.y}, ${ctrl2X} ${tgt.y}, ${tgt.x} ${tgt.y}`;

                return (
                  <path
                    key={link.id}
                    d={pathData}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeOpacity={strokeOpacity}
                    className="transition-all duration-200"
                  />
                );
              })}
            </g>

            {/* نودها (Nodes Layer) */}
            <g className="nodes-layer">
              {nodes.map((node) => {
                const isActive = activeNodeIds.has(node.id);
                const isSelected = selectedNodeId === node.id;
                const isHovered = hoveredNodeId === node.id;
                const isMatched =
                  searchQuery.trim() !== '' &&
                  (node.label.includes(searchQuery) ||
                    node.fullTitle.includes(searchQuery) ||
                    node.description.includes(searchQuery));

                let opacity = 1;
                if (hoveredNeighbors) {
                  opacity = hoveredNeighbors.has(node.id) ? 1 : 0.18;
                } else if (!isActive && selectedPreset !== 'custom') {
                  opacity = 0.32; // کمرنگ شدن بقیه مسیرها طبق خواسته کاربر
                }

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
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
                    {/* حلقه بیرونی نودهای فعال یا انتخاب‌شده */}
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
                      fill={isActive ? node.color : '#1e293b'}
                      fillOpacity={isActive ? 0.35 : 0.85}
                      stroke={node.color}
                      strokeWidth={isSelected ? 3 : 1.8}
                      className="transition-colors duration-200"
                    />

                    {/* مغز داخلی نود */}
                    <circle r={node.radius * 0.4} fill={node.color} />

                    {/* پلاک عنوان نود (با پس‌زمینه خوانا جهت جلوگیری از هرگونه تداخل متنی) */}
                    <g transform={`translate(0, ${node.radius + 15})`} pointerEvents="none">
                      <rect
                        x="-70"
                        y="-11"
                        width="140"
                        height="18"
                        rx="5"
                        fill="#0b1329"
                        fillOpacity="0.88"
                        stroke={isSelected ? node.color : 'rgba(51, 65, 85, 0.6)'}
                        strokeWidth="0.8"
                      />
                      <text
                        x="0"
                        y="2"
                        textAnchor="middle"
                        className="fill-text-primary text-[10.5px] font-black"
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

        {/* راهنمای کوتاه لمسی در گوشه بوم */}
        <div className="absolute top-2 left-3 pointer-events-none rounded-lg bg-bg-card/75 border border-border-c/60 px-2.5 py-1 text-3xs text-text-muted">
          <span>🖱 درگ: حرکت در بوم | اسکرول: زوم | کلیک روی نود: ویرایش مقادیر</span>
        </div>
      </div>

      {/* ۳. پنل جامع ویرایشگر پارامترها و بازرسی نود انتخاب‌شده (Interactive Parameter Editor) */}
      <div className="border-t border-border-c/80 bg-bg-card/95 p-4 sm:p-5 backdrop-blur-xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          {/* سمت راست: مشخصات و فرمول نود */}
          <div className="flex items-start gap-3.5">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg font-black shadow-lg"
              style={{
                backgroundColor: `${inspectedNode.color}22`,
                border: `1.5px solid ${inspectedNode.color}66`,
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

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-xs sm:text-sm font-black text-text-primary">{inspectedNode.fullTitle}</h3>
                <span className="rounded bg-bg-primary px-2 py-0.5 text-3xs font-bold text-accent-blue border border-border-c">
                  {inspectedNode.page}
                </span>
                <span className="rounded bg-bg-primary px-2 py-0.5 text-3xs font-bold text-text-muted">
                  رکن: {inspectedNode.stageName}
                </span>
                {symbol && (
                  <span className="rounded bg-bg-primary px-2 py-0.5 text-3xs font-bold text-accent-cyan border border-border-c">
                    نماد فعال: {symbol}
                  </span>
                )}
              </div>
              <p className="text-2xs text-text-muted max-w-3xl leading-relaxed">{inspectedNode.description}</p>
              <div className="text-3xs text-text-secondary font-mono flex items-center gap-1 pt-0.5">
                <span className="text-text-muted font-sans font-bold">فرمول و شرط:</span>
                <span>{inspectedNode.ruleFormula}</span>
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
                className="rounded-xl border border-border-c/70 bg-bg-primary px-3 py-1.5 text-2xs font-bold text-accent-yellow hover:bg-accent-yellow/15 transition-all"
                title="بازنشانی پارامترهای این نود به مقدار اصلی جزوه"
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
                    ? 'bg-accent-red/20 border border-accent-red text-accent-red'
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
          <div className="mt-4 pt-3.5 border-t border-border-c/60 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {/* ۱. حجم مشکوک ۳ برابری */}
            {inspectedNode.editableParamKeys.includes('minVolumeRatio') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">ضریب حجم مشکوک:</span>
                  <span className="text-xs font-black text-neon-cyan font-mono">{toFaDigits(params.minVolumeRatio)} برابر</span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="5.0"
                  step="0.1"
                  value={params.minVolumeRatio}
                  onChange={(e) => updateParam('minVolumeRatio', parseFloat(e.target.value))}
                  className="w-full accent-neon-cyan cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵×</span>
                  <span className="text-accent-yellow">جزوه: ۳.۰×</span>
                  <span>۵.۰×</span>
                </div>
              </div>
            )}

            {/* ۲. حداقل قدرت خریدار به فروشنده */}
            {inspectedNode.editableParamKeys.includes('minBuyerPower') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">حداقل قدرت خریدار:</span>
                  <span className="text-xs font-black text-neon-cyan font-mono">{toFaDigits(params.minBuyerPower)}</span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="2.5"
                  step="0.05"
                  value={params.minBuyerPower}
                  onChange={(e) => updateParam('minBuyerPower', parseFloat(e.target.value))}
                  className="w-full accent-neon-cyan cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۰</span>
                  <span className="text-accent-yellow">جزوه: ۱.۲</span>
                  <span>۲.۵</span>
                </div>
              </div>
            )}

            {/* ۳. درصد الگوی ساعت */}
            {inspectedNode.editableParamKeys.includes('clockPriceDiffPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">حداقل اختلاف ساعت:</span>
                  <span className="text-xs font-black text-accent-green font-mono">{toFaDigits(params.clockPriceDiffPct)}٪</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="3.0"
                  step="0.1"
                  value={params.clockPriceDiffPct}
                  onChange={(e) => updateParam('clockPriceDiffPct', parseFloat(e.target.value))}
                  className="w-full accent-accent-green cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۰.۵٪</span>
                  <span className="text-accent-yellow">جزوه: ۱.۰٪</span>
                  <span>۳.۰٪</span>
                </div>
              </div>
            )}

            {/* ۴. دوره میانگین متحرک استاپ نوسان‌گیر */}
            {inspectedNode.editableParamKeys.includes('stopLossMaPeriod') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">دوره میانگین متحرک استاپ:</span>
                  <span className="text-xs font-black text-accent-red font-mono">MA-{toFaDigits(params.stopLossMaPeriod)}</span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[10, 14, 20].map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => updateParam('stopLossMaPeriod', period)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.stopLossMaPeriod === period
                          ? 'bg-accent-red/20 border border-accent-red text-accent-red'
                          : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      MA-{toFaDigits(period)} {period === 14 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۵. درصد حد ضرر ثابت از ورود */}
            {inspectedNode.editableParamKeys.includes('stopLossFixedPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">درصد حد ضرر ثابت:</span>
                  <span className="text-xs font-black text-accent-red font-mono">{toFaDigits(params.stopLossFixedPct)}٪</span>
                </div>
                <input
                  type="range"
                  min="2.0"
                  max="10.0"
                  step="0.5"
                  value={params.stopLossFixedPct}
                  onChange={(e) => updateParam('stopLossFixedPct', parseFloat(e.target.value))}
                  className="w-full accent-accent-red cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۲٪</span>
                  <span className="text-accent-yellow">جزوه: ۵٪</span>
                  <span>۱۰٪</span>
                </div>
              </div>
            )}

            {/* ۶. حداقل حاشیه سود ناخالص بنیادی */}
            {inspectedNode.editableParamKeys.includes('minGrossMarginPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">حداقل حاشیه سود ناخالص:</span>
                  <span className="text-xs font-black text-accent-green font-mono">{toFaDigits(params.minGrossMarginPct)}٪</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="40"
                  step="1"
                  value={params.minGrossMarginPct}
                  onChange={(e) => updateParam('minGrossMarginPct', parseInt(e.target.value, 10))}
                  className="w-full accent-accent-green cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-accent-yellow">جزوه: ۲۰٪ (سوپر ۳۰٪)</span>
                  <span>۴۰٪</span>
                </div>
              </div>
            )}

            {/* ۷. درصد رشد فروش ماهانه کدال */}
            {inspectedNode.editableParamKeys.includes('minMonthlySalesGrowthPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">حداقل رشد فروش ماهانه:</span>
                  <span className="text-xs font-black text-accent-green font-mono">{toFaDigits(params.minMonthlySalesGrowthPct)}٪</span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="60"
                  step="5"
                  value={params.minMonthlySalesGrowthPct}
                  onChange={(e) => updateParam('minMonthlySalesGrowthPct', parseInt(e.target.value, 10))}
                  className="w-full accent-accent-green cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۲۰٪</span>
                  <span className="text-accent-yellow">جزوه: ۴۰٪</span>
                  <span>۶۰٪</span>
                </div>
              </div>
            )}

            {/* ۸. درصد ذخیره سود ۵۰٪ FTS */}
            {inspectedNode.editableParamKeys.includes('exitHalfPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">درصد فروش در مقاومت ۱:</span>
                  <span className="text-xs font-black text-accent-blue font-mono">{toFaDigits(params.exitHalfPct)}٪</span>
                </div>
                <div className="grid grid-cols-4 gap-1.5">
                  {[30, 50, 70, 100].map((pct) => (
                    <button
                      key={pct}
                      type="button"
                      onClick={() => updateParam('exitHalfPct', pct)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.exitHalfPct === pct
                          ? 'bg-accent-blue/20 border border-accent-blue text-accent-blue'
                          : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(pct)}٪ {pct === 50 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۹. حداقل نسبت ریسک به ریوارد */}
            {inspectedNode.editableParamKeys.includes('minRiskRewardRatio') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">حداقل نسبت سود به ریسک:</span>
                  <span className="text-xs font-black text-purple-400 font-mono">{toFaDigits(params.minRiskRewardRatio)}</span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="3.5"
                  step="0.1"
                  value={params.minRiskRewardRatio}
                  onChange={(e) => updateParam('minRiskRewardRatio', parseFloat(e.target.value))}
                  className="w-full accent-purple-400 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵</span>
                  <span className="text-accent-yellow">جزوه: ۲.۰</span>
                  <span>۳.۵</span>
                </div>
              </div>
            )}

            {/* ۱۰. سقف وزن صنعت */}
            {inspectedNode.editableParamKeys.includes('maxIndustryWeightPct') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">سقف سرمایه‌گذاری هر صنعت:</span>
                  <span className="text-xs font-black text-accent-green font-mono">{toFaDigits(params.maxIndustryWeightPct)}٪</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="35"
                  step="5"
                  value={params.maxIndustryWeightPct}
                  onChange={(e) => updateParam('maxIndustryWeightPct', parseInt(e.target.value, 10))}
                  className="w-full accent-accent-green cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-accent-yellow">جزوه: ۲۰٪</span>
                  <span>۳۵٪</span>
                </div>
              </div>
            )}

            {/* ۱۱. اهرم خرید ساعت شنی */}
            {inspectedNode.editableParamKeys.includes('hourglassLeverageMultiplier') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">ضریب اهرم خرید در کف:</span>
                  <span className="text-xs font-black text-accent-yellow font-mono">{toFaDigits(params.hourglassLeverageMultiplier)} برابر</span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[2.0, 3.0, 4.0].map((mul) => (
                    <button
                      key={mul}
                      type="button"
                      onClick={() => updateParam('hourglassLeverageMultiplier', mul)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.hourglassLeverageMultiplier === mul
                          ? 'bg-accent-yellow/20 border border-accent-yellow text-accent-yellow'
                          : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(mul)}× {mul === 3.0 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۱۲. روزهای تثبیت ستاپ جت */}
            {inspectedNode.editableParamKeys.includes('jetStabilizationDays') && (
              <div className="rounded-xl border border-border-c/60 bg-bg-primary/60 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xs font-bold text-text-primary">فرصت تثبیت ستاپ جت:</span>
                  <span className="text-xs font-black text-neon-cyan font-mono">{toFaDigits(params.jetStabilizationDays)} روز</span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[1, 3, 5].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => updateParam('jetStabilizationDays', d)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.jetStabilizationDays === d
                          ? 'bg-neon-cyan/20 border border-neon-cyan text-neon-cyan'
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
