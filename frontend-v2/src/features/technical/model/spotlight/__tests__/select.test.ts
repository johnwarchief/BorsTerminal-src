import { describe, expect, it } from 'vitest';
import type { SpotlightModel } from '../types';
import { selectSpotlightPattern } from '../select';

function model(over: Partial<SpotlightModel>): SpotlightModel {
  return {
    id: over.id ?? 'm1',
    source: 'classic',
    kind: 'TRIANGLE_SYM',
    kindLabel: 'مثلث متقارن',
    direction: 'neutral',
    status: 'confirmed',
    quality: 60,
    anchorIndex: 100,
    points: [],
    upper: 110,
    lower: 100,
    target: 120,
    stop: 95,
    ...over,
  };
}

describe('selectSpotlightPattern', () => {
  it('returns null for an empty pool', () => {
    expect(selectSpotlightPattern([], 300)).toBeNull();
  });

  it('prefers a recent forming W/M over an older confirmed triangle', () => {
    const wm = model({
      id: 'W',
      source: 'doubleTap',
      kind: 'DOUBLE_BOTTOM',
      status: 'forming',
      quality: 55,
      anchorIndex: 290,
    });
    const triangle = model({ id: 'T', status: 'confirmed', quality: 92, anchorIndex: 240 });
    expect(selectSpotlightPattern([triangle, wm], 300)?.id).toBe('W');
  });

  it('drops invalidated, failed and timed-out patterns', () => {
    const dead = model({ id: 'dead', status: 'invalidated', quality: 99, anchorIndex: 299 });
    const failed = model({ id: 'failed', status: 'failed', quality: 99, anchorIndex: 299 });
    const timedOut = model({ id: 'timed', status: 'timed_out', quality: 99, anchorIndex: 299 });
    const alive = model({ id: 'alive', status: 'confirmed', quality: 50, anchorIndex: 298 });
    expect(selectSpotlightPattern([dead, failed, timedOut, alive], 300)?.id).toBe('alive');
    expect(selectSpotlightPattern([dead, failed, timedOut], 300)).toBeNull();
  });

  it('falls back to a confirmed anchor within 120 bars when no forming is inside 60', () => {
    const stagnant = model({ id: 'stagnant', status: 'forming', quality: 90, anchorIndex: 200 });
    const confirmed = model({ id: 'confirmed', status: 'confirmed', quality: 70, anchorIndex: 250 });
    // lastIndex=300: forming خارج از پنجرهٔ ۶۰، confirmed داخل ۱۲۰.
    expect(selectSpotlightPattern([stagnant, confirmed], 300)?.id).toBe('confirmed');
  });

  it('falls back to the highest quality when nothing sits in the priority windows', () => {
    const older = model({ id: 'older', status: 'forming', quality: 71, anchorIndex: 10 });
    const best = model({ id: 'best', status: 'confirmed', quality: 88, anchorIndex: 20 });
    expect(selectSpotlightPattern([older, best], 600)?.id).toBe('best');
  });

  it('never selects a classic DOUBLE_TOP/DOUBLE_BOTTOM duplicate', () => {
    const classicTop = model({
      id: 'classic-top',
      kind: 'DOUBLE_TOP',
      status: 'forming',
      quality: 99,
      anchorIndex: 299,
    });
    const wm = model({
      id: 'dt', source: 'doubleTap', kind: 'DOUBLE_TOP', status: 'confirmed', quality: 40, anchorIndex: 280,
    });
    expect(selectSpotlightPattern([classicTop, wm], 300)?.id).toBe('dt');
    expect(selectSpotlightPattern([classicTop], 300)).toBeNull();
  });

  it('respects the visible range when it is provided', () => {
    const inside = model({ id: 'inside', status: 'forming', quality: 51, anchorIndex: 295 });
    const outsideVisible = model({ id: 'outside', status: 'forming', quality: 95, anchorIndex: 150 });
    expect(selectSpotlightPattern([outsideVisible, inside], 300, [280, 300])?.id).toBe('inside');
  });

  it('uses quality then recency inside the same window', () => {
    const a = model({ id: 'a', status: 'forming', quality: 60, anchorIndex: 290 });
    const b = model({ id: 'b', status: 'forming', quality: 60, anchorIndex: 295 });
    expect(selectSpotlightPattern([a, b], 300)?.id).toBe('b');
  });
});
