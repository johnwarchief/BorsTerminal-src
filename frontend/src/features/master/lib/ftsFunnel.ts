// features/master/lib/ftsFunnel.ts -- قراردادِ نمایشِ قیف FTS (مدل، نه داور)
//
// ترتیبِ گام‌ها را خودِ موتور درِ پاسخ می‌گوید (`flow`)؛ پیش‌فرضِ جزوه
// تابلوخوانیِ امروز ← تکنیکال ← بنیادیِ پنج‌شاخصه ← تحویل است و استراتژیِ
// «تکنیکال‌محور» همان چهار گام را با ترتیبِ تکنیکال ← تابلو ← بنیادی ← تحویل
// اجرا می‌کند. فرانت فقط می‌خواند.
//
// داوریِ کشفِ نماد دیگر درِ این فایل نیست. `funnel_engine.py` حکمِ canonical را
// می‌سازد، `/api/funnel` همان را می‌دهد و `lib/funnelView.ts` فقط نام‌هایِ پاسخ
// را به همین مدلِ نمایشی برمی‌گرداند. آنچه اینجا مانده نوع‌ها، برچسب‌ها و
// واژگانِ وضعیت‌اند: هیچ `if` قاعده‌ای، هیچ آستانه‌ای، هیچ `slice`اي.
//
// پنج حالت + یک وضعیتِ جامعۀ غربالگری — تنها واژگانِ وضعیتِ هر گام درِ کلِ
// فرانت (بندِ ۱۹
// و ۳۵ از قانونِ مالک: «سنجیده نشده» ممنوع؛ هر نماد درِ هر گام یک حکمِ قابلِ
// توضیح دارد):
//   pass         درِ جزوه باز
//   reject       درِ جزوه بسته — داوریِ صریحِ موتور
//   pending      موتور نگاه کرد و نظر نمی‌دهد (هفتگی UNKNOWN، صندوق «FTS ندارد»،
//               نقطه‌زنی‌ای که اسکرینر فیلدش را ندارد)
//   unavailable  منبعی برایِ داوریِ این مرحله نبود — هیچ‌وقت رد نیست
//   not_required گامِ پیشین نماد را رد کرده؛ این گام اجرا نمی‌شود. توقفِ قطعی و
//               توضیح‌دار است، نه «بی‌سنجش» — reason_code نامِ گامِ بازدارنده را
//               درِ خودِ کد می‌نویسد (NOT_REQUIRED_AFTER_TAPE_REJECT و…).
//   not_in_universe نماد اصلاً عضو جامعۀ غربالگری نبود (وضعیتِ رسمیِ بازار
//               اجازه نمی‌دهد) — نه «رد» است و نه «سنجیده نشده»؛ درِ جدولِ
//               گام‌ها نمایش داده نمی‌شود و درِ «خارج از جامعۀ غربالگری» با
//               علتش می‌نشیند (رأیِ مالک ۱۴۰۵-۰۷-۱۶).
import type { AssetType } from '@features/market/lib/assetType';
import type { FunnelRowView, FunnelScreenView } from './funnelView';
import {
  DEFAULT_FUND_FLOOR,
  DEFAULT_TECH_SCREENS,
  DEFAULT_UNMEASURED,
  type UnmeasuredPolicy,
} from '../stores/funnelPrefsStore';

// پلِ ورودِ مسیرِ سفارشیِ قیف — همان پنج گره‌ای چارت ۳ ستون S؛ «پول هوشمند»
// و «کد به کد» فیلترهایِ تازۀ فایل‌اند که از چیپ‌هایِ تابلو (QUICK_FILTERS درِ
// tapeStore) دستی انتخاب می‌شوند و داوری‌شان عیناً پرچمِ بک‌اند است، نه آینه.
const FILE_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'] as const;

/** واژگانِ روندِ موتور (`_fts_classify_trend`) به زبانِ خودِ چارت ۳ ستون T. */
export const TREND_LABEL: Record<string, string> = {
  up: 'صعودی',
  down: 'نزولی',
  range: 'خنثی',
  na: 'بی‌ساختار',
};

export function trendLabel(t: string | null | undefined): string {
  if (!t) return '—';
  return TREND_LABEL[t] ?? '—';
}

/** سرستون‌هایِ پنج‌شاخصه — عینِ پنج سطرِ صفحۀ ۱ چارت (بنیادی:F). */
export const IND_COLUMNS = [
  { key: 'i1', label: 'رشد فروش', full: 'درآمد و فروش از ابتدای سال تا اکنون، در برابرِ سالِ قبل (کفِ ۴۰٪، هدفِ ۶۰٪)' },
  { key: 'i2', label: 'EPSِ سه‌ساله', full: 'EPS (سود و زیان) سه سال گذشته' },
  { key: 'i3', label: 'حاشیه ناخالص', full: 'حاشیه سود ناخالص (کفِ ۲۰٪، استانداردِ ۳۰٪)' },
  { key: 'i4', label: 'فروش÷ارزش', full: 'تخمینِ فروشِ ۱۲ ماهه ÷ ارزش بازار (کفِ ۰٫۳۳، ایده‌آلِ ۱٫۰)' },
  { key: 'i5', label: 'نرخ‌گذاری', full: 'نرخ‌گذاری دلاری/ریالی — دستوری بودن وتو است' },
] as const;

/**
 * سبکِ انتخابی درِ همان درخت استراتژی، دربِ قیف را تعیین می‌کند — عینِ شاخۀ
 * «فیلتر» در چارت ۳ (S: SELECTION)ِ جزوه: نوسان‌گیر = ساعت + جت + حجم مشکوک،
 * روندگیر = کف‌روبی + نقطه‌زنی (ورود در کف سوم یا پنجم). ساعت شنی در چارت ۴
 * با MA=52 و RSI=5 هفتگی تعریف شده و فیلترِ تابلوییِ جدا ندارد، پس همان دو
 * گره‌ای که درخت برایش گذاشته (کف‌روبی + ساعت) می‌ماند و چیزی اضافه نمی‌شود.
 */
export type TreePreset = 'swing' | 'trend' | 'hourglass' | 'custom' | 'tech_first';

export const PRESET_ENTRY: Record<TreePreset, { label: string; filters: string[] }> = {
  swing: { label: 'شخص نوسان‌گیر (زیر ۳ ماه)', filters: ['f_clock', 'f_jet', 'f_susp'] },
  trend: { label: 'شخص روندگیر (بالای ۳ ماه)', filters: ['f_roobi', 'f_noqteh'] },
  // رأیِ Q-1 و `funnel_registry.py`: ساعت شنی درِ هیچ منبعی فیلترِ تابلویی ندارد
  // (تعریفش گیتِ هفتگی MA=52/RSI=5 است). آینهٔ فرانت پیش‌تر کف‌روبی+ساعت را
  // قرض می‌گرفت که بی‌منبع بود و با موتور نمی‌خواند.
  hourglass: { label: 'استراتژی ساعت شنی (۳ تا ۱۰ ساله)', filters: [] },
  // استراتژیِ «تکنیکال اول»: زنجیرۀ تابلو از چیپ‌هایِ خودِ کاربر می‌آید (مثلِ
  // بقیۀ اشخاص)، ولی موتور اول گیتِ هفتگی و شرط‌هایِ تکنیکال را اجرا می‌کند.
  tech_first: { label: 'تکنیکال‌محور (تکنیکال ← تابلو ← بنیادی ← تحویل)', filters: [] },
  // مسیرِ دستی: خودِ کاربر گره‌ها را چیده، پس قیف با پنج فیلتر باز می‌شود و
  // چیپ‌هایِ روشنِ تبِ تابلو همان‌ها را باریک می‌کنند.
  custom: { label: 'مسیر سفارشی (انتخاب دستی)', filters: [...FILE_FILTERS] },
};

/** نامِ خودِ چیپ‌ها، برایِ پیش‌نمایِ/personِ انتخابی (۱۴۰۵-۰۷-۲۰). هفت تا، عینِ
 *  `tapeStore.QUICK_FILTERS` — master از market import نمی‌گیرد (مرزِ FSD). */
export const FILTER_LABEL: Record<string, string> = {
  f_clock: 'الگوی ساعت',
  f_susp: 'حجم مشکوک',
  f_jet: 'فیلتر جت',
  f_roobi: 'کف‌روبی',
  f_noqteh: 'نقطه زنی',
  f_smart: 'ورود پول هوشمند',
  f_legal: 'کد به کد حقوقی به حقیقی',
};

/** انگیزۀ هر شخص، به زبانِ خودِ فایل (چارت ۳ و جزوه) — برایِ پیش‌نمایش. */
export const PRESET_MOTIVE: Record<TreePreset, string> = {
  swing: 'نوسان‌گیر: از تابلو وارد می‌شود؛ ساعت و جت و حجم مشکوک نشانهٔ پولِ امروزند.',
  trend: 'روندگیر: کف سوم یا پنجم؛ حجم مشکوک لازم نیست (جزوه: «روندگیر به حجم مشکوک نیازی ندارد»).',
  hourglass: 'ساعت شنی: فیلترِ تابلویی ندارد؛ دربش MA=52 و RSI=5 در تایم هفتگی است.',
  tech_first: 'تکنیکال‌محور: اول ساختارِ هفتگی و شرط‌هایِ تکنیکالِ شما رأی می‌دهد، سپس تابلوخوانی رویِ همان ماندگان. گیتِ هفتگی با انتخابِ ستاپ خاموش نمی‌شود.',
  custom: 'مسیر سفارشی: خودتان فیلترها را انتخاب و مرتب می‌کنید؛ چیپ‌هایِ بالایِ غربالگری همین زنجیره را کم و زیاد می‌کنند.',
};

/** شش‌حالته — تنها واژگانِ داوریِ کشفِ نماد درِ کلِ فرانت (مقادیرِ
 *  `funnel_engine.STATUSES`؛ ششمین (`not_in_universe`) حکمِ گام نیست، عضو
 *  نبودنِ نماد درِ خودِ جامعۀ غربالگری است). */
export type StageStatus = 'pass' | 'reject' | 'pending' | 'unavailable'
  | 'not_required' | 'not_in_universe' | 'not_applicable';

export const STATUS_LABEL: Record<StageStatus, string> = {
  pass: 'تأیید',
  reject: 'رد',
  pending: 'در انتظار',
  unavailable: 'داده در دسترس نیست',
  not_required: 'لازم نبود',
  not_in_universe: 'خارج از جامعۀ غربالگری',
  // «کاربرد ندارد» با «قابل ارزیابی نیست» دو چیزند (رأیِ مالک ۱۴۰۵-۰۷-۲۱):
  // این یکی یعنی خودِ منبع نظر نمی‌دهد، آن یکی یعنی داده نرسیده است.
  not_applicable: 'کاربرد ندارد',
};

export const STATUS_HINT: Record<StageStatus, string> = {
  pass: 'درِ جزوه باز است.',
  reject: 'موتور صریحاً رد کرد — این تصمیم است، نه کمبودِ داده.',
  pending: 'این نماد بررسی شده اما هنوز نتیجهٔ قطعی ندارد؛ بنابراین رد نشده است (نقطه‌زنی سنجیده‌نشده، روند هفتگی بی‌حکم، ابزار بی‌FTS).',
  unavailable: 'هیچ منبعی برایِ این مرحله نبود؛ «رد» نیست و نباید رد خوانده شود.',
  not_required: 'گامِ پیشینِ غربالگری نماد را رد کرده بود؛ این گام اجرا نمی‌شود. توقفِ توضیح‌دار است، نه «سنجیده نشده».',
  not_in_universe: 'این نماد عضو جامعۀ غربالگری نبود: وضعیتِ رسمیِ بازار (تعلیق، ممنوع، یا ردیفِ روزِ معاملاتیِ کهنه) اجازهٔ غربال نمی‌دهد. نه «رد» است و نه «سنجیده نشده».',
  not_applicable: 'این شاخص برایِ این نماد معنا ندارد (مبنایِ تلفیقی، نبودِ سطرِ بهای تمام‌شده، یا طبقۀ صندوق/هلدینگ)؛ بنابراین نه رد شده و نه در انتظارِ داده است.',
};

export type FunnelMode = 'reverse' | 'review';

export const MODE_LABEL: Record<FunnelMode, string> = {
  reverse: 'مهندسی معکوس FTS',
  review: 'مرورِ کامل بازار',
};

export const MODE_PATH: Record<FunnelMode, string> = {
  reverse: 'اول تابلوخوانی، سپس تکنیکال، بعد بنیادی، در پایان تحویل',
  review: 'کلِ بازار از بنیادی شروع می‌شود، سپس تکنیکال، در پایان تحویل',
};

export const MODE_HINT: Record<FunnelMode, string> = {
  reverse:
    'همان مسیرِ جزوه (صفحۀ ۴: ۱ تابلو ۲ تکنیکال ۳ بنیادی): غربالگری از نشانه‌هایِ تابلویِ امروز شروع می‌شود.',
  review:
    'برایِ بازارِ بسته یا وقتی تابلو در دسترس نیست: کلِ universe از فیلترِ بنیادی وارد می‌شود و تکنیکال بررسی می‌شود. تابلو درِ ورود را نمی‌بندد — نبودنش «رد» نیست.',
};

/** تازگیِ خوراکِ تابلو — برایِ اینکه دادهٔ دیروز جایِ زنده خوانده نشود (#16). */
export type TapeFreshness = 'live' | 'stale' | 'unavailable';

export const TAPE_FRESHNESS_LABEL: Record<TapeFreshness, string> = {
  live: 'تابلویِ زنده',
  stale: 'تابلو — آخرین روز معاملاتی',
  unavailable: 'تابلو در دسترس نیست',
};

export type FunnelStageKey = 'tape' | 'technical' | 'fundamental' | 'handover';

export const STAGE_KEYS: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

/** ترتیبِ واقعیِ اجرا را `funnel_engine` درِ پاسخ می‌نویسد (`flow`)؛ فرانت آن را
 *  می‌خواند و هیچ قاعده‌ای دربارهٔ ترتیب نمی‌سازد. `tape_first` همان ترتیبِ
 *  جزوه است و `tech_first` استراتژیِ تازه: گیتِ هفتگی و شرط‌هایِ تکنیکال اول،
 *  فیلترهایِ تابلو بعد. */
export type FunnelFlow = 'tape_first' | 'tech_first';

export const FLOW_LABEL: Record<FunnelFlow, string> = {
  tape_first: 'تابلو ← تکنیکال',
  tech_first: 'تکنیکال ← تابلو',
};

export const FLOW_PATH: Record<FunnelFlow, string> = {
  tape_first: 'تابلوخوانی ← تکنیکال ← بنیادی ← تحویل',
  tech_first: 'تکنیکال ← تابلوخوانی ← بنیادی ← تحویل',
};

export const FLOW_HINT: Record<FunnelFlow, string> = {
  tape_first: 'ترتیبِ جزوه (صفحۀ ۴): اول نشانه‌هایِ تابلویِ امروز، سپس گیتِ هفتگی.',
  tech_first: 'اول گیتِ روندِ هفتگی و شرط‌هایِ تکنیکالِ انتخابی؛ فیلترهایِ تابلو رویِ همان ماندگان اجرا می‌شوند.',
};

/** ترتیبِ گام‌ها برایِ هر جریان — تنها جایِ تعریفِ «کدام جدول اول می‌آید». */
export function stageOrderOf(flow: FunnelFlow): FunnelStageKey[] {
  if (flow === 'tech_first') return ['technical', 'tape', 'fundamental', 'handover'];
  return [...STAGE_KEYS];
}

/**
 * دو پیچِ تنظیمی که درِ بنیادی را به دستِ خودِ مالک می‌دهند (بی‌آنکه سخت‌گیریِ
 * جزوه را کم کنند — پیش‌فرضِ هر دو عینِ جزوه است):
 *   - `fundFloor` : چند شاخص از پنج‌شاخصه کافی است.
 *   - `unmeasured`: سرنوشتِ ردیفی که بنیادش واقعاً سنجیده نشده (صندوق، اختیار،
 *     حق تقدم یا هر آنچه در ۸۷۳ شرکتِ اسکرینر نیست).
 */
export type FunnelOptions = {
  fundFloor: number;
  unmeasured: UnmeasuredPolicy;
  /** true = تکنیکال غربال می‌کند (جزوه). false = ردشده‌ها فقط برچسب می‌خورند
   *  و به بنیادی می‌رسند، تا خودِ مالک ستونِ روندِ هفتگی را بخواند. */
  techScreens: boolean;
};

export const DEFAULT_FUNNEL_OPTIONS: FunnelOptions = {
  fundFloor: DEFAULT_FUND_FLOOR,
  unmeasured: DEFAULT_UNMEASURED,
  techScreens: DEFAULT_TECH_SCREENS,
};

/** زمینۀ اجرا: حالت + تازگیِ تابلو + زمانِ داده‌ها. همه اختیاری تا فراخوانیِ
 *  پیشینِ تک‌ردیفه (`symbolStageProgress`) نشکند. */
export type FunnelContext = {
  mode: FunnelMode;
  tape: TapeFreshness;
  /** `as_of` خودِ بک‌اند (`/api/screener`) — ثانیهٔ epoch؛ null یعنی پاسخِ قدیمی
   *  این فیلد را ندارد و از زمانِ دریافتِ خودِ کلاینت می‌خوانیم. */
  screenAsOf: number | null;
  /** زمانِ دریافتِ رأیِ زندهٔ هر نماد (`/api/fts/{symbol}`) */
  techAsOf: Map<string, number>;
};

export const DEFAULT_FUNNEL_CONTEXT: FunnelContext = {
  mode: 'reverse',
  tape: 'live',
  screenAsOf: null,
  techAsOf: new Map(),
};

/** شمارشِ هر مرحلۀ قیف — «چند تا واقعاً ماند»، نه «چند تا خواسته بود».
 *  جمعِ این پنج عدد درِ هر گام باید با جامعۀ غربالگری (`Funnel.total`) بخواند
 *  (گاردِ مالک: `input universe == output evaluated symbols`); «سنجیده نشده»
 *  جایِ خودِ `pending`/`unavailable` را پر نمی‌کند، چون نبودش یعنی نمادی
 *  بی‌حکم مانده. نمادهایِ خارج از جامعه درِ این پنج عدد نیستند و ششمین
 *  وضعیتِ `coverage` (`not_in_universe`) شمارشان را جدا می‌دهد. */
export type StageSummary = {
  pass: number;
  reject: number;
  pending: number;
  unavailable: number;
  not_required: number;
};

export type Candidate = {
  symbol: string;
  name: string;
  sector: string;
  /** طبقهٔ ابزار — همان «صندوق/اختیار/حق تقدم» که پنج‌شاخصه دربارهٔ آنها نظر نمی‌دهد */
  kind: AssetType;
  /** ردیفِ نمایشیِ قیف — فقط فیلدهای `FunnelRowView`؛ پرچم‌های تابلو اینجا نیستند */
  row: FunnelRowView | null;
  /** همان برای اسکرین — `score` اینجا null‌پذیر است، نه بازهٔ ۰..۵ِ اسکرینر */
  screen: FunnelScreenView | null;
  /** برچسبِ پنج فیلترِ فایل که این ردیف درِ تابلو رد کرد — عینِ بجِ ستونِ «الگو» */
  patterns: string[];
  /** چهار درِ قیف، با یک واژگانِ واحد */
  status: Record<FunnelStageKey, StageStatus>;
  why: Record<FunnelStageKey, string>;
  score: number | null;
  /** روندِ دو زمانه همان‌طور که موتور می‌بیند: 'up' | 'down' | 'range' | 'na' | null */
  trendW: string | null;
  trendD: string | null;
  /** شاخهٔ روزانه طبق چارت: جت/پولبک، فیبوناچی/CHoCH یا کف‌دوقلو/آخرین ساختار */
  dailyStrategy: string | null;
  /** ستاپ‌های فعالِ این نماد (جت/فیبو/CHoCH/…) — فقط شواهدِ مثبت/کمکی، نه گیت */
  setups: string;
  /** شرط‌هایِ اجراشدۀ همین گام (گیتِ هفتگی + انتخاب‌هایِ کاربر) به ترتیبِ اجرا */
  techChecks: TechCheck[];
  /** زمانِ ساختِ همین داوری درِ `funnel_tech_scan` (epoch ثانیه). تاریخِ خودِ
   *  ماشه درِ اسکن ذخیره نمی‌شود، پس رابط این را «تاریخِ داوری» می‌خواند، نه
   *  «تاریخِ سیگنال» — عددِ ساخته‌نشده. */
  techVerdictAt: number | null;
  /** امتیازِ کمکیِ تکنیکال برای Ranking؛ هرگز درِ T را به‌تنهایی باز/بسته نمی‌کند. */
  technicalPoints: number | null;
  /** تک‌تکِ پنج شاخص: pass / reject / pending / not_required — همان سطرهای صفحۀ ۱ چارت */
  inds: StageStatus[];
  /** «عبور با ملاحظات» از خودِ موتور: حداقل سه PASS ولی بعضی شاخص‌ها رد یا ناقص.
   *  نشانِ زرد است و هیچ وزنی در امتیاز/رتبه ندارد (رأیِ مالک ۱۴۰۵-۰۷-۲۱). */
  fundCaveat: boolean;
  /** شمارِ واقعیِ شاخص‌های PASS و کفِ عبور — برایِ متنِ علت، نه شمارشِ رابط */
  fundPassed: number | null;
  fundMinPass: number | null;
  /** رأیِ تکنیکال از کجا آمده: `live` = `/api/fts/{symbol}`، `screen` = غنی‌سازیِ
   *  اسکرینر (سقفِ `watchlist_max`)، `null` = هیچ‌کدام — «بی‌داده» */
  techSource: 'live' | 'screen' | null;
  /** شواهدِ ستاپِ جت از رأیِ زنده — برایِ «فاصله تا ماشه»؛ بی‌رأیِ زنده `null` است */
  jetEvidence: { resistance: number | null; pctAboveRes: number | null } | null;
  /** وتوی مجمعِ پیش‌رو — داوریِ بک‌اند (`assembly_veto` در /api/screener)، نه یک
   *  فرمولِ دوم در فرانت. رأیِ مالک است، نه چارتِ چهارصفحه‌ای. */
  assemblyVeto: boolean;
  assemblyWhy: string;
  /** رتبۀ رسمیِ بک‌اند درِ `/api/screener` (excluded ➔ primary_score ➔ score ➔ mcap
   *  ➔ symbol). `null` یعنی درِ اسکرینر نبود. تنها مبنایِ صفِ تکنیکال. */
  screenRank: number | null;
  /** وضعیتِ معاملاتیِ این نماد از جهانِ زندۀِ خودِ بک‌اند (`market_universe`) و
   *  اولویتِ نمایشش (کمتر = زنده‌تر). `null` یعنی هنوز در این اجرا مشاهده نشده.
   *  این دو هرگز گیت نیستند: نمادی که همین حالا معامله ندارد از غربالگری حذف
   *  نمی‌شود، فقط رو‌به‌رو قرار می‌گیرد (بندِ ۲ و ۳ مأموریتِ P1). `undefined`
   *  یعنی بک‌اند این دور آن را گزارش نکرده (نسخۀ قدیمیِ نصبی). */
  universePriority?: number | null;
  universeStatus?: string | null;
};

/** نتیجۀ یک شرطِ تکنیکال رویِ همین نماد — همان دیکشنری‌هایی که `technical_stage`
 *  درِ بک‌اند ساخته است. `value` عینِ ستونِ `funnel_tech_scan` است و `status` حکمِ
 *  همان سطر؛ هیچ‌کدام درِ فرانت دوباره حساب نمی‌شود. `origin` می‌گوید شاهد از
 *  جزوه آمده یا از برنامۀ خودِ برنامه (ستاپی که سطرِ مستقلِ جزوه ندارد). */
export type TechCheck = {
  filterId: string;
  label: string;
  role: string;
  column: string;
  value: string | number | null;
  status: StageStatus;
  reasonCode: string;
  humanReason: string;
  source: string;
  origin: string;
};

/** شمارشِ یک فیلترِ تکنیکال رویِ ورودیِ همین گام
 *  (`stages.technical.filter_counts`ِ خودِ موتور). نامِ فیلتر از رجیستریِ همان
 *  سرور می‌آید، پس اینجا عددِ مستقلی برایِ متن نداریم. */
export type TechFilterCount = {
  pass: number; reject: number; pending: number; unavailable: number;
};

/** سازۀ پیشینِ `FunnelEntry` — نامِ کوتاهِ همان کاندید، برایِ خواناییِ رندررها. */
export type FunnelEntry = Candidate;

/** یک گام از زنجیرۀ تابلو — شمارشِ ترتیب‌محور، همان چیزی که موتور گفته است.
 *  نمایشِ «۵۸۶۵ → ۱۲۱ → ۴» اثباتِ دیدنیِ اشتراکِ ترتیبی است، نه چیزِ دیگری. */
export type StageStep = {
  seq: number; filter_id: string; label: string;
  input_count: number; matched_count: number; removed_count: number;
  unmeasured_count?: number; source_ref?: string; formula_version?: string;
  parameter_set?: Record<string, unknown>; status?: StageStatus;
};

export type FunnelStage = {
  key: FunnelStageKey;
  entries: Candidate[];
  /** گام‌هایِ درونیِ همین مرحله (فعلاً تابلو: هر فیلتر با شمارشِ خودش) */
  steps: StageStep[];
  /** چند نماد واردِ این گام شد — از `stages.<key>.inputِ` خودِ موتور. بدونِ آن
   *  «۱۰ از ۱۰۳۵» با «۱۰ از ۱۰» یکی خوانده می‌شد. */
  input: number;
  /** چه تعداد از مرحلۀ قبل بیرون افتاد (تکنیکال و بنیادی هر دو حذف می‌کنند) */
  dropped: number;
  /** چه تعداد روی این مرحله برچسبِ «رد» خوردند — با «رد نکند، خودم چک می‌کنم»
   *  dropped صفر است ولی این شمار همان ردشده‌ها را نشان می‌دهد */
  rejected: number;
  /** چه تعداد درِ همین گام «داده در دسترس نبود» — یعنی سنجشِ نشدنی، نه رد */
  unmeasured: number;
  /** چه تعداد گامِ پیشین جلویِ رسیدن به این مرحله را گرفته (`not_required`) */
  notRequired: number;
  /** چند نماد از جامعۀ ورودی درِ همین گام حکم دارند — باید با `Funnel.total`
   *  بخواند؛ کمتر باشد یعنی نمادی بی‌حکم گم شده (خطایِ معماری، نه حالتِ عادی) */
  ruled: number;
  /** در مرحلۀ بنیادی: سنجیده‌نشده‌ها — نه رد شده‌اند، نه به تحویل می‌روند */
  pending: Candidate[];
  /** شمارشِ پنج‌حالتيِ همین مرحله رویِ **کلِ** جامعۀ ورودی (از `coverage`ِ بک‌اند) */
  summary: StageSummary;
};

/** یک نمادِ بیرون از جامعۀ غربالگری — با علتِ استخراج‌شدۀ خودِ بازار.
 *  درِ جدولِ چهار گام نمایش داده نمی‌شود (رأیِ مالک: جدول را شلوغ نکن); درِ
 *  بخشِ بازشوندهٔ «خارج از جامعۀ غربالگری» و درِ بازرِسِ همان نماد می‌نشیند. */
export type UniverseExclusion = {
  symbol: string;
  name: string;
  sector: string;
  last: number | null;
  reasonCode: string;
  humanReason: string;
  stateCode: string | null;
  stateTitle: string | null;
  stopState: string | null;
  isLive: boolean | null;
};

/** شمارشِ یک فیلتر رویِ **نامزدِ جاری** — از `stages.tape.filter_counts` خودِ
 *  موتور. «نامزد» همان `matched` است رویِ همان مجموعه‌ای که همین حالا رویِ میز
 *  است (leave-one-out از چیپ‌هایِ روشن)؛ `unmeasured` پرچمی است که موتور درباره‌اش
 *  نظر نداد (نه رد، نه قبول). `universe` کلِّ جامعۀ غربالگری است. */
export type FilterCount = {
  name: string; matched: number; removed: number; unmeasured: number;
  input: number; universe?: number;
};

export type Funnel = {
  mode: FunnelMode;
  /** ترتیبِ واقعیِ اجرا از خودِ موتور (`flow`) — تنها مبنایِ «کدام جدول اول» */
  flow: FunnelFlow;
  /** ترتیبِ گام‌ها همان `flow` است؛ رندررها این را می‌خوانند، نه فهرستِ دستی */
  stageOrder: FunnelStageKey[];
  /** زنجیرۀ فیلترهایِ تکنیکالِ اجراشده (گیتِ هفتگی همیشه مقدم) */
  techChain: string[];
  tape: TapeFreshness;
  /** پوششِ داوریِ تکنیکال: چند کاندید رأیِ زنده داشت، چند تا فقط از غنی‌سازیِ
   *  اسکرینر (`watchlist_max`) خوانده شد، و چند تا هیچ منبعی نداشتند (#12).
   *  خودِ بودجه/سقف را `useFtsTechBoard` گزارش می‌کند، نه این مدل. */
  techCoverage: { universe: number; live: number; fromScreen: number; none: number };
  /** نمادهایِ جامعِ دو مرحلۀ آخر = آنچه درِ تحویل است */
  stages: Record<FunnelStageKey, FunnelStage>;
  boardScope: number;
  /**epoch ثانیه‌ایِ خودِ سرور درِ لحظۀِ داوری (`as_of` پاسخِ `/api/funnel`).
   *  تا پیش از این هیچ‌جا نمایش داده نمی‌شد، پس کاربر نمی‌فهمید «آخرین محاسبۀ
   *  موفق» کِی بوده و با «در حال محاسبه» قاطی می‌شد. */
  asOf: number | null;
  /** جامعۀ غربالگری — همان چیزی که جدولِ هر گام از آن ساخته می‌شود و جمعِ
   *  پنج وضعیتِ هر گام با آن می‌خواند. */
  total: number;
  /** جامعۀ تابلو: تک‌تکِ نمادهایِ این نشست (غربالگری + خارج‌ها). `X = Y + Z`. */
  marketUniverse: number;
  /** شمارِ خارج از جامعۀ غربالگری (Z) */
  excludedCount: number;
  /** آیا موتور واقعاً «حذفِ پسوندِ عددی» را اعمال کرد؟ `null` = پاسخِ بی‌این field */
  dropSuffixApplied: boolean | null;
  /** علتِ خروجِ تک‌تکِ خارج‌ها، به همان ترتیبِ خودِ تابلو */
  exclusions: UniverseExclusion[];
  /** شمارشِ علت‌ها (مثلاً `NOT_LIVE_SESSION: ۱۸۷۲`) — از خودِ بک‌اند */
  exclusionCounts: Record<string, number>;
  /** واژۀ فارسیِ هر علت، همان‌که موتور می‌گوید (رابط دوم نمی‌سازد) */
  exclusionLabels: Record<string, string>;
  /** شمارشِ واقعیِ هر چهار در (رویِ جامعۀ غربالگری) */
  counts: Record<FunnelStageKey, StageSummary>;
  /** نامزدِ هر یک از هفت فیلتر، مستقل از زنجیره و از اشتراک/اجتماع — برایِ عددِ
   *  کنارِ چیپ‌هایِ نوارِ غربالگری. `{}` = پاسخِ سرورِ قدیمی این را نگفته. */
  filterCounts: Record<string, FilterCount>;
  /** شمارشِ هر فیلترِ تکنیکال رویِ ورودیِ گامِ تکنیکال
   *  (`stages.technical.filter_counts`) — عددِ کنارِ چیپ‌هایِ همین گام. */
  techFilterCounts: Record<string, TechFilterCount>;
  /** هدف‌هایِ جزوه (رأیِ ۶): هیچ‌کدام گیت نیستند، فقط مرجعِ نمایش‌اند. */
  targets: { initial: number; watchlist: number; basketMin: number; basketMax: number };
};
