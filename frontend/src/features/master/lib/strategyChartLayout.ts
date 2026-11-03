// features/master/lib/strategyChartLayout.ts — چیدمانِ خالصِ چهار چارت FTS.
//
// داده فقط از `ftsChartModel` می‌آید: parent/childِ خودِ چارت، ریشهٔ چهار Zone و
// سه وابستگیِ اعلام‌شدهٔ چارت ۴ (`ZONE_LINKS`). هیچ گره/یالِ تازه اینجا ساخته
// نمی‌شود؛ این فایل فقط x/y و مسیرِ SVG می‌سازد.
import {
  ZONES, ZONE_LINKS,
  type FtsChartModel, type FtsChartNode, type FtsZone,
} from './ftsChartModel';

export const NODE_W = 250;
export const NODE_H = 68;
export const VIEW_W = 1240;
export const VIEW_H = 860;

const GAP_Y = 14;
const INDENT = 32;
const COL_GAP = 86;
const LANE_HEAD = 90;
const RAIL_Y = 68;

export type ChartMode = 'zone' | 'master';

export interface LayoutNode {
  node: FtsChartNode;
  x: number;
  y: number;
  w: number;
  h: number;
  depth: number;
  hiddenCount: number;
}

export interface LayoutEdge {
  id: string;
  kind: 'tree' | 'zone';
  source: string;
  target: string;
  path: string;
  sourceZone: FtsZone;
  targetZone: FtsZone;
}

export interface ChartLane {
  zone: FtsZone;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ChartLayout {
  mode: ChartMode;
  focus: FtsZone | null;
  width: number;
  height: number;
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  lanes: ChartLane[];
}

/** ترتیبِ ستون‌ها در نقشهٔ جامع: جریانِ مستندِ S→T→F→M از راست به چپ. */
export const MASTER_COLUMN_ORDER: FtsZone[] = ['M', 'F', 'T', 'S'];

function kidsOf(model: FtsChartModel, id: string, collapsed: Set<string>): FtsChartNode[] {
  if (collapsed.has(id)) return [];
  return (model.childrenOf.get(id) ?? [])
    .map((x) => model.byId.get(x))
    .filter((x): x is FtsChartNode => Boolean(x))
    .sort((a, b) => a.order - b.order);
}

function hiddenCount(model: FtsChartModel, id: string): number {
  let n = 0;
  const walk = (cur: string) => {
    for (const c of model.childrenOf.get(cur) ?? []) { n += 1; walk(c); }
  };
  walk(id);
  return n;
}

type Relative = { node: FtsChartNode; x: number; y: number; depth: number; hiddenCount: number };
type Pair = { source: string; target: string; kind: 'tree' };

function zoneTree(model: FtsChartModel, zone: FtsZone, collapsed: Set<string>) {
  const nodes: Relative[] = [];
  const pairs: Pair[] = [];
  let cursor = 0;

  const walk = (id: string, depth: number): { top: number; bottom: number } => {
    const node = model.byId.get(id);
    if (!node) return { top: cursor, bottom: cursor };
    const kids = kidsOf(model, id, collapsed);
    const top = cursor;
    if (!kids.length) {
      const y = cursor;
      cursor += NODE_H + GAP_Y;
      nodes.push({ node, x: depth * INDENT, y, depth, hiddenCount: hiddenCount(model, id) });
      return { top: y, bottom: y + NODE_H };
    }
    for (const k of kids) {
      walk(k.id, depth + 1);
      pairs.push({ source: id, target: k.id, kind: 'tree' });
    }
    const bottom = cursor - GAP_Y;
    const y = top + Math.max(0, (bottom - top - NODE_H) / 2);
    nodes.push({ node, x: depth * INDENT, y, depth, hiddenCount: hiddenCount(model, id) });
    return { top, bottom };
  };

  walk(model.roots[zone], 0);
  return {
    nodes,
    pairs,
    width: Math.max(NODE_W, ...nodes.map((n) => n.x + NODE_W)),
    height: Math.max(NODE_H, cursor - GAP_Y),
  };
}

function treePath(a: LayoutNode, b: LayoutNode): string {
  const sx = a.x + a.w / 2;
  const sy = a.y + a.h;
  const tx = b.x + b.w / 2;
  const ty = b.y;
  const bend = Math.max(18, Math.abs(ty - sy) / 2);
  return `M ${sx} ${sy} C ${sx} ${sy + bend}, ${tx} ${ty - bend}, ${tx} ${ty}`;
}

function zonePath(a: LayoutNode, b: LayoutNode): string {
  const sx = a.x + a.w / 2;
  const tx = b.x + b.w / 2;
  return `M ${sx} ${a.y} L ${sx} ${RAIL_Y} L ${tx} ${RAIL_Y} L ${tx} ${b.y}`;
}

/** گره‌های دارای فرزند، جز ریشه — پیش‌فرضِ نقشهٔ جامع برایِ خوانایی در fit. */
export function defaultCollapsedForMaster(model: FtsChartModel): Set<string> {
  const roots = new Set(Object.values(model.roots));
  return new Set(model.nodes
    .filter((n) => !roots.has(n.id) && (model.childrenOf.get(n.id)?.length ?? 0) > 0)
    .map((n) => n.id));
}

export function layoutStrategyChart(
  model: FtsChartModel,
  opts: { mode: ChartMode; zone?: FtsZone; focus?: FtsZone | null; collapsed?: Set<string> },
): ChartLayout {
  const collapsed = opts.collapsed ?? new Set<string>();
  const focus = opts.mode === 'master' ? (opts.focus ?? null) : null;
  const zones = opts.mode === 'zone'
    ? [opts.zone ?? 'F']
    : (focus ? [focus] : MASTER_COLUMN_ORDER);

  const trees = zones.map((z) => ({ zone: z, ...zoneTree(model, z, collapsed) }));
  const colWidth = Math.max(...trees.map((t) => t.width));
  const nodes: LayoutNode[] = [];
  const lanes: ChartLane[] = [];

  trees.forEach((t, i) => {
    const x0 = i * (colWidth + COL_GAP);
    lanes.push({ zone: t.zone, x: x0, y: 0, width: colWidth, height: LANE_HEAD + t.height });
    for (const n of t.nodes) {
      const box: LayoutNode = {
        node: n.node, x: x0 + n.x, y: LANE_HEAD + n.y,
        w: NODE_W, h: NODE_H, depth: n.depth, hiddenCount: n.hiddenCount,
      };
      nodes.push(box);
    }
  });

  const byId = new Map(nodes.map((n) => [n.node.id, n]));
  const edges: LayoutEdge[] = [];
  for (const t of trees) {
    for (const p of t.pairs) {
      const a = byId.get(p.source);
      const b = byId.get(p.target);
      if (!a || !b) continue;
      edges.push({
        id: `tree_${p.source}_${p.target}`, kind: 'tree',
        source: p.source, target: p.target,
        path: treePath(a, b), sourceZone: a.node.zone, targetZone: b.node.zone,
      });
    }
  }
  if (opts.mode === 'master' && !focus) {
    for (const zl of ZONE_LINKS) {
      const a = byId.get(model.roots[zl.from]);
      const b = byId.get(model.roots[zl.to]);
      if (!a || !b) continue;
      edges.push({
        id: `zone_${zl.id}`, kind: 'zone',
        source: zl.from, target: zl.to,
        path: zonePath(a, b), sourceZone: zl.from, targetZone: zl.to,
      });
    }
  }

  return {
    mode: opts.mode, focus,
    width: Math.max(...lanes.map((l) => l.x + l.width)),
    height: Math.max(...lanes.map((l) => l.height)),
    nodes, edges, lanes,
  };
}

export const ZONE_CHART_META = ZONES;
