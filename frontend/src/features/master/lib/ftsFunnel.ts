// features/master/lib/ftsFunnel.ts -- مرحلۀ قیف: چه چیزی وارد شد، چه چیزی ماند
//
// ترتیبِ مرحله از خودِ جزوه است و از همان چیزهایی که درِ «درخت استراتژی FTS»
// ستون‌ست: تابلوخوانیِ امروز ← تکنیکال ← بنیادیِ پنج‌شاخصه ← تحویل.
//
// مرحلۀ تکنیکال **غربال می‌کند، نه فقط نشانه می‌گذارد** (رأیِ تازهٔ
// مالک): وتوی هفتگی و نبودِ ستاپِ همان سبک، نماد را بیرون می‌اندازد؛
// وگرنه گره‌هایِ ستون T درِ درخت معنایشان را از دست می‌دهند. داوریِ
// هفتگی از خودِ `trend.matrix.decision` در api/chart.py می‌آید — همان
// داورِ جدولِ بنیادی و بج‌ها — نه یک فرمولِ دوم در فرانت.
//
// قانونِ «بی‌داده وتو نیست» همه‌جا برقرار است: ردیفی که اسکرینر پوششش نداده
// یا صندوقی که پنج‌شاخصه دربارهٔ او نظر نمی‌دهد، مردود حساب نمی‌شود؛ درِ
// مرحلۀ بعد با برچسبِ «سنجیده نشد» می‌رود.
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

export type StageMark = 'ok' | 'no' | 'na';

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

export type FunnelEntry = {
  symbol: string;
  name: string;
  sector: string;
  /** طبقهٔ ابزار — همان «صندوق/اختیار/حق تقدم» که پنج‌شاخصه دربارهٔ آنها نظر نمی‌دهد */
  kind: AssetType;
  row: MarketRow | null;
  screen: FtsScreenRow | null;
  /** برچسبِ پنج فیلترِ فایل که این ردیف درِ تابلو رد کرد — عینِ بجِ ستونِ «الگو» */
  patterns: string[];
  tech: StageMark;
  techWhy: string;
  fund: StageMark;
  fundWhy: string;
  score: number | null;
  /** روندِ دو زمانه همان‌طور که موتور می‌بیند: 'up' | 'down' | 'range' | 'na' | null */
  trendW: string | null;
  trendD: string | null;
  /** ستاپ‌های فعالِ این نماد (جت/فیبو/CHoCH/…) — ستونِ مرحلۀ تکنیکال */
  setups: string;
  /** تک‌تکِ پنج شاخص: ok / no / na — همان سطرهای صفحۀ ۱ چارت */
  inds: StageMark[];
  /** وتوی مجمعِ پیش‌رو — داوریِ بک‌اند (`assembly_veto` در /api/screener)، نه یک
   *  فرمولِ دوم در فرانت. رأیِ مالک است، نه چارتِ چهارصفحه‌ای. */
  assemblyVeto: boolean;
  assemblyWhy: string;
};

export type FunnelStageKey = 'tape' | 'technical' | 'fundamental' | 'handover';

export type FunnelStage = {
  key: FunnelStageKey;
  entries: FunnelEntry[];
  /** چه تعداد از مرحلۀ قبل بیرون افتاد (تکنیکال و بنیادی هر دو حذف می‌کنند) */
  dropped: number;
  /** چه تعداد روی این مرحله برچسبِ «رد» خوردند — با «رد نکند، خودم چک می‌کنم»
   *  dropped صفر است ولی این شمار همان ردشده‌ها را نشان می‌دهد */
  rejected: number;
  /** چه تعداد «سنجیده نشد» روی این مرحلۀ آنها خورده است */
  unmeasured: number;
  /** در مرحلۀ بنیادی: سنجیده‌نشده‌ها — نه رد شده‌اند، نه به تحویل می‌روند */
  pending: FunnelEntry[];
};

export type Funnel = {
  /** نمادهایِ جامعِ دو مرحلۀ آخر = آنچه درِ تحویل است */
  stages: Record<FunnelStageKey, FunnelStage>;
  boardScope: number;
  total: number;
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
  pointHunt: boolean;
  /** روندِ خامِ دو زمانه از خودِ موتور (`_fts_classify_trend`) */
  trendW: string | null;
  trendD: string | null;
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
    pointHunt: false,
    trendW: sc.tech_trend_w ?? null,
    trendD: sc.tech_trend_d ?? null,
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
  };
}

/**
 * ستاپ‌هایِ پذیرفتنیِ هر سبک — عینِ گره‌هایِ «setup» درِ درخت استراتژی
 * (`StrategyTreePage.activeNodes`) و شرحِ همان افق‌ها: نوسان‌گیر با جت یا
 * ترازِ نزدیکِ فیبو وارد می‌شود، روندگیر با فیبو/CHoCH/جت پله‌ای می‌خرد،
 * ساعت شنی ستاپِ عمیقِ خودش را می‌خواهد.
 */
const PRESET_SETUP: Record<TreePreset, { label: string; test: (t: TechSignals) => boolean }> = {
  swing: {
    label: `جت یا فیبوی ${toFaDigits('33-40')}`,
    test: (t) => t.jet || t.fibZone === '33-40',
  },
  trend: {
    // چارت ۳ برایِ روندگیر: کف‌روبی + نقطه‌زنی (ورود رویِ کفِ سوم یا پنجمِ
    // کانال) — همان دو گره‌ای که درختِ روندگیر حالا به آن می‌رسد. فیبو/CHoCH/جت
    // از ستاپ‌هایِ پذیرفتنیِ همین سبک می‌مانند (درخت آن‌ها را هم دارد).
    label: `فیبو یا CHoCH یا جت یا کفِ ${toFaDigits('3')}/${toFaDigits('5')}`,
    test: (t) => t.fibZone != null || t.chochBull || t.jet || t.pointHunt,
  },
  hourglass: {
    label: 'ستاپِ عمیقِ ساعت شنی',
    test: (t) => t.hourglass,
  },
  custom: {
    label: 'هر ستاپِ جزوه',
    test: (t) => t.jet || t.fibZone != null || t.chochBull || t.doubleBottom || t.rangeBreak || t.hourglass,
  },
};

/** ستاپ‌هایی که همین حالا روی نماد فعال‌اند — برایِ توضیحِ «چرا رد شد» */
function activeSetups(t: TechSignals): string {
  const on: string[] = [];
  if (t.jet) on.push('جت');
  if (t.fibZone) on.push(`فیبوی ${toFaDigits(t.fibZone)}`);
  if (t.chochBull) on.push('CHoCHِ صعودی');
  if (t.doubleBottom) on.push('کفِ دوقلو');
  if (t.rangeBreak) on.push('کفِ باکسِ رنج');
  if (t.hourglass) on.push('ساعت شنی');
  if (t.pointHunt) on.push('نقطه‌زنی');
  return on.join(' + ');
}

/**
 * درِ تکنیکال — ستون T درِ چارت (تکنیکالِ دو زمانه):
 *   وتوی هفتگی ⇒ رد. بی‌رأی یا UNKNOWN ⇒ «سنجیده نشد»، نه رد.
 *   هفتگی صعودی + ستاپِ همان سبک ⇒ قبول. هفتگی صعودیِ بی‌ستاپِ سبک ⇒ رد،
 *   چون درِ درخت «ستاپ» گرهٔ ورود است، نه تزیینات.
 * رأیِ هفتگی از `trend.matrix.decision`ِ بک‌اند می‌آید تا قیف و جدولِ بنیادی
 * و بج‌ها هیچ‌وقت دو داوریِ متفاوت نداشته باشند.
 */
function techMark(t: TechSignals | null, preset: TreePreset): { s: StageMark; why: string } {
  if (!t) {
    return { s: 'na', why: 'تکنیکال: تحلیلِ دو زمانه روی این نماد اجرا نشده — سنجیده نشد، وتو نیست' };
  }
  if (t.decision === 'REJECT' || t.weeklyVeto) {
    return { s: 'no', why: `تکنیکال: وتوی هفتگیِ چارت — ${t.matrixDesc ?? 'روندِ هفتگی صعودی نیست'}` };
  }
  if (t.decision == null || t.decision === 'UNKNOWN') {
    return { s: 'na', why: 'تکنیکال: روندِ هفتگی قابلِ تشخیص نیست (کمتر از دو پیوتِ کامل) — نظر داده نمی‌شود' };
  }
  const gate = PRESET_SETUP[preset];
  const act = activeSetups(t);
  if (!gate.test(t)) {
    return {
      s: 'no',
      why: `تکنیکال: هفتگی صعودی است ولی ستاپِ «${gate.label}» نیست${act ? ` — ستاپِ فعالِ او: ${act}` : ' — ستاپِ فعالی نیست'}`,
    };
  }
  return { s: 'ok', why: `تکنیکال: هفتگی صعودی + ستاپِ «${gate.label}»${act ? ` (${act})` : ''}` };
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
): { s: StageMark; why: string; score: number | null } {
  if (!sc) {
    return {
      s: 'na',
      why: NON_COMPANY.includes(kind)
        ? `بنیادی: پنج‌شاخصه شرکت‌ها را می‌سنجد و این «${ASSET_LABELS[kind]}» شرکت نیست — سنجیده نشد، وتو نیست`
        : 'بنیادی: ردیفِ این شرکت در اسکرینرِ کدال نبود — سنجیده نشد، وتو نیست',
      score: null,
    };
  }
  if (sc.applicable === false) {
    return { s: 'na', why: 'بنیادی: پنج‌شاخصه دربارهٔ این ابزار نظر نمی‌دهد (نه رد، نه قبول)', score: null };
  }
  const mode = (sc.pricing_mode ?? '').toLowerCase();
  const regulated = mode === 'regulated' || mode === 'دستوری';
  const score = typeof sc.score === 'number' ? sc.score : null;
  if (sc.excluded || regulated) {
    return { s: 'no', why: regulated ? 'بنیادی: نرخ‌گذاریِ دستوری' : `بنیادی: ${sc.exclusion_reasons || 'مستثنی'}`, score };
  }
  if (score == null) return { s: 'na', why: 'بنیادی: نمره‌ای ساخته نشده', score };
  return score >= opts.fundFloor
    ? { s: 'ok', why: `بنیادی: ${toFaDigits(score)} از ${toFaDigits(5)} شاخصِ جزوه`, score }
    : { s: 'no', why: `بنیادی: ${toFaDigits(score)} از ${toFaDigits(5)} — زیرِ کفِ ${toFaDigits(opts.fundFloor)}`, score };
}

/**
 * پنج شاخص یکی‌یکی، نه فقط جمعشان. `i1_pass … i5_pass` را همان موتورِ
 * `api/screener` می‌نویسد، پس این‌جا فقط نگاشت می‌شوند؛ `null` یعنی آن شاخص
 * داوری نشد (بی‌گزارش) و «رد» نیست.
 */
function indMarks(sc: FtsScreenRow | null): StageMark[] {
  if (!sc || sc.applicable === false) return ['na', 'na', 'na', 'na', 'na'];
  return [sc.i1_pass, sc.i2_pass, sc.i3_pass, sc.i4_pass, sc.i5_pass].map(
    (v): StageMark => (v === true ? 'ok' : v === false ? 'no' : 'na'),
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

/** ردیف‌هایِ مرحلۀ تابلو: دامنهٔ زندهٔ تابلو که دستِ‌کم یک فیلترِ درب را رد کرده */
function tapeRows(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  preset: TreePreset,
): { scope: MarketRow[]; picks: MarketRow[] } {
  const scope = boardScope(rows);
  // ۱) تابلوخوانی: سبکِ انتخابی درِ درخت تعیین می‌کند کدام فیلترها دربِ قیف‌اند
  //    (چارت ۳). اگر کاربر خودِ چیپ‌هایِ تابلو را روشن کرده باشد، همان چیپ‌ها
  //    حاکم‌اند — قیف نباید چیزی نشان دهد که تبِ تابلو پشتِ آن نرفته است.
  const entryFilters = quickFilters.length ? quickFilters : PRESET_ENTRY[preset].filters;
  return { scope, picks: scope.filter((r) => entryFilters.some((f) => tapeFilterVerdict(r, f, cfg))) };
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

const STAGE_KEYS: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

export function symbolStageProgress(
  row: MarketRow | null,
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screen: FtsScreenRow | null,
  inBasket: boolean,
  preset: TreePreset = 'custom',
  tech: Map<string, TechVerdict> = new Map(),
  opts: FunnelOptions = DEFAULT_FUNNEL_OPTIONS,
): StageProgress[] {
  if (!row || !row.symbol) {
    const none = 'تابلو: ردیفِ این نماد در خوراکِ زنده نیست — سنجیده نشد، وتو نیست';
    return STAGE_KEYS.map((k) => ({ key: k, state: 'unknown' as const, why: k === 'tape' ? none : '' }));
  }
  const f = buildFunnel(
    [row], cfg, quickFilters, screen ? [screen] : [],
    new Set(inBasket ? [row.symbol] : []), preset, tech, opts,
  );
  const entry = f.stages.tape.entries[0];
  const on = (k: FunnelStageKey) => f.stages[k].entries.some((e) => e.symbol === row.symbol);
  const mark = (s: StageMark): StageProgress['state'] =>
    s === 'ok' ? 'passed' : s === 'no' ? 'blocked' : 'waiting';

  return STAGE_KEYS.map((k) => {
    if (k === 'tape') {
      return on('tape')
        ? { key: k, state: 'passed' as const, why: 'تابلو: حداقل یک فیلترِ دربِ این سبک روشن است' }
        : { key: k, state: 'blocked' as const, why: 'تابلو: هیچ‌کدام از فیلترهایِ درب روی این ردیف روشن نیست' };
    }
    if (!entry) {
      // درِ تابلو بسته بوده؛ مرحله‌های بعد چیزی برای گفتن ندارند
      return { key: k, state: 'unknown' as const, why: '' };
    }
    if (k === 'technical') return { key: k, state: mark(entry.tech), why: entry.techWhy };
    if (k === 'fundamental') return { key: k, state: mark(entry.fund), why: entry.fundWhy };
    if (on('handover')) return { key: k, state: 'passed' as const, why: 'تحویل: آمادهٔ ارائه به کاکپیتِ داوری' };
    // تحویل فقط وقتی حرف می‌زند که سه درِ اول باز بوده باشند؛ وگرنه علتِ
    // خالی‌بودنش بالادست گفته شده و این‌جا چیزی اضافه نمی‌کنیم.
    const upstreamClosed = entry.tech !== 'ok' || entry.fund !== 'ok';
    if (upstreamClosed) return { key: k, state: 'unknown' as const, why: '' };
    return {
      key: k,
      state: 'blocked' as const,
      why: entry.assemblyVeto
        ? entry.assemblyWhy
        : inBasket
          ? 'تحویل: نماد همین حالا در سبدِ شماست — این فهرست جایِ خریدِ تازه است'
          : 'تحویل: بسته',
    };
  });
}

export function buildFunnel(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screenRows: FtsScreenRow[],
  portfolioSet: Set<string>,
  preset: TreePreset = 'custom',
  techMap: Map<string, TechVerdict> = new Map(),
  opts: FunnelOptions = DEFAULT_FUNNEL_OPTIONS,
): Funnel {
  const { scope, picks: tapePicked } = tapeRows(rows, cfg, quickFilters, preset);
  const screenBySymbol = new Map<string, FtsScreenRow>();
  for (const s of screenRows) if (s.symbol) screenBySymbol.set(s.symbol, s);

  const picked = tapePicked
    .map<FunnelEntry>((r) => {
      const screen = screenBySymbol.get(r.symbol ?? '') ?? null;
      // رأیِ تازهٔ `/api/fts` مقدم است (همین حالا برایِ همین نماد خوانده شده)؛
      // اگر نبود، ردیفِ اسکرینر همان موتور را دارد.
      const live = techMap.get(r.symbol ?? '');
      const sig = (live ? techFromVerdict(live) : null) ?? techFromScreen(screen);
      const t = techMark(sig, preset);
      const kind = classifyAssetType(r);
      const f = fundMark(screen, kind, opts);
      const av = assemblyVetoOf(screen);
      return {
        symbol: r.symbol ?? '',
        name: r.name ?? '',
        sector: r.sector_name ?? '',
        kind,
        row: r,
        screen,
        patterns: patternBadges(r, cfg)
          .filter((b) => b.filter)
          .map((b) => b.label),
        tech: t.s,
        techWhy: t.why,
        fund: f.s,
        fundWhy: f.why,
        score: f.score,
        trendW: sig?.trendW ?? null,
        trendD: sig?.trendD ?? null,
        setups: sig ? activeSetups(sig) : '',
        inds: indMarks(screen),
        assemblyVeto: av.veto,
        assemblyWhy: av.why,
      };
    })
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

  const unmeasuredOn = (list: FunnelEntry[], key: 'tech' | 'fund') =>
    list.filter((e) => e[key] === 'na').length;

  // ۲) تکنیکال: وتوی هفتگی یا نبودِ ستاپِ همان سبک ⇒ بیرون (چارت ۳، ستون T).
  //    «سنجیده نشد» نمی‌افتد — بی‌داده وتو نیست — به مرحلۀ بعد می‌رود و
  //    برچسبِ «سنجیده نشد» رویِ خودش می‌ماند.
  //    با `techScreens: false` همان ردیف‌ها حذف نمی‌شوند، فقط برچسبِ رد
  //    می‌خورند و به بنیادی می‌رسند: مالک ستونِ روندِ هفتگی را خودش می‌خواند.
  const techRejected = picked.filter((e) => e.tech === 'no');
  const techKept = opts.techScreens ? picked.filter((e) => e.tech !== 'no') : picked;
  const techDropped = opts.techScreens ? techRejected.length : 0;
  // ۳) بنیادی: «ردِ صریح» همیشه بیرون می‌افتد. سرنوشتِ «سنجیده نشد» دستِ خودِ
  //    مالک است (پیچِ `unmeasured` در store): درِ انتظار بماند (پیش‌فرضِ جزوه)،
  //    با برچسب به تحویل برود، یا از قیف حذف شود.
  const judged = techKept.filter((e) => e.fund !== 'na');
  const unjudged = techKept.filter((e) => e.fund === 'na');
  const accepted = judged.filter((e) => e.fund === 'ok');
  const fundEntries =
    opts.unmeasured === 'pass' ? techKept.filter((e) => e.fund !== 'no') : accepted;
  const passed = fundEntries;
  const pending = opts.unmeasured === 'hold' ? unjudged : [];
  const fundDropped = techKept.length - fundEntries.length - pending.length;
  // ۴) تحویل: بنیادش واقعاً سنجیده و قبول شده، هنوز درِ سبد نیست و مجمعِ
  //    نزدیک ندارد. وتوی مجمع اینجا می‌ایستد نه درِ مرحلۀ بنیادی: مجمع ضعفِ
  //    بنیادی نیست، زمان‌بندیِ ورود است — نماد در روزِ مجمع متوقف می‌شود و پس
  //    از آن گپِ قیمتی می‌خورد. پس نمرۀ پنج‌شاخصه دست‌نخورده می‌ماند و فقط
  //    «امروز» تحویل داده نمی‌شود؛ فردا که مجمع تمام شد خودش برمی‌گردد.
  //    شمارشِ «مجمع مانع شد» فقط رویِ کسانِ بیرونِ سبد است: نمادی که ازپیش
  //    خریده‌اید به‌خاطرِ سبد تحویل نمی‌شود، نه به‌خاطرِ مجمع، و دوشماره‌ای
  //    شدنش عددِ ردِ این در را تورم می‌داد.
  const candidates = passed.filter((e) => !portfolioSet.has(e.symbol));
  const assemblyBlocked = candidates.filter((e) => e.assemblyVeto);
  const handover = candidates.filter((e) => !e.assemblyVeto);

  return {
    boardScope: scope.length,
    total: picked.length,
    stages: {
      tape: { key: 'tape', entries: picked, dropped: 0, rejected: 0, unmeasured: 0, pending: [] },
      technical: {
        key: 'technical',
        entries: picked,
        dropped: techDropped,
        rejected: techRejected.length,
        unmeasured: unmeasuredOn(picked, 'tech'),
        pending: [],
      },
      fundamental: {
        key: 'fundamental',
        entries: passed,
        dropped: fundDropped,
        rejected: techKept.filter((e) => e.fund === 'no').length,
        unmeasured: pending.length,
        pending,
      },
      handover: {
        key: 'handover',
        entries: handover,
        dropped: assemblyBlocked.length,
        rejected: assemblyBlocked.length,
        unmeasured: 0,
        pending: [],
      },
    },
  };
}
