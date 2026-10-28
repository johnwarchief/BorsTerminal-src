export type TilePanel = 'board' | 'watch';
export type SplitDir = 'row' | 'col';
export type MoveDir = 'left' | 'right' | 'up' | 'down';

export type LayoutNode =
  | { kind: 'tile'; id: string; panel: TilePanel; follow: boolean }
  | { kind: 'split'; id: string; dir: SplitDir; ratio: number;
      first: LayoutNode; second: LayoutNode };

export const PANEL_LABEL: Record<TilePanel, string> = {
  board: 'تابلو',
  watch: 'دیده‌بان‌ها',
};

export const PANEL_MIN: Record<TilePanel, { w: number; h: number }> = {
  board: { w: 520, h: 240 },
  watch: { w: 220, h: 180 },
};

export const MAX_DEPTH = 3;
export const MAX_TILES = 2;

export const DEFAULT_LAYOUT: LayoutNode = {
  kind: 'split', id: 's-root', dir: 'row', ratio: 0.7,
  first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
  second: { kind: 'tile', id: 't-watch', panel: 'watch', follow: false },
};
