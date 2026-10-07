// features/master/lib/ftsFunnel.ts -- قراردادِ canonical کاندیدهایِ FTS (یک مدل، چند رندرر)
//
// ترتیبِ مرحله از خودِ جزوه است و از همان چیزهایی که درِ «درخت استراتژی FTS»
// ستون‌ست: تابلوخوانیِ امروز ← تکنیکال ← بنیادیِ پنج‌شاخصه ← تحویل.
//
// این فایل **تنها** جایِ داوریِ کشفِ نماد درِ فرانت است. فهرست‌هایِ تحویلِ پیشین (حذف‌شده در Round M §۶) و
// `FtsFunnelStages` و سایدبارِ چپ همه فقط خروجیِ همین‌ را می‌خوانند؛ هیچ‌کدام
// گیتِ دومِ «score>=3» یا `slice(0,50)` یا برچسبِ ستاپِ دست‌ساز ندارند. هر چیزی
// که آن‌ها نشان می‌دهد یا از داوریِ بک‌اند می‌آید (`api/chart.py`،
// `api/screener.py`، `tape_flags.py`) یا بی‌برچسب می‌ماند.
//
// دو حالت، یک قرارداد:
//   reverse (پیش‌فرضِ جزوه): S ➔ T ➔ F ➔ M — از تابلویِ امروز شروع می‌شود.
//   review  (مرورِ کامل بازار): Universe ➔ F ➔ T ➔ M — برایِ وقتی که تابلویِ زنده
//     نیست یا کاربر می‌خواهد کلِ universe را مستقلِ از تابلو ببیند. در این حالت
//     تابلو درِ ورود را **نمی‌بندد**؛ فقط اگر نشانه‌ای باشد خبر می‌دهد.
//
// قانونِ «بی‌داده وتو نیست» همه‌جا برقرار است و حالا چهارحالته، نه سه‌حالته:
//   pass        درِ جزوه باز
//   reject      درِ جزوه بسته — داوریِ صریحِ موتور
//   pending     موتور نگاه کرد و نظر نمی‌دهد (هفتگی UNKNOWN، صندوق «FTS ندارد»،
//               نقطه‌زنی‌ای که اسکرینر فیلدش را ندارد)
//   unavailable منبعی برایِ داوریِ این مرحله نبود (ردیفِ اسکرینر نیست، رأیِ زنده
//               نیامده، تابلو در دسترس نیست) — هیچ‌وقت رد نیست
import type { MarketRow } from '@shared/types/marketRow';
import { ASSET_LABELS, classifyAssetType, type AssetType } from '@features/market/lib/assetType';
import { DEFAULT_ASSET_TYPES } from '@features/market/stores/tapeStore';
import { dropNumericSuffixRows } from '@features/market/lib/tapeFts';
import { tapeFilterVerdict, type TapeFilterConfig } from '@features/market/lib/tapeAlgorithms';
import { patternBadges } from '@features/market/lib/tapeBadges';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { TechVerdict } from '../api/useFtsTechBoard';
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

/** چهارحالته — تنها واژگانِ داوریِ کشفِ نماد درِ کلِ فرانت. */
export type StageStatus = 'pass' | 'reject' | 'pending' | 'unavailable';

export const STATUS_LABEL: Record<StageStatus, string> = {
  pass: 'تأیید',
  reject: 'رد',
  pending: 'در انتظار',
  unavailable: 'داده در دسترس نیست',
};

export const STATUS_HINT: Record<StageStatus, string> = {
  pass: 'درِ جزوه باز است.',
  reject: 'موتور صریحاً رد کرد — این تصمیم است، نه کمبودِ داده.',
  pending: 'موتور نگاه کرد و نظر نداد (نقطه‌زنی سنجیده‌نشده، روند هفتگی بی‌حکم، ابزار بی‌FTS).',
  unavailable: 'هیچ منبعی برایِ این مرحله نبود؛ «رد» نیست و نباید رد خوانده شود.',
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

/** شمارشِ هر مرحلۀ قیف — «چند تا واقعاً ماند»، نه «چند تا خواسته بود». */
export type StageSummary = {
  pass: number;
  reject: number;
  pending: number;
  unavailable: number;
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

export type FunnelStage = {
  key: FunnelStageKey;
  entries: Candidate[];
  /** چه تعداد از مرحلۀ قبل بیرون افتاد (تکنیکال و بنیادی هر دو حذف می‌کنند) */
  dropped: number;
  /** چه تعداد روی این مرحله برچسبِ «رد» خوردند — با «رد نکند، خودم چک می‌کنم»
   *  dropped صفر است ولی این شمار همان ردشده‌ها را نشان می‌دهد */
  rejected: number;
  /** چه تعداد «سنجیده نشد» روی این مرحلۀ آنها خورده است */
  unmeasured: number;
  /** در مرحلۀ بنیادی: سنجیده‌نشده‌ها — نه رد شده‌اند، نه به تحویل می‌روند */
  pending: Candidate[];
  /** شمارشِ چهارحالتيِ همین مرحله */
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

/**
 * نمادهایِ تابلویی که قیف از آنها شروع می‌شود: همان نمایِ تبِ تابلو.
 * این سه قیدِ خودکار است و تنظیمِ نمایشِ «پسوندِ عددی» دستِ کاربر را عمداً
 * نمی‌خواند: سوییچ، قواعدۀ نمایشِ جدول را شل می‌کند در حالی که جامعۀ قیف
 * یک قواعدۀ روش‌شناسی است (جزوه: تابلو ← تکنیکال ← بنیادی ← تحویل).
 */
function boardScope(rows: MarketRow[]): MarketRow[] {
  return dropNumericSuffixRows(
    rows.filter((r) => r.is_live !== false && DEFAULT_ASSET_TYPES.includes(classifyAssetType(r))),
  );
}

/** رتبۀ رسمیِ بک‌اند: آرایه‌ای که `/api/screener` می‌دهد **از قبل** با کلیدِ
 *  `screener.py:440` مرتب شده؛ اینجا فقط ایندکس می‌خوانیم تا هیچ رتبه‌بندیِ
 *  تازه‌ای درِ فرانت ساخته نشود. */
export function officialRankMap(screenRows: FtsScreenRow[]): Map<string, number> {
  const m = new Map<string, number>();
  screenRows.forEach((r, i) => {
    if (r.symbol && !m.has(r.symbol)) m.set(r.symbol, i);
  });
  return m;
}

/**
 * رأیِ تکنیکال از دو منبع می‌رسد و هر دو به یک شکل نرمال می‌شوند: ردیفِ
 * اسکرینر (فقط سقفِ `watchlist_max` نماد را تحلیل می‌کند) و `/api/fts/{symbol}`
 * که برایِ خودِ نامادهایِ قیف خوانده می‌شود (`useFtsTechBoard`). هیچ‌کدام رأیِ
 * تازه‌ای نمی‌سازند — هر دو خروجیِ همان موتورِ `api/chart.py`اند.
 */
export type TechSignals = {
  decision: string | null;
  matrixDesc: string | null;
  weeklyVeto: boolean;
  jet: boolean;
  fibZone: string | null;
  chochBull: boolean;
  doubleBottom: boolean;
  rangeBreak: boolean;
  hourglass: boolean;
  /** `null` = این فیلد درِ همان منبع نیست. اسکرینر `point_hunt` منتشر نمی‌کند،
   *  پس «false» ساختنِ آن یعنی نتیجه‌گیریِ از رویِ نبودِ داده (#7). */
  pointHunt: boolean | null;
  /** روندِ خامِ دو زمانه از خودِ موتور (`_fts_classify_trend`) */
  trendW: string | null;
  trendD: string | null;
  jetEvidence: { resistance: number | null; pctAboveRes: number | null } | null;
};

/** ردیفِ اسکرینر؛ `null` یعنی تحلیلِ دو زمانه روی این نماد اجرا نشده است */
export function techFromScreen(sc: FtsScreenRow | null): TechSignals | null {
  if (!sc) return null;
  if (sc.tech_matrix_decision == null && sc.weekly_veto !== true) return null;
  return {
    decision: sc.tech_matrix_decision ?? null,
    matrixDesc: sc.tech_matrix_desc ?? null,
    weeklyVeto: sc.weekly_veto === true,
    jet: sc.tech_jet === true,
    fibZone: sc.tech_fib_zone ?? null,
    chochBull: sc.tech_choch_bull === true,
    doubleBottom: sc.tech_double_bottom === true,
    rangeBreak: sc.tech_range_break === true,
    hourglass: sc.tech_hourglass_active === true,
    // اسکرینر این فیلد را ندارد؛ «نسنجیده» می‌ماند نه «رد».
    pointHunt: null,
    trendW: sc.tech_trend_w ?? null,
    trendD: sc.tech_trend_d ?? null,
    jetEvidence: null,
  };
}

/** رأیِ زندهٔ `/api/fts/{symbol}` — برایِ نمادهایی که اسکرینر تحلیلشان نکرده */
export function techFromVerdict(v: TechVerdict): TechSignals {
  return {
    decision: v.decision,
    matrixDesc: v.matrixDesc,
    weeklyVeto: v.decision === 'REJECT',
    jet: v.jet,
    fibZone: v.fibZone,
    chochBull: v.chochBull,
    doubleBottom: v.doubleBottom,
    rangeBreak: v.rangeBreak,
    hourglass: v.hourglass,
    pointHunt: v.pointHunt,
    trendW: v.trendW ?? null,
    trendD: v.trendD ?? null,
    jetEvidence: v.jetResistance == null && v.jetPctAbove == null ? null : {
      resistance: v.jetResistance ?? null,
      pctAboveRes: v.jetPctAbove ?? null,
    },
  };
}

/**
 * ستاپ‌ها در مرحلۀ T «branch/evidence» هستند، نه شرطِ عبور.
 *
 * چارتِ چهارصفحه‌ای ابتدا ماتریسِ روند را می‌خواند: هفتگی نزولی/خنثی => reject؛
 * هفتگی صعودی => ورود به شاخهٔ روزانه. روزانهٔ صعودی/نزولی/خنثی هر سه شاخهٔ معتبرند.
 * پولبک، جت، فیبو، CHoCH، کف دوقلو، باکس رنج، ساعت شنی و نقطه‌زنی فقط شواهدِ کمکی‌اند.
 * «پولبک» تا وقتی فیلد مستقل و قابل اتکایی از API نداشته باشد این‌جا جعل نمی‌شود.
 */
function dailyBranchFor(t: TechSignals): string | null {
  if (t.trendD === 'up') return 'جت / پولبک';
  if (t.trendD === 'down') return 'فیبوناچی / CHoCH';
  if (t.trendD === 'range') return 'کف دوقلو / آخرین کف-سقف ساختاری';
  return null;
}

function setupEvidenceCount(t: TechSignals): number {
  if (t.trendD === 'up') {
    // Pullback فیلد مستقل ندارد؛ فقط Jet واقعی را از API می‌پذیریم.
    return t.jet ? 1 : 0;
  }
  if (t.trendD === 'down') {
    return [t.fibZone != null, t.chochBull].filter(Boolean).length;
  }
  if (t.trendD === 'range') {
    return t.doubleBottom ? 1 : 0;
  }
  return 0;
}

/**
 * متنِ شاخهٔ روزانه فقط از روند می‌آید، نه از فعال‌شدنِ ستاپ.
 * این تفاوت مهم است: «روزانه صعودی» یعنی شاخهٔ Jet/Pullback، حتی اگر
 * موتور هنوز Jet یا Pullback قطعی پیدا نکرده باشد.
 */
export function technicalDailyBranch(t: TechSignals | null): string | null {
  return t ? dailyBranchFor(t) : null;
}

/**
 * امتیازِ Ranking-only: روندِ هفتگی/روزانه پایه است و فقط شواهدِ مربوط به
 * شاخهٔ همان روزانه امتیاز کمکی می‌گیرند. این عدد هیچ‌گاه درِ T را باز یا بسته نمی‌کند.
 */
export function technicalEvidencePoints(t: TechSignals | null): number | null {
  if (!t || t.trendW !== 'up') return null;
  if (t.trendD !== 'up' && t.trendD !== 'down' && t.trendD !== 'range') return null;
  const weeklyPoints = 2;
  const dailyPoints = t.trendD === 'up' ? 2 : 1;
  const setupPoints = Math.min(2, setupEvidenceCount(t));
  return weeklyPoints + dailyPoints + setupPoints;
}


/** ستاپ‌هایی که همین حالا روی نماد فعال‌اند — برایِ نمایشِ شواهد */
function activeSetups(t: TechSignals): string {
  const on: string[] = [];
  if (t.jet) on.push('جت');
  if (t.fibZone) on.push(`فیبوی ${toFaDigits(t.fibZone)}`);
  if (t.chochBull) on.push('CHoCHِ صعودی');
  if (t.doubleBottom) on.push('کفِ دوقلو');
  if (t.rangeBreak) on.push('باکسِ رنج');
  if (t.hourglass) on.push('ساعت شنی');
  if (t.pointHunt === true) on.push('نقطه‌زنی');
  return on.join(' + ');
}

/**
 * درِ تکنیکال — ترتیبِ قطعیِ داوری:
 *   ۱) روندِ هفتگی
 *   ۲) روندِ روزانه
 *   ۳) ستاپ‌ها فقط شواهد/امتیاز کمکی
 *
 * از چارت: هفتگی نزولی یا خنثی => REJECT. هفتگی صعودی وارد شاخهٔ روزانه می‌شود؛
 * روزانهٔ صعودی/نزولی/خنثی همگی شاخه‌های معتبر خریدند، پس روزانهٔ نزولی یا خنثی
 * به‌خودی‌خود REJECT نیست. اگر یکی از دو روند ناشناخته باشد => PENDING.
 */
function techMark(t: TechSignals | null): { s: StageStatus; why: string } {
  if (!t) {
    return {
      s: 'unavailable',
      why: 'تکنیکال: تحلیلِ دو زمانه روی این نماد اجرا نشده — سنجیده نشد، وتو نیست',
    };
  }

  const weekly = t.trendW;
  if (weekly === 'down' || weekly === 'range') {
    return { s: 'reject', why: `تکنیکال: روندِ هفتگی ${trendLabel(weekly)} است — وتوی FTS` };
  }

  // اگر روند خام در پاسخ نیامده ولی موتور رأیِ صریحِ وتو داده، همان رأی را حفظ می‌کنیم.
  if (weekly == null || weekly === 'na') {
    if (t.weeklyVeto || t.decision === 'REJECT') {
      return { s: 'reject', why: `تکنیکال: رأیِ صریحِ موتور برایِ وتوی هفتگی — ${t.matrixDesc ?? 'روندِ هفتگی مجاز نیست'}` };
    }
    return {
      s: 'pending',
      why: 'تکنیکال: روندِ هفتگی قابلِ تشخیص نیست — هنوز نمی‌توان وارد شاخهٔ روزانه شد',
    };
  }

  if (weekly !== 'up') {
    return { s: 'pending', why: 'تکنیکال: وضعیتِ روندِ هفتگی نامشخص است — رأیِ قطعی داده نمی‌شود' };
  }

  const daily = t.trendD;
  const act = activeSetups(t);
  if (daily === 'up') {
    return { s: 'pass', why: `تکنیکال: هفتگی صعودی + روزانه صعودی${act ? ` — شواهد: ${act}` : ''}` };
  }
  if (daily === 'down') {
    return { s: 'pass', why: `تکنیکال: هفتگی صعودی + روزانه نزولی — شاخهٔ فیبو/CHoCH${act ? `؛ شواهد: ${act}` : ''}` };
  }
  if (daily === 'range') {
    return { s: 'pass', why: `تکنیکال: هفتگی صعودی + روزانه خنثی — شاخهٔ کف/محدوده${act ? `؛ شواهد: ${act}` : ''}` };
  }
  return {
    s: 'pending',
    why: 'تکنیکال: روندِ روزانه قابلِ تشخیص نیست — قبل از عبور باید شاخهٔ روزانه مشخص شود',
  };
}

/**
 * ابزارهایی که در پنج‌شاخصهٔ کدال «شرکت» حساب نمی‌شوند: برایِ این‌ها نبودِ
 * ردیفِ اسکرینر ضعفِ داده نیست، ذاتِ ابزار است (صندوق صورتِ سودِ شرکتی ندارد).
 */
const NON_COMPANY: AssetType[] = ['option', 'fund', 'bond', 'right', 'teseh', 'tal'];

function fundMark(
  sc: FtsScreenRow | null,
  kind: AssetType,
  opts: FunnelOptions,
): { s: StageStatus; why: string; score: number | null } {
  if (!sc) {
    return {
      s: 'unavailable',
      why: NON_COMPANY.includes(kind)
        ? `بنیادی: پنج‌شاخصه شرکت‌ها را می‌سنجد و این «${ASSET_LABELS[kind]}» شرکت نیست — سنجیده نشد، وتو نیست`
        : 'بنیادی: ردیفِ این شرکت در اسکرینرِ کدال نبود — سنجیده نشد، وتو نیست',
      score: null,
    };
  }
  if (sc.applicable === false) {
    return { s: 'pending', why: 'بنیادی: پنج‌شاخصه دربارهٔ این ابزار نظر نمی‌دهد (نه رد، نه قبول)', score: null };
  }
  const mode = (sc.pricing_mode ?? '').toLowerCase();
  const regulated = mode === 'regulated' || mode === 'دستوری';
  const score = typeof sc.score === 'number' ? sc.score : null;
  if (sc.excluded || regulated) {
    return { s: 'reject', why: regulated ? 'بنیادی: نرخ‌گذاریِ دستوری' : `بنیادی: ${sc.exclusion_reasons || 'مستثنی'}`, score };
  }
  if (score == null) return { s: 'pending', why: 'بنیادی: نمره‌ای ساخته نشده', score };
  return score >= opts.fundFloor
    ? { s: 'pass', why: `بنیادی: ${toFaDigits(score)} از ${toFaDigits(5)} شاخصِ جزوه`, score }
    : { s: 'reject', why: `بنیادی: ${toFaDigits(score)} از ${toFaDigits(5)} — زیرِ کفِ ${toFaDigits(opts.fundFloor)}`, score };
}

/**
 * پنج شاخص یکی‌یکی، نه فقط جمعشان. `i1_pass … i5_pass` را همان موتورِ
 * `api/screener` می‌نویسد، پس این‌جا فقط نگاشت می‌شوند؛ `null` یعنی آن شاخص
 * داوری نشد (بی‌گزارش) و «رد» نیست.
 */
function indMarks(sc: FtsScreenRow | null): StageStatus[] {
  if (!sc || sc.applicable === false) return ['pending', 'pending', 'pending', 'pending', 'pending'];
  return [sc.i1_pass, sc.i2_pass, sc.i3_pass, sc.i4_pass, sc.i5_pass].map(
    (v): StageStatus => (v === true ? 'pass' : v === false ? 'reject' : 'pending'),
  );
}

/**
 * وتوی مجمع — از خودِ ردیفِ اسکرینر خوانده می‌شود، نه از یک تقویمِ دوم در فرانت.
 * بک‌اند (`_apply_assembly_veto` در api/screener.py) بیرونِ کشِ ۱۲ ساعته و روی
 * هر درخواست تازه داوری می‌کند؛ قیف اینجا داوریِ تازه‌ای نمی‌سازد، فقط منتقل
 * می‌کند — همان قراردادی که وتوی هفتگی دارد.
 * `screen === null` یعنی اسکرینر این نماد را پوشش نداده ⇒ وتو نیست (بی‌داده وتو نیست).
 */
function assemblyVetoOf(sc: FtsScreenRow | null): { veto: boolean; why: string } {
  if (sc?.assembly_veto !== true) return { veto: false, why: '' };
  const d = typeof sc.assembly_days === 'number' ? sc.assembly_days : null;
  const tail =
    d == null ? '' : d <= 0 ? ' — امروز مجمع عمومی دارد' : ` — ${toFaDigits(d)} روز تا مجمع عمومی`;
  return { veto: true, why: `تحویل: وتوی مجمع${tail}؛ نماد در روزِ مجمع متوقف می‌شود` };
}

/** درِ تابلو (S) — در حالتِ مرورِ بازار هیچ‌وقت درِ ورود را نمی‌بندد. */
function tapeMarkOf(
  row: MarketRow | null,
  entryFilters: string[],
  cfg: TapeFilterConfig,
  ctx: FunnelContext,
): { s: StageStatus; why: string } {
  // تازگی درِ هر دو حالت نوشته می‌شود (#16): دادهٔ آخرینِ نشست نباید جایِ
  // دادهٔ زنده خوانده شود، حتی وقتی فقط «خبر» می‌دهد.
  const staleTag = ctx.tape === 'stale' ? ' — داده از آخرینِ نشست است، نه زنده' : '';
  if (ctx.mode === 'review') {
    if (ctx.tape === 'unavailable' || !row) {
      return { s: 'unavailable', why: 'تابلو: درِ مرورِ کامل بازار نشانه‌ای از تابلو نمی‌خواهد — بی‌داده، وتو نیست' };
    }
    const on = entryFilters.some((f) => tapeFilterVerdict(row, f, cfg));
    return on
      ? { s: 'pass', why: 'تابلو: نشانه‌ای از فیلترهایِ این سبک روشن است (درِ مرورِ بازار فقط خبر می‌دهد، نمی‌بندد)' + staleTag }
      : { s: 'pending', why: 'تابلو: امروز نشانه‌ای از فیلترهایِ این سبک روشن نیست — درِ مرورِ بازار به‌خاطرِ آن رد نمی‌شود' + staleTag };
  }
  if (ctx.tape === 'unavailable') {
    return { s: 'unavailable', why: 'تابلو: خوراکِ تابلو در دسترس نیست — مهندسیِ معکوس بی‌تابلو شروع نمی‌شود؛ برایِ بررسیِ کلِ بازار حالتِ «مرورِ کامل بازار» را بزنید' };
  }
  if (!row) {
    return { s: 'unavailable', why: 'تابلو: ردیفِ این نماد در خوراکِ تابلو نبود — سنجیده نشد، وتو نیست' };
  }
  const on = entryFilters.some((f) => tapeFilterVerdict(row, f, cfg));
  if (!on) {
    return { s: 'reject', why: `تابلو: هیچ‌کدام از فیلترهایِ دربِ این سبک (${entryFilters.length ? entryFilters.join('، ') : '—'}) رویِ این ردیف روشن نیست` };
  }
  return {
    s: 'pass',
    why: ctx.tape === 'stale'
      ? 'تابلو: نشانه‌ای از فیلترهایِ این سبک روشن است — داده از آخرینِ نشست است، نه زنده'
      : 'تابلو: حداقل یک فیلترِ دربِ این سبک روشن است',
  };
}

/** ردیف‌هایِ مرحلۀ تابلو: دامنهٔ زندهٔ تابلو که دستِ‌کم یک فیلترِ درب را رد کرده */
function tapeRows(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  preset: TreePreset,
): { scope: MarketRow[]; picks: MarketRow[]; entryFilters: string[] } {
  const scope = boardScope(rows);
  // ۱) تابلوخوانی: سبکِ انتخابی درِ درخت تعیین می‌کند کدام فیلترها دربِ قیف‌اند
  //    (چارت ۳). اگر کاربر خودِ چیپ‌هایِ تابلو را روشن کرده باشد، همان چیپ‌ها
  //    حاکم‌اند — قیف نباید چیزی نشان دهد که تبِ تابلو پشتِ آن نرفته است.
  const entryFilters = quickFilters.length ? quickFilters : PRESET_ENTRY[preset].filters;
  return { scope, picks: scope.filter((r) => entryFilters.some((f) => tapeFilterVerdict(r, f, cfg))), entryFilters };
}

/**
 * نمادهایِ مرحلۀ تابلو — همان فهرستی که قیف برایش رأیِ تکنیکال می‌خواهد،
 * پیش از آنکه بداند بنیادیِ هرکدام چه می‌شود (`useFtsTechBoard` این را می‌خواند).
 */
export function tapePickedSymbols(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  preset: TreePreset,
): string[] {
  return tapeRows(rows, cfg, quickFilters, preset).picks.map((r) => r.symbol ?? '').filter(Boolean);
}

/**
 * صفِ بودجۀ تکنیکال (#12): `useFtsTechBoard` به ازای هر نماد یک `/api/fts` می‌زند
 * و هزینه‌اش واقعی است، پس سقفِ `TECH_QUERY_CAP` می‌ماند — اما چه کسی داخلِ بودجه
 * است؟ ترتیبِ تابلو پاسخِ بدی است (با هر رفرش عوض می‌شود و «کی سنجیده شد» را
 * تصادفی می‌کند). تنها رتبۀ رسمیِ موجود، رتبۀ خودِ بک‌اند درِ `/api/screener` است
 * (`screener.py:440`: سه محورِ بلاکر، بعد امتیازِ پنج‌تایی، بعد ارزش، بعد نماد).
 * پس صف = رتبۀ رسمی، و هرچه بیرونِ بودجه ماند `unavailable` خوانده می‌شود —
 * نه رد، و نه با یک sortِ دلخواه «تاپ» جا زده می‌شود.
 */
export function orderOfficial(symbols: string[], rank: Map<string, number>): string[] {
  return [...new Set(symbols.filter(Boolean))]
    .map((s, i) => ({ s, i, r: rank.get(s) ?? Number.POSITIVE_INFINITY }))
    .sort((a, b) => a.r - b.r || a.i - b.i)
    .map((x) => x.s);
}

export function techQueryQueue(
  symbols: string[],
  rank: Map<string, number>,
  cap: number,
): { symbols: string[]; beyondCap: number } {
  const ordered = orderOfficial(symbols, rank);
  const budget = Math.max(0, cap);
  return { symbols: ordered.slice(0, budget), beyondCap: Math.max(0, ordered.length - budget) };
}

/**
 * جامعۀ ورودِ قیف، به ترتیبِ رتبۀ رسمیِ بک‌اند. هم `buildFunnel` و هم صفِ
 * بودجۀ `/api/fts` از همین یک تابع می‌خوانند — تا «چه کسی داوری می‌شود» و
 * «چه کسی رأیِ زنده می‌گیرد» هیچ‌وقت دو فهرستِ متفاوت نسازند.
 */
export function funnelUniverse(
  mode: FunnelMode,
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  preset: TreePreset,
  screenRows: FtsScreenRow[],
): { ordered: string[]; entryFilters: string[]; scope: MarketRow[]; rank: Map<string, number> } {
  const { scope, picks, entryFilters } = tapeRows(rows, cfg, quickFilters, preset);
  const rank = officialRankMap(screenRows);
  const universe = mode === 'review'
    ? screenRows.map((s) => s.symbol ?? '').filter(Boolean)
    : picks.map((r) => r.symbol ?? '').filter(Boolean);
  return { ordered: orderOfficial(universe, rank), entryFilters, scope, rank };
}

/**
 * مرحلۀ خودِ یک نماد، از همان `buildFunnel` — نه یک پیاده‌سازی دوم.
 * سایدبارِ چپ می‌خواهد بگوید «این نماد کجای قیف ایستاده»: به‌جای نوشتنِ دوبارهٔ
 * قواعد (که دو نسخه‌اش حتماً از هم جدا می‌افتد)، قیف رویِ تک‌ردیفِ همین نماد
 * اجرا می‌شود و پیشرفتِ همان را گزارش می‌دهد. O(۱) است.
 */
export type StageProgress = {
  key: FunnelStageKey;
  /** 'passed' رد شده · 'blocked' اینجا مانده · 'waiting' سنجیده نشده ·
   *  'unknown' هیچ منبعی برایِ داوریِ این مرحله نیست (نه رد، نه قبول) */
  state: 'passed' | 'blocked' | 'waiting' | 'unknown';
  /** چرا — برایِ tooltip و خطِ «ایستاده در …» */
  why: string;
};

export function statusToProgress(s: StageStatus): StageProgress['state'] {
  return s === 'pass' ? 'passed' : s === 'reject' ? 'blocked' : s === 'pending' ? 'waiting' : 'unknown';
}

/** ورودیِ داوریِ تک‌ناماد — یک بار، از هر دو راه (قیف و سایدبار) خوانده می‌شود. */
export type CandidateInput = {
  symbol: string;
  /** پیکربندیِ فیلترهایِ تابلو (آستانه‌هایِ خودِ تبِ تابلو، نه چیزِ تازه) */
  cfg: TapeFilterConfig;
  row: MarketRow | null;
  screen: FtsScreenRow | null;
  /** رأیِ زندۀ `/api/fts/{symbol}`؛ `null` یعنی نخوانده یا پاسخِ خطا */
  live: TechVerdict | null;
  preset: TreePreset;
  opts: FunnelOptions;
  ctx: FunnelContext;
  entryFilters: string[];
  portfolioSet: Set<string>;
  screenRank: number | null;
};

/**
 * **تنها جایِ داوریِ کاندید.** `buildFunnel` این را رویِ هر عضوِ universe اجرا
 * می‌کند و `symbolStageProgress` رویِ تک‌نامادِ سایدبار — پس هیچ‌وقت دو نسخهٔ
 * قواعد نداریم (چیزی که فهرست‌هایِ تحویلِ پیشین (حذف‌شده در Round M §۶) با `phaseMarksFor` می‌ساخت، از همین‌جا
 * خوانده می‌شود).
 */
export function evaluateCandidate(input: CandidateInput): Candidate {
  const { symbol, cfg, row, screen, live, preset, opts, ctx, entryFilters, portfolioSet, screenRank } = input;
  // رأیِ تازهٔ `/api/fts` مقدم است (همین حالا برایِ همین نماد خوانده شده)؛
  // اگر نبود، ردیفِ اسکرینر همان موتور را دارد.
  const sig = (live ? techFromVerdict(live) : null) ?? techFromScreen(screen);
  const t = techMark(sig);
  const kind = classifyAssetType({
    symbol,
    name: row?.name ?? screen?.name ?? null,
    sector_name: row?.sector_name ?? screen?.sector_name ?? null,
  });
  const f = fundMark(screen, kind, opts);
  const av = assemblyVetoOf(screen);
  // درِ تابلو برایِ هر دو حالت از خودِ فیلترها خوانده می‌شود. در reverse جامعۀ
  // قیف از پیشِ همین فیلترها رد شده، پس نتیجه «pass» است؛ ولی سایدبارِ چپ تک‌نامادِ
  // دلخواه را اینجا می‌آورد و باید راست بگوید که آن ناماد درِ تابلو ایستاده یا نه.
  const tp = tapeMarkOf(row, entryFilters, cfg, ctx);
  const inBasket = portfolioSet.has(symbol);
  const upstreamClosed = t.s === 'reject' || f.s === 'reject';
  const qualified = t.s === 'pass' && f.s === 'pass';
  // ترتیبِ داوری عمدی است: نمادی که ازپیش درِ سبد است به‌خاطرِ سبد تحویل
  // نمی‌شود، نه به‌خاطرِ مجمع — بی‌این شرط، یک نماد دوشماره‌ای می‌شد و عددِ
  // توقف‌هایِ مجمعِ این در را تورم می‌داد (تستِ «هم در سبد هم مجمع»).
  const hd: { s: StageStatus; why: string } = upstreamClosed
    ? { s: 'reject', why: 'تحویل: بالادست بسته است — این مرحله حرفی برای گفتن ندارد' }
    : inBasket
      ? { s: 'pending', why: 'تحویل: نماد همین حالا در سبدِ شماست — این فهرست جایِ خریدِ تازه است' }
      : av.veto
        ? { s: 'pending', why: av.why }
        : qualified
          ? { s: 'pass', why: 'تحویل: آمادهٔ ارائه به کاکپیتِ داوری' }
          : // پیچِ «عبور با برچسب» (opts.unmeasured = 'pass') تصمیمِ خودِ مالک است
            // که سنجیده‌نشده هم به تحویل برود؛ پس برچسبِ همین در هم همان را
            // «قبول با برچسب» می‌گوید — وگرنه فهرستِ تحویل و برچسبِ ردیف دو
            // روایت از یک نماد می‌شدند (تستِ «عبور با برچسب»).
            opts.unmeasured === 'pass'
            ? { s: 'pass', why: 'تحویل: با برچسبِ «سنجیده نشد» عبور کرد (پیچِ «عبور با برچسب») — درِ جزوه هنوز باز نشده' }
            : { s: 'pending', why: 'تحویل: صبر تا درِ تکنیکال یا بنیادی واقعاً سنجیده شود (بی‌داده وتو نیست)' };
  return {
    symbol,
    name: row?.name ?? screen?.name ?? '',
    sector: row?.sector_name ?? screen?.sector_name ?? '',
    kind,
    row,
    screen,
    patterns: row ? patternBadges(row, cfg).filter((b) => b.filter).map((b) => b.label) : [],
    status: { tape: tp.s, technical: t.s, fundamental: f.s, handover: hd.s },
    why: { tape: tp.why, technical: t.why, fundamental: f.why, handover: hd.why },
    score: f.score,
    trendW: sig?.trendW ?? null,
    trendD: sig?.trendD ?? null,
    dailyStrategy: technicalDailyBranch(sig),
    setups: sig ? activeSetups(sig) : '',
    technicalPoints: technicalEvidencePoints(sig),
    inds: indMarks(screen),
    techSource: live ? 'live' : sig ? 'screen' : null,
    jetEvidence: sig?.jetEvidence ?? null,
    assemblyVeto: av.veto,
    assemblyWhy: av.why,
    screenRank,
  };
}

export function symbolStageProgress(
  row: MarketRow | null,
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screen: FtsScreenRow | null,
  inBasket: boolean,
  preset: TreePreset = 'custom',
  tech: Map<string, TechVerdict> = new Map(),
  opts: FunnelOptions = DEFAULT_FUNNEL_OPTIONS,
  ctx: Partial<FunnelContext> = {},
): StageProgress[] {
  if (!row || !row.symbol) {
    const none = 'تابلو: ردیفِ این نماد در خوراکِ زنده نیست — سنجیده نشد، وتو نیست';
    return STAGE_KEYS.map((k) => ({ key: k, state: 'unknown' as const, why: k === 'tape' ? none : '' }));
  }
  const full: FunnelContext = { ...DEFAULT_FUNNEL_CONTEXT, ...ctx };
  const entryFilters = quickFilters.length ? quickFilters : PRESET_ENTRY[preset].filters;
  const cand = evaluateCandidate({
    symbol: row.symbol,
    cfg,
    row,
    screen,
    live: tech.get(row.symbol) ?? null,
    preset,
    opts,
    // سایدبار تک‌ناماد را رویِ همان قواعدِ مهندسیِ معکوس می‌خواند؛ تابلو از خودِ
    // ردیفِ همین نماد داوری می‌شود، پس `cfg` باید برسد.
    ctx: { ...full, tape: full.tape === 'unavailable' && !row ? 'unavailable' : full.tape },
    entryFilters,
    portfolioSet: new Set(inBasket ? [row.symbol] : []),
    screenRank: null,
  });
  return STAGE_KEYS.map((k) => ({
    key: k,
    state: statusToProgress(cand.status[k]),
    why: cand.why[k],
  }));
}

function emptySummary(): StageSummary {
  return { pass: 0, reject: 0, pending: 0, unavailable: 0 };
}

function summarize(list: Candidate[], key: FunnelStageKey): StageSummary {
  const s = emptySummary();
  for (const e of list) s[e.status[key]] += 1;
  return s;
}

/** هدف‌هایِ جزوه (رأیِ ۶): ۵۰ مانور اولیه، ۱۰ واچ‌لیست، ۵ تا ۷ سبد. مرجعِ نمایش. */
export const FUNNEL_TARGETS = { initial: 50, watchlist: 10, basketMin: 5, basketMax: 7 } as const;

export function buildFunnel(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screenRows: FtsScreenRow[],
  portfolioSet: Set<string>,
  preset: TreePreset = 'custom',
  techMap: Map<string, TechVerdict> = new Map(),
  opts: FunnelOptions = DEFAULT_FUNNEL_OPTIONS,
  ctxIn: Partial<FunnelContext> = {},
): Funnel {
  const ctx: FunnelContext = { ...DEFAULT_FUNNEL_CONTEXT, ...ctxIn };
  const { ordered: orderedUniverse, entryFilters, scope, rank } = funnelUniverse(
    ctx.mode, rows, cfg, quickFilters, preset, screenRows,
  );
  const screenBySymbol = new Map<string, FtsScreenRow>();
  for (const s of screenRows) if (s.symbol) screenBySymbol.set(s.symbol, s);
  const rowBySymbol = new Map<string, MarketRow>();
  for (const r of scope) if (r.symbol) rowBySymbol.set(r.symbol, r);

  const build = (symbol: string): Candidate | null => {
    const screen = screenBySymbol.get(symbol) ?? null;
    if (ctx.mode === 'review' && !screen) return null;
    return evaluateCandidate({
      symbol,
      cfg,
      row: rowBySymbol.get(symbol) ?? null,
      screen,
      live: techMap.get(symbol) ?? null,
      preset,
      opts,
      ctx,
      entryFilters,
      portfolioSet,
      screenRank: rank.get(symbol) ?? null,
    });
  };

  // ترتیبِ نهایی: رتبۀ رسمیِ بک‌اند، و بعدِ آن ترتیبِ تابلو برایِ بیرونِ اسکرینر.
  // هیچ slice برایِ رسیدن به عددِ موردنظر انجام نمی‌شود (#3 و #15).
  const picked = orderedUniverse
    .map(build)
    .filter((c): c is Candidate => c !== null)
    .sort((a, b) => (a.screenRank ?? Number.POSITIVE_INFINITY) - (b.screenRank ?? Number.POSITIVE_INFINITY));

  const techOf = (e: Candidate) => e.status.technical;
  const fundOf = (e: Candidate) => e.status.fundamental;

  const techRejected = picked.filter((e) => techOf(e) === 'reject');
  const techKept = opts.techScreens ? picked.filter((e) => techOf(e) !== 'reject') : picked;
  const techDropped = opts.techScreens ? techRejected.length : 0;
  // ۳) بنیادی: «ردِ صریح» همیشه بیرون می‌افتد. سرنوشتِ «سنجیده نشد» دستِ خودِ
  //    مالک است (پیچِ `unmeasured` در store): درِ انتظار بماند (پیش‌فرضِ جزوه)،
  //    با برچسب به تحویل برود، یا از قیف حذف شود.
  const judged = techKept.filter((e) => fundOf(e) !== 'pending' && fundOf(e) !== 'unavailable');
  const unjudged = techKept.filter((e) => fundOf(e) === 'pending' || fundOf(e) === 'unavailable');
  const accepted = judged.filter((e) => fundOf(e) === 'pass');
  const fundEntries =
    opts.unmeasured === 'pass' ? techKept.filter((e) => fundOf(e) !== 'reject') : accepted;
  const passed = fundEntries;
  const pending = opts.unmeasured === 'hold' ? unjudged : [];
  const fundDropped = techKept.length - fundEntries.length - pending.length;
  // ۴) تحویل: بنیادش واقعاً سنجیده و قبول شده، هنوز درِ سبد نیست و مجمعِ
  //    نزدیک ندارد. وتوی مجمع اینجا می‌ایستد نه درِ مرحلۀ بنیادی: مجمع ضعفِ
  //    بنیادی نیست، زمان‌بندیِ ورود است — نماد در روزِ مجمع متوقف می‌شود و پس
  //    از آن گپِ قیمتی می‌خورد. پس نمرۀ پنج‌شاخصه دست‌نخورده می‌ماند و فقط
  //    «امروز» تحویل داده نمی‌شود؛ فردا که مجمع تمام شد خودش برمی‌گردد.
  // `entries` باید با `status` یکی باشد: تحویل = هر چهار درِ باز، بیرونِ سبد،
  // بی‌وتوی مجمع. بی‌این، نمادی که تکنیکالش «در انتظار» بود درِ فهرستِ تحویل
  // می‌نشست در حالی که برچسبش «pending» بود — دو روایت از یک ردیف.
  const handover = passed.filter((e) => e.status.handover === 'pass');

  // شمارش رویِ «کسانی که درِ این مرحله داوری شدند» است، نه فقط بازمانده‌ها —
  // وگرنه `reject` درِ مرحلۀ حذف‌شده همیشه صفر می‌شد و چهارشماره معنا نداشت.
  const counts = {
    tape: summarize(picked, 'tape'),
    technical: summarize(picked, 'technical'),
    fundamental: summarize(techKept, 'fundamental'),
    handover: summarize(passed, 'handover'),
  };

  return {
    mode: ctx.mode,
    tape: ctx.tape,
    techCoverage: {
      universe: orderedUniverse.length,
      live: orderedUniverse.filter((s) => techMap.has(s)).length,
      fromScreen: orderedUniverse.filter((s) => !techMap.has(s) && techFromScreen(screenBySymbol.get(s) ?? null) != null).length,
      none: orderedUniverse.filter((s) => !techMap.has(s) && techFromScreen(screenBySymbol.get(s) ?? null) == null).length,
    },
    boardScope: scope.length,
    total: picked.length,
    counts,
    targets: FUNNEL_TARGETS,
    stages: {
      tape: {
        key: 'tape', entries: picked, dropped: 0, rejected: counts.tape.reject,
        unmeasured: counts.tape.pending + counts.tape.unavailable, pending: [], summary: counts.tape,
      },
      technical: {
        key: 'technical', entries: picked, dropped: techDropped, rejected: counts.technical.reject,
        unmeasured: counts.technical.pending + counts.technical.unavailable, pending: [], summary: counts.technical,
      },
      fundamental: {
        key: 'fundamental', entries: passed, dropped: fundDropped, rejected: counts.fundamental.reject,
        unmeasured: counts.fundamental.pending + counts.fundamental.unavailable, pending, summary: counts.fundamental,
      },
      // تحویل: وتوی مجمع و «همین حالا در سبد» توقف‌اند، نه ردِ کیفی — پس درِ
      // `rejected` نمی‌نشینند و درِ `pending` می‌مانند (#15). خودِ فهرستِ متوقفان
      // هم می‌آید تا UI بگوید «چرا خالی است» را از رویِ علت، نه از رویِ حدس.
      handover: {
        key: 'handover', entries: handover, dropped: passed.length - handover.length,
        rejected: counts.handover.reject,
        unmeasured: counts.handover.pending + counts.handover.unavailable,
        pending: passed.filter((e) => e.status.handover === 'pending'),
        summary: counts.handover,
      },
    },
  };
}
