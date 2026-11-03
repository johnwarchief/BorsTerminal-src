// features/technical/lib/structure3Layers.ts -- نگاشتِ قراردادِ موتورِ سوم به اورلیِ موتور-مستقل
// این فایل تنها راهِ `/api/structure3` به رابطِ موتور است و *فقط نقشه می‌زند*:
// نه زیگزاگِ دوباره‌ای می‌سازد، نه آستانه‌ای، نه پیوتی. چیزی که سرور نگفته
// رسم نمی‌شود؛ `meta.pending` (ساختارِ تأییدنشده) هم عمداً رسم نمی‌شود، چون
// نمایشِ پیش از تأیید همان repaint است که گاردِ مرحلۀ ۱۰ آن را رد می‌کند.
// مرزِ سه‌موتوره: group = 'fts-e3' و برچسبِ «م۳» رویِ هر مارکر، پس خروجیِ این
// موتور درِ چارت با نقاطِ ساختاریِ موتورِ اول (گروهِ fts-structure) یکی خوانده
// نمی‌شود و رأیِ رسمی FTS را جابه‌جا نمی‌کند.
import type { Structure3Data, Structure3PointData } from '../api/useStructure3';
import type { ChartOverlaySpec } from '../engine/types';
import { toFaDigits } from '@shared/lib/fmt';

/** گروهِ یکتای لایه -- کلیدِ پاک‌کردن/جایگزینی درِ هر دو موتور */
export const E3_GROUP = 'fts-e3';

/** پالتِ جدا از رنگ‌هایِ لایه‌هایِ FTS؛ زیگزاگِ موتورِ سوم نباید با فیبو/جت/ساختار
 *  موتورِ اول اشتباه گرفته شود (§مرحلۀ ۲: «درِ رابط قابل‌تشخیص بماند»). */
export const E3_COLORS = {
  line: '#e879f9',
  pivotHigh: '#e879f9',
  pivotLow: '#c026d3',
  chochBull: '#f0abfc',
  chochBear: '#fbcfe8',
} as const;

export type E3LayerInput = {
  e3: Structure3Data | null | undefined;
  /** نخستین کندلِ دید -- بیرونِ دید رسم نمی‌شود (تعدادِ اورلی بی‌سقف نمی‌رود) */
  startTs: number;
  /** آخرین کندلِ دید */
  anchorTs: number;
  /** ریالِ تحلیل → فضایِ قیمتِ چارت (تعدیل عملکردی؛ قاعدۀ لایۀ ۴) */
  toDisp: (rial: number) => number;
  /** 'YYYY-MM-DD' → timestamp، یا null اگر آن روز درِ این سری نیست */
  tsForDate: (date: string) => number | null;
  /** سقفِ *رسم* نه سقفِ تحلیل: سرور همهٔ پیوت‌هایِ تأییدشده را می‌فرستد (وبملت
   *  ۳٬۷۰۰ کندل ⇒ ۵۴۷ پیوت) و هر پیوت یک اورلی است. تازه‌ترین‌ها می‌مانند،
   *  همان کاری که موتورِ اول با `structure_points` (۱۴ نقطه) می‌کند. */
  maxPoints?: number;
};

const usable = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0;

/** برچسبِ مارکر: واژۀِ موتور + امضایِ موتورِ سوم، تا «HH»ِ این لایه با
 *  «HH»ِ ساختارِ موتورِ اول اشتباه خوانده نشود */
export const e3MarkerLabel = (p: Structure3PointData): string =>
  `${p.label ?? (p.kind === 'high' ? 'High' : 'Low')}·م${toFaDigits(3)}`;

/** سقفِ *رسمِ* لایه (تازه‌ترین پیوت‌ها). تحلیل دست‌نخورده است؛ فقط تعدادِ
 *  اورلی‌هایِ رویِ بوم محدود می‌شود -- موتورِ اول هم ساختارش را برش می‌زند. */
export const E3_MAX_DRAWN_POINTS = 200;

export const usablePoint = (p: { timestamp: number | null; value: number } | undefined): boolean =>
  !!p && Number.isFinite(p.value) && p.value > 0;

/** specِ مشترک → اورلیِ klinecharts v10 (خطِ شکسته = `segment`، برچسب = چیپِ متن)
 *  درِ گروهِ موتورِ سوم. موتورِ دوم از همان spec به `toFfcDrawing` می‌رود، پس
 *  یک نگاشتِ سوم برایِ اعداد نداریم. */
export function e3KlinechartsOverlay(
  spec: ChartOverlaySpec,
  groupId: string,
): Record<string, unknown> | null {
  const first = spec.points[0];
  if (spec.kind === 'segment' && spec.points.length >= 2
      && usablePoint(spec.points[0]) && usablePoint(spec.points[1])) {
    return {
      name: 'segment',
      groupId,
      lock: true,
      points: spec.points.slice(0, 2).map((p) => ({ timestamp: p.timestamp, value: p.value })),
      styles: { line: { color: spec.color, size: spec.width ?? 1.6, style: spec.dashed ? 'dashed' : 'solid' } },
    };
  }
  if (spec.kind === 'marker' && usablePoint(first)) {
    return {
      name: 'simpleAnnotation',
      groupId,
      lock: true,
      points: [{ timestamp: first.timestamp, value: first.value }],
      extendData: spec.label ?? '',
      styles: {
        text: {
          color: spec.color,
          size: 10,
          family: 'Vazirmatn',
          backgroundColor: 'rgba(11,17,28,0.72)',
          borderColor: spec.color,
          borderSize: 1,
          borderRadius: 4,
          paddingLeft: 3,
          paddingRight: 3,
          paddingTop: 1,
          paddingBottom: 1,
        },
      },
    };
  }
  return null;
}

/** تنها نگاشتِ مجاز: payloadِ `/api/structure3` → اورلی‌هایِ رابطِ موتور */
export function structure3Layers(i: E3LayerInput): ChartOverlaySpec[] {
  const e3 = i.e3;
  // بی‌پاسخِ موفق (error/empty/insufficient) هیچ لایه‌ای ساخته نمی‌شود؛
  // «چارتِ خالی» باید با «سنجیده نشد» یکی شود، نه با صفرِ ساختگی.
  if (!e3 || e3.status !== 'success') return [];
  const pts = e3.points ?? [];
  const out: ChartOverlaySpec[] = [];
  const visible: { ts: number; v: number; p: Structure3PointData }[] = [];
  for (const p of pts) {
    if (!usable(p.price) || !p.time) continue;
    const ts = i.tsForDate(p.time.slice(0, 10));
    if (ts == null || ts < i.startTs || ts > i.anchorTs) continue;
    const v = i.toDisp(p.price);
    if (!usable(v)) continue;
    visible.push({ ts, v, p });
  }
  const cap = i.maxPoints ?? E3_MAX_DRAWN_POINTS;
  const placed = cap > 0 && visible.length > cap ? visible.slice(visible.length - cap) : visible;
  for (const { ts, v, p } of placed) {
    out.push({
      id: `e3-pv-${p.time}`,
      kind: 'marker',
      group: E3_GROUP,
      points: [{ timestamp: ts, value: v }],
      color: p.kind === 'high' ? E3_COLORS.pivotHigh : E3_COLORS.pivotLow,
      label: e3MarkerLabel(p),
      width: 1,
    });
  }
  // خطِ شکسته: بینِ entriesِ *متوالیِ همین فهرستِ دید*. پیوتِ بیرونِ دید رسم
  // نمی‌شود، پس نخستین پاره‌خط از نخستین پیوتِ دید شروع می‌شود و نه از وترِ
  // یک پیوتِ رفته.
  for (let k = 1; k < placed.length; k += 1) {
    const a = placed[k - 1];
    const b = placed[k];
    out.push({
      id: `e3-seg-${a.p.time}-${b.p.time}`,
      kind: 'segment',
      group: E3_GROUP,
      points: [
        { timestamp: a.ts, value: a.v },
        { timestamp: b.ts, value: b.v },
      ],
      color: E3_COLORS.line,
      label: null,
      width: 1.6,
      dashed: false,
    });
  }
  for (const c of e3.choch ?? []) {
    if (!usable(c.level) || !c.time) continue;
    const ts = i.tsForDate(String(c.time).slice(0, 10));
    if (ts == null || ts < i.startTs || ts > i.anchorTs) continue;
    const v = i.toDisp(c.level);
    if (!usable(v)) continue;
    out.push({
      id: `e3-choch-${c.time}-${c.kind}`,
      kind: 'marker',
      group: E3_GROUP,
      points: [{ timestamp: ts, value: v }],
      color: c.direction === 'bullish' ? E3_COLORS.chochBull : E3_COLORS.chochBear,
      label: `CHoCH م${toFaDigits(3)}`,
      width: 1,
    });
  }
  return out;
}
