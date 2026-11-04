import { beforeEach, describe, expect, it } from 'vitest';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';

beforeEach(() => {
  useFundamentalPrefs.setState({ density: 'comfortable', sortKey: 'score', sortDir: 'desc' });
});

describe('fundamental prefs', () => {
  it('defaults to comfortable/score desc without a surface', () => {
    const state = useFundamentalPrefs.getState();
    expect([state.density, state.sortKey, state.sortDir]).toEqual(['comfortable', 'score', 'desc']);
    expect('surface' in state).toBe(false);
  });
  it('updates density and sort without a surface', () => {
    useFundamentalPrefs.getState().setDensity('compact');
    useFundamentalPrefs.getState().setSort('margin', 'asc');
    const state = useFundamentalPrefs.getState();
    expect([state.density, state.sortKey, state.sortDir]).toEqual(['compact', 'margin', 'asc']);
    expect('surface' in state).toBe(false);
  });
});
