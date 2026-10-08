// features/master/lib/ftsFunnel.ts -- قراردادِ نمایشِ قیف FTS (مدل، نه داور)
//
// ترتیبِ مرحله از خودِ جزوه است: تابلوخوانیِ امروز ← تکنیکال ← بنیادیِ پنج‌شاخصه ← تحویل.
//
// داوریِ کشفِ نماد دیگر درِ این فایل نیست. `funnel_engine.py` حکمِ canonical را
// می‌سازد، `/api/funnel` همان را می‌دهد و `lib/funnelView.ts` فقط نام‌هایِ پاسخ
// را به همین مدلِ نمایشی برمی‌گرداند. آنچه اینجا مانده نوع‌ها، برچسب‌ها و
// واژگانِ وضعیت‌اند: هیچ `if` قاعده‌ای، هیچ آستانه‌ای، هیچ `slice`اي.
//
// پنج‌حالته — تنها واژگانِ وضعیتِ هر گام درِ کلِ فرانت (بندِ ۱۹ و ۳۵ از قانونِ
// مالک: «سنجیده نشده» ممنوع؛ هر نماد درِ هر گام یک حکمِ قابلِ توضیح دارد):
//   pass         درِ جزوه باز
//   reject       درِ جزوه بسته — داوریِ صریحِ موتور
//   pending      موتور نگاه کرد و نظر نمی‌دهد (هفتگی UNKNOWN، صندوق «FTS ندارد»،
//               نقطه‌زنی‌ای که اسکرینر فیلدش را ندارد)
//   unavailable  منبعی برایِ داوریِ این مرحله نبود — هیچ‌وقت رد نیست
//   not_required گامِ پیشین نماد را رد کرده؛ این گام اجرا نمی‌شود. توقفِ قطعی و
//               توضیح‌دار است، نه «بی‌سنجش» — reason_code نامِ گامِ بازدارنده را
//               درِ خودِ کد می‌نویسد (NOT_REQUIRED_AFTER_TAPE_REJECT و…).
import type { MarketRow } from '@shared/types/marketRow';
import type { AssetType } from '@features/market/lib/assetType';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
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
export type TreePreset = 'swing' | 'trend' | 'hourglass' | 'custom';

export const PRESET_ENTRY: Record<TreePreset, { label: string; filters: string[] }> = {
  swing: { label: 'شخص نوسان‌گیر (زیر ۳ ماه)', filters: ['f_clock', 'f_jet', 'f_susp'] },
  trend: { label: 'شخص روندگیر (بالای ۳ ماه)', filters: ['f_roobi', 'f_noqteh'] },
  hourglass: { label: 'استراتژی ساعت شنی (۳ تا ۱۰ ساله)', filters: ['f_roobi', 'f_clock'] },
  // مسیرِ دستی: خودِ کاربر گره‌ها را چیده، پس قیف با پنج فیلتر باز می‌شود و
  // چیپ‌هایِ روشنِ تبِ تابلو همان‌ها را باریک می‌کنند.
  custom: { label: 'مسیر سفارشی (انتخاب دستی)', filters: [...FILE_FILTERS] },
};

/** پنج‌حالته — تنها واژگانِ داوریِ کشفِ نماد درِ کلِ فرانت. */
export type StageStatus = 'pass' | 'reject' | 'pending' | 'unavailable' | 'not_required';

export const STATUS_LABEL: Record<StageStatus, string> = {
  pass: 'تأیید',
  reject: 'رد',
  pending: 'در انتظار',
  unavailable: 'داده در دسترس نیست',
  not_required: 'لازم نبود',
};

export const STATUS_HINT: Record<StageStatus, string> = {
  pass: 'درِ جزوه باز است.',
  reject: 'موتور صریحاً رد کرد — این تصمیم است، نه کمبودِ داده.',
  pending: 'موتور نگاه کرد و نظر نداد (نقطه‌زنی سنجیده‌نشده، روند هفتگی بی‌حکم، ابزار بی‌FTS).',
  unavailable: 'هیچ منبعی برایِ این مرحله نبود؛ «رد» نیست و نباید رد خوانده شود.',
  not_required: 'گامِ پیشینِ قیف نماد را رد کرده بود؛ این گام اجرا نمی‌شود. توقفِ توضیح‌دار است، نه «سنجیده نشده».',
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
    'همان مسیرِ جزوه (صفحۀ ۴: ۱ تابلو ۲ تکنیکال ۳ بنیادی): قیف از نشانه‌هایِ تابلویِ امروز شروع می‌شود.',
  review:
    'برایِ بازارِ بسته یا وقتی تابلو در دسترس نیست: کلِ universe از فیلترِ بنیادی وارد می‌شود و تکنیکال بررسی می‌شود. تابلو درِ ورود را نمی‌بندد — نبودنش «رد» نیست.',
};

/** تازگیِ خوراکِ تابلو — برایِ اینکه دادهٔ دیروز جایِ زنده خوانده نشود (#16). */
export type TapeFreshness = 'live' | 'stale' | 'unavailable';

export const TAPE_FRESHNESS_LABEL: Record<TapeFreshness, string> = {
  live: 'تابلویِ زنده',
  stale: 'تابلو — آخرینِ نشست',
  unavailable: 'تابلو در دسترس نیست',
};

export type FunnelStageKey = 'tape' | 'technical' | 'fundamental' | 'handover';

export const STAGE_KEYS: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

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
 *  جمعِ این پنج عدد درِ هر گام باید با جامعۀ ورودی بخواند (گاردِ مالک:
 *  `input universe == output evaluated symbols`); «سنجیده نشده» جایِ خودِ
 *  `pending`/`unavailable` را پر نمی‌کند، چون نبودش یعنی نمادی بی‌حکم مانده. */
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
  row: MarketRow | null;
  screen: FtsScreenRow | null;
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
  /** امتیازِ کمکیِ تکنیکال برای Ranking؛ هرگز درِ T را به‌تنهایی باز/بسته نمی‌کند. */
  technicalPoints: number | null;
  /** تک‌تکِ پنج شاخص: pass / reject / pending — همان سطرهای صفحۀ ۱ چارت */
  inds: StageStatus[];
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

export type Funnel = {
  mode: FunnelMode;
  tape: TapeFreshness;
  /** پوششِ داوریِ تکنیکال: چند کاندید رأیِ زنده داشت، چند تا فقط از غنی‌سازیِ
   *  اسکرینر (`watchlist_max`) خوانده شد، و چند تا هیچ منبعی نداشتند (#12).
   *  خودِ بودجه/سقف را `useFtsTechBoard` گزارش می‌کند، نه این مدل. */
  techCoverage: { universe: number; live: number; fromScreen: number; none: number };
  /** نمادهایِ جامعِ دو مرحلۀ آخر = آنچه درِ تحویل است */
  stages: Record<FunnelStageKey, FunnelStage>;
  boardScope: number;
  total: number;
  /** شمارشِ واقعیِ هر چهار در */
  counts: Record<FunnelStageKey, StageSummary>;
  /** هدف‌هایِ جزوه (رأیِ ۶): هیچ‌کدام گیت نیستند، فقط مرجعِ نمایش‌اند. */
  targets: { initial: number; watchlist: number; basketMin: number; basketMax: number };
};
