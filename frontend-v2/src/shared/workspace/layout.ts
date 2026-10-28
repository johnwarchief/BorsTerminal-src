import {
  MAX_DEPTH, MAX_TILES, PANEL_MIN,
  type LayoutNode, type MoveDir, type SplitDir, type TilePanel,
} from './types';

export * from './types';

export function panelsInOrder(node: LayoutNode): Array<{ id: string; panel: TilePanel; follow: boolean }> {
  if (node.kind === 'tile') return [{ id: node.id, panel: node.panel, follow: node.follow }];
  return [...panelsInOrder(node.first), ...panelsInOrder(node.second)];
}

export function findTile(node: LayoutNode, id: string): Extract<LayoutNode, { kind: 'tile' }> | null {
  if (node.kind === 'tile') return node.id === id ? node : null;
  return findTile(node.first, id) ?? findTile(node.second, id);
}

export function depthOf(node: LayoutNode): number {
  if (node.kind === 'tile') return 1;
  return 1 + Math.max(depthOf(node.first), depthOf(node.second));
}

function tileCount(node: LayoutNode): number {
  return node.kind === 'tile' ? 1 : tileCount(node.first) + tileCount(node.second);
}

export function splitTile(
  root: LayoutNode, tileId: string, dir: SplitDir, newPanel: TilePanel,
  makeId: (prefix: string) => string = defaultId,
): LayoutNode | null {
  if (tileCount(root) >= MAX_TILES) return null;
  if (findTile(root, tileId) === null) return null;
  if (panelsInOrder(root).some((p) => p.panel === newPanel)) return null;

  function walk(node: LayoutNode, depth: number): { node: LayoutNode; done: boolean } {
    if (node.kind === 'tile') {
      if (node.id !== tileId || depth > MAX_DEPTH) return { node, done: false };
      return {
        done: true,
        node: {
          kind: 'split', id: makeId('s'), dir, ratio: 0.5,
          first: node,
          second: { kind: 'tile', id: makeId('t'), panel: newPanel, follow: true },
        },
      };
    }
    const a = walk(node.first, depth + 1);
    if (a.done) return { node: { ...node, first: a.node }, done: true };
    const b = walk(node.second, depth + 1);
    if (b.done) return { node: { ...node, second: b.node }, done: true };
    return { node, done: false };
  }

  const out = walk(root, 1);
  return out.done ? out.node : null;
}

export function closeTile(root: LayoutNode, tileId: string): LayoutNode | null {
  if (findTile(root, tileId)?.panel === 'board') return null;

  function walk(node: LayoutNode): { node: LayoutNode | null } {
    if (node.kind === 'tile') {
      return node.id === tileId ? { node: null } : { node };
    }
    const first = walk(node.first);
    if (first.node === null) return { node: node.second };
    const second = walk(node.second);
    if (second.node === null) return { node: node.first };
    if (first.node !== node.first || second.node !== node.second) {
      return { node: { ...node, first: first.node, second: second.node } };
    }
    return { node };
  }

  return walk(root).node;
}

interface Rect { x: number; y: number; w: number; h: number }

function rects(node: LayoutNode, rect: Rect, out: Map<string, Rect>): void {
  if (node.kind === 'tile') {
    out.set(node.id, rect);
    return;
  }
  if (node.dir === 'row') {
    const firstW = rect.w * node.ratio;
    rects(node.first, { x: rect.x + rect.w - firstW, y: rect.y, w: firstW, h: rect.h }, out);
    rects(node.second, { x: rect.x, y: rect.y, w: rect.w - firstW, h: rect.h }, out);
  } else {
    const firstH = rect.h * node.ratio;
    rects(node.first, { x: rect.x, y: rect.y, w: rect.w, h: firstH }, out);
    rects(node.second, { x: rect.x, y: rect.y + firstH, w: rect.w, h: rect.h - firstH }, out);
  }
}

function tileRects(root: LayoutNode): Map<string, Rect> {
  const out = new Map<string, Rect>();
  rects(root, { x: 0, y: 0, w: 1, h: 1 }, out);
  return out;
}

export function neighborOf(root: LayoutNode, tileId: string, dir: MoveDir): string | null {
  const map = tileRects(root);
  const from = map.get(tileId);
  if (!from) return null;
  let best: { id: string; gap: number; overlap: number } | null = null;

  for (const [id, r] of map) {
    if (id === tileId) continue;
    const overlap = dir === 'left' || dir === 'right'
      ? Math.min(from.y + from.h, r.y + r.h) - Math.max(from.y, r.y)
      : Math.min(from.x + from.w, r.x + r.w) - Math.max(from.x, r.x);
    if (overlap <= 0.0001) continue;

    const gap = dir === 'right' ? r.x - (from.x + from.w)
      : dir === 'left' ? from.x - (r.x + r.w)
      : dir === 'down' ? r.y - (from.y + from.h)
      : from.y - (r.y + r.h);
    if (gap < -0.0001) continue;

    if (!best || gap < best.gap - 0.0001
      || (Math.abs(gap - best.gap) <= 0.0001 && overlap > best.overlap)) {
      best = { id, gap, overlap };
    }
  }
  return best ? best.id : null;
}

export function swapWithNeighbor(
  root: LayoutNode, tileId: string, dir: MoveDir,
): { root: LayoutNode; movedTo: string } | null {
  const target = neighborOf(root, tileId, dir);
  if (!target) return null;
  const a = findTile(root, tileId);
  const b = findTile(root, target);
  if (!a || !b) return null;

  function walk(node: LayoutNode): LayoutNode {
    if (node.kind === 'tile') {
      if (node.id === a!.id) return { ...node, panel: b!.panel, follow: b!.follow };
      if (node.id === b!.id) return { ...node, panel: a!.panel, follow: a!.follow };
      return node;
    }
    return { ...node, first: walk(node.first), second: walk(node.second) };
  }

  return { root: walk(root), movedTo: target };
}

function minExtent(node: LayoutNode, axis: 'w' | 'h'): number {
  if (node.kind === 'tile') return PANEL_MIN[node.panel][axis];
  const sameAxis = (node.dir === 'row') === (axis === 'w');
  return sameAxis
    ? minExtent(node.first, axis) + minExtent(node.second, axis)
    : Math.max(minExtent(node.first, axis), minExtent(node.second, axis));
}

export function clampRatio(
  node: LayoutNode, ratio: number, width: number, height: number,
): number | null {
  if (node.kind !== 'split') return null;
  const total = node.dir === 'row' ? width : height;
  if (total <= 0) return null;
  const axis = node.dir === 'row' ? 'w' : 'h';
  const lo = minExtent(node.first, axis) / total;
  const hi = 1 - minExtent(node.second, axis) / total;
  if (lo > hi) return null;
  return Math.min(hi, Math.max(lo, ratio));
}

export function ratioFromPointer(
  rect: { left: number; top: number; width: number; height: number },
  dir: SplitDir, x: number, y: number,
): number {
  const raw = dir === 'row'
    ? (rect.left + rect.width - x) / Math.max(1, rect.width)
    : (y - rect.top) / Math.max(1, rect.height);
  return Math.min(0.95, Math.max(0.05, raw));
}

export function isValidLayout(node: unknown): node is LayoutNode {
  let board = 0;
  let total = 0;

  function walk(n: unknown, depth: number): boolean {
    if (!n || typeof n !== 'object') return false;
    const item = n as Record<string, unknown>;
    if (item.kind === 'tile') {
      total += 1;
      if (!['board', 'symbol', 'watch', 'chart'].includes(String(item.panel))) return false;
      if (item.panel === 'board') board += 1;
      return typeof item.id === 'string' && typeof item.follow === 'boolean';
    }
    if (item.kind === 'split') {
      if (depth > MAX_DEPTH) return false;
      const ratio = Number(item.ratio);
      if (!(ratio >= 0.05 && ratio <= 0.95)) return false;
      if (item.dir !== 'row' && item.dir !== 'col') return false;
      return walk(item.first, depth + 1) && walk(item.second, depth + 1);
    }
    return false;
  }

  return walk(node, 1) && board === 1 && total <= MAX_TILES;
}

let counter = 0;
function defaultId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter}`;
}
