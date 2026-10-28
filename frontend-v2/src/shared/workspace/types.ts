export type TilePanel = 'board' | 'symbol' | 'watch' | 'chart';
export type SplitDir = 'row' | 'col';
export type MoveDir = 'left' | 'right' | 'up' | 'down';

export type LayoutNode =
  | { kind: 'tile'; id: string; panel: TilePanel; follow: boolean }
  | { kind: 'split'; id: string; dir: SplitDir; ratio: number;
      first: LayoutNode; second: LayoutNode };

export const PANEL_LABEL: Record<TilePanel, string> = {
  board: 'تابلو',
  symbol: 'نماد',
  watch: 'دیده‌بان‌ها',
  chart: 'چارت',
};

export const PANEL_MIN: Record<TilePanel, { w: number; h: number }> = {
  board: { w: 520, h: 240 },
  symbol: { w: 300, h: 200 },
  watch: { w: 260, h: 180 },
  chart: { w: 320, h: 140 },
};

export const MAX_DEPTH = 3;
export const MAX_TILES = 4;

export const DEFAULT_LAYOUT: LayoutNode = {
  kind: 'split', id: 's-root', dir: 'row', ratio: 0.68,
  first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
  second: {
    kind: 'split', id: 's-right', dir: 'col', ratio: 0.58,
    first: { kind: 'tile', id: 't-symbol', panel: 'symbol', follow: true },
    second: { kind: 'tile', id: 't-watch', panel: 'watch', follow: false },
  },
};
