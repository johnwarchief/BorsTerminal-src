// features/master/lib/ftsChartLayout.ts -- چیدمانِ محاسبه‌شدهٔ «نقشۀ چهار صفحۀ FTS»
// هیچ مختصِ دستی‌ای درِ این فایل نیست (قیدِ مالک: layout باید محاسبه شود). هر Zone
// یک ستونِ ثابت با جایگاهِ ثابت است و رتبه‌ها از خودِ درختِ `ftsChartModel` خوانده
// می‌شوند: ترتیبِ سطر = ترتیبِ سطرهایِ چارت، و تورفتگی = عمقِ parent/child.
//
// چینش از راست به چپ است (RTL): ریشۀ هر Zone در لبۀ راستِ آن Zone، و فرزندان
// یک‌اندازه به چپ تورفته‌اند. آرنجِ رابط از تنۀ سمتِ راستِ گرهٔ والد پایین می‌آید
// و به لبۀ راستِ فرزند می‌رسد — همان شکلِ درختِ پوشایِ راست‌به‌چپ.

import type { FtsChartModel, FtsZone } from './ftsChartModel';
import { ZONES } from './ftsChartModel';

export const ZONE_W = 336;
export const ZONE_GAP = 22;
export const PAD_X = 14;
export const HEADER_H = 52;
export const RAIL_H = 44;
export const PAD_TOP = 12;
export const PAD_BOTTOM = 16;
export const ROW_LEAF_H = 33;
export const ROW_HEAD_H = 19;
export const ROW_GAP = 4;
export const INDENT = 15;
export const LEAF_W = 244;
export const HEAD_W = 210;

/* ----اندازۀ متنِ واقعی: برچسبِ فارسیِ بلند باید داخلِ کارت بشکند، نه اینکه
   از لبۀ ۲۴۴پیکسلی بیرون بزند (Task #78). قیاس با contextِ canvas و فال‌بک
   تخمینی برایِ محیط‌های بی‌canvas (jsdom). ---- */
const LEAF_FS = 11.5;
const HEAD_FS = 11;
const LEAD_LINE = 14;
const TEXT_INNER_W = { leaf: LEAF_W - 20, head: HEAD_W - 8 };

let measureCtx: CanvasRenderingContext2D | null | undefined;
let measureFontFamily: string | undefined;

function glyphWidth(text: string, fs: number): number {
  if (typeof measureCtx === 'undefined') {
    try {
      const canvas = document.createElement('canvas');
      measureCtx = canvas.getContext('2d');
      measureFontFamily = getComputedStyle(document.body).fontFamily || 'sans-serif';
    } catch {
      measureCtx = null;
    }
  }
  if (measureCtx) {
    measureCtx.font = `900 ${fs}px ${measureFontFamily}`;
    return measureCtx.measureText(text).width;
  }
  // فال‌بکِ محافظه‌کار: فارسیِ پررنگ ≈ ۰٫۵۴ِ اندازهٔ فونت به ازای هر نویسه
  return text.length * fs * 0.54;
}

/** واژگان را خط‌به‌خط می‌چیند؛ اگر سه خط هم نشد، با «…» کوتاه می‌کند. */
function wrapLabel(label: string, kind: 'head' | 'leaf'): { lines: string[]; fs: number } {
  const maxW = TEXT_INNER_W[kind];
  for (const fs of kind === 'leaf' ? [LEAF_FS, 10.5] : [HEAD_FS, 10]) {
    const words = label.split(/\s+/).filter(Boolean);
    const lines: string[] = [];
    let cur = '';
    for (const word of words) {
      const next = cur ? `${cur} ${word}` : word;
      if (glyphWidth(next, fs) <= maxW || !cur) cur = next;
      else {
        lines.push(cur);
        cur = word;
      }
    }
    if (cur) lines.push(cur);
    if (lines.length <= 3) {
      if (lines.length === 3 && glyphWidth(lines[2], fs) > maxW) {
        let tail = lines[2];
        while (tail.length > 1 && glyphWidth(`${tail}…`, fs) > maxW) tail = tail.slice(0, -1);
        lines[2] = `${tail}…`;
      }
      return { lines, fs };
    }
  }
  // سه خط هم نشد (برچسبِ بی‌فاصلۀ بسیار بلند): تک‌واژگانی می‌شکند و خطِ آخر حذف
  const fs = kind === 'leaf' ? 10 : 9.5;
  const lines: string[] = [];
  let cur = '';
  for (const ch of label) {
    const next = cur + ch;
    if (glyphWidth(next, fs) <= maxW) cur = next;
    else {
      lines.push(cur);
      cur = ch;
      if (lines.length === 3) break;
    }
  }
  if (lines.length < 3 && cur) lines.push(cur);
  else lines[2] = lines[2].slice(0, -1) + '…';
  return { lines, fs };
}

/** قدِ سطرِ تازه‌شدهٔ هر دو سرِ شاخه و برگ */
const HEAD_EXTRA = 12;
const LEAF_EXTRA = LEAD_LINE;

export interface MapRow {
  id: string;
  zone: FtsZone;
  depth: number;
  kind: 'head' | 'leaf';
  x: number;
  y: number;
  w: number;
  h: number;
  midY: number;
  right: number;
  /** برچسبِ خط‌شکسته بر پایۀ اندازۀ واقعیِ متن (۱ تا ۳ خط) */
  lines: string[];
  /** اندازهٔ فونتِ همان سطر — همان چیزی که با آن اندازه‌گیری شد */
  fs: number;
}

export interface ZoneBox {
  key: FtsZone;
  /** جایگاهِ ثابتِ Zone: ۰ = راست‌ترین (صفحۀ ۱) تا ۳ = چپ‌ترین (صفحۀ ۴) */
  slot: number;
  x: number;
  y: number;
  w: number;
  h: number;
  contentTop: number;
  rowCount: number;
}

export interface TreeLink {
  id: string;
  source: string;
  target: string;
  d: string;
}

export interface MapLayout {
  width: number;
  height: number;
  zones: ZoneBox[];
  rows: MapRow[];
  rowById: Map<string, MapRow>;
  links: TreeLink[];
  /** بلندیِ هر Zone بی‌جمع‌شدگی — برایِ اینکه چیدمانِ تازه به قدِ قبلی قفل بماند */
  fullHeight: number;
}

/** قدِ یک سطر: پایه + سرِ خطهایِ اضافه — تک‌خطی‌ها دقیقاً قدِ همیشگی را دارند */
function rowH(kind: 'head' | 'leaf', lineCount = 1): number {
  const base = kind === 'head' ? ROW_HEAD_H : ROW_LEAF_H;
  const extra = kind === 'head' ? HEAD_EXTRA : LEAF_EXTRA;
  return base + Math.max(0, lineCount - 1) * extra;
}

/** فاصلۀ عمودیِ خطهایِ برچسبِ چندخطی — رسمِ tspan باید همین را بزند */
export const ROW_LEAD = { head: HEAD_EXTRA, leaf: LEAF_EXTRA } as const;

/** ترتیبِ خواندنِ چارت: والد پیش از فرزند، فرزندان به ترتیبِ `order` */
function walk(model: FtsChartModel, rootId: string, out: { id: string; depth: number }[], skip: (id: string) => boolean) {
  const push = (id: string, depth: number) => {
    out.push({ id, depth });
    if (skip(id)) return;
    for (const c of model.childrenOf.get(id) ?? []) push(c, depth + 1);
  };
  push(rootId, 0);
}

/**
 * چیدمانِ کاملِ نقشه. `collapsed` = سرِ شاخه‌هایی که بچه‌هایشان پنهان است.
 * بلندیِ بوم از بلندترین Zone حساب می‌شود، پس چهار ستون هم‌قد دیده می‌شوند.
 */
export function layoutMap(model: FtsChartModel, collapsed: Set<string> = new Set()): MapLayout {
  const skip = (id: string) => collapsed.has(id);
  const zones: ZoneBox[] = [];
  const rows: MapRow[] = [];
  const perZone = new Map<FtsZone, { id: string; depth: number }[]>();

  for (const z of ZONES) {
    const list: { id: string; depth: number }[] = [];
    const root = model.roots[z.key];
    if (root) walk(model, root, list, skip);
    perZone.set(z.key, list);
  }

  // هر برچسب یک‌بار اندازه‌گیری/خط‌بندی می‌شود و همان نتیجه در قد و رسم می‌نشیند
  const wrapOf = new Map<string, { lines: string[]; fs: number }>();
  const wrapFor = (id: string, kind: 'head' | 'leaf', label: string) => {
    let w = wrapOf.get(id);
    if (!w) {
      w = wrapLabel(label, kind);
      wrapOf.set(id, w);
    }
    return w;
  };

  // بلندترین ستون، قدِ بوم را تعیین می‌کند (چهار Zone هم‌قد رسم می‌شوند)
  let tallest = 0;
  for (const z of ZONES) {
    const list = perZone.get(z.key) ?? [];
    const h = list.reduce((acc, r) => {
      const node = model.byId.get(r.id);
      if (!node) return acc;
      const kind = node.kind as 'head' | 'leaf';
      const wr = wrapFor(r.id, kind, node.label);
      return acc + rowH(kind, wr.lines.length) + ROW_GAP;
    }, PAD_TOP);
    if (h > tallest) tallest = h;
  }

  const top = HEADER_H + RAIL_H;
  for (let i = 0; i < ZONES.length; i += 1) {
    const z = ZONES[i];
    const list = perZone.get(z.key) ?? [];
    // RTL: slot 0 (صفحۀ ۱) راست‌ترین است
    const x = PAD_X + (ZONES.length - 1 - i) * (ZONE_W + ZONE_GAP);
    zones.push({
      key: z.key,
      slot: i,
      x,
      y: top,
      w: ZONE_W,
      h: tallest,
      contentTop: top + PAD_TOP,
      rowCount: list.length,
    });
    const boxRight = x + ZONE_W - PAD_X;
    let y = top + PAD_TOP;
    for (const r of list) {
      const node = model.byId.get(r.id);
      if (!node) continue;
      const kind = node.kind;
      const wr = wrapFor(r.id, kind, node.label);
      const h = rowH(kind, wr.lines.length);
      const w = kind === 'head' ? HEAD_W : LEAF_W;
      // تورفتگی از راست: لبۀ راستِ فرزند INDENT واحد چپ‌تر از والد
      const right = boxRight - r.depth * INDENT;
      const row: MapRow = {
        id: r.id,
        zone: z.key,
        depth: r.depth,
        kind,
        x: right - w,
        y,
        w,
        h,
        midY: y + h / 2,
        right,
        lines: wr.lines,
        fs: wr.fs,
      };
      rows.push(row);
      y += h + ROW_GAP;
    }
  }

  const rowById = new Map(rows.map((r) => [r.id, r]));
  const links: TreeLink[] = [];
  for (const row of rows) {
    const node = model.byId.get(row.id);
    if (!node?.parent) continue;
    const p = rowById.get(node.parent);
    if (!p) continue;
    const trunkX = p.right - 9;
    const enterX = row.right + 1;
    links.push({
      id: 'lk_' + node.parent + '_' + row.id,
      source: node.parent,
      target: row.id,
      d: `M ${trunkX} ${p.y + p.h} L ${trunkX} ${row.midY} L ${enterX} ${row.midY}`,
    });
  }

  const width = PAD_X * 2 + ZONES.length * ZONE_W + (ZONES.length - 1) * ZONE_GAP;
  return {
    width,
    height: top + tallest + PAD_BOTTOM,
    zones,
    rows,
    rowById,
    links,
    fullHeight: top + tallest + PAD_BOTTOM,
  };
}

/** مسیرِ منحنیِ نرم برایِ «هم‌نام»ها (خط‌چین)، بینِ دو سطرِ هر دو Zone */
export function refPath(a: MapRow, b: MapRow): string {
  const mid = (a.x + b.x) / 2;
  return `M ${a.x} ${a.midY} C ${mid} ${a.midY}, ${mid} ${b.midY}, ${b.x} ${b.midY}`;
}
