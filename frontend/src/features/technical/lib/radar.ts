// features/technical/lib/radar.ts -- هندسه و محورهای رادار بازار (سایدبار تب رادار)
// خالص و مستقل از DOM. هر محور به بازهٔ ۰..۱۰۰ نگاشت می‌شود؛ مقیاس‌ها فقط برای نمایش‌اند
// (دادهٔ ساختگی نیست). نبود هر ورودی ⇒ مقدار null (پنل «بدون داده» می‌شود).

export type RadarAxis = { label: string; value: number | null };

export type RadarInput = {
  /** درصد نمادهای مثبت از دماسنج بازار (۰..۱۰۰) */
  positivePct: number | null;
  /** قدرت خرید حقیقی (خرید÷فروش سرانه) */
  power: number | null;
  /** نسبت ارزش صف خرید به فروش */
  queueRatio: number | null;
  /** سهم نمادهای معامله‌شده از کل (۰..۱۰۰) */
  tradedSharePct: number | null;
};

/** مقیاس نمایشی هر محور (نه داده) — «پر» یعنی صددرصد رادار */
export const RADAR_SCALE = { powerFull: 2, ratioFull: 3 };

export function clamp01to100(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, v));
}

/** چهار محور سلامت کلان بازار؛ null = ورودی غایب */
export function buildRadarAxes(input: RadarInput): RadarAxis[] {
  const norm = (v: number | null, full: number): number | null =>
    v == null || !Number.isFinite(v) ? null : clamp01to100((v / full) * 100);
  return [
    { label: 'درصد مثبت', value: input.positivePct == null ? null : clamp01to100(input.positivePct) },
    { label: 'قدرت خرید', value: norm(input.power, RADAR_SCALE.powerFull) },
    { label: 'تراز صف', value: norm(input.queueRatio, RADAR_SCALE.ratioFull) },
    { label: 'پهنای معامله', value: input.tradedSharePct == null ? null : clamp01to100(input.tradedSharePct) },
  ];
}

/** آیا همهٔ محورها مقدار دارند؟ (برای رسم چندضلعی) */
export function radarComplete(axes: RadarAxis[]): boolean {
  return axes.length >= 3 && axes.every((a) => a.value != null);
}

export type RadarGeometry = { path: string; points: { x: number; y: number }[] };

/** هندسهٔ چندضلعی رادار؛ محور اول در بالا (زاویه -۹۰ درجه)، ساعتگرد */
export function radarPolygon(values: number[], cx: number, cy: number, r: number): RadarGeometry | null {
  if (values.length < 3 || values.some((v) => !Number.isFinite(v))) return null;
  const points = values.map((v, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / values.length;
    const rad = (clamp01to100(v) / 100) * r;
    return { x: cx + rad * Math.cos(ang), y: cy + rad * Math.sin(ang) };
  });
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' ') + ' Z';
  return { path, points };
}

/** مختصات برچسب هر محور روی محیط دایره (برای متن SVG) */
export function radarLabelPositions(count: number, cx: number, cy: number, r: number): { x: number; y: number; anchor: 'middle' }[] {
  return Array.from({ length: Math.max(0, count) }, (_, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / count;
    return { x: cx + r * 1.18 * Math.cos(ang), y: cy + r * 1.18 * Math.sin(ang) + 3, anchor: 'middle' as const };
  });
}
