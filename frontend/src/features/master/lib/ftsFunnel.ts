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
import { classifyAssetType } from '@features/market/lib/assetType';
import { DEFAULT_ASSET_TYPES } from '@features/market/stores/tapeStore';
import { dropNumericSuffixRows } from '@features/market/lib/tapeFts';
import { tapeFilterVerdict, type TapeFilterConfig } from '@features/market/lib/tapeAlgorithms';
import { patternBadges } from '@features/market/lib/tapeBadges';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type { TechVerdict } from '../api/useFtsTechBoard';

const FILE_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'] as const;

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

export type FunnelEntry = {
  symbol: string;
  name: string;
  sector: string;
  row: MarketRow | null;
  screen: FtsScreenRow | null;
  /** برچسبِ پنج فیلترِ فایل که این ردیف درِ تابلو رد کرد — عینِ بجِ ستونِ «الگو» */
  patterns: string[];
  tech: StageMark;
  techWhy: string;
  fund: StageMark;
  fundWhy: string;
  score: number | null;
};

export type FunnelStageKey = 'tape' | 'technical' | 'fundamental' | 'handover';

export type FunnelStage = {
  key: FunnelStageKey;
  entries: FunnelEntry[];
  /** چه تعداد از مرحلۀ قبل بیرون افتاد (تکنیکال و بنیادی هر دو حذف می‌کنند) */
  dropped: number;
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

/** نمادهایِ تابلویی که قیف از آنها شروع می‌شود: همان نمایِ تبِ تابلو. */
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
    label: 'فیبو یا CHoCH یا جت',
    test: (t) => t.fibZone != null || t.chochBull || t.jet,
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
function fundMark(sc: FtsScreenRow | null): { s: StageMark; why: string; score: number | null } {
  if (!sc) return { s: 'na', why: 'بنیادی: درِ اسکرینرِ کدال پوشش داده نشده — سنجیده نشد', score: null };
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
  return score >= 3
    ? { s: 'ok', why: `بنیادی: ${score} از ۵ شاخصِ جزوه`, score }
    : { s: 'no', why: `بنیادی: ${score} از ۵ — زیرِ کفِ سه`, score };
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

export function buildFunnel(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screenRows: FtsScreenRow[],
  portfolioSet: Set<string>,
  preset: TreePreset = 'custom',
  techMap: Map<string, TechVerdict> = new Map(),
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
      const f = fundMark(screen);
      return {
        symbol: r.symbol ?? '',
        name: r.name ?? '',
        sector: r.sector_name ?? '',
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
      };
    })
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

  const unmeasuredOn = (list: FunnelEntry[], key: 'tech' | 'fund') =>
    list.filter((e) => e[key] === 'na').length;

  // ۲) تکنیکال: وتوی هفتگی یا نبودِ ستاپِ همان سبک ⇒ بیرون (چارت ۳، ستون T).
  //    «سنجیده نشد» نمی‌افتد — بی‌داده وتو نیست — به مرحلۀ بعد می‌رود و
  //    برچسبِ «سنجیده نشد» رویِ خودش می‌ماند.
  const techKept = picked.filter((e) => e.tech !== 'no');
  const techDropped = picked.length - techKept.length;
  // ۳) بنیادی: فقط «ردِ صریح» بیرون می‌افتد. «سنجیده نشد» نه مردود است و نه
  //    تحویل — در گروهِ خودش دیده می‌شود تا لیستِ تحویل قابلِ اتکا بماند.
  const measured = techKept.filter((e) => e.screen);
  const passed = measured.filter((e) => e.fund !== 'no');
  const pending = techKept.filter((e) => !e.screen);
  // ۴) تحویل: بنیادش واقعاً سنجیده و قبول شده و هنوز درِ سبد نیست
  const handover = passed.filter((e) => !portfolioSet.has(e.symbol));

  return {
    boardScope: scope.length,
    total: picked.length,
    stages: {
      tape: { key: 'tape', entries: picked, dropped: 0, unmeasured: 0, pending: [] },
      technical: {
        key: 'technical',
        entries: picked,
        dropped: techDropped,
        unmeasured: unmeasuredOn(picked, 'tech'),
        pending: [],
      },
      fundamental: {
        key: 'fundamental',
        entries: passed,
        dropped: measured.length - passed.length,
        unmeasured: pending.length,
        pending,
      },
      handover: { key: 'handover', entries: handover, dropped: 0, unmeasured: 0, pending: [] },
    },
  };
}
