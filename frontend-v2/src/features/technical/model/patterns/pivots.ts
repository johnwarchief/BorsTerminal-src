// model/patterns/pivots.ts
import type { EngineCandle } from '../doubleTapEngine';

export interface PivotPoint {
  index: number;
  price: number;
  kind: 'high' | 'low';
}

/** عیناً از doubleTapEngine منتقل شده؛ رفتار نباید تغییر کند. */
export function isPivotHigh(data: readonly EngineCandle[], idx: number, left: number, right: number): boolean {
  const h = data[idx].high;
  for (let j = Math.max(0, idx - left); j <= Math.min(data.length - 1, idx + right); j++) {
    if (j !== idx && data[j].high > h) return false;
  }
  return true;
}

export function isPivotLow(data: readonly EngineCandle[], idx: number, left: number, right: number): boolean {
  const l = data[idx].low;
  for (let j = Math.max(0, idx - left); j <= Math.min(data.length - 1, idx + right); j++) {
    if (j !== idx && data[j].low < l) return false;
  }
  return true;
}

/** پیوت‌های متناوب؛ دو قلهٔ پشتِ‌سرِهم فقط بلندتر می‌ماند، دو دره فقط پایین‌تر. */
export function findAlternatingPivots(
  data: readonly EngineCandle[],
  left: number,
  right: number,
): PivotPoint[] {
  const raw: PivotPoint[] = [];
  for (let i = left; i < data.length - right; i++) {
    if (isPivotHigh(data, i, left, right)) raw.push({ index: i, price: data[i].high, kind: 'high' });
    else if (isPivotLow(data, i, left, right)) raw.push({ index: i, price: data[i].low, kind: 'low' });
  }
  const out: PivotPoint[] = [];
  for (const point of raw) {
    const last = out[out.length - 1];
    if (last && last.kind === point.kind) {
      const moreExtreme = point.kind === 'high' ? point.price >= last.price : point.price <= last.price;
      if (moreExtreme) out[out.length - 1] = point;
    } else {
      out.push(point);
    }
  }
  return out;
}
