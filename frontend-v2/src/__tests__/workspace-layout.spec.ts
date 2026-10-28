import { describe, expect, it } from 'vitest';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, isValidLayout, neighborOf, panelsInOrder,
  ratioFromPointer, splitTile, swapWithNeighbor, type LayoutNode,
} from '@shared/workspace/layout';

const ids = (root: LayoutNode) => panelsInOrder(root).map((p) => p.panel);

describe('layout tree', () => {
  it('reads panels right-to-left then top-to-bottom', () => {
    expect(ids(DEFAULT_LAYOUT)).toEqual(['board', 'symbol', 'watch']);
  });

  it('splits the focused tile and refuses a duplicate panel', () => {
    const next = splitTile(DEFAULT_LAYOUT, 't-symbol', 'col', 'chart', () => 't-new');
    expect(next).not.toBeNull();
    expect(panelsInOrder(next!).map((p) => p.panel).sort()).toEqual(['board', 'chart', 'symbol', 'watch']);
    expect(splitTile(next!, 't-symbol', 'col', 'chart', () => 't-x')).toBeNull();
  });

  it('refuses to split beyond four tiles', () => {
    const four = splitTile(DEFAULT_LAYOUT, 't-symbol', 'col', 'chart', () => 't-chart')!;
    expect(splitTile(four, 't-board', 'row', 'chart', () => 't-dup')).toBeNull();
  });

  it('closes a tile and collapses its parent', () => {
    const closed = closeTile(DEFAULT_LAYOUT, 't-watch');
    expect(closed).not.toBeNull();
    expect(ids(closed!)).toEqual(['board', 'symbol']);
    expect(closeTile(DEFAULT_LAYOUT, 't-board')).toBeNull();
  });

  it('finds the visual neighbour in RTL', () => {
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'left')).toBe('t-symbol');
    expect(neighborOf(DEFAULT_LAYOUT, 't-symbol', 'right')).toBe('t-board');
    expect(neighborOf(DEFAULT_LAYOUT, 't-symbol', 'down')).toBe('t-watch');
  });

  it('swaps payloads and keeps tree ids stable', () => {
    const moved = swapWithNeighbor(DEFAULT_LAYOUT, 't-symbol', 'down')!;
    expect(moved.movedTo).toBe('t-watch');
    expect(panelsInOrder(moved.root).map((p) => p.panel)).toEqual(['board', 'watch', 'symbol']);
    expect(moved.root.kind).toBe('split');
  });

  it('clamps ratio by pixel minimums and refuses impossible splits', () => {
    expect(clampRatio(DEFAULT_LAYOUT, 0.95, 1000, 700)).toBeCloseTo(0.7, 5);
    expect(clampRatio(DEFAULT_LAYOUT, 0.68, 500, 700)).toBeNull();
  });

  it('maps pointer position to ratio from the start edge', () => {
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'row', 300, 0)).toBeCloseTo(0.7);
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'col', 0, 300)).toBeCloseTo(0.5);
  });

  it('rejects an invalid layout', () => {
    const noBoard: LayoutNode = { kind: 'tile', id: 'x', panel: 'symbol', follow: true };
    expect(isValidLayout(noBoard)).toBe(false);
    expect(isValidLayout(DEFAULT_LAYOUT)).toBe(true);
  });
});
