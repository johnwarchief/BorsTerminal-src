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
 */
export type PatternInputs = {
  jet: { active: boolean; level: number | null };
  choch: { active: boolean; level: number | null };
  pointHunt: { active: boolean; floor: number | null; touches: number | null; ts: number | null };
  double: { active: boolean; level: number | null; breakout: boolean };
  /** سقف دوقلو: همان «دوقلو»ی جزوه در سمتِ سقف — موتور در لایۀ ۳ می‌گوید و
   *  تا این نگاشت نبود هیچ‌وقت رسم می‌شد (برچسبِ لایه «کف/سقف دوقلو» بود). */
  doubleTop: { active: boolean; level: number | null };
  headShoulders: { active: boolean; neckline: number | null };
  thirdPeak: { active: boolean; level: number | null };
  ma14Exit: { active: boolean; level: number | null };
  hourglass: { active: boolean; ma52Weekly: number | null; rsi14: number | null };
};

export type PatternMapOptions = {
  /** ریالِ تحلیل → فضایِ قیمتِ چارت (تعدیل عملکردی) */
  toDisp: (rial: number) => number;
  /** «YYYY-MM-DD»ِ سرور → timestampِ کندلِ چارت، یا null اگر آن کندل درِ دید نیست */
  tsForDate: (date: string) => number | null;
};

const price = (v: number | null | undefined, toDisp: (n: number) => number): number | null =>
  typeof v === 'number' && Number.isFinite(v) && v > 0 ? toDisp(v) : null;

/** تنها نگاشتِ مجاز: دهانه‌هایِ payload → ورودیِ هشت الگو (#193) */
export function patternInputsFromFts(
  fts: FtsAnalysisData | null | undefined,
  opts: PatternMapOptions,
): PatternInputs {
  const { toDisp, tsForDate } = opts;
  const l1 = fts?.exit_engine?.l1;
  const l3 = fts?.exit_engine?.l3;
  const ph = fts?.point_hunt;
  return {
    jet: { active: fts?.jet?.active === true, level: price(fts?.jet?.resistance, toDisp) },
    choch: {
      active: fts?.choch?.bearish === true || fts?.choch?.bullish === true,
      level: price(fts?.choch?.level, toDisp),
    },
    pointHunt: {
      active: ph?.active === true,
      floor: price(ph?.floor_price, toDisp),
      touches: typeof ph?.touches === 'number' ? ph.touches : null,
      // بی‌تاریخِ معتبر هیچ نشانگرایی نمی‌کاریم؛ اندیسِ سرور قابلِ اتکا نیست
      ts: ph?.floor_date ? tsForDate(ph.floor_date) : null,
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
      rsi14: typeof fts?.hourglass?.weekly_rsi5 === 'number' ? fts.hourglass.weekly_rsi5 : null,
    },
  };
}

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

  /** کمربندِ تمام‌عرض: یا مستطیلِ پر، یا (وقتی از پنل بلندتر است) دو خطِ سطح */
  const pushBand = (kind: PatternKind, overlayName: string, label: string, hi: number, lo: number) => {
    const edge = col(kind);
    const fill = alpha(edge, op(kind));
    if (span > 0 && (hi - lo) / span > BAND_MAX_OF_VIEW) {
      for (const v of [hi, lo]) {
        out.push({
          kind,
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

  // ۱) جت: خط مقاومت + هایلایتِ سه کندلی (سطح از سرور)
  if (on('jet') && inputs.jet.active && inputs.jet.level != null && lastTs > 0) {
    out.push({
      kind: 'jet',
      overlayName: 'ftsJetLine',
      label: 'JET',
      points: [{ timestamp: lastTs, value: inputs.jet.level }],
      styles: { color: col('jet'), size: 1 },
      extendData: { label: 'JET', highlightBars: 3, highlightColor: alpha(col('jet'), op('jet')) },
    });
  }

  // ۲) CHoCH: خط خط‌چین + فلش (جهت را سرور گفته، اینجا فقط رسم می‌شود)
  if (on('choch') && inputs.choch.active && inputs.choch.level != null && lastTs > 0) {
    out.push({
      kind: 'choch',
      overlayName: 'ftsJetLine',
      label: 'CHoCH',
      points: [{ timestamp: lastTs, value: inputs.choch.level }],
      styles: { color: col('choch'), size: 1, style: 'dashed' },
      extendData: { label: 'CHoCH', arrow: true },
    });
  }

  // ۳) نقطه‌زنی: دایره رویِ کندلِ لنگر، به‌شرطِ اینکه آن کندل درِ چارت باشد
  if (on('pointhunt') && inputs.pointHunt.active && inputs.pointHunt.floor != null && inputs.pointHunt.ts != null) {
    out.push({
      kind: 'pointhunt',
      overlayName: 'ftsPointHunt',
      label: `کف ${fmtInt(inputs.pointHunt.floor)} (${toFaDigits(inputs.pointHunt.touches ?? 0)} لمس)`,
      points: [{ timestamp: inputs.pointHunt.ts, value: inputs.pointHunt.floor }],
      styles: { color: col('pointhunt'), size: 1 },
      extendData: { label: 'نقطه‌زنی', touches: inputs.pointHunt.touches },
    });
  }

  // ۴) کف دوقلو: خط گردن + نشانگر شکست (یقه و شکست هر دو از سرور)
  if (on('double') && inputs.double.active && inputs.double.level != null && lastTs > 0) {
    out.push({
      kind: 'double',
      overlayName: 'ftsNeckline',
      label: 'خط گردن (دوقلو)',
      points: [{ timestamp: lastTs, value: inputs.double.level }],
      styles: { color: col('double'), size: 1 },
      extendData: { label: 'خط گردن (دوقلو)', breakout: inputs.double.breakout },
    });
  }

  // ۵) سقف دوقلو: خط گردنِ شکسته‌شده — همان لایۀ «دوقلو»، سمتِ سقف
  if (on('double') && inputs.doubleTop.active && inputs.doubleTop.level != null && lastTs > 0) {
    out.push({
      kind: 'double',
      overlayName: 'ftsNeckline',
      label: 'خط گردن (سقف دوقلو)',
      points: [{ timestamp: lastTs, value: inputs.doubleTop.level }],
      styles: { color: col('double'), size: 1, style: 'dashed' },
      extendData: { label: 'خط گردن (سقف دوقلو)', warning: true },
    });
  }

  // ۶) سر و شانه: خط گردن قرمز + هشدار خروج
  if (on('headshoulders') && inputs.headShoulders.active && inputs.headShoulders.neckline != null && lastTs > 0) {
    out.push({
      kind: 'headshoulders',
      overlayName: 'ftsNeckline',
      label: 'خط گردن سر و شانه',
      points: [{ timestamp: lastTs, value: inputs.headShoulders.neckline }],
      styles: { color: col('headshoulders'), size: 1, style: 'dashed' },
      extendData: { label: 'هشدار خروج (سر و شانه)', warning: true },
    });
  }

  // ۷) سقف سوم: نوار هشدار حولِ سقفِ تخت (سطحِ سرور، ±۲٪ پهنایِ باند)
  if (on('thirdpeak') && inputs.thirdPeak.active && inputs.thirdPeak.level != null && lastTs > 0) {
    pushBand(
      'thirdpeak',
      'ftsZoneBands',
      'منطقه پرریسک سقف سوم',
      inputs.thirdPeak.level * 1.02,
      inputs.thirdPeak.level * 0.98,
    );
  }

  // ۷) خروج کامل زیر MA14: ضربد رویِ همان کندل، رویِ خطِ MA14
  if (on('ma14exit') && inputs.ma14Exit.active && inputs.ma14Exit.level != null && lastTs > 0) {
    out.push({
      kind: 'ma14exit',
      overlayName: 'ftsExitCross',
      label: 'خروج (زیر MA14)',
      points: [{ timestamp: lastTs, value: inputs.ma14Exit.level }],
      styles: { color: col('ma14exit'), size: 1 },
      extendData: { label: '×', warning: true },
    });
  }

  // ۸) ساعت شنی: نوارِ ورود پله‌ای حولِ MA52ِ هفتگی (RSI فقط در برچسب)
  if (on('hourglass') && inputs.hourglass.active && inputs.hourglass.ma52Weekly != null && lastTs > 0) {
    pushBand(
      'hourglass',
      'ftsZoneBands',
      `ساعت شنی (RSI ${toFaDigits(Math.round(inputs.hourglass.rsi14 ?? 0))})`,
      inputs.hourglass.ma52Weekly * 1.03,
      inputs.hourglass.ma52Weekly * 0.97,
    );
  }

  return out;
}
