import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { DEFAULT_SLOTS, sanitizeWorkspace, useWorkspace } from '@shared/workspace/store';

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

describe('workspace store', () => {
  it('starts with the approved default layout and four cards', () => {
    const state = useWorkspace.getState();
    expect(state.workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
    expect(state.workspaces[0].slots).toEqual(DEFAULT_SLOTS);
    expect(state.activeSymbol).toBeNull();
  });

  it('splits, closes and swaps through actions', () => {
    const store = useWorkspace.getState();
    store.split('t-symbol', 'col', 'chart');
    expect(useWorkspace.getState().workspaces[0].layout.kind).toBe('split');
    store.swap('t-symbol', 'down');
    const afterSwap = useWorkspace.getState().workspaces[0].layout;
    expect(JSON.stringify(afterSwap)).toContain('"panel":"watch"');
    useWorkspace.getState().close('t-watch');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).not.toContain('"panel":"watch"');
  });

  it('keeps slots unique and refuses fewer than three', () => {
    useWorkspace.getState().setSlots(['tedpix', 'tedpix', 'breadth']);
    expect(useWorkspace.getState().workspaces[0].slots).toEqual(DEFAULT_SLOTS);
    useWorkspace.getState().setSlots(['tedpix', 'retailValue', 'breadth', 'boardVolume', 'marketTrades', 'tedpix']);
    expect(useWorkspace.getState().workspaces[0].slots).toHaveLength(5);
    expect(new Set(useWorkspace.getState().workspaces[0].slots).size).toBe(5);
  });

  it('rejects an invalid persisted layout', () => {
    expect(sanitizeWorkspace({ version: 1, workspaces: [{ layout: { kind: 'tile' } }] })).toBeNull();
    expect(sanitizeWorkspace(null)).toBeNull();
  });

  it('resets to the default layout', () => {
    useWorkspace.getState().split('t-symbol', 'col', 'chart');
    useWorkspace.getState().resetLayout();
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });
});
