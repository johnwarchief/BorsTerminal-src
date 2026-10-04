// features/technical/lib/engineFtsLayers.ts -- لایه‌های FTSِ سرور برای موتورِ دوم
// رابطِ موتور (engine/types) اورلی را «نیتِ موتور-مستقل» می‌گیرد: level، band،
// segment، marker. چارتِ klinecharts همین داورها را با اورلی‌هایِ ثبت‌شدهٔ خودش
// می‌کشد؛ این فایل همان عددها را به همان شکل به آن رابط می‌دهد تا موتورِ دوم
// «تحلیلِ دوم» نسازد. هیچ داوری اینجا حساب نمی‌شود و هیچ عددی ساخته نمی‌شود:
// چیزی که سرور نگفته رسم نمی‌شود (قاعدهٔ «بی‌داده رأی نیست»).
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import type { ChartOverlaySpec } from '../engine/types';
import { FTS_OVERLAY_COLORS } from './ftsOverlays';

export type FtsLayerInput = {
  fts: FtsAnalysisData | null | undefined;
  /** کندلِ آخرِ دید -- لایه‌های تمام‌عرض تا اینجا کشیده می‌شوند */
  anchorTs: number;
  /** نخستین کندلِ دید -- بی‌این کمربند یک‌نقطه‌ای و نامرئی می‌شد */
  startTs: number;
  /** ریالِ تحلیل → فضایِ قیمتِ چارت (تعدیل عملکردی) */
  toDisp: (rial: number) => number;
  /** «YYYY-MM-DD»ِ سرور → timestamp، یا null اگر آن کندل درِ دید نیست */
  tsForDate: (date: string) => number | null;
  /** سلسله‌مراتبِ دورِ J: سطح‌هایِ هفتگانه فیبو پیش‌فرض رسم نمی‌شوند (زمینه، مزاحمِ
   *  کندل). همان flag درِ هر دو موتور رعایت می‌شود تا ظاهرِ دو موتور یکی بماند. */
  showFibLevels?: boolean;
};

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : null;

/** دو کرانۀ یک کمربند: از اولِ دید تا کندلِ آخر، با سقف و کفِ همان کمربند */
const band = (
  id: string,
  group: string,
  lo: number,
  hi: number,
  label: string,
  edge: string,
  fill: string,
  i: FtsLayerInput,
): ChartOverlaySpec => ({
  id,
  kind: 'band',
  group,
  points: [
    { timestamp: i.startTs, value: lo },
    { timestamp: i.anchorTs, value: hi },
  ],
  color: edge,
  fill,
  label,
  width: 1,
  dashed: true,
});

const level = (
  id: string,
  value: number,
  label: string,
  color: string,
  i: FtsLayerInput,
  dashed = false,
): ChartOverlaySpec => ({
  id,
  kind: 'level',
  group: 'fts-pattern',
  points: [{ timestamp: i.anchorTs, value }],
  color,
  label,
  width: 1.2,
  dashed,
});

/** تنها نگاشتِ مجاز: payloadِ `/api/fts` → اورلی‌هایِ رابطِ موتور */
export function engineFtsLayers(i: FtsLayerInput): ChartOverlaySpec[] {
  const fts = i.fts;
  if (!fts) return [];
  const out: ChartOverlaySpec[] = [];
  const disp = (rial: number | null | undefined): number | null => {
    const v = num(rial);
    return v == null ? null : i.toDisp(v);
  };

  // ۱) کمربندهای فیبو -- عددِ سرور، جهتِ سرور (موجِ نزولی از کف به بالا)
  const fib = fts.fib;
  for (const [key, edge, fill, label] of [
    ['zone_33_40', FTS_OVERLAY_COLORS.fibStep1Edge, FTS_OVERLAY_COLORS.fibStep1, 'پله اول ۳۳-۴۰٪'],
    ['zone_618_70', FTS_OVERLAY_COLORS.fibStep2Edge, FTS_OVERLAY_COLORS.fibStep2, 'کمربند طلایی ۶۱.۸-۷۰٪'],
  ] as const) {
    const z = fib?.[key];
    const lo = disp(z?.lo);
    const hi = disp(z?.hi);
    if (lo != null && hi != null && hi > lo) out.push(band(`fib-${key}`, 'fts-fib', lo, hi, label, edge, fill, i));
  }
  for (const lv of i.showFibLevels ? fib?.levels ?? [] : []) {
    const p = disp(lv.price);
    if (p == null) continue;
    out.push({
      id: `fib-level-${lv.ratio}`,
      kind: 'level',
      group: 'fts-fib',
      points: [{ timestamp: i.anchorTs, value: p }],
      color: FTS_OVERLAY_COLORS.fibText,
      label: `${Math.round(lv.ratio * 100)}٪`,
      width: 1,
      dashed: true,
    });
  }

  // ۲) ستاپ‌ها و سطوحِ تک‌خطی — جت فقط وضعیتِ فعلی (کندلِ آخر)
  const jet = disp(fts.jet?.resistance);
  if (fts.jet?.active === true && jet != null) {
    const fromTs = fts.jet?.resistance_date ? i.tsForDate(fts.jet.resistance_date) : null;
    if (fromTs != null && fromTs < i.anchorTs) {
      out.push({
        id: 'jet',
        kind: 'segment',
        group: 'fts-pattern',
        points: [
          { timestamp: fromTs, value: jet },
          { timestamp: i.anchorTs, value: jet },
        ],
        color: FTS_OVERLAY_COLORS.jet,
        label: 'JET',
        width: 2,
        dashed: false,
      });
    } else {
      out.push(level('jet', jet, 'JET', FTS_OVERLAY_COLORS.jet, i));
    }
  }
  const ch = disp(fts.choch?.level);
  if ((fts.choch?.bearish === true || fts.choch?.bullish === true) && ch != null) {
    out.push(level('choch', ch, 'CHoCH', FTS_OVERLAY_COLORS.chohRed, i, true));
  }
  const neck = disp(fts.double_bottom?.neckline);
  if (fts.double_bottom?.active === true && neck != null) {
    out.push(level('double-bottom', neck, 'خط گردن (کف دوقلو)', '#10b981', i));
  }
  const floor = disp(fts.point_hunt?.floor_price);
  // مارکرِ خرید رویِ کندلِ تریگر است، نه لنگرِ کفِ کانال (#221)
  const triggerTs = fts.point_hunt?.trigger_date ? i.tsForDate(fts.point_hunt.trigger_date) : null;
  if (fts.point_hunt?.active === true && floor != null && triggerTs != null) {
    out.push({
      id: 'point-hunt',
      kind: 'marker',
      group: 'fts-pattern',
      points: [{ timestamp: triggerTs, value: floor }],
      color: '#a78bfa',
      label: `تریگر نقطه‌زنی (${String(fts.point_hunt.touches ?? 0)} لمس)`,
      width: 1,
    });
  }

  // ۳) تریگرِ فعلیِ موتور (برجسته‌ترین انوتیشن، درِ هر دو موتور یکی)
  const trig = fts.status?.trigger;
  if (trig && typeof trig.price === 'number' && trig.price > 0 && trig.date) {
    const tts = i.tsForDate(trig.date);
    if (tts != null) {
      out.push({
        id: 'current-trigger',
        kind: 'marker',
        group: 'fts-pattern',
        points: [{ timestamp: tts, value: i.toDisp(trig.price) }],
        color: '#22d3ee',
        label: `▲ ${trig.label ?? trig.kind}`,
        width: 2,
      });
    }
  }

  // ۴) لایه‌های خروج -- حدِ ضرر و MA14 از لایۀ ۱، ساعت شنی و سقف سوم از ۳
  const stop = disp(fts.exit_engine?.l1?.hard_stop);
  if (stop != null) out.push(level('hard-stop', stop, 'حد ضرر', '#f23645', i, true));
  const ma14 = disp(fts.exit_engine?.l1?.ma14);
  if (fts.exit_engine?.l1?.ma14_exit === true && ma14 != null) {
    out.push(level('ma14-exit', ma14, 'خروج (زیر MA14)', '#fb7185', i));
  }
  const third = disp(fts.exit_engine?.l3?.third_peak_level);
  if (fts.exit_engine?.l3?.third_peak === true && third != null) {
    out.push(band('third-peak', 'fts-pattern', i.toDisp(third * 0.98), i.toDisp(third * 1.02),
      'منطقه پرریسک سقف سوم', '#facc15', 'rgba(250, 204, 21, 0.12)', i));
  }
  const ma52 = disp(fts.hourglass?.ma52);
  if (fts.hourglass?.active === true && ma52 != null) {
    out.push(band('hourglass', 'fts-pattern', i.toDisp(ma52 * 0.97), i.toDisp(ma52 * 1.03),
      'ساعت شنی', '#38bdf8', 'rgba(56, 189, 248, 0.12)', i));
  }

  return out;
}
