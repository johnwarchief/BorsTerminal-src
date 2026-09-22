// features/master/components/ObsidianStrategyGraph.tsx -- گراف شبکه‌ای تعاملی سبک ابسیدین (Obsidian-Style Graph)
// تجمیع ۴ صفحه چارت درختی متدولوژی FTS (عرفان نصرتی) در یک نمودار زنده و پیوسته
import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';

export type GraphCategory = 'core' | 'fund' | 'tech' | 'tape' | 'money';

export interface StrategyGraphNode {
  id: string;
  label: string;
  fullTitle: string;
  category: GraphCategory;
  stage: number; // 0: Core, 1: Fundamental, 2: Technical, 3: Tape, 4: Money
  stageName: string;
  page: string; // شماره صفحه جزوه
  description: string;
  ruleFormula: string;
  badge: string;
  color: string;
  glowColor: string;
  radius: number;
  x: number;
  y: number;
}

export interface StrategyGraphLink {
  id: string;
  source: string;
  target: string;
  label?: string;
  presets: ('swing' | 'trend' | 'hourglass')[];
  isCross?: boolean;
}

// لیست ۲۶ نود جامع ۴ صفحه چارت FTS
const INITIAL_NODES: StrategyGraphNode[] = [
  // ─── هسته مرکزی (Core Hub) ───
  {
    id: 'fts_core',
    label: '🌟 استراتژی جامع FTS',
    fullTitle: 'متدولوژی سه‌گانه FTS (عرفان نصرتی)',
    category: 'core',
    stage: 0,
    stageName: 'هسته متدولوژی',
    page: 'صفحه ۱ تا ۴',
    description: 'ترکیب همزمان فیلتر بنیادی کدال (F)، فیلتر تکنیکال دو زمانه (T)، و تابلوخوانی و زمان‌سنج (S) با مدیریت سرمایه صلب.',
    ruleFormula: 'F (Fundamental) + T (Technical) + S (Selection/Tape) = Trade Execution',
    badge: 'هسته مرکزی',
    color: '#38bdf8',
    glowColor: '#38bdf8',
    radius: 34,
    x: 650,
    y: 410,
  },

  // ─── فاز ۱: هاب دسته‌بندی بنیادی (Pillar 1) ───
  {
    id: 'cat_fund',
    label: '۱. فیلتر بنیادی (کدال)',
    fullTitle: 'پالایش ۵ شاخص سلامت بنیادی از سامانه کدال',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'چارت صفحه ۱',
    description: 'بررسی ۵ فاکتور کلیدی: رشد فروش، سودآوری ۳ ساله، حاشیه سود ناخالص بالای ۲۰٪، فروش به ارزش بازار و صنایع بدون نرخ دستوری.',
    ruleFormula: 'امتیاز ۱ تا ۵ بر مبنای ۵ شاخص رسمی جزوه',
    badge: 'رکن اول F',
    color: '#22c55e',
    glowColor: '#22c55e',
    radius: 25,
    x: 930,
    y: 230,
  },
  {
    id: 'fund_super',
    label: '💎 سوپربنیادی (۵ از ۵)',
    fullTitle: 'نماد سوپربنیادی شاخص‌ساز (امتیاز کامل)',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱ و ۴',
    description: 'رشد فروش ماهانه کدال > ۴۰٪، سودآوری ۳ ساله متوالی، حاشیه سود ناخالص بالای ۳۰٪ و صنایع دلاری/کالایی بدون قیمت‌گذاری دستوری.',
    ruleFormula: 'فروش ۴۰٪+ | EPS ۳ساله مثبت | حاشیه > ۳۰٪ | دلاری',
    badge: 'امتیاز ۵/۵',
    color: '#22c55e',
    glowColor: '#4ade80',
    radius: 20,
    x: 1140,
    y: 130,
  },
  {
    id: 'fund_good',
    label: 'بنیادی مطلوب (۴ از ۵)',
    fullTitle: 'بنیادی مطلوب برای ورود روندی',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱',
    description: 'دارای رشد فروش ماهانه و سودآوری ۳ ساله، حاشیه سود بالای ۲۰٪؛ تایید برای موقعیت‌های روندی بالای ۳ ماه.',
    ruleFormula: 'امتیاز ۴ از ۵ FTS | حاشیه > ۲۰٪',
    badge: 'تایید روندی',
    color: '#10b981',
    glowColor: '#34d399',
    radius: 18,
    x: 1200,
    y: 220,
  },
  {
    id: 'fund_medium',
    label: 'بنیادی متوسط (۳ از ۵)',
    fullTitle: 'بنیادی متوسط؛ صرفاً نوسان‌گیری مجاز',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱',
    description: 'فاقد سودآوری ۳ ساله ولی دارای رشد فروش فصلی؛ طبق جزوه صرفاً معاملات نوسان‌گیری با ستاپ جت مجاز است و ورود روندی ممنوع است.',
    ruleFormula: 'امتیاز ۳ از ۵ | ورود صرفاً نوسان‌گیری زیر ۳ ماه',
    badge: 'فقط نوسانی',
    color: '#eab308',
    glowColor: '#facc15',
    radius: 17,
    x: 1150,
    y: 310,
  },
  {
    id: 'fund_weak',
    label: '⛔ رد بنیادی (زیر ۳)',
    fullTitle: 'رد صلب بنیادی (ریجکت و توقف)',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱',
    description: 'صنایع مشمول قیمت‌گذاری دستوری شدید (خودرو/قطعات) یا افت شدید حاشیه سود به زیر ۲۰٪ یا شرکت‌های زیان‌ده؛ معامله اکیداً ممنوع.',
    ruleFormula: 'امتیاز < ۳ یا زیان‌ده یا حاشیه < ۲۰٪ -> توقف فوری',
    badge: 'ریجکت',
    color: '#ef4444',
    glowColor: '#f87171',
    radius: 17,
    x: 1040,
    y: 380,
  },
  {
    id: 'crit_sales_growth',
    label: 'رشد فروش کدال > ۴۰٪',
    fullTitle: 'شاخص ۱: رشد فروش ماهانه نسبت به سال قبل',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱',
    description: 'گزارش فعالیت ماهانه منتشرشده در سامانه کدال؛ رشد فروش تجمیعی حداقل ۴۰٪ نسبت به دوره مشابه سال گذشته.',
    ruleFormula: 'فروش ماهانه کدال نسبت به سال گذشته > ۴۰٪',
    badge: 'شاخص ۱',
    color: '#10b981',
    glowColor: '#34d399',
    radius: 13,
    x: 1290,
    y: 110,
  },
  {
    id: 'crit_3y_eps',
    label: 'سودآوری ۳ ساله (EPS+)',
    fullTitle: 'شاخص ۲: سودآوری مستمر ۳ ساله بدون زیان',
    category: 'fund',
    stage: 1,
    stageName: 'بنیادی F',
    page: 'صفحه ۱',
    description: 'روند EPS شرکت در ۳ سال گذشته صعودی و مثبت بوده و فاقد زیان انباشته عملیاتی باشد.',
    ruleFormula: 'EPS سال ۱ < سال ۲ < سال ۳ | عدم زیان انباشته',
    badge: 'شاخص ۲',
    color: '#10b981',
    glowColor: '#34d399',
    radius: 13,
    x: 1280,
    y: 280,
  },

  // ─── فاز ۲: هاب دسته‌بندی تکنیکال دو زمانه (Pillar 2) ───
  {
    id: 'cat_tech',
    label: '۲. فیلتر تکنیکال ۲ زمانه',
    fullTitle: 'تحلیل دو زمانه تکنیکال (هفتگی ماژور + روزانه مینور)',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'چارت صفحه ۲',
    description: 'تایم‌فریم بالاتر (هفتگی) تعیین‌کننده جهت و مجوز ورود است؛ تایم‌فریم پایین‌تر (روزانه) تعیین‌کننده ستاپ دقیق و نقطه ورود است.',
    ruleFormula: 'تایم هفتگی صعودی = مجوز ورود روزانه | هفتگی نزولی = ریجکت قطعی',
    badge: 'رکن دوم T',
    color: '#06b6d4',
    glowColor: '#22d3ee',
    radius: 25,
    x: 370,
    y: 230,
  },
  {
    id: 'tech_weekly_up',
    label: '📈 تایم هفتگی صعودی',
    fullTitle: 'تاییدیه ماژور تایم‌فریم هفتگی',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲',
    description: 'تشکیل سقف‌ها و کف‌های بالاتر (Higher High / Higher Low)؛ قرارگیری قیمت بالای میانگین متحرک هفتگی (EMA20) و مکدی صعودی.',
    ruleFormula: 'سقف/کف بالاتر در هفتگی + کندل بالای میانگین متحرک هفتگی',
    badge: 'مجوز ورود',
    color: '#22c55e',
    glowColor: '#4ade80',
    radius: 20,
    x: 370,
    y: 90,
  },
  {
    id: 'tech_weekly_reject',
    label: '⛔ ریجکت هفتگی (وتو)',
    fullTitle: 'ریجکت صلب در تایم هفتگی نزولی یا خنثی',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲',
    description: 'اگر روند هفتگی نزولی یا خنثی باشد، طبق صراحت صفحه ۲ جزوه، سهم اکیداً ریجکت است و هیچ ستاپ روزانه‌ای معتبر نخواهد بود.',
    ruleFormula: 'هفتگی نزولی یا خنثی -> وتوی کامل تمام ستاپ‌های روزانه',
    badge: 'وتوی قطعی',
    color: '#ef4444',
    glowColor: '#f87171',
    radius: 17,
    x: 190,
    y: 90,
  },
  {
    id: 'tech_weekly_hourglass',
    label: '⏳ کف هفتگی ساعت شنی',
    fullTitle: 'اشباع فروش عمیق در کف تاریخی هفتگی',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲ و ۴',
    description: 'در تایم هفتگی قیمت زیر MA-52 قرار داشته و شاخص RSI در اشباع فروش عمیق زیر ۷ (یا ۵) باشد؛ موقعیت فعال‌سازی استراتژی ساعت شنی.',
    ruleFormula: 'هفتگی زیر MA=52 + شاخص RSI < 7 (کف تاریخی)',
    badge: 'اهرم خرید',
    color: '#eab308',
    glowColor: '#facc15',
    radius: 18,
    x: 540,
    y: 90,
  },
  {
    id: 'setup_jet',
    label: '🚀 ستاپ جت (Jet Breakout)',
    fullTitle: 'استراتژی پرتاب جت و شکست مقاومت',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲',
    description: 'شکست سقف تاریخی یا مقاومت استاتیک با کندل ماروبوزو و پرقدرت؛ معامله‌گر تا ۳ روز فرصت ورود پله‌ای روی تثبیت یا پولبک دارد.',
    ruleFormula: 'عبور قدرتمند از سقف تاریخی/استاتیک + فرصت ۳ روزه تثبیت',
    badge: 'ستاپ پرتاب',
    color: '#06b6d4',
    glowColor: '#22d3ee',
    radius: 19,
    x: 230,
    y: 200,
  },
  {
    id: 'setup_fib',
    label: '📐 ستاپ فیبوناچی ۳۳-۴۰ و ۶۱.۸',
    fullTitle: 'پله‌های اصلاحی فیبوناچی در روند صعودی',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲',
    description: 'ورود پله اول در تراز ۳۳ تا ۴۰ درصد فیبوناچی و پله دوم در تراز ۶۱.۸ تا ۷۰ درصد؛ اصلاح سالم در روند صعودی بدون شکست ساختار.',
    ruleFormula: 'پله ۱: تراز 33-40% | پله ۲: تراز 61.8-70% فیبو',
    badge: 'پله‌های ورود',
    color: '#38bdf8',
    glowColor: '#60a5fa',
    radius: 18,
    x: 160,
    y: 280,
  },
  {
    id: 'setup_choch',
    label: '🔄 تغییر ساختار CHoCH / کف دوقلو',
    fullTitle: 'ستاپ بازگشتی تغییر ساختار یا الگوی کف دوقلو',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲',
    description: 'شکست آخرین سقف در روند نزولی مینور (Change of Character) یا شکست خط گردن الگوی کف دوقلو با پولبک تاییدکننده.',
    ruleFormula: 'شکست آخرین سقف موج نزولی (CHoCH) + تایید تثبیت',
    badge: 'الگوی بازگشتی',
    color: '#a855f7',
    glowColor: '#c084fc',
    radius: 18,
    x: 210,
    y: 360,
  },
  {
    id: 'setup_point_hunt',
    label: '🎯 ستاپ شکار نقطه حمایت',
    fullTitle: 'ورود در کف سوم یا پنجم کانال و خط روند',
    category: 'tech',
    stage: 2,
    stageName: 'تکنیکال T',
    page: 'صفحه ۲ و ۳',
    description: 'واکنش دقیق قیمت به کف سوم یا پنجم کانال صعودی یا خط روند ماژور همزمان با کاهش فشار فروش.',
    ruleFormula: 'برخورد به کف خط روند صعودی + کندل چکشی یا تاییدیه بازگشت',
    badge: 'نقطه‌زنی',
    color: '#38bdf8',
    glowColor: '#60a5fa',
    radius: 15,
    x: 100,
    y: 360,
  },

  // ─── فاز ۳: هاب دسته‌بندی تابلوخوانی و زمان‌سنج (Pillar 3) ───
  {
    id: 'cat_tape',
    label: '۳. تابلوخوانی و زمان‌سنج',
    fullTitle: 'پالایش جریان نقدینگی و زمان‌سنج ورود تابلو (S)',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'چارت صفحه ۳',
    description: 'تکنیکال نقطه را مشخص می‌کند، اما تابلو زمان دقیق شلیک (Timing) را صادر می‌کند؛ الگوهای اختصاصی FTS روی سفارشات.',
    ruleFormula: 'الگوی ساعت + حجم مشکوک ۳× + خشک شدن فروشنده',
    badge: 'رکن سوم S',
    color: '#eab308',
    glowColor: '#facc15',
    radius: 25,
    x: 930,
    y: 590,
  },
  {
    id: 'tape_clock',
    label: '⏰ الگوی ساعت FTS',
    fullTitle: 'اختلاف معنادار قیمت آخرین معامله از قیمت پایانی',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'صفحه ۳',
    description: 'قیمت آخرین معامله حداقل ۱٪ بالاتر از پایانی باشد (بهترین حالت: پایانی منفی و آخرین مثبت)؛ پیش‌خور شدن تقاضای فردا در معاملات امروز.',
    ruleFormula: '((آخرین - پایانی) / پایانی) * ۱۰۰ >= ۱.۰٪',
    badge: 'زمان‌سنج ورود',
    color: '#22c55e',
    glowColor: '#4ade80',
    radius: 20,
    x: 1140,
    y: 510,
  },
  {
    id: 'tape_volume',
    label: '🌊 حجم مشکوک (۳ برابر)',
    fullTitle: 'ورود پول هوشمند و دست‌به‌دست شدن سهم',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'صفحه ۳',
    description: 'حجم معاملات امروز حداقل ۳ برابر میانگین ماهانه (۲۱ روزه) باشد همراه با قدرت خریدار حقیقی بالای ۱.۲ برابر فروشندگان.',
    ruleFormula: 'حجم روز >= ۳ × میانگین ۲۱ روزه + قدرت خریدار > ۱.۲',
    badge: 'پول هوشمند',
    color: '#06b6d4',
    glowColor: '#22d3ee',
    radius: 19,
    x: 1200,
    y: 600,
  },
  {
    id: 'tape_breakout',
    label: '📦 خروج از باکس رنج',
    fullTitle: 'شکست سقف کانال تراکم قیمت در تابلو',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'صفحه ۳',
    description: 'شکست سقف محدوده درجا زدن با کندل صعودی پرقدرت و پر شدن حجم مبنا + ورود همزمان پول حقیقی.',
    ruleFormula: 'شکست سقف تراکم + جهش ارزش معاملات + الگوی ساعت',
    badge: 'آغاز شتاب',
    color: '#38bdf8',
    glowColor: '#60a5fa',
    radius: 18,
    x: 1140,
    y: 690,
  },
  {
    id: 'tape_floor_sweep',
    label: '🧹 کف‌روبی و خشک کردن',
    fullTitle: 'جمع‌آوری صف فروش و پایان فشار عرضه',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'صفحه ۳',
    description: 'سهم صف فروش است اما کدهای درشت خریدار صف را بلعیده و حجم مبنا را پر می‌کنند؛ یا عرضه سهم کاملاً خشک و فروشنده‌ها محو شده‌اند.',
    ruleFormula: 'بلعیده شدن صف فروش با کدهای سنگین یا حجم معاملات به صفر میل کرده',
    badge: 'جمع‌آوری صف',
    color: '#a855f7',
    glowColor: '#c084fc',
    radius: 17,
    x: 1040,
    y: 750,
  },
  {
    id: 'tape_smart_money',
    label: '💳 ورود پول از فیکس به سهام',
    fullTitle: 'خروج نقدینگی از صندوق‌های درآمد ثابت و تزریق به سهم',
    category: 'tape',
    stage: 3,
    stageName: 'تابلوخوانی S',
    page: 'صفحه ۳',
    description: 'چرخش سرمایه‌های کلان بازار از صندوق‌های درآمد ثابت (حامی/فیکس) به سمت سهام پیشرو؛ نشانه آغاز رالی در سهم‌های بنیادی.',
    ruleFormula: 'جریان نقدینگی منفی صندوق‌های درآمد ثابت + مثبت شدن سهام خرد',
    badge: 'چرخش نقدینگی',
    color: '#10b981',
    glowColor: '#34d399',
    radius: 14,
    x: 1220,
    y: 750,
  },

  // ─── فاز ۴: هاب دسته‌بندی مدیریت سرمایه و خروج (Pillar 4) ───
  {
    id: 'cat_money',
    label: '۴. مدیریت سرمایه و خروج',
    fullTitle: 'قواعد صلب حد ضرر، ذخیره سود ۵۰٪ و سقف ریسک',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'چارت صفحه ۴',
    description: 'تفکیک صریح حد ضرر نوسان‌گیر (استاپ تکنیکالی MA-14 یا ۵٪) از حد ضرر روندگیر (کدال و فصلی) و اجرای قانون ذخیره سود ۵۰٪ FTS.',
    ruleFormula: 'حد ضرر معین + ذخیره سود ۵۰٪ در مقاومت ۱ + R/R >= ۲',
    badge: 'رکن چهارم M',
    color: '#38bdf8',
    glowColor: '#60a5fa',
    radius: 25,
    x: 370,
    y: 590,
  },
  {
    id: 'stop_swing',
    label: '🛑 حد ضرر نوسان‌گیر (MA-14)',
    fullTitle: 'حد ضرر صلب نوسان‌گیر: کندل زیر MA-14 یا ۵٪',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۴',
    description: 'تشکیل یک کندل کامل زیر میانگین متحرک ۱۴ روزه (MA=14) یا افت ۵٪ زیر نقطه ورود یا آخرین کف صعودی؛ خروج قطعی و بدون تاخیر.',
    ruleFormula: 'تشکیل کندل کامل زیر MA=14 یا افت ۵٪ زیر خرید -> خروج بی‌چون‌وچرا',
    badge: 'استاپ تکنیکالی',
    color: '#ef4444',
    glowColor: '#f87171',
    radius: 19,
    x: 220,
    y: 520,
  },
  {
    id: 'stop_trend',
    label: '🛡️ حد ضرر بنیادی روندگیر',
    fullTitle: 'حد ضرر بنیادی روندگیر در صورت‌های مالی کدال',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۴',
    description: 'شخص روندگیر حد ضرر تکنیکالی ۵ درصدی ندارد؛ حد ضرر در صورت‌های مالی است: توقف رشد فروش ماهانه کدال یا افت حاشیه سود به زیر ۲۰٪.',
    ruleFormula: 'افت حاشیه سود به زیر ۲۰٪ یا توقف رشد فروش فصلی -> تعویض سهم',
    badge: 'استاپ کدالی',
    color: '#22c55e',
    glowColor: '#4ade80',
    radius: 19,
    x: 140,
    y: 610,
  },
  {
    id: 'stop_hourglass',
    label: '⏳ اهرم ساعت شنی (۲-۴ برابر)',
    fullTitle: 'پله‌بندی سنگین اهرمی در کف تاریخی به دید ۳ تا ۱۰ سال',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۴',
    description: 'در کف‌های عمیق تاریخی و اشباع RSI هفتگی، حجم ورود نسبت به پله‌های عادی ۲ تا ۴ برابر افزایش می‌یابد؛ بدون استاپ نوسانی.',
    ruleFormula: 'ضریب حجم ورود: ۲× تا ۴× پله معمول | افق ۳ تا ۱۰ ساله',
    badge: 'اهرم بلندمدت',
    color: '#eab308',
    glowColor: '#facc15',
    radius: 18,
    x: 230,
    y: 700,
  },
  {
    id: 'exit_half',
    label: '💰 قانون ذخیره سود ۵۰٪ FTS',
    fullTitle: 'فروش ۵۰٪ در مقاومت اول برای آزادسازی اصل سرمایه',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۲ و ۴',
    description: 'در برخورد با مقاومت استاتیک اول R1 یا سقف موج، ۵۰٪ حجم سهم فروخته می‌شود تا اصل سرمایه خارج شده و ادامه مسیر کاملاً بدون ریسک باشد.',
    ruleFormula: 'رسیدن به مقاومت R1 -> فروش دقیق ۵۰٪ دارایی تک‌سهم',
    badge: 'خروج اصل پول',
    color: '#38bdf8',
    glowColor: '#60a5fa',
    radius: 18,
    x: 130,
    y: 710,
  },
  {
    id: 'rule_rr',
    label: '⚖️ نسبت ریسک به ریوارد (R/R > 2)',
    fullTitle: 'الزام نسبت سود به زیان حداقل ۱ به ۲ در تمام معاملات',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۴',
    description: 'فاصله تا هدف سود حداقل باید ۲ برابر فاصله تا حد ضرر باشد؛ در غیر این صورت معامله ارزش ریسک ندارد.',
    ruleFormula: '(تارگت سود - نقطه ورود) / (نقطه ورود - حد ضرر) >= ۲.۰',
    badge: 'ریسک به ریوارد',
    color: '#a855f7',
    glowColor: '#c084fc',
    radius: 15,
    x: 220,
    y: 790,
  },
  {
    id: 'rule_cap',
    label: '📊 سقف وزن صنعت (حداکثر ۲۰٪)',
    fullTitle: 'قانون تنوع‌بخشی: سقف ۲۰٪ سبد به یک صنعت',
    category: 'money',
    stage: 4,
    stageName: 'مدیریت سرمایه M',
    page: 'صفحه ۴',
    description: 'مجموع سرمایه تخصیص‌یافته به تمام نمادهای یک صنعت (مثلاً فلزات یا پتروشیمی) نباید از ۲۰٪ کل دارایی پورتفوی بیشتر شود.',
    ruleFormula: 'مجموع وزن نمادهای صنعت جاری <= ۲۰٪ کل سبد',
    badge: 'تنوع‌بخشی',
    color: '#10b981',
    glowColor: '#34d399',
    radius: 14,
    x: 370,
    y: 760,
  },
];

// اتصالات پیوسته و متقاطع بین ۴ فاز FTS (Edges / Links)
const INITIAL_LINKS: StrategyGraphLink[] = [
  // اتصال هسته مرکزی به ۴ هاب دسته‌بندی
  { id: 'l_core_fund', source: 'fts_core', target: 'cat_fund', presets: ['swing', 'trend', 'hourglass'] },
  { id: 'l_core_tech', source: 'fts_core', target: 'cat_tech', presets: ['swing', 'trend', 'hourglass'] },
  { id: 'l_core_tape', source: 'fts_core', target: 'cat_tape', presets: ['swing', 'trend', 'hourglass'] },
  { id: 'l_core_money', source: 'fts_core', target: 'cat_money', presets: ['swing', 'trend', 'hourglass'] },

  // فاز ۱: هاب بنیادی به شاخه‌های بنیادی
  { id: 'l_fund_super', source: 'cat_fund', target: 'fund_super', presets: ['trend', 'hourglass'] },
  { id: 'l_fund_good', source: 'cat_fund', target: 'fund_good', presets: ['swing', 'trend'] },
  { id: 'l_fund_medium', source: 'cat_fund', target: 'fund_medium', presets: ['swing'] },
  { id: 'l_fund_weak', source: 'cat_fund', target: 'fund_weak', presets: [] },

  // زیرشاخه‌های بنیادی
  { id: 'l_super_crit_sales', source: 'fund_super', target: 'crit_sales_growth', presets: ['trend'] },
  { id: 'l_super_crit_eps', source: 'fund_super', target: 'crit_3y_eps', presets: ['trend', 'hourglass'] },
  { id: 'l_good_crit_sales', source: 'fund_good', target: 'crit_sales_growth', presets: ['trend'] },

  // ─── کراس‌کانکشن ۱: بنیادی به تکنیکال (پل ارتباطی فاز ۱ به ۲) ───
  { id: 'l_cross_fund_super_tech', source: 'fund_super', target: 'tech_weekly_up', presets: ['trend'], isCross: true },
  { id: 'l_cross_fund_super_hg', source: 'fund_super', target: 'tech_weekly_hourglass', presets: ['hourglass'], isCross: true },
  { id: 'l_cross_fund_good_tech', source: 'fund_good', target: 'tech_weekly_up', presets: ['swing', 'trend'], isCross: true },
  { id: 'l_cross_fund_med_tech', source: 'fund_medium', target: 'tech_weekly_up', presets: ['swing'], isCross: true },
  { id: 'l_cross_fund_weak_reject', source: 'fund_weak', target: 'tech_weekly_reject', presets: [], isCross: true },

  // فاز ۲: هاب تکنیکال به شاخه‌ها
  { id: 'l_tech_up', source: 'cat_tech', target: 'tech_weekly_up', presets: ['swing', 'trend'] },
  { id: 'l_tech_reject', source: 'cat_tech', target: 'tech_weekly_reject', presets: [] },
  { id: 'l_tech_hg', source: 'cat_tech', target: 'tech_weekly_hourglass', presets: ['hourglass'] },

  // هفتگی صعودی به ستاپ‌های روزانه
  { id: 'l_up_jet', source: 'tech_weekly_up', target: 'setup_jet', presets: ['swing'] },
  { id: 'l_up_fib', source: 'tech_weekly_up', target: 'setup_fib', presets: ['swing', 'trend'] },
  { id: 'l_up_choch', source: 'tech_weekly_up', target: 'setup_choch', presets: ['trend'] },
  { id: 'l_up_hunt', source: 'tech_weekly_up', target: 'setup_point_hunt', presets: ['swing'] },

  // ─── کراس‌کانکشن ۲: تکنیکال به تابلوخوانی (پل ارتباطی فاز ۲ به ۳) ───
  { id: 'l_cross_jet_clock', source: 'setup_jet', target: 'tape_clock', presets: ['swing'], isCross: true },
  { id: 'l_cross_jet_vol', source: 'setup_jet', target: 'tape_volume', presets: ['swing'], isCross: true },
  { id: 'l_cross_fib_clock', source: 'setup_fib', target: 'tape_clock', presets: ['swing', 'trend'], isCross: true },
  { id: 'l_cross_fib_box', source: 'setup_fib', target: 'tape_breakout', presets: ['trend'], isCross: true },
  { id: 'l_cross_choch_vol', source: 'setup_choch', target: 'tape_volume', presets: ['trend'], isCross: true },
  { id: 'l_cross_choch_smart', source: 'setup_choch', target: 'tape_smart_money', presets: ['trend'], isCross: true },
  { id: 'l_cross_hunt_sweep', source: 'setup_point_hunt', target: 'tape_floor_sweep', presets: ['swing'], isCross: true },
  { id: 'l_cross_hg_sweep', source: 'tech_weekly_hourglass', target: 'tape_floor_sweep', presets: ['hourglass'], isCross: true },

  // فاز ۳: هاب تابلوخوانی به شاخه‌ها
  { id: 'l_tape_clock', source: 'cat_tape', target: 'tape_clock', presets: ['swing'] },
  { id: 'l_tape_vol', source: 'cat_tape', target: 'tape_volume', presets: ['swing', 'trend'] },
  { id: 'l_tape_box', source: 'cat_tape', target: 'tape_breakout', presets: ['trend'] },
  { id: 'l_tape_sweep', source: 'cat_tape', target: 'tape_floor_sweep', presets: ['hourglass'] },
  { id: 'l_tape_smart', source: 'cat_tape', target: 'tape_smart_money', presets: ['trend'] },

  // ─── کراس‌کانکشن ۳: تابلوخوانی به مدیریت سرمایه (پل ارتباطی فاز ۳ به ۴) ───
  { id: 'l_cross_clock_stopswing', source: 'tape_clock', target: 'stop_swing', presets: ['swing'], isCross: true },
  { id: 'l_cross_vol_stopswing', source: 'tape_volume', target: 'stop_swing', presets: ['swing'], isCross: true },
  { id: 'l_cross_box_stoptrend', source: 'tape_breakout', target: 'stop_trend', presets: ['trend'], isCross: true },
  { id: 'l_cross_smart_stoptrend', source: 'tape_smart_money', target: 'stop_trend', presets: ['trend'], isCross: true },
  { id: 'l_cross_sweep_hgstop', source: 'tape_floor_sweep', target: 'stop_hourglass', presets: ['hourglass'], isCross: true },

  // فاز ۴: هاب مدیریت سرمایه به شاخه‌ها
  { id: 'l_money_swing', source: 'cat_money', target: 'stop_swing', presets: ['swing'] },
  { id: 'l_money_trend', source: 'cat_money', target: 'stop_trend', presets: ['trend'] },
  { id: 'l_money_hg', source: 'cat_money', target: 'stop_hourglass', presets: ['hourglass'] },
  { id: 'l_money_exit', source: 'cat_money', target: 'exit_half', presets: ['swing', 'trend'] },
  { id: 'l_money_rr', source: 'cat_money', target: 'rule_rr', presets: ['swing', 'trend'] },
  { id: 'l_money_cap', source: 'cat_money', target: 'rule_cap', presets: ['trend', 'hourglass'] },

  // اتصال پایانی مدیریت سرمایه و سیو سود
  { id: 'l_stop_swing_exit', source: 'stop_swing', target: 'exit_half', presets: ['swing'] },
  { id: 'l_stop_trend_exit', source: 'stop_trend', target: 'exit_half', presets: ['trend'] },
  { id: 'l_exit_rr', source: 'exit_half', target: 'rule_rr', presets: ['swing', 'trend'] },
  { id: 'l_trend_cap', source: 'stop_trend', target: 'rule_cap', presets: ['trend'] },
  { id: 'l_hg_cap', source: 'stop_hourglass', target: 'rule_cap', presets: ['hourglass'] },
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
  // نگهداری مختصات نودها با قابلیت درگ
  const [nodes, setNodes] = useState<StrategyGraphNode[]>(INITIAL_NODES);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('fts_core');
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState<number | 'all'>('all');

  // متغیرهای زوم و پن
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const dragStartPos = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // محاسبه نقشه نودها با کلید ID
  const nodeMap = useMemo(() => {
    const map = new Map<string, StrategyGraphNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  // نودهای فعال بر اساس پری‌ست انتخابی یا حالت سفارشی
  const activeNodeIds = useMemo(() => {
    if (selectedPreset === 'custom') {
      const set = new Set<string>(['fts_core', 'cat_fund', 'cat_tech', 'cat_tape', 'cat_money', ...activeCustomNodes]);
      return set;
    }
    const set = new Set<string>();
    INITIAL_LINKS.forEach((link) => {
      if (link.presets.includes(selectedPreset)) {
        set.add(link.source);
        set.add(link.target);
      }
    });
    set.add('fts_core');
    return set;
  }, [selectedPreset, activeCustomNodes]);

  // همسایگان متصل به نود هاور شده (برای افکت Obsidian Hover Isolation)
  const hoveredNeighbors = useMemo(() => {
    if (!hoveredNodeId) return null;
    const set = new Set<string>([hoveredNodeId]);
    INITIAL_LINKS.forEach((link) => {
      if (link.source === hoveredNodeId) set.add(link.target);
      if (link.target === hoveredNodeId) set.add(link.source);
    });
    return set;
  }, [hoveredNodeId]);

  // نود انتخاب شده جهت بازرسی در پنل اطلاعات
  const inspectedNode = useMemo(() => {
    return nodeMap.get(selectedNodeId || '') || nodeMap.get('fts_core') || null;
  }, [selectedNodeId, nodeMap]);

  // رویدادهای زوم با چرخ ماوس
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      setZoom((prev) => Math.min(Math.max(prev * zoomFactor, 0.45), 2.4));
    };

    svgEl.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      svgEl.removeEventListener('wheel', handleWheel);
    };
  }, []);

  // هندلرهای درگ پن بوم و جابجایی نودها
  const handlePointerDown = (e: React.PointerEvent) => {
    if (draggedNodeId) return;
    setIsPanning(true);
    dragStartPos.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (draggedNodeId) {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const scaleX = 1400 / (rect.width * zoom);
      const scaleY = 880 / (rect.height * zoom);

      const mouseX = (e.clientX - rect.left - pan.x) * scaleX;
      const mouseY = (e.clientY - rect.top - pan.y) * scaleY;

      setNodes((prev) =>
        prev.map((n) => (n.id === draggedNodeId ? { ...n, x: Math.round(mouseX), y: Math.round(mouseY) } : n)),
      );
      return;
    }

    if (isPanning) {
      setPan({
        x: e.clientX - dragStartPos.current.x,
        y: e.clientY - dragStartPos.current.y,
      });
    }
  };

  const handlePointerUp = () => {
    setIsPanning(false);
    setDraggedNodeId(null);
  };

  // بازنشانی نما به حالت پیش‌فرض
  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setNodes(INITIAL_NODES);
  };

  // بررسی وضعیت نود منطبق بر جستجو
  const isMatchSearch = useCallback(
    (node: StrategyGraphNode) => {
      if (!searchQuery.trim()) return false;
      const q = searchQuery.toLowerCase().trim();
      return (
        node.label.toLowerCase().includes(q) ||
        node.fullTitle.toLowerCase().includes(q) ||
        node.description.toLowerCase().includes(q) ||
        node.ruleFormula.toLowerCase().includes(q)
      );
    },
    [searchQuery],
  );

  return (
    <div className="relative flex flex-col w-full h-[760px] lg:h-[820px] rounded-2xl border border-border-c/90 bg-[#070b14] overflow-hidden shadow-2xl select-none">
      {/* ۱. تولبار بالای بوم: دکمه‌های کنترل پری‌ست، فیلترها و زوم HUD */}
      <div className="absolute top-3 inset-x-3 z-30 flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-border-c/60 bg-bg-card/75 p-2 backdrop-blur-md">
        {/* پری‌ست‌ها و سبک بازی */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-2xs font-bold text-text-muted ms-1 hidden sm:inline">مسیر استراتژی:</span>
          <button
            type="button"
            onClick={() => onSelectPreset('swing')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'swing'
                ? 'bg-accent-blue/25 border border-accent-blue text-accent-blue shadow-[0_0_10px_rgba(56,189,248,0.3)]'
                : 'border border-border-c/50 bg-bg-primary/60 text-text-muted hover:text-text-primary'
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
                ? 'bg-accent-green/25 border border-accent-green text-accent-green shadow-[0_0_10px_rgba(34,197,94,0.3)]'
                : 'border border-border-c/50 bg-bg-primary/60 text-text-muted hover:text-text-primary'
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
                ? 'bg-accent-yellow/25 border border-accent-yellow text-accent-yellow shadow-[0_0_10px_rgba(234,179,8,0.3)]'
                : 'border border-border-c/50 bg-bg-primary/60 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>⏳</span>
            <span>ساعت شنی (۳ تا ۱۰ سال)</span>
          </button>

          <button
            type="button"
            onClick={() => onSelectPreset('custom')}
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
              selectedPreset === 'custom'
                ? 'bg-neon-cyan/25 border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(6,182,212,0.3)]'
                : 'border border-border-c/50 bg-bg-primary/60 text-text-muted hover:text-text-primary'
            }`}
          >
            <span>🛠</span>
            <span>مسیر من (شخصی‌سازی)</span>
          </button>
        </div>

        {/* فیلتر مراحل ۴ گانه و کادر جستجو */}
        <div className="flex items-center gap-2 flex-wrap ms-auto">
          {/* فیلتر مرحله */}
          <div className="flex items-center gap-1 text-3xs">
            <button
              type="button"
              onClick={() => setStageFilter('all')}
              className={`px-2 py-0.5 rounded ${stageFilter === 'all' ? 'bg-accent-blue text-black font-bold' : 'text-text-muted hover:text-text-primary'}`}
            >
              همه
            </button>
            <button
              type="button"
              onClick={() => setStageFilter(1)}
              className={`px-2 py-0.5 rounded ${stageFilter === 1 ? 'bg-accent-green text-black font-bold' : 'text-text-muted hover:text-text-primary'}`}
            >
              F بنیادی
            </button>
            <button
              type="button"
              onClick={() => setStageFilter(2)}
              className={`px-2 py-0.5 rounded ${stageFilter === 2 ? 'bg-neon-cyan text-black font-bold' : 'text-text-muted hover:text-text-primary'}`}
            >
              T تکنیکال
            </button>
            <button
              type="button"
              onClick={() => setStageFilter(3)}
              className={`px-2 py-0.5 rounded ${stageFilter === 3 ? 'bg-accent-yellow text-black font-bold' : 'text-text-muted hover:text-text-primary'}`}
            >
              S تابلو
            </button>
            <button
              type="button"
              onClick={() => setStageFilter(4)}
              className={`px-2 py-0.5 rounded ${stageFilter === 4 ? 'bg-purple-500 text-white font-bold' : 'text-text-muted hover:text-text-primary'}`}
            >
              M خروج
            </button>
          </div>

          {/* کادر جستجوی زنده نود */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 جستجو در نودها..."
              className="w-28 sm:w-36 rounded-lg border border-border-c/60 bg-bg-primary/80 px-2 py-1 text-3xs text-text-primary placeholder:text-text-muted focus:border-accent-blue focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute left-1.5 top-1 text-3xs text-text-muted hover:text-text-primary"
              >
                ✕
              </button>
            )}
          </div>

          {/* دکمه‌های کنترل زوم */}
          <div className="flex items-center gap-1 border-s border-border-c/50 ps-2">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(z + 0.15, 2.4))}
              title="بزرگ‌نمایی"
              className="h-6 w-6 rounded border border-border-c/60 bg-bg-primary text-xs font-bold text-text-secondary hover:text-text-primary"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.45))}
              title="کوچک‌نمایی"
              className="h-6 w-6 rounded border border-border-c/60 bg-bg-primary text-xs font-bold text-text-secondary hover:text-text-primary"
            >
              −
            </button>
            <button
              type="button"
              onClick={handleResetView}
              title="بازنشانی زاویه نما"
              className="px-1.5 h-6 rounded border border-border-c/60 bg-bg-primary text-3xs font-bold text-text-secondary hover:text-text-primary"
            >
              ⊙ ریست
            </button>
          </div>
        </div>
      </div>

      {/* ۲. بوم گراف تعاملی SVG (Obsidian Network Canvas) */}
      <div
        className="w-full h-full cursor-grab active:cursor-grabbing overflow-hidden"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <svg
          ref={svgRef}
          viewBox="0 0 1400 880"
          className="w-full h-full pointer-events-auto"
          preserveAspectRatio="xMidYMid meet"
          data-testid="obsidian-strategy-canvas"
        >
          <defs>
            {/* الگوی شبکه‌ای ستاره‌ای ابسیدین */}
            <pattern id="obsidianGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="20" cy="20" r="0.8" fill="rgba(148, 163, 184, 0.18)" />
            </pattern>

            {/* فیلترهای نئونی درخشش (Glow Filters) */}
            <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-green" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-yellow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-red" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-purple" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* نشانگرهای انتهای یال‌ها (Arrow Markers) */}
            <marker id="arrow-active" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
            </marker>
            <marker id="arrow-dim" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="rgba(148, 163, 184, 0.25)" />
            </marker>
          </defs>

          {/* پس‌زمینه ابسیدین با ماتریس ستاره‌ای */}
          <rect width="1400" height="880" fill="#070b14" />
          <rect width="1400" height="880" fill="url(#obsidianGrid)" />

          {/* گروه متحرک قابل زوم و پن */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} transform-origin="700 440">
            {/* ۲.۱. ترسیم یال‌ها و خطوط ارتباطی منحنی (Curved Bezier Edges) */}
            <g className="links-layer">
              {INITIAL_LINKS.map((link) => {
                const srcNode = nodeMap.get(link.source);
                const tgtNode = nodeMap.get(link.target);
                if (!srcNode || !tgtNode) return null;

                // بررسی فعال بودن یال در استراتژی جاری
                const isPresetActive =
                  selectedPreset === 'custom'
                    ? activeNodeIds.has(link.source) && activeNodeIds.has(link.target)
                    : link.presets.includes(selectedPreset);

                // بررسی هاور موضعی
                const isHoverIsolated =
                  hoveredNeighbors && (!hoveredNeighbors.has(link.source) || !hoveredNeighbors.has(link.target));

                // درصد شفافیت یال
                let strokeOpacity = 0.22;
                let strokeWidth = 1.2;
                let strokeColor = 'rgba(148, 163, 184, 0.28)';

                if (isPresetActive) {
                  strokeOpacity = 0.95;
                  strokeWidth = link.isCross ? 2.6 : 2.2;
                  strokeColor = link.isCross ? '#06b6d4' : srcNode.color;
                }

                if (hoveredNeighbors?.has(link.source) && hoveredNeighbors?.has(link.target)) {
                  strokeOpacity = 1;
                  strokeWidth = 3;
                  strokeColor = '#38bdf8';
                } else if (isHoverIsolated) {
                  strokeOpacity = 0.08;
                }

                // محاسبه خط منحنی نرم بزیه (Smooth Quadratic Curve)
                const dx = tgtNode.x - srcNode.x;
                const dy = tgtNode.y - srcNode.y;
                const midX = (srcNode.x + tgtNode.x) / 2;
                const midY = (srcNode.y + tgtNode.y) / 2;
                // انحنای ملایم شبیه خطوط عصبی ابسیدین
                const curveOffset = link.isCross ? 35 : 15;
                const ctrlX = midX - (dy / (Math.hypot(dx, dy) || 1)) * curveOffset;
                const ctrlY = midY + (dx / (Math.hypot(dx, dy) || 1)) * curveOffset;

                const pathData = `M ${srcNode.x} ${srcNode.y} Q ${ctrlX} ${ctrlY} ${tgtNode.x} ${tgtNode.y}`;

                return (
                  <g key={link.id}>
                    <path
                      d={pathData}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      strokeOpacity={strokeOpacity}
                      strokeDasharray={link.isCross ? '4 3' : undefined}
                      className="transition-all duration-300"
                    />

                    {/* پالس نورانی متحرک روی یال‌های فعال */}
                    {isPresetActive && !isHoverIsolated && (
                      <circle r="2.5" fill="#38bdf8" filter="url(#glow-cyan)">
                        <animateMotion path={pathData} dur={link.isCross ? '2.8s' : '3.6s'} repeatCount="indefinite" />
                      </circle>
                    )}
                  </g>
                );
              })}
            </g>

            {/* ۲.۲. ترسیم نودها (Nodes Layer) */}
            <g className="nodes-layer">
              {nodes.map((node) => {
                // بررسی وضعیت فعال/کمرنگ بودن
                const isActive = activeNodeIds.has(node.id);
                const isHovered = hoveredNodeId === node.id;
                const isSelected = selectedNodeId === node.id;
                const isSearched = isMatchSearch(node);
                const isStageFiltered = stageFilter !== 'all' && node.stage !== 0 && node.stage !== stageFilter;

                // محاسبه شفافیت و مقیاس (Dimming & Scaling)
                let opacity = 1;
                let scale = 1;

                if (hoveredNeighbors) {
                  opacity = hoveredNeighbors.has(node.id) ? 1 : 0.18;
                  if (isHovered) scale = 1.15;
                } else if (!isActive && selectedPreset !== 'custom') {
                  opacity = 0.28; // کمرنگ شدن بقیه مسیرها طبق خواسته کاربر ("بقیه یه کوچولو کمرنگ شن")
                  scale = 0.94;
                } else if (selectedPreset === 'custom' && !isActive) {
                  opacity = 0.32;
                }

                if (isStageFiltered) {
                  opacity = 0.15;
                }

                if (isSearched) {
                  opacity = 1;
                  scale = 1.25;
                }

                const filterUrl =
                  node.category === 'fund'
                    ? 'url(#glow-green)'
                    : node.category === 'tech'
                      ? 'url(#glow-cyan)'
                      : node.category === 'tape'
                        ? 'url(#glow-yellow)'
                        : node.category === 'money'
                          ? 'url(#glow-red)'
                          : 'url(#glow-cyan)';

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y}) scale(${scale})`}
                    className="cursor-pointer transition-all duration-300"
                    style={{ opacity }}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      setDraggedNodeId(node.id);
                    }}
                    onClick={() => {
                      setSelectedNodeId(node.id);
                      if (selectedPreset === 'custom' && onToggleCustomNode && node.stage > 0) {
                        onToggleCustomNode(node.id);
                      }
                    }}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                  >
                    {/* حلقه نئونی خارجی برای نودهای فعال یا سرچ‌شده */}
                    {(isActive || isSearched || isSelected) && (
                      <circle
                        r={node.radius + 7}
                        fill="none"
                        stroke={node.color}
                        strokeWidth={isSelected ? '2.5' : '1.5'}
                        strokeOpacity={isSelected ? 0.9 : 0.4}
                        strokeDasharray={isSelected ? '4 2' : undefined}
                        filter={filterUrl}
                        className={isActive ? 'animate-pulse' : undefined}
                      />
                    )}

                    {/* دایره اصلی نود */}
                    <circle
                      r={node.radius}
                      fill={isActive ? node.color : '#1e293b'}
                      fillOpacity={isActive ? 0.35 : 0.8}
                      stroke={node.color}
                      strokeWidth={isSelected ? 3 : 1.8}
                      className="transition-colors duration-200"
                    />

                    {/* نقطه مرکزی نئونی در هسته نود */}
                    <circle r={node.radius * 0.38} fill={node.color} />

                    {/* برچسب متنی فارسی نود */}
                    <text
                      y={node.radius + 15}
                      textAnchor="middle"
                      className="fill-text-primary text-[11px] font-black pointer-events-none drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)]"
                    >
                      {node.label}
                    </text>

                    {/* زیرنویس و برچسب کوچک مرحله */}
                    <text
                      y={node.radius + 27}
                      textAnchor="middle"
                      className="fill-text-muted text-[8.5px] font-medium pointer-events-none drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]"
                    >
                      {node.badge}
                    </text>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>
      </div>

      {/* ۳. کارت راهنمای شناور و بازرسی نود انتخاب‌شده (Node Inspector Panel) */}
      {inspectedNode && (
        <div className="absolute bottom-3 inset-x-3 z-30 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 rounded-xl border border-border-c/70 bg-bg-card/90 p-3.5 backdrop-blur-xl shadow-2xl animate-fade-in">
          <div className="flex items-start gap-3">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg font-black shadow-lg"
              style={{
                backgroundColor: `${inspectedNode.color}22`,
                border: `1px solid ${inspectedNode.color}66`,
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

            <div className="space-y-0.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-xs sm:text-sm font-black text-text-primary">{inspectedNode.fullTitle}</h3>
                <span className="rounded bg-bg-primary px-1.5 py-0.5 text-3xs font-bold text-accent-blue border border-border-c">
                  {inspectedNode.page}
                </span>
                <span className="rounded bg-bg-primary px-1.5 py-0.5 text-3xs font-bold text-text-muted">
                  مرحله: {inspectedNode.stageName}
                </span>
              </div>
              <p className="text-2xs text-text-muted max-w-2xl leading-relaxed">{inspectedNode.description}</p>
              <div className="flex items-center gap-1.5 pt-0.5 text-3xs text-accent-cyan font-mono">
                <span className="text-text-muted font-sans">قاعده رسمی جزوه:</span>
                <span className="text-text-secondary font-sans font-bold">{inspectedNode.ruleFormula}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end md:self-center shrink-0">
            {symbol && (
              <div className="rounded-lg border border-border-c/60 bg-bg-primary px-2.5 py-1 text-2xs">
                <span className="text-text-muted">نماد:</span>{' '}
                <strong className="text-accent-blue font-black">{symbol}</strong>
              </div>
            )}
            {selectedPreset === 'custom' && inspectedNode.stage > 0 && onToggleCustomNode && (
              <button
                type="button"
                onClick={() => onToggleCustomNode(inspectedNode.id)}
                className={`rounded-lg px-3 py-1 text-2xs font-bold transition-all ${
                  activeCustomNodes.includes(inspectedNode.id)
                    ? 'bg-accent-red/20 border border-accent-red text-accent-red hover:bg-accent-red/30'
                    : 'bg-accent-green/20 border border-accent-green text-accent-green hover:bg-accent-green/30'
                }`}
              >
                {activeCustomNodes.includes(inspectedNode.id) ? '✕ حذف از مسیر من' : '＋ فعال‌سازی در مسیر من'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ۴. راهنمای کلیدهای بازی در گوشه بوم */}
      <div className="pointer-events-none absolute left-3 top-16 z-20 hidden lg:flex flex-col gap-1 rounded-xl border border-border-c/40 bg-bg-card/40 p-2.5 backdrop-blur-sm text-3xs text-text-muted">
        <span className="font-bold text-text-secondary">🎮 تعامل با نمودار:</span>
        <span>● کلیک روی هر نود: بازرسی جزئیات و صفحه جزوه</span>
        <span>● درگ نودها: جابجایی آزاد در بوم</span>
        <span>● اسکرول ماوس: زوم روان شبکه‌ای</span>
        <span>● تغییر پری‌ست: هایلایت مسیر و کمرنگ شدن بقیه</span>
      </div>
    </div>
  );
}
