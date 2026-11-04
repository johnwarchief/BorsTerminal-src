import { beforeEach, describe, expect, it } from 'vitest';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';

beforeEach(() => {
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
});

describe('fundamental prefs', () => {
  it('defaults to comfortable/paper/score desc', () => {
    const s = useFundamentalPrefs.getState();
    expect([s.density, s.surface, s.sortKey, s.sortDir]).toEqual(['comfortable', 'paper', 'score', 'desc']);
  });
  it('updates density, surface and sort', () => {
    useFundamentalPrefs.getState().setDensity('compact');
    useFundamentalPrefs.getState().setSurface('ink');
    useFundamentalPrefs.getState().setSort('margin', 'asc');
    const s = useFundamentalPrefs.getState();
    expect([s.density, s.surface, s.sortKey, s.sortDir]).toEqual(['compact', 'ink', 'margin', 'asc']);
  });
});
