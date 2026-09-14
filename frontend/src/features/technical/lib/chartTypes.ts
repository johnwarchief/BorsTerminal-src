// features/technical/lib/chartTypes.ts -- محاسبات خالص انواع چارت (HA/Renko/Kagi/PnF)
// خروجی همه: سری {time,open,high,low,close} (KLineData) تا با همان رندرر کندل نمایش داده شود.
// بدون mock؛ دادهٔ ناکافی ⇒ آرایهٔ خالی (صادقانه). زمان‌ها همیشه اکیداً صعودی و یکتا
// (klinecharts به تکرار/ناترتی حساس است؛ چند بریک/ستون در یک کندل با +1ms جدا می‌شوند).
import type { KLineData } from '../../../vendor/klinecharts';

export type ChartTransform = 'heikin_ashi' | 'renko' | 'kagi' | 'pnf';
export const TRANSFORM_CHART_TYPES: readonly ChartTransform[] = ['heikin_ashi', 'renko', 'kagi', 'pnf'];

export function isChartTransform(t: string): t is ChartTransform {
  return (TRANSFORM_CHART_TYPES as readonly string[]).includes(t);
}

/** اطمینان از اکیداً صعودی/یکتا بودن زمان‌ها */
export function withUniqueTime(rows: KLineData[]): KLineData[] {
  const out: KLineData[] = [];
  let last = Number.NEGATIVE_INFINITY;
  for (const r of rows) {
    const t = r.timestamp <= last ? last + 1 : r.timestamp;
    out.push({ ...r, timestamp: t });
    last = t;
  }
  return out;
}

/** دامنهٔ واقعی یک کندل نسبت به بستهٔ قبلی */
export function trueRange(prevClose: number | null, high: number, low: number): number {
  if (prevClose == null) return high - low;
  return Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
}

/** ATR با میانگین سادهٔ TR (پیش‌فرض ۱۴) — برای اندازهٔ خودکار بریک/باکس */
export function atr(candles: KLineData[], period = 14): number | null {
  if (candles.length < period + 1 || period < 1) return null;
  let sum = 0;
  for (let i = candles.length - period; i < candles.length; i++) {
    sum += trueRange(candles[i - 1]?.close ?? null, candles[i].high, candles[i].low);
  }
  const v = sum / period;
  return Number.isFinite(v) && v > 0 ? v : null;
}

/** Heikin-Ashi: میانگین‌گیری قیمت‌ها برای کندل هموار */
export function heikinAshi(candles: KLineData[]): KLineData[] {
  const out: KLineData[] = [];
  let prevOpen: number | null = null;
  let prevClose: number | null = null;
  for (const c of candles) {
    const haClose: number = (c.open + c.high + c.low + c.close) / 4;
    const haOpen: number =
      prevOpen == null || prevClose == null ? (c.open + c.close) / 2 : (prevOpen + prevClose) / 2;
    out.push({
      timestamp: c.timestamp,
      open: haOpen,
      high: Math.max(c.high, haOpen, haClose),
      low: Math.min(c.low, haOpen, haClose),
      close: haClose,
      volume: c.volume,
    });
    prevOpen = haOpen;
    prevClose = haClose;
  }
  return out;
}

export type RenkoOptions = { boxSize?: number; atrPeriod?: number; atrMultiplier?: number };

/** Renko: هر بریک یک بازهٔ ثابت (ATR×ضریب یا عدد ثابت)؛ فقط بسته‌ها لحاظ می‌شوند */
export function renko(candles: KLineData[], opts: RenkoOptions = {}): KLineData[] {
  if (candles.length === 0) return [];
  const { atrPeriod = 14, atrMultiplier = 1 } = opts;
  const size = opts.boxSize ?? (atr(candles, atrPeriod) ?? 0) * atrMultiplier;
  if (!(size > 0)) return [];
  const out: KLineData[] = [];
  let ref = candles[0].close;
  for (const c of candles) {
    let guard = 0;
    while (Math.abs(c.close - ref) >= size && guard < 1000) {
      guard += 1;
      const up = c.close > ref;
      const open = ref;
      const close = up ? ref + size : ref - size;
      out.push({ timestamp: c.timestamp, open, high: Math.max(open, close), low: Math.min(open, close), close });
      ref = close;
    }
  }
  return withUniqueTime(out);
}

export type KagiOptions = { reversalPct?: number };

/** Kagi: خط شکسته بر پایهٔ سقف/کف و برگشت درصدی */
export function kagi(candles: KLineData[], opts: KagiOptions = {}): KLineData[] {
  if (candles.length === 0) return [];
  const { reversalPct = 4 } = opts;
  const seg = (start: number, end: number, ts: number): KLineData => ({
    timestamp: ts,
    open: start,
    close: end,
    high: Math.max(start, end),
    low: Math.min(start, end),
  });
  const out: KLineData[] = [];
  let dir: 1 | -1 = 1;
  let start = candles[0].close;
  let extreme = start;
  let segTs = candles[0].timestamp;
  const rev = (p: number) => (Math.abs(p) * reversalPct) / 100;
  for (const c of candles) {
    const p = c.close;
    if (dir === 1) {
      if (p > extreme) extreme = p;
      else if (extreme - p >= rev(extreme)) {
        out.push(seg(start, extreme, segTs));
        dir = -1;
        start = extreme;
        extreme = p;
        segTs = c.timestamp;
      }
    } else if (p < extreme) {
      extreme = p;
    } else if (p - extreme >= rev(extreme)) {
      out.push(seg(start, extreme, segTs));
      dir = 1;
      start = extreme;
      extreme = p;
      segTs = c.timestamp;
    }
  }
  if (extreme !== start) out.push(seg(start, extreme, segTs));
  return withUniqueTime(out);
}

export type PnfOptions = { boxSize?: number; atrPeriod?: number; atrMultiplier?: number; reversal?: number };

/**
 * Point & Figure ساده‌شده: ستون‌های X/O بر پایهٔ باکس (ATR×ضریب یا ثابت) و
 * برگشت `reversal` باکس. هر ستون یک کندل: X صعودی (open=کف، close=سقف)، O نزولی.
 */
export function pointAndFigure(candles: KLineData[], opts: PnfOptions = {}): KLineData[] {
  if (candles.length === 0) return [];
  const { atrPeriod = 14, atrMultiplier = 0.5, reversal = 3 } = opts;
  const size = opts.boxSize ?? (atr(candles, atrPeriod) ?? 0) * atrMultiplier;
  if (!(size > 0) || reversal < 1) return [];
  const box = (p: number) => Math.round(p / size);
  const out: KLineData[] = [];
  const emit = (dir: 1 | -1, lo: number, hi: number, ts: number) => {
    const loP = lo * size;
    const hiP = hi * size;
    out.push(
      dir === 1
        ? { timestamp: ts, open: loP, high: hiP, low: loP, close: hiP }
        : { timestamp: ts, open: hiP, high: hiP, low: loP, close: loP },
    );
  };
  let dir: 1 | -1 = 1;
  let min = box(candles[0].close);
  let max = min;
  let colTs = candles[0].timestamp;
  for (const c of candles) {
    const b = box(c.close);
    if (dir === 1) {
      if (b > max) max = b;
      else if (max - b >= reversal) {
        emit(1, min, max, colTs);
        dir = -1;
        min = max - reversal;
        colTs = c.timestamp;
        if (b < min) min = b;
      }
    } else if (b < min) {
      min = b;
    } else if (b - min >= reversal) {
      emit(-1, min, max, colTs);
      dir = 1;
      max = min + reversal;
      colTs = c.timestamp;
      if (b > max) max = b;
    }
  }
  emit(dir, min, max, colTs);
  return withUniqueTime(out);
}

/** نگاشت نوع چارت به ترنسفورم (اگر ترنسفورم نباشد، همان ورودی برمی‌گردد) */
export function transformCandles(kind: string, candles: KLineData[]): KLineData[] {
  switch (kind) {
    case 'heikin_ashi':
      return heikinAshi(candles);
    case 'renko':
      return renko(candles);
    case 'kagi':
      return kagi(candles);
    case 'pnf':
      return pointAndFigure(candles);
    default:
      return candles;
  }
}
