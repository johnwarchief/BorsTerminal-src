import { describe, expect, it } from 'vitest';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, findTile, isValidLayout, neighborOf,
  panelsInOrder, ratioFromPointer, splitTile, swapWithNeighbor, type LayoutNode,
} from '@shared/workspace/layout';

const ids = (root: LayoutNode) => panelsInOrder(root).map((item) => item.panel);

describe('layout tree', () => {
  it('reads panels right-to-left', () => {
    expect(ids(DEFAULT_LAYOUT)).toEqual(['board', 'watch']);
  });

  it('refuses a duplicate panel and allows adding watch once it is closed', () => {
    expect(splitTile(DEFAULT_LAYOUT, 't-board', 'col', 'watch', () => 't-x')).toBeNull();
    const closed = closeTile(DEFAULT_LAYOUT, 't-watch')!;
    const next = splitTile(closed, 't-board', 'col', 'watch', () => 't-new');
    expect(next).not.toBeNull();
    expect(ids(next!).sort()).toEqual(['board', 'watch']);
  });

  it('closes a tile, collapses its parent and refuses to close the board', () => {
    expect(ids(closeTile(DEFAULT_LAYOUT, 't-watch')!)).toEqual(['board']);
    expect(closeTile(DEFAULT_LAYOUT, 't-board')).toBeNull();
  });

  it('finds the visual neighbour in RTL', () => {
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'left')).toBe('t-watch');
    expect(neighborOf(DEFAULT_LAYOUT, 't-watch', 'right')).toBe('t-board');
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'down')).toBeNull();
  });

  it('swaps payloads and keeps tree ids stable', () => {
    const moved = swapWithNeighbor(DEFAULT_LAYOUT, 't-board', 'left')!;
    expect(moved.movedTo).toBe('t-watch');
    expect(findTile(moved.root, 't-board')?.panel).toBe('watch');
    expect(findTile(moved.root, 't-watch')?.panel).toBe('board');
  });

  it('clamps ratio by pixel minimums and refuses impossible splits', () => {
    expect(clampRatio(DEFAULT_LAYOUT, 0.95, 1000, 700)).toBeCloseTo(0.78, 5);
    expect(clampRatio(DEFAULT_LAYOUT, 0.7, 700, 700)).toBeNull();
  });

  it('maps pointer position to ratio from the start edge', () => {
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'row', 300, 0)).toBeCloseTo(0.7);
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'col', 0, 300)).toBeCloseTo(0.5);
  });

  it('rejects a legacy symbol panel and accepts the two-pane default', () => {
    const legacy: LayoutNode = { kind: 'tile', id: 'x', panel: 'symbol' as never, follow: false };
    expect(isValidLayout(legacy)).toBe(false);
    expect(isValidLayout(DEFAULT_LAYOUT)).toBe(true);
  });
});
