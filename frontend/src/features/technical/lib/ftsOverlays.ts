// features/technical/lib/ftsOverlays.ts -- رجیستری اورلی های سفارشی FTS روی klinecharts v10
// فیبو کمربندی (rect + لیبل قیمت)، مارکر ستاپ (جت/پولبک روی کندل) و خط مقاومت.
// همه چیز از داده ی بک اند (fib_zones / setups / jet) ساخته می شود؛ هیچ بازتولید محاسبه در فرانت نیست.
import type { OverlayFigure, RegisterOverlayDef } from '../../../vendor/klinecharts';

/** رنگ های ثالت لایه ها (خنثی نسبت به تم؛ پالت رنگ از setStyles می آید) */
export const FTS_OVERLAY_COLORS = {
  fibStep1: 'rgba(34, 211, 238, 0.16)',
  fibStep1Edge: 'rgba(34, 211, 238, 0.75)',
  fibStep2: 'rgba(251, 191, 36, 0.18)',
  fibStep2Edge: 'rgba(251, 191, 36, 0.85)',
  fibText: '#22d3ee',
  fibText2: '#fbbf24',
  jet: '#22d3ee',
  jetFill: 'rgba(34, 211, 238, 0.10)',
  pullback: '#10b981',
  pullbackFill: 'rgba(16, 185, 129, 0.12)',
  chohRed: '#ff3860',
} as const;

function fmtPrice(p: number): string {
  return Number.isFinite(p) ? p.toFixed(0) : '';
}

/**
 * fibZoneOverlay: کمربند فیبو به شکل باکس هایلایت تمام-عرض با لیبل قیمت.
 * points = دو نقطه با همان timestamp: y از قیمت lo و hi تزریق میشود؛
 * چون klinecharts قیمت نقطه را به y مپ میکند، باکس از y(lo) تا y(hi) رسم میشود.
 * extendData = { color, edge, textColor, label }
 */
export const FIB_ZONE_OVERLAY = 'ftsFibZone';

/**
 * jetMarkerOverlay: بج ستاپ روی کندل — فلش/لوزی بالای کندل با لیبل.
 * extendData = { label, color, fill, dir } ; dir='up' بالای کندل، 'down' زیر کندل.
 */
export const JET_MARKER_OVERLAY = 'ftsJetMarker';

/** pullbackMarkerOverlay: همان شکل مارکر، برای ستاپ پولبک کم ریسک */
export const PULLBACK_MARKER_OVERLAY = 'ftsPullbackMarker';

/** jetResistanceOverlay: خط مقاومت جت (خط آبی پرواز) با لیبل قیمت */
export const JET_LINE_OVERLAY = 'ftsJetLine';

/** ابزارهای ترسیمی سفارشیِ تعاملی FTS — نگاشتِ نبودشان در klinecharts v10 */
export const FTS_FIB_OVERLAY = 'ftsFib';
/** حالت لگاریتمی فیبوی FTS (سطوح روی ln قیمت) */
export const FTS_FIB_LOG_OVERLAY = 'ftsFibLog';
export const FTS_MEASURE_OVERLAY = 'ftsMeasure';
export const FTS_POSITION_OVERLAY = 'ftsPosition';

/** سطوح فیبوی FTS (FTS_SPEC بخش اول بند ۳): دو کمربند + مبنا ۱.۰ */
export const FTS_FIB_LEVELS = [0, 0.33, 0.4, 0.618, 0.7, 1] as const;
export const FTS_FIB_BANDS: readonly (readonly [number, number])[] = [
  [0.33, 0.4],
  [0.618, 0.7],
];

type MarkerCtx = {
  overlay: Record<string, unknown>;
  coordinates: { x: number; y: number }[];
  barSpace: { bar: number };
};

function markerFigures(ctx: MarkerCtx) {
  const ext = (ctx.overlay.extendData ?? {}) as { label?: string; color?: string; fill?: string; dir?: string };
  const { x, y } = ctx.coordinates[0];
  const r = Math.max(5, Math.min(9, ctx.barSpace.bar * 0.42));
  const up = ext.dir !== 'down';
  const tip = up ? y - r * 2.4 : y + r * 2.4;
  const base = up ? y - r * 0.6 : y + r * 0.6;
  const color = ext.color ?? FTS_OVERLAY_COLORS.jet;
  const figures: OverlayFigure[] = [
    {
      type: 'polygon',
      attrs: { coordinates: [{ x: x - r, y: base }, { x: x + r, y: base }, { x, y: tip }] },
      styles: { style: 'fill', color: ext.fill ?? color, borderColor: color, borderSize: 1 },
      ignoreEvent: true,
    },
  ];
  const label = ext.label ?? '';
  if (label) {
    figures.push({
      type: 'text',
      attrs: { x, y: up ? tip - 6 : tip + r * 1.6, text: label, align: 'center', baseline: up ? 'bottom' : 'top' },
      styles: { color, size: 10, family: 'Vazirmatn, sans-serif', weight: 'bold' },
      ignoreEvent: true,
    });
  }
  return figures;
}

/** ثبت همه ی اورلی های سفارشی؛ idempotent (فراخوانی دوباره خطا نیست) */
export function registerFtsOverlays(api: {
  registerOverlay: (o: RegisterOverlayDef) => void;
  getSupportedOverlays?: () => string[];
}): void {
  const have = api.getSupportedOverlays?.() ?? [];
  const reg = (def: RegisterOverlayDef) => {
    if (have.includes(def.name)) return;
    api.registerOverlay(def);
  };
  reg({
    name: FIB_ZONE_OVERLAY,
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: (ctx) => {
      const ext = (ctx.overlay.extendData ?? {}) as {
        color?: string;
        edge?: string;
        textColor?: string;
        label?: string;
      };
      // دو نقطه: [0]=hi (y بالای باکس)، [1]=lo (y پایین باکس)
      const a = ctx.coordinates[0];
      const b = ctx.coordinates[1];
      if (!a || !b || typeof a.y !== 'number' || typeof b.y !== 'number') return [];
      const top = Math.min(a.y, b.y);
      const h = Math.max(2, Math.abs(a.y - b.y));
      const w = ctx.bounding.width;
      const figures: OverlayFigure[] = [
        {
          type: 'rect',
          attrs: { x: 0, y: top, width: w, height: h },
          styles: {
            color: ext.color ?? FTS_OVERLAY_COLORS.fibStep1,
            borderColor: ext.edge ?? FTS_OVERLAY_COLORS.fibStep1Edge,
            borderSize: 1,
            borderStyle: 'dashed',
            borderRadius: 4,
          },
          ignoreEvent: true,
        },
      ];
      const label = ext.label ?? '';
      if (label) {
        figures.push({
          type: 'text',
          attrs: { x: w - 8, y: top + h + 4, text: label, align: 'right', baseline: 'top' },
          styles: { color: ext.textColor ?? FTS_OVERLAY_COLORS.fibText, size: 10, family: 'Vazirmatn, sans-serif', weight: 'bold' },
          ignoreEvent: true,
        });
      }
      return figures;
    },
  });
  reg({
    name: JET_MARKER_OVERLAY,
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: (ctx) =>
      markerFigures({ overlay: ctx.overlay, coordinates: ctx.coordinates, barSpace: ctx.barSpace }) as never,
  });
  reg({
    name: PULLBACK_MARKER_OVERLAY,
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: (ctx) =>
      markerFigures({ overlay: ctx.overlay, coordinates: ctx.coordinates, barSpace: ctx.barSpace }) as never,
  });
  reg({
    name: JET_LINE_OVERLAY,
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: (ctx) => {
      const ext = (ctx.overlay.extendData ?? {}) as { label?: string; color?: string };
      const pt = ctx.coordinates[0];
      const yRaw = typeof pt?.y === 'number' ? pt.y : null;
      if (yRaw == null) return [];
      const w = ctx.bounding.width;
      const color = ext.color ?? FTS_OVERLAY_COLORS.jet;
      const figures: OverlayFigure[] = [
        {
          type: 'line',
          attrs: { coordinates: [{ x: 0, y: yRaw }, { x: w, y: yRaw }] },
          styles: { style: 'solid', color, size: 1.5 },
          ignoreEvent: true,
        },
      ];
      const label = ext.label ?? '';
      if (label) {
        figures.push({
          type: 'text',
          attrs: { x: 8, y: yRaw - 5, text: label, align: 'left', baseline: 'bottom' },
          styles: { color, size: 10, family: 'Vazirmatn, sans-serif', weight: 'bold' },
          ignoreEvent: true,
        });
      }
      return figures;
    },
  });
  registerFtsDrawing(reg);
}

/**
 * اورلی‌های ترسیمی تعاملی FTS: فیبوی بازگشتی FTS (۳۳/۴۰/۶۱.۸/۷۰/۱۰۰)،
 * اندازه‌گیری (دو نقطه) و پوزیشن لانگ/شورت (سه نقطه). قیمت/زمان از overlay.points،
 * مختصات از ctx.coordinates (هم‌الگو با fibonacciLine خود vendor).
 */
function registerFtsDrawing(reg: (def: RegisterOverlayDef) => void): void {
  const ptsOf = (ctx: { overlay: Record<string, unknown> }) =>
    (ctx.overlay.points ?? []) as { value?: number; timestamp?: number }[];
  const label = (x: number, y: number, text: string, color: string, align: 'left' | 'right' | 'center' = 'right'): OverlayFigure => ({
    type: 'text',
    attrs: { x, y, text, align, baseline: 'bottom' },
    styles: { color, size: 10, family: 'Vazirmatn, sans-serif', weight: 'bold' },
    ignoreEvent: true,
  });
  const band = (x: number, y1: number, y2: number, w: number, color: string, edge: string): OverlayFigure => ({
    type: 'rect',
    attrs: { x, y: Math.min(y1, y2), width: w, height: Math.max(2, Math.abs(y1 - y2)) },
    styles: { color, borderColor: edge, borderSize: 1, borderStyle: 'dashed' },
    ignoreEvent: true,
  });

  const fibDef = (name: string, log: boolean, textColor: string): RegisterOverlayDef => ({
    name,
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: true,
    needDefaultYAxisFigure: true,
    createPointFigures: (ctx) => {
      const c = ctx.coordinates;
      if (c.length < 2 || typeof c[0]?.y !== 'number' || typeof c[1]?.y !== 'number') return [];
      const w = ctx.bounding.width;
      const pts = ptsOf(ctx);
      const yOf = (t: number) => (c[1].y as number) + ((c[0].y as number) - (c[1].y as number)) * t;
      // قیمت سطح: حالت عادی خطی؛ حالت لگاریتمی هندسی (درست روی محور log)
      const v0 = typeof pts[0]?.value === 'number' ? (pts[0].value as number) : null;
      const v1 = typeof pts[1]?.value === 'number' ? (pts[1].value as number) : null;
      const priceOf = (t: number): number | null => {
        if (v0 == null || v1 == null) return null;
        if (log) {
          if (v0 <= 0 || v1 <= 0) return null;
          return Math.exp(Math.log(v1) + t * (Math.log(v0) - Math.log(v1)));
        }
        return v1 + (v0 - v1) * t;
      };
      const figs: OverlayFigure[] = [];
      for (const [b0, b1] of FTS_FIB_BANDS) {
        const shallow = b0 < 0.5;
        figs.push(
          band(0, yOf(b0), yOf(b1), w, shallow ? FTS_OVERLAY_COLORS.fibStep1 : FTS_OVERLAY_COLORS.fibStep2, shallow ? FTS_OVERLAY_COLORS.fibStep1Edge : FTS_OVERLAY_COLORS.fibStep2Edge),
        );
      }
      for (const t of FTS_FIB_LEVELS) {
        const y = yOf(t);
        figs.push({
          type: 'line',
          attrs: { coordinates: [{ x: 0, y }, { x: w, y }] },
          styles: { style: 'solid', color: FTS_OVERLAY_COLORS.fibText, size: 1 },
          ignoreEvent: true,
        });
        const p = priceOf(t);
        figs.push(label(w - 4, y - 4, `${p == null ? '-' : p.toFixed(0)} (${(t * 100).toFixed(1)}%)`, textColor));
      }
      return figs;
    },
  });
  reg(fibDef(FTS_FIB_OVERLAY, false, FTS_OVERLAY_COLORS.fibText));
  reg(fibDef(FTS_FIB_LOG_OVERLAY, true, FTS_OVERLAY_COLORS.fibText2));

  reg({
    name: FTS_MEASURE_OVERLAY,
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: true,
    needDefaultYAxisFigure: true,
    createPointFigures: (ctx) => {
      const c = ctx.coordinates;
      if (c.length < 2 || typeof c[0]?.y !== 'number' || typeof c[1]?.y !== 'number') return [];
      const pts = ptsOf(ctx);
      const v0 = pts[0]?.value;
      const v1 = pts[1]?.value;
      const t0 = pts[0]?.timestamp;
      const t1 = pts[1]?.timestamp;
      let bars: number | null = null;
      try {
        if (typeof t0 === 'number' && typeof t1 === 'number') {
          const list = ctx.chart.getDataList();
          const lo = Math.min(t0, t1);
          const hi = Math.max(t0, t1);
          bars = list.filter((k) => k.timestamp >= lo && k.timestamp <= hi).length;
        }
      } catch {
        bars = null;
      }
      const delta = typeof v0 === 'number' && typeof v1 === 'number' ? v1 - v0 : null;
      const pct = delta != null && typeof v0 === 'number' && v0 !== 0 ? (delta / v0) * 100 : null;
      const up = delta == null || delta >= 0;
      const color = up ? FTS_OVERLAY_COLORS.pullback : FTS_OVERLAY_COLORS.chohRed;
      const sign = (n: number) => (n >= 0 ? '+' : '');
      const text = `${delta == null ? '-' : sign(delta) + delta.toFixed(0)} (${pct == null ? '-' : sign(pct) + pct.toFixed(1) + '%'})${bars == null ? '' : ` · ${bars} کندل`}`;
      return [
        {
          type: 'line',
          attrs: { coordinates: [{ x: c[0].x, y: c[0].y }, { x: c[1].x, y: c[1].y }] },
          styles: { style: 'dashed', color, size: 1.5 },
          ignoreEvent: true,
        },
        label((c[0].x + c[1].x) / 2, Math.min(c[0].y as number, c[1].y as number) - 6, text, color, 'center'),
      ];
    },
  });

  reg({
    name: FTS_POSITION_OVERLAY,
    totalStep: 4,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: true,
    needDefaultYAxisFigure: true,
    createPointFigures: (ctx) => {
      const c = ctx.coordinates;
      if (c.length < 3) return [];
      const pts = ptsOf(ctx);
      const w = ctx.bounding.width;
      const entry = pts[0]?.value;
      const stop = pts[1]?.value;
      const target = pts[2]?.value;
      const yEntry = c[0].y as number;
      const yStop = c[1].y as number;
      const yTarget = c[2].y as number;
      const rr =
        typeof entry === 'number' && typeof stop === 'number' && typeof target === 'number' && Math.abs(entry - stop) > 0
          ? Math.abs(target - entry) / Math.abs(entry - stop)
          : null;
      return [
        band(0, yEntry, yTarget, w, 'rgba(16, 185, 129, 0.14)', 'rgba(16, 185, 129, 0.6)'),
        band(0, yEntry, yStop, w, 'rgba(244, 63, 94, 0.14)', 'rgba(244, 63, 94, 0.6)'),
        {
          type: 'line',
          attrs: { coordinates: [{ x: 0, y: yEntry }, { x: w, y: yEntry }] },
          styles: { style: 'solid', color: '#38bdf8', size: 1.5 },
          ignoreEvent: true,
        },
        label(w - 4, yEntry - 4, `ورود ${entry == null ? '-' : entry.toFixed(0)} · R/R ${rr == null ? '-' : rr.toFixed(2)}`, '#38bdf8'),
      ];
    },
  });
}

/** ساخت spec کمربند فیبو از داده ی بک اند (fib_zones) — هیچ محاسبه ای بازتولید نمی شود */
export function fibZoneSpecs(
  fib: {
    zone_33_40?: { lo?: number | null; hi?: number | null; in_zone?: boolean | null } | null;
    zone_618_70?: { lo?: number | null; hi?: number | null; in_zone?: boolean | null } | null;
  } | null | undefined,
): { lo: number; hi: number; label: string; color: string; edge: string; textColor: string }[] {
  if (!fib) return [];
  const out: { lo: number; hi: number; label: string; color: string; edge: string; textColor: string }[] = [];
  const z1 = fib.zone_33_40;
  if (z1 && typeof z1.lo === 'number' && typeof z1.hi === 'number' && z1.hi > z1.lo) {
    out.push({
      lo: z1.lo,
      hi: z1.hi,
      label: `پله اول ۳۳-۴۰٪ (${fmtPrice(z1.lo)} - ${fmtPrice(z1.hi)})`,
      color: FTS_OVERLAY_COLORS.fibStep1,
      edge: FTS_OVERLAY_COLORS.fibStep1Edge,
      textColor: FTS_OVERLAY_COLORS.fibText,
    });
  }
  const z2 = fib.zone_618_70;
  if (z2 && typeof z2.lo === 'number' && typeof z2.hi === 'number' && z2.hi > z2.lo) {
    out.push({
      lo: z2.lo,
      hi: z2.hi,
      label: `کمربند طلایی ۶۱.۸-۷۰٪ (${fmtPrice(z2.lo)} - ${fmtPrice(z2.hi)})`,
      color: FTS_OVERLAY_COLORS.fibStep2,
      edge: FTS_OVERLAY_COLORS.fibStep2Edge,
      textColor: FTS_OVERLAY_COLORS.fibText2,
    });
  }
  return out;
}

export type SetupMarker = {
  name: string;
  overlay: string;
  label: string;
  color: string;
  fill: string;
  dir: 'up' | 'down';
  timestamp: number;
  price: number;
};

/** overlay کمربند فیبو: دو نقطه با timestamp آخرین کندل و قیمت hi/lo کمربند */
export function fibZoneOverlayObj(spec: {
  lo: number;
  hi: number;
  label: string;
  color: string;
  edge: string;
  textColor: string;
}, anchorTs: number, groupId: string): Record<string, unknown> {
  return {
    name: FIB_ZONE_OVERLAY,
    groupId,
    points: [
      { timestamp: anchorTs, price: spec.hi },
      { timestamp: anchorTs, price: spec.lo },
    ],
    extendData: { color: spec.color, edge: spec.edge, textColor: spec.textColor, label: spec.label },
  };
}

/** overlay مارکر ستاپ روی یک کندل (timestamp + price مشخص) */
export function markerOverlayObj(
  overlayName: string,
  m: { label: string; color: string; fill: string; dir: 'up' | 'down' },
  timestamp: number,
  price: number,
  groupId: string,
): Record<string, unknown> {
  return {
    name: overlayName,
    groupId,
    points: [{ timestamp, price }],
    extendData: { label: m.label, color: m.color, fill: m.fill, dir: m.dir },
  };
}

/** overlay خط مقاومت جت: خط افقی تمام-عرض با لیبل قیمت */
export function jetLineOverlayObj(
  price: number,
  anchorTs: number,
  groupId: string,
  label = 'خط آبی (مقاومت جت)',
): Record<string, unknown> {
  return {
    name: JET_LINE_OVERLAY,
    groupId,
    points: [{ timestamp: anchorTs, price }],
    extendData: { label: `${label} ${fmtPrice(price)}`, color: FTS_OVERLAY_COLORS.jet },
  };
}

export { fmtPrice };
