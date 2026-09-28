// features/master/lib/ftsFunnel.ts -- مرحلۀ قیف: چه چیزی وارد شد، چه چیزی ماند
//
// ترتیبِ مرحله از خودِ جزوه است و از همان چیزهایی که درِ «درخت استراتژی FTS»
// ستون‌ست: تابلوخوانیِ امروز ← تکنیکال ← بنیادیِ پنج‌شاخصه ← تحویل. یک فرقِ
// مهم با نسخهٔ پیشین: **تکنیکال درِ این قیف هیچ نمادی را حذف نمی‌کند** —
// موتورِ تکنیکال هنوز کامل نیست و رأیِ مالک (۱۴۰۵-۰۷-۰۷) همین است. نشانه‌اش
// می‌ماند تا چشمِ کاربر گم نشود، ولی غربال با تابلو و بنیاد است.
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
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

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
  /** چه تعداد از این مرحلۀ قبل بیرون افتاد (تکنیکال همیشه صفر) */
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

function techMark(e: { screen: FtsScreenRow | null; row: MarketRow | null }): { s: StageMark; why: string } {
  const sc = e.screen;
  if (!sc) return { s: 'na', why: 'تکنیکال: اسکرینر این نماد را پوشش نداده — سنجیده نشد، وتو نیست' };
  const vetoed = sc.weekly_veto === true || sc.tech_matrix_decision === 'REJECT';
  const weeklyUp = sc.tech_trend_w === 'up' || sc.tech_matrix_decision === 'PERMITTED';
  const setup = sc.tech_jet || !!sc.tech_fib_zone || sc.tech_hourglass_active || e.row?.f_jet || e.row?.f_clock;
  if (vetoed) return { s: 'no', why: 'تکنیکال: وتوی هفتگی / REJECTِ ماتریس (نشانه است، حذف نمی‌کند)' };
  if (weeklyUp && setup) return { s: 'ok', why: 'تکنیکال: روندِ هفتگی صعودی با ستاپِ فعال' };
  if (weeklyUp) return { s: 'ok', why: 'تکنیکال: روندِ هفتگی صعودی، ستاپی هنوز نیست' };
  if (setup) return { s: 'na', why: 'تکنیکال: ستاپ هست، روندِ هفتگی صعودیِ تاییدشده نیست' };
  return { s: 'na', why: 'تکنیکال: ستاپی نیست' };
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

export function buildFunnel(
  rows: MarketRow[],
  cfg: TapeFilterConfig,
  quickFilters: string[],
  screenRows: FtsScreenRow[],
  portfolioSet: Set<string>,
  preset: TreePreset = 'custom',
): Funnel {
  const scope = boardScope(rows);
  const screenBySymbol = new Map<string, FtsScreenRow>();
  for (const s of screenRows) if (s.symbol) screenBySymbol.set(s.symbol, s);

  // ۱) تابلوخوانی: سبکِ انتخابی درِ درخت تعیین می‌کند کدام فیلترها دربِ قیف‌اند
  //    (چارت ۳). اگر کاربر خودِ چیپ‌هایِ تابلو را روشن کرده باشد، همان چیپ‌ها
  //    حاکم‌اند — قیف نباید چیزی نشان دهد که تبِ تابلو پشتِ آن نرفته است.
  const entryFilters = quickFilters.length ? quickFilters : PRESET_ENTRY[preset].filters;

  const picked = scope
    .filter((r) => entryFilters.some((f) => tapeFilterVerdict(r, f, cfg)))
    .map<FunnelEntry>((r) => {
      const screen = screenBySymbol.get(r.symbol ?? '') ?? null;
      const t = techMark({ screen, row: r });
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

  // ۲) تکنیکال: هیچ حذفی — فقط نشانه (رأیِ مالک ۱۴۰۵-۰۷-۰۷)
  // ۳) بنیادی: فقط «ردِ صریح» بیرون می‌افتد. «سنجیده نشد» نه مردود است و نه
  //    تحویل — در گروهِ خودش دیده می‌شود تا لیستِ تحویل قابلِ اتکا بماند
  //    (رأیِ jev-pilot: b، اطمینان ۰٫۷۶).
  const measured = picked.filter((e) => e.screen);
  const passed = measured.filter((e) => e.fund !== 'no');
  const pending = picked.filter((e) => !e.screen);
  // ۴) تحویل: بنیادش واقعاً قبول شده و هنوز درِ سبد نیست
  const handover = passed.filter((e) => !portfolioSet.has(e.symbol));

  return {
    boardScope: scope.length,
    total: picked.length,
    stages: {
      tape: { key: 'tape', entries: picked, dropped: 0, unmeasured: 0, pending: [] },
      technical: {
        key: 'technical', entries: picked, dropped: 0,
        unmeasured: unmeasuredOn(picked, 'tech'), pending: [],
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
