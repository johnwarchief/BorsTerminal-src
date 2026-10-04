// features/technical/lib/patternOverlays.ts -- نگاشتِ داورهایِ FTSِ سرور به اورلیهایِ ترسیمی
// #193: این لایه دیگر خودش الگو شناسایی نمی‌کند. تا این نسخه سومین موتور بود
// (سرور + نهایات‌نگر + خودش) و با سرور نمی‌خواند: سنجشِ ۱۲ نماد در ۱۴۰۵-۰۷-۰۵ —
// ۱۱ نماد اختلاف، نمونهٔ «پارس»: سطحِ جتِ این موتور ۱۱٬۸۰۸ در برابر ۲٬۷۵۸ِ سرور،
// تلورانس دوقلوی ۲٪ در برابر ۱٫۵٪، و «ساعت شنی» با MA۵۲ِ ۲۶۰ روزهٔ روزانه در
// برابر میانگینِ هفتگی. حالا هر داور فقط یک جا حساب می‌شود: /api/fts.
// خالص: فقط توصیف می‌سازد (نام/نقاط/استایل)؛ ترسیم و سوییچ‌ها لایهٔ چارت است.
// هیچ داوری از نو ساخته نمی‌شود و هیچ عددی درِ همین فایل مقایسه نمی‌شود.
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

import type { FtsAnalysisData } from '../api/useFtsAnalysis';

export type PatternKind =
  | 'jet'
  | 'choch'
  | 'pointhunt'
  | 'double'
  | 'headshoulders'
  | 'thirdpeak'
  | 'ma14exit'
  | 'hourglass';

export const PATTERN_LABELS: Record<PatternKind, string> = {
  jet: 'جت (شکست مقاومت)',
  choch: 'CHoCH',
  pointhunt: 'نقطه‌زنی کف‌ها',
  double: 'کف/سقف دوقلو',
  headshoulders: 'سر و شانه',
  thirdpeak: 'سقف سوم',
  ma14exit: 'خروج زیر MA14',
  hourglass: 'ساعت شنی (MA52/RSI)',
};

export type PatternPref = { enabled: boolean; color: string; opacity: number };
export type PatternPrefs = Record<PatternKind, PatternPref>;

/** پیش‌فرض‌ها: رنگ/شفافیت مطابق نقشهٔ راه فاز ۴ (شفافیت ۰٫۱–۰٫۲) */
export const PATTERN_PREFS_DEFAULT: PatternPrefs = {
  jet: { enabled: true, color: '#22d3ee', opacity: 0.1 },
  choch: { enabled: true, color: '#fb923c', opacity: 0.9 },
  pointhunt: { enabled: true, color: '#a78bfa', opacity: 0.9 },
  double: { enabled: true, color: '#10b981', opacity: 0.2 },
  headshoulders: { enabled: true, color: '#f43f5e', opacity: 0.2 },
  thirdpeak: { enabled: true, color: '#facc15', opacity: 0.12 },
  ma14exit: { enabled: true, color: '#fb7185', opacity: 0.9 },
  hourglass: { enabled: true, color: '#38bdf8', opacity: 0.12 },
};

const alpha = (hex: string, op: number): string => {
  const a = Math.max(0, Math.min(1, op));
  const h = hex.replace('#', '');
  if (h.length !== 6) return hex;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

/** یک اورلی پیشنهادی برای چارت */
export type PatternOverlaySpec = {
  kind: PatternKind;
  /** نقشِ این پرچم از جدولِ موتور — سبک/رنگِ لایۀ نمایش از همین می‌آید */
  role: SignalRole;
  /** نام اورلی ثبت‌شده در موتور (ftsJetLine/مارکر/…) */
  overlayName: string;
  label: string;
  points: { timestamp: number; value: number }[];
  styles?: Record<string, unknown>;
  extendData?: Record<string, unknown>;
};

/** کندلِ دیده‌شده — high/low فقط برایِ سنجشِ ارتفاعِ بصریِ کمربند لازم‌اند */
export type PatternRow = { timestamp: number; low?: number; high?: number };

/**
 * سقفِ ارتفاعِ بصریِ کمربند (#193، داورِ jev-pilot «الف»):
 * کمربندِ سقفِ سوم و ساعت شنی ±۲٪ و ±۳٪ِ قیمت‌اند. رویِ نمادی که دامنهٔ
 * دیده‌شده‌اش مثلاً ۳٪ است همان کمربند هفتادِ درصدِ پنل را پر می‌کرد
 * (سنجشِ پیکسلیِ زندهٔ «آكام»: ۲۶۶۲۳۳ پیکسلِ تغییر از ۱٬۱۲×۳۶۶).
 * اگر پهنایِ کمربند از یک‌پنجمِ دامنهٔ دیده‌شده بلندتر شد، پرکردن حذف می‌شود
 * و فقط دو خطِ سطحِ تمام‌عرض می‌مانند — داوریِ سرور دست‌نخورده می‌ماند.
 */
export const BAND_MAX_OF_VIEW = 0.2;

/** دامنهٔ قیمتِ دیده‌شده (از کندل‌هایِ رویِ چارت)، یا صفر اگر دادهای نباشد */
function visibleSpan(rows: PatternRow[]): number {
  let hi = -Infinity;
  let lo = Infinity;
  for (const r of rows) {
    if (typeof r.high === 'number' && Number.isFinite(r.high)) hi = Math.max(hi, r.high);
    if (typeof r.low === 'number' && Number.isFinite(r.low)) lo = Math.min(lo, r.low);
  }
  return hi > lo && Number.isFinite(hi) && Number.isFinite(lo) ? hi - lo : 0;
}

/**
 * ورودی‌هایِ لایه، عینِ داورهایِ سرور (به فضایِ قیمتِ نمایش نگاشت‌شده).
 * `null` یعنی «سرور نگفت» — هیچ‌کدام صفرِ ساختگی نمی‌شوند.
 * `roles` جدولِ نقش‌هایِ خودِ موتور است (`/api/fts` → `roles`): سبکِ خط از همان
 * می‌آید، نه از سلیقۀ این فایل — تریگرِ ورود پررنگ، زمینه نازک، هشدار و خروج
 * خط‌چین با رنگِ خودش.
 */
export type SignalRole = 'entry' | 'context' | 'warning' | 'exit';

export type PatternInputs = {
  jet: { active: boolean; level: number | null; fromTs: number | null };
  choch: { active: boolean; bullish: boolean; bearish: boolean; level: number | null };
  /** `triggerTs` = کندلی که لمس + ریباند رویِ آن رخ داده (جایِ مارکرِ خرید).
   *  `anchorTs` = لنگرِ کفِ کانال (فقط ساختار/خط). این دو یکی نیستند (#221). */
  pointHunt: {
    active: boolean;
    floor: number | null;
    touches: number | null;
    triggerTs: number | null;
    anchorTs: number | null;
  };
  double: { active: boolean; level: number | null; breakout: boolean };
  /** سقف دوقلو: همان «دوقلو»ی جزوه در سمتِ سقف — موتور در لایۀ ۳ می‌گوید و
   *  تا این نگاشت نبود هیچ‌وقت رسم می‌شد (برچسبِ لایه «کف/سقف دوقلو» بود). */
  doubleTop: { active: boolean; level: number | null };
  headShoulders: { active: boolean; neckline: number | null };
  thirdPeak: { active: boolean; level: number | null };
  ma14Exit: { active: boolean; level: number | null };
  hourglass: { active: boolean; ma52Weekly: number | null; rsi5Weekly: number | null };
  roles: Record<string, SignalRole>;
};

/** سبک‌هایِ نقش‌محور — یک‌جا، تا هیچ کامپوننتی رنگِ دیگری نسازد */
export const ROLE_STYLES: Record<SignalRole, { size: number; style: 'solid' | 'dashed'; opacityCap: number }> = {
  entry: { size: 2, style: 'solid', opacityCap: 1 },
  context: { size: 1, style: 'dashed', opacityCap: 0.35 },
  warning: { size: 1, style: 'dashed', opacityCap: 0.9 },
  exit: { size: 2, style: 'dashed', opacityCap: 1 },
};

export type PatternMapOptions = {
  /** ریالِ تحلیل → فضایِ قیمتِ چارت (تعدیل عملکردی) */
  toDisp: (rial: number) => number;
  /** «YYYY-MM-DD»ِ سرور → timestampِ کندلِ چارت، یا null اگر آن کندل درِ دید نیست */
  tsForDate: (date: string) => number | null;
};

const price = (v: number | null | undefined, toDisp: (n: number) => number): number | null =>
  typeof v === 'number' && Number.isFinite(v) && v > 0 ? toDisp(v) : null;

/** تنها نگاشتِ مجاز: دهانه‌هایِ payload → ورودیِ الگوها (#193، نقش‌ها از دورِ J) */
export function patternInputsFromFts(
  fts: FtsAnalysisData | null | undefined,
  opts: PatternMapOptions,
): PatternInputs {
  const { toDisp, tsForDate } = opts;
  const l1 = fts?.exit_engine?.l1;
  const l3 = fts?.exit_engine?.l3;
  const ph = fts?.point_hunt;
  return {
    jet: {
      active: fts?.jet?.active === true,
      level: price(fts?.jet?.resistance, toDisp),
      // خطِ مقاومت از همان کندلی می‌آید که سقفِ پلکان را زده، نه از ابتدای تاریخ
      fromTs: fts?.jet?.resistance_date ? tsForDate(fts.jet.resistance_date) : null,
    },
    choch: {
      active: fts?.choch?.bearish === true || fts?.choch?.bullish === true,
      bullish: fts?.choch?.bullish === true,
      bearish: fts?.choch?.bearish === true,
      level: price(fts?.choch?.level, toDisp),
    },
    pointHunt: {
      active: ph?.active === true,
      floor: price(ph?.floor_price, toDisp),
      touches: typeof ph?.touches === 'number' ? ph.touches : null,
      // بی‌تاریخِ معتبر هیچ نشانگرایی نمی‌کاریم؛ اندیسِ سرور قابلِ اتکا نیست.
      // مارکرِ خرید رویِ کندلِ تریگر می‌نشیند؛ لنگرِ کف فقط خطِ کانال است.
      triggerTs: ph?.trigger_date ? tsForDate(ph.trigger_date) : null,
      anchorTs: ph?.floor_date ? tsForDate(ph.floor_date) : null,
    },
    double: {
      active: fts?.double_bottom?.active === true,
      level: price(fts?.double_bottom?.neckline, toDisp),
      breakout: fts?.double_bottom?.pct_above_neck != null,
    },
    doubleTop: { active: l3?.double_top === true, level: price(l3?.level ?? l3?.neckline, toDisp) },
    headShoulders: { active: l3?.hs_break === true, neckline: price(l3?.neckline, toDisp) },
    thirdPeak: { active: l3?.third_peak === true, level: price(l3?.third_peak_level, toDisp) },
    ma14Exit: { active: l1?.ma14_exit === true, level: price(l1?.ma14, toDisp) },
    hourglass: {
      active: fts?.hourglass?.active === true,
      ma52Weekly: price(fts?.hourglass?.ma52, toDisp),
      // ساعتِ شنی با RSIِ هفتگیِ دورهٔ ۵ سنجیده می‌شود (جزوه)، نه RSI۱۴
      rsi5Weekly: typeof fts?.hourglass?.weekly_rsi5 === 'number' ? fts.hourglass.weekly_rsi5 : null,
    },
    roles: (fts?.roles ?? {}) as Record<string, SignalRole>,
  };
}

/** نقشِ هر کلیدِ payload؛ اگر payloadِ بی‌نقش برسد (fixture قدیمی) همین جدولِ
 *  ثابت همان taxonomyِ موتور است — اینجا هیچ داوری تازه‌ای ساخته نمی‌شود. */
const DEFAULT_ROLES: Record<string, SignalRole> = {
  jet: 'entry',
  choch_bullish: 'entry',
  choch_bearish: 'exit',
  point_hunt: 'entry',
  double_bottom: 'entry',
  range_break: 'entry',
  hourglass: 'entry',
  double_top: 'exit',
  hs_break: 'exit',
  third_peak: 'warning',
  ma14_exit: 'exit',
};

/** ساخت اورلیها بر اساس انتخاب کاربر — هیچ داوری از نو اینجا نمی‌شود */
export function buildPatternOverlays(
  inputs: PatternInputs,
  prefs: PatternPrefs,
  rows: PatternRow[],
): PatternOverlaySpec[] {
  const lastTs = rows.length > 0 ? rows[rows.length - 1].timestamp : 0;
  const span = visibleSpan(rows);
  const out: PatternOverlaySpec[] = [];
  const on = (k: PatternKind) => prefs[k]?.enabled !== false;
  const col = (k: PatternKind) => prefs[k]?.color ?? PATTERN_PREFS_DEFAULT[k].color;
  const op = (k: PatternKind) => prefs[k]?.opacity ?? PATTERN_PREFS_DEFAULT[k].opacity;
  const roleOf = (key: string): SignalRole => inputs.roles?.[key] ?? DEFAULT_ROLES[key] ?? 'context';
  /** سبکِ نقش‌محور: تریگر پررنگ و پیوسته، زمینه نازک و کم‌رنگ، هشدار/خروج خط‌چین */
  const styleFor = (role: SignalRole, k: PatternKind) => {
    const s = ROLE_STYLES[role];
    return { color: col(k), size: s.size, style: s.style, opacity: Math.min(op(k), s.opacityCap) };
  };

  /** کمربندِ تمام‌عرض: یا مستطیلِ پر، یا (وقتی از پنل بلندتر است) دو خطِ سطح */
  const pushBand = (kind: PatternKind, role: SignalRole, overlayName: string, label: string, hi: number, lo: number) => {
    const edge = col(kind);
    const fill = alpha(edge, Math.min(op(kind), ROLE_STYLES[role].opacityCap));
    if (span > 0 && (hi - lo) / span > BAND_MAX_OF_VIEW) {
      for (const v of [hi, lo]) {
        out.push({
          kind,
          role,
          overlayName: 'ftsJetLine',
          label,
          points: [{ timestamp: lastTs, value: v }],
          styles: { color: edge, size: 1, style: 'dashed' },
          extendData: { label, linesOnly: true },
        });
      }
      return;
    }
    out.push({
      kind,
      role,
      overlayName,
      label,
      points: [
        { timestamp: lastTs, value: hi },
        { timestamp: lastTs, value: lo },
      ],
      styles: { color: fill, borderColor: edge, borderSize: 1, borderStyle: 'dashed' },
      extendData: { label },
    });
  };

  // ۱) جت — فقط وضعیتِ فعلی (رأیِ مالک: جت رویِ کندلِ آخر). یک خطِ مقاومت از
  //    همان کندلی که سقف را ساخته تا امروز، و یک هایلایتِ سه‌کندلی رویِ تریگر.
  //    هیچ مارکرِ تاریخی جت اینجا ساخته نمی‌شود و درِ `_fts_setup_history` هم
  //    حذف شده است.
  if (on('jet') && inputs.jet.active && inputs.jet.level != null && lastTs > 0) {
    const role = roleOf('jet');
    const fromTs = inputs.jet.fromTs ?? lastTs;
    out.push({
      kind: 'jet',
      role,
      overlayName: 'ftsJetLine',
      label: 'JET',
      points: [
        { timestamp: fromTs, value: inputs.jet.level },
        { timestamp: lastTs, value: inputs.jet.level },
      ],
      styles: styleFor(role, 'jet'),
      extendData: { label: 'JET', bounded: true, highlightBars: 3, highlightColor: alpha(col('jet'), op('jet')) },
    });
  }

  // ۲) CHoCH: خط خط‌چین + فلش. جهت را سرور گفته؛ نقش هم از همان جدول می‌آید
  //    (صعودی = تریگرِ ورود، نزولی = خروجِ ساختاری) پس رنگ/سبکِ این دو یکی نیست.
  if (on('choch') && inputs.choch.active && inputs.choch.level != null && lastTs > 0) {
    const role = roleOf(inputs.choch.bullish ? 'choch_bullish' : 'choch_bearish');
    out.push({
      kind: 'choch',
      role,
      overlayName: 'ftsJetLine',
      label: 'CHoCH',
      points: [{ timestamp: lastTs, value: inputs.choch.level }],
      styles: styleFor(role, 'choch'),
      extendData: { label: 'CHoCH', arrow: true },
    });
  }

  // ۳) نقطه‌زنی: مارکرِ خرید رویِ کندلِ **تریگر** (لمس + ریباندِ همین کندل)،
  //    نه رویِ لنگرِ کفِ کانال؛ بی‌تاریخِ تریگر هیچ نشانگرایی نمی‌کاریم (#221).
  if (on('pointhunt') && inputs.pointHunt.active && inputs.pointHunt.floor != null && inputs.pointHunt.triggerTs != null) {
    const role = roleOf('point_hunt');
    out.push({
      kind: 'pointhunt',
      role,
      overlayName: 'ftsPointHunt',
      label: `تریگر ${fmtInt(inputs.pointHunt.floor)} (${toFaDigits(inputs.pointHunt.touches ?? 0)} لمس)`,
      points: [{ timestamp: inputs.pointHunt.triggerTs, value: inputs.pointHunt.floor }],
      styles: styleFor(role, 'pointhunt'),
      extendData: { label: 'نقطه‌زنی', touches: inputs.pointHunt.touches },
    });
  }

  // ۴) کف دوقلو: خط گردن + نشانگر شکست (یقه و شکست هر دو از سرور)
  if (on('double') && inputs.double.active && inputs.double.level != null && lastTs > 0) {
    const role = roleOf('double_bottom');
    out.push({
      kind: 'double',
      role,
      overlayName: 'ftsNeckline',
      label: 'خط گردن (کف دوقلو)',
      points: [{ timestamp: lastTs, value: inputs.double.level }],
      styles: styleFor(role, 'double'),
      extendData: { label: 'خط گردن (کف دوقلو)', breakout: inputs.double.breakout },
    });
  }

  // ۵) سقف دوقلو: خط گردنِ شکسته‌شده — همان لایۀ «دوقلو»، سمتِ سقف (نقش: خروج)
  if (on('double') && inputs.doubleTop.active && inputs.doubleTop.level != null && lastTs > 0) {
    const role = roleOf('double_top');
    out.push({
      kind: 'double',
      role,
      overlayName: 'ftsNeckline',
      label: 'خط گردن (سقف دوقلو)',
      points: [{ timestamp: lastTs, value: inputs.doubleTop.level }],
      styles: styleFor(role, 'double'),
      extendData: { label: 'خط گردن (سقف دوقلو)', exit: true },
    });
  }

  // ۶) سر و شانه: خط گردن — موتور آن را در لایۀ خروج می‌شمارد، پس نقش «خروج»
  //    است نه «هشدار» (تفکیکِ warning/exit درِ خودِ موتور حساب شده).
  if (on('headshoulders') && inputs.headShoulders.active && inputs.headShoulders.neckline != null && lastTs > 0) {
    const role = roleOf('hs_break');
    out.push({
      kind: 'headshoulders',
      role,
      overlayName: 'ftsNeckline',
      label: 'خط گردن سر و شانه',
      points: [{ timestamp: lastTs, value: inputs.headShoulders.neckline }],
      styles: styleFor(role, 'headshoulders'),
      extendData: { label: 'خروج (سر و شانه)', exit: role === 'exit' },
    });
  }

  // ۷) سقف سوم: **هشدار**، نه خروجِ تأییدشده — باندِ نازک حولِ سقفِ تخت
  if (on('thirdpeak') && inputs.thirdPeak.active && inputs.thirdPeak.level != null && lastTs > 0) {
    pushBand(
      'thirdpeak',
      roleOf('third_peak'),
      'ftsZoneBands',
      'منطقه پرریسک سقف سوم (هشدار)',
      inputs.thirdPeak.level * 1.02,
      inputs.thirdPeak.level * 0.98,
    );
  }

  // ۸) خروج کامل زیر MA14: ضربد رویِ همان کندل، رویِ خطِ MA14
  if (on('ma14exit') && inputs.ma14Exit.active && inputs.ma14Exit.level != null && lastTs > 0) {
    const role = roleOf('ma14_exit');
    out.push({
      kind: 'ma14exit',
      role,
      overlayName: 'ftsExitCross',
      label: 'خروج (زیر MA14)',
      points: [{ timestamp: lastTs, value: inputs.ma14Exit.level }],
      styles: styleFor(role, 'ma14exit'),
      extendData: { label: '×', exit: true },
    });
  }

  // ۹) ساعت شنی: نوارِ ورود پله‌ای حولِ MA52ِ هفتگی (RSI۵ِ هفتگی فقط در برچسب)
  if (on('hourglass') && inputs.hourglass.active && inputs.hourglass.ma52Weekly != null && lastTs > 0) {
    pushBand(
      'hourglass',
      roleOf('hourglass'),
      'ftsZoneBands',
      `ساعت شنی (RSI۵ ${toFaDigits(Math.round(inputs.hourglass.rsi5Weekly ?? 0))})`,
      inputs.hourglass.ma52Weekly * 1.03,
      inputs.hourglass.ma52Weekly * 0.97,
    );
  }

  return out;
}
