// features/technical/lib/lwChart.ts -- نگاشت دادهٔ FTS به سری‌های Lightweight Charts (v5)
// خالص و مستقل از DOM: سری کندل/حجم/MA/RSI از KLineData. همان اعداد و اندیکاتورهای
// lib/indicators.ts (SMA و RSI وایلدر) استفاده می‌شوند؛ هیچ mock/عدد ساختگی نیست.
import type { CandlestickData, HistogramData, LineData, UTCTimestamp } from 'lightweight-charts';
import type { KLineData } from '../../../vendor/klinecharts';
import { FTS_RSI_PERIOD, rsi, sma } from './indicators';

/** رنگ‌های هم‌ارز پالت (مثل KLineChartWrapper) */
export const LW_UP = '#10b981';
export const LW_DOWN = '#f43f5e';

/** رنگ مووینگ‌های FTS (هم‌خوان با KLineChartWrapper) */
export const LW_MA_COLORS: Record<number, string> = { 14: '#1d4ed8', 21: '#06b6d4', 52: '#f97316', 100: '#a78bfa' };

/** ms → ثانیهٔ UTC (نوع زمانی Lightweight Charts) */
export function toLwTime(tsMs: number): UTCTimestamp {
  return Math.floor(tsMs / 1000) as UTCTimestamp;
}

function sortedUniq(candles: KLineData[]): KLineData[] {
  const sorted = [...candles].sort((a, b) => a.timestamp - b.timestamp);
  const seen = new Set<number>();
  const out: KLineData[] = [];
  for (const c of sorted) {
    const t = toLwTime(c.timestamp);
    if (seen.has(t)) continue;
    seen.add(t);
    out.push(c);
  }
  return out;
}

/** سری کندل؛ زمان‌ها صعودی و یکتا (LW به تکرار/ناصرتی حساس است) */
export function toLwCandles(candles: KLineData[]): CandlestickData<UTCTimestamp>[] {
  return sortedUniq(candles).map((c) => ({
    time: toLwTime(c.timestamp),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

/** هیستوگرام حجم با رنگ هم‌جهت کندل */
export function toLwVolume(candles: KLineData[]): HistogramData<UTCTimestamp>[] {
  return sortedUniq(candles).map((c) => ({
    time: toLwTime(c.timestamp),
    value: c.volume ?? 0,
    color: c.close >= c.open ? 'rgba(16,185,129,0.45)' : 'rgba(244,63,94,0.45)',
  }));
}

/** خط عمومی از یک سریِ مقدارِ هم‌راستا با کندل‌ها (مقادیر null/نامعتبر حذف می‌شوند) */
export function toLwLine(
  candles: KLineData[],
  values: (number | null)[],
  color?: string,
): LineData<UTCTimestamp>[] {
  const rows = sortedUniq(candles);
  const out: LineData<UTCTimestamp>[] = [];
  for (let i = 0; i < rows.length; i++) {
    const v = values[i];
    if (typeof v !== 'number' || !Number.isFinite(v)) continue;
    const point: LineData<UTCTimestamp> = { time: toLwTime(rows[i].timestamp), value: v };
    if (color) point.color = color;
    out.push(point);
  }
  return out;
}

/** MA ساده روی بسته‌ها */
export function maLine(candles: KLineData[], period: number, color?: string): LineData<UTCTimestamp>[] {
  const closes = candles.map((c) => c.close);
  return toLwLine(candles, sma(closes, period), color);
}

/** MA روی حجم (پیش‌فرض ۲۱ — FTS_SPEC بخش اول بند ۲) */
export function volumeMaLine(candles: KLineData[], period = 21, color?: string): LineData<UTCTimestamp>[] {
  const vols = candles.map((c) => (typeof c.volume === 'number' ? c.volume : null));
  return toLwLine(candles, sma(vols, period), color);
}

/** RSI وایلدر (پیش‌فرض ۱۴) روی بسته‌ها */
export function rsiLine(candles: KLineData[], period = FTS_RSI_PERIOD, color?: string): LineData<UTCTimestamp>[] {
  const closes = candles.map((c) => c.close);
  return toLwLine(candles, rsi(closes, period), color);
}
