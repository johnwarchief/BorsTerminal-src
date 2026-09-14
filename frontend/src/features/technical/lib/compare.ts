// features/technical/lib/compare.ts -- مقایسهٔ چند نماد روی یک محور (نرمال‌شده به پایهٔ ۱۰۰)
// خالص و مستقل از DOM. فقط زمان‌های مشترک همهٔ نمادها مقایسه می‌شوند تا سری‌ها هم‌مقیاس باشند.
import type { KLineData } from '../../../vendor/klinecharts';

export const COMPARE_COLORS = ['#38bdf8', '#fbbf24', '#a78bfa'] as const;
export const COMPARE_MAX_SYMBOLS = 3;
export const COMPARE_BASE = 100;

export type CompareLine = { symbol: string; values: number[]; changePct: number | null; last: number | null };
export type CompareResult = { timestamps: number[]; lines: CompareLine[] };

/** نرمال‌سازی یک سری به پایهٔ ۱۰۰ (نسبت به اولین بستهٔ معتبر) */
export function normalizeTo100(candles: KLineData[]): { ts: number[]; values: number[] } {
  const rows = [...candles].sort((a, b) => a.timestamp - b.timestamp).filter((c) => Number.isFinite(c.close) && c.close > 0);
  if (rows.length === 0) return { ts: [], values: [] };
  const base = rows[0].close;
  return { ts: rows.map((r) => r.timestamp), values: rows.map((r) => (r.close / base) * COMPARE_BASE) };
}

/** هم‌ترازی چند نماد روی زمان‌های مشترک و نرمال‌سازی نسبت به اولین زمان مشترک */
export function alignCompare(series: { symbol: string; candles: KLineData[] }[]): CompareResult {
  if (series.length === 0) return { timestamps: [], lines: [] };
  const maps = series.map((s) => {
    const m = new Map<number, number>();
    for (const c of [...s.candles].sort((a, b) => a.timestamp - b.timestamp)) {
      if (Number.isFinite(c.close) && c.close > 0) m.set(c.timestamp, c.close);
    }
    return { symbol: s.symbol, m };
  });
  const common = [...maps[0].m.keys()].filter((ts) => maps.every((x) => x.m.has(ts))).sort((a, b) => a - b);
  if (common.length < 2) return { timestamps: [], lines: [] };
  const lines: CompareLine[] = maps.map((x) => {
    const base = x.m.get(common[0]) as number;
    const values = common.map((ts) => ((x.m.get(ts) as number) / base) * COMPARE_BASE);
    const last = values[values.length - 1] ?? null;
    return { symbol: x.symbol, values, changePct: last == null ? null : last - COMPARE_BASE, last };
  });
  return { timestamps: common, lines };
}

export type CompareGeometry = { lines: { symbol: string; path: string; color: string }[]; min: number; max: number };

/** هندسهٔ خطوط مقایسه (SVG) با مقیاس مشترک و خط مرجع ۱۰۰ */
export function compareGeometry(
  result: CompareResult,
  width = 600,
  height = 200,
  pad = 12,
): CompareGeometry | null {
  const { timestamps, lines } = result;
  if (lines.length === 0 || timestamps.length < 2) return null;
  const all = lines.flatMap((l) => l.values).filter((v) => Number.isFinite(v));
  if (all.length === 0) return null;
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (max === min) {
    min -= 1;
    max += 1;
  }
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const xOf = (i: number) => pad + (i * innerW) / (timestamps.length - 1);
  const yOf = (v: number) => pad + innerH * (1 - (v - min) / (max - min));
  return {
    min,
    max,
    lines: lines.map((l, idx) => ({
      symbol: l.symbol,
      color: COMPARE_COLORS[idx % COMPARE_COLORS.length],
      path: l.values.map((v, i) => `${i === 0 ? 'M' : 'L'}${xOf(i).toFixed(2)} ${yOf(v).toFixed(2)}`).join(' '),
    })),
  };
}

/** y خط مرجع ۱۰۰ در هندسهٔ داده‌شده (برای رسم خط‌چین پایه) */
export function baseLineY(geo: CompareGeometry, height = 200, pad = 12): number {
  const innerH = height - pad * 2;
  const t = (COMPARE_BASE - geo.min) / (geo.max - geo.min);
  return pad + innerH * (1 - t);
}
