// features/technical/lib/macroChart.ts -- هندسهٔ چارت خطی نمای کلان (کل بورس)
// خالص و مستقل از DOM؛ ورودی سری کلان (عدد/رشتهٔ عددی/null) از /api/mstat/timeline.
// کمتر از دو نقطهٔ معتبر ⇒ null (Circuit Breaker: «بدون داده»، نه خط ساختگی).

export type LinePoint = { x: number; y: number; value: number };
export type LineGeometry = { points: LinePoint[]; path: string; min: number; max: number };

/** نگه‌داشتن فقط اعداد متناهی؛ رشتهٔ عددی نیز پذیرفته می‌شود (دامنهٔ سری mstat انعطاف‌پذیر است) */
export function finiteSeries(values: (number | string | null | undefined)[]): number[] {
  const out: number[] = [];
  for (const v of values) {
    const n = typeof v === 'string' ? Number(v) : v;
    if (typeof n === 'number' && Number.isFinite(n)) out.push(n);
  }
  return out;
}

/**
 * هندسهٔ polyline برای یک سری مقداری. عرض/ارتفاع در فضای SVG.
 * خط تخت (min==max) به میانهٔ ارتفاع نگاشت می‌شود تا تقسیم بر صفر رخ ندهد.
 */
export function buildLineGeometry(
  values: (number | string | null | undefined)[],
  width = 320,
  height = 140,
  pad = 8,
): LineGeometry | null {
  const vals = finiteSeries(values);
  if (vals.length < 2 || width <= pad * 2 || height <= pad * 2) return null;
  let min = Math.min(...vals);
  let max = Math.max(...vals);
  if (max === min) {
    min -= 0.5;
    max += 0.5;
  }
  const span = max - min;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const step = innerW / (vals.length - 1);
  const points: LinePoint[] = vals.map((v, i) => ({
    x: pad + i * step,
    y: pad + innerH * (1 - (v - min) / span),
    value: v,
  }));
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');
  return { points, path, min, max };
}
