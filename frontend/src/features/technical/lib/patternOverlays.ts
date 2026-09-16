// features/technical/lib/patternOverlays.ts -- نگاشت خروجی موتور الگوها به اورلیهای قابل ترسیم
// خالص: فقط توصیف میسازد (نام/نقاط/استایل) تا لایهٔ چارت آنها را createOverlay کند.
// هر الگوی خاموش‌شده هیچ سنتزی تولید نمی‌کند و الگوهای کهنه (anti-clutter) حذف می‌شوند.
import { isStale } from './ftsPatterns';
import type {
  ChochSignal,
  DoubleSignal,
  FibZigzag,
  HeadShoulders,
  Hourglass,
  JetSignal,
  Ma14Exit,
  PointHuntSignal,
  ThirdPeak,
} from './ftsPatterns';

export type PatternKind = 'jet' | 'fib' | 'choch' | 'pointhunt' | 'double' | 'headshoulders' | 'thirdpeak' | 'ma14exit' | 'hourglass';

export const PATTERN_LABELS: Record<PatternKind, string> = {
  jet: 'جت (شکست مقاومت)',
  fib: 'فیبوی لگاریتمی',
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
  fib: { enabled: true, color: '#22c55e', opacity: 0.15 },
  choch: { enabled: true, color: '#fb923c', opacity: 0.9 },
  pointhunt: { enabled: true, color: '#a78bfa', opacity: 0.9 },
  double: { enabled: true, color: '#10b981', opacity: 0.2 },
  headshoulders: { enabled: true, color: '#f43f5e', opacity: 0.2 },
  thirdpeak: { enabled: true, color: '#facc15', opacity: 0.12 },
  ma14exit: { enabled: true, color: '#f43f5e', opacity: 0.9 },
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
  /** نام اورلی ثبت‌شده در موتور (ftsFibZones/ftsJetLine/مارکر/…) */
  overlayName: string;
  label: string;
  points: { timestamp: number; value: number }[];
  styles?: Record<string, unknown>;
  extendData?: Record<string, unknown>;
};

export type PatternInputs = {
  jet?: JetSignal | null;
  fib?: FibZigzag | null;
  choch?: ChochSignal | null;
  pointHunt?: PointHuntSignal | null;
  double?: DoubleSignal | null;
  headShoulders?: HeadShoulders | null;
  thirdPeak?: ThirdPeak | null;
  ma14Exit?: Ma14Exit | null;
  hourglass?: Hourglass | null;
};

/** ساخت اورلیها بر اساس انتخاب کاربر + anti-clutter */
export function buildPatternOverlays(
  inputs: PatternInputs,
  prefs: PatternPrefs,
  rows: { timestamp: number }[],
): PatternOverlaySpec[] {
  const lastTs = rows.length > 0 ? rows[rows.length - 1].timestamp : 0;
  const barsFromEnd = (ts: number): number => {
    const idx = rows.findIndex((r) => r.timestamp >= ts);
    return idx < 0 ? Number.POSITIVE_INFINITY : rows.length - 1 - idx;
  };
  const out: PatternOverlaySpec[] = [];
  const on = (k: PatternKind) => prefs[k]?.enabled !== false;
  const col = (k: PatternKind) => prefs[k]?.color ?? PATTERN_PREFS_DEFAULT[k].color;
  const op = (k: PatternKind) => prefs[k]?.opacity ?? PATTERN_PREFS_DEFAULT[k].opacity;
  const stale = (ts: number) => isStale(barsFromEnd(ts));

  // ۱) جت: خط مقاومت + نشانگر JET (هایلایت ۳ کندلی در همان رنگ با شفافیت کم)
  if (on('jet') && inputs.jet?.active && inputs.jet.level != null && lastTs > 0) {
    out.push({
      kind: 'jet',
      overlayName: 'ftsJetLine',
      label: 'JET',
      points: [{ timestamp: lastTs, value: inputs.jet.level }],
      styles: { color: col('jet'), size: 1 },
      extendData: { label: 'JET', highlightBars: 3, highlightColor: alpha(col('jet'), op('jet')) },
    });
  }

  // ۲) فیبوی لگاریتمی: دو باکس ملایم با لیبل
  if (on('fib') && inputs.fib?.active && inputs.fib.entry1 && inputs.fib.entry2 && lastTs > 0) {
    out.push({
      kind: 'fib',
      overlayName: 'ftsFibZones',
      label: 'Fibo Entry 1 (33-40%)',
      points: [
        { timestamp: lastTs, value: inputs.fib.entry1.to },
        { timestamp: lastTs, value: inputs.fib.entry1.from },
      ],
      styles: { color: alpha('#22c55e', op('fib')), borderColor: col('fib'), borderSize: 1, borderStyle: 'dashed' },
      extendData: { label: 'Fibo Entry 1 (33-40%)' },
    });
    out.push({
      kind: 'fib',
      overlayName: 'ftsFibZones',
      label: 'Fibo Entry 2 (61.8-70%)',
      points: [
        { timestamp: lastTs, value: inputs.fib.entry2.to },
        { timestamp: lastTs, value: inputs.fib.entry2.from },
      ],
      styles: { color: alpha('#22d3ee', op('fib')), borderColor: '#22d3ee', borderSize: 1, borderStyle: 'dashed' },
      extendData: { label: 'Fibo Entry 2 (61.8-70%)' },
    });
  }

  // ۳) CHoCH: خط خط‌چین + فلش
  if (on('choch') && inputs.choch?.active && inputs.choch.level != null && lastTs > 0 && !stale(lastTs)) {
    out.push({
      kind: 'choch',
      overlayName: 'ftsJetLine',
      label: 'CHoCH',
      points: [{ timestamp: lastTs, value: inputs.choch.level }],
      styles: { color: col('choch'), size: 1, style: 'dashed' },
      extendData: { label: 'CHoCH', arrow: true },
    });
  }

  // ۴) نقطه‌زنی: خط روند + دایرهٔ توخالی + تگ کف
  if (on('pointhunt') && inputs.pointHunt?.active && inputs.pointHunt.floor != null && rows.length > 0) {
    const hitTs = inputs.pointHunt.hits.length > 0 ? rows[Math.min(rows.length - 1, inputs.pointHunt.hits[0])]?.timestamp : undefined;
    if (hitTs != null && !stale(hitTs)) {
      out.push({
        kind: 'pointhunt',
        overlayName: 'ftsPointHunt',
        label: `کف ${inputs.pointHunt.floor} (نقطه‌زنی)`,
        points: [{ timestamp: hitTs, value: 0 }],
        styles: { color: col('pointhunt'), size: 1 },
        extendData: { label: `کف ${inputs.pointHunt.floor} (نقطه‌زنی)`, slopePct: inputs.pointHunt.slopePct },
      });
    }
  }

  // ۵) کف دوقلو: خط گردن + نشانگر شکست
  if (on('double') && inputs.double?.active && inputs.double.level != null && lastTs > 0 && !stale(lastTs)) {
    out.push({
      kind: 'double',
      overlayName: 'ftsNeckline',
      label: 'خط گردن (دوقلو)',
      points: [{ timestamp: lastTs, value: inputs.double.level }],
      styles: { color: col('double'), size: 1 },
      extendData: { label: 'خط گردن (دوقلو)', breakout: inputs.double.breakout },
    });
  }

  // ۶) سر و شانه: خط گردن قرمز + هشدار خروج
  if (on('headshoulders') && inputs.headShoulders?.active && inputs.headShoulders.neckline != null && lastTs > 0 && !stale(lastTs)) {
    out.push({
      kind: 'headshoulders',
      overlayName: 'ftsNeckline',
      label: 'خط گردن سر و شانه',
      points: [{ timestamp: lastTs, value: inputs.headShoulders.neckline }],
      styles: { color: col('headshoulders'), size: 1, style: 'dashed' },
      extendData: { label: 'هشدار خروج (سر و شانه)', warning: true },
    });
  }

  // ۷) سقف سوم: نوار هشدار
  if (on('thirdpeak') && inputs.thirdPeak?.active && inputs.thirdPeak.level != null && lastTs > 0 && !stale(lastTs)) {
    out.push({
      kind: 'thirdpeak',
      overlayName: 'ftsZoneBands',
      label: 'منطقه پرریسک سقف سوم',
      points: [
        { timestamp: lastTs, value: inputs.thirdPeak.level * 1.02 },
        { timestamp: lastTs, value: inputs.thirdPeak.level * 0.98 },
      ],
      styles: { color: alpha(col('thirdpeak'), op('thirdpeak')), borderColor: col('thirdpeak'), borderSize: 1, borderStyle: 'dashed' },
      extendData: { label: 'منطقه پرریسک سقف سوم' },
    });
  }

  // ۸) خروج کامل زیر MA14: ضربدر قرمز زیر کندل
  if (on('ma14exit') && inputs.ma14Exit?.active && lastTs > 0 && !stale(lastTs)) {
    out.push({
      kind: 'ma14exit',
      overlayName: 'ftsExitCross',
      label: 'خروج (زیر MA14)',
      points: [{ timestamp: lastTs, value: inputs.ma14Exit.level ?? 0 }],
      styles: { color: col('ma14exit'), size: 1 },
      extendData: { label: '×', warning: true },
    });
  }

  // ۹) ساعت شنی: نوار ورود پله‌ای
  if (on('hourglass') && inputs.hourglass?.active && lastTs > 0) {
    out.push({
      kind: 'hourglass',
      overlayName: 'ftsZoneBands',
      label: 'ساعت شنی (MA52 هفتگی + RSI<30)',
      points: [
        { timestamp: lastTs, value: (inputs.hourglass.ma52Weekly ?? 0) * 1.03 },
        { timestamp: lastTs, value: (inputs.hourglass.ma52Weekly ?? 0) * 0.97 },
      ],
      styles: { color: alpha(col('hourglass'), op('hourglass')), borderColor: col('hourglass'), borderSize: 1, borderStyle: 'dashed' },
      extendData: { label: 'ساعت شنی' },
    });
  }

  return out;
}
