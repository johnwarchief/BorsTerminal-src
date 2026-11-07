export type TilePanel = 'board' | 'watch';
export type SplitDir = 'row' | 'col';
export type MoveDir = 'left' | 'right' | 'up' | 'down';

/** سقف‌های درخت چیدمان؛ میزکار بازار و میزکار تکنیکال سقف‌های جدا دارند. */
export interface LayoutLimits {
  maxDepth: number;
  maxTiles: number;
}

export const MARKET_LIMITS: LayoutLimits = { maxDepth: 3, maxTiles: 2 };
export const TECHNICAL_LIMITS: LayoutLimits = { maxDepth: 4, maxTiles: 4 };

export type LayoutNode<P extends string = TilePanel> =
  | { kind: 'tile'; id: string; panel: P; follow: boolean }
  | { kind: 'split'; id: string; dir: SplitDir; ratio: number;
      first: LayoutNode<P>; second: LayoutNode<P> };

export const PANEL_LABEL: Record<TilePanel, string> = {
  board: 'تابلو',
  watch: 'دیده‌بان‌ها',
};

export const PANEL_MIN: Record<TilePanel, { w: number; h: number }> = {
  board: { w: 520, h: 240 },
  watch: { w: 220, h: 180 },
};

/** سازگاری با مصرف‌کننده‌های موجودِ میزکار بازار. */
export const MAX_DEPTH = MARKET_LIMITS.maxDepth;
export const MAX_TILES = MARKET_LIMITS.maxTiles;

export const DEFAULT_LAYOUT: LayoutNode = {
  kind: 'split', id: 's-root', dir: 'row', ratio: 0.7,
  first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
  second: { kind: 'tile', id: 't-watch', panel: 'watch', follow: false },
};
