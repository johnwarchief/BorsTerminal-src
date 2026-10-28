import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT, findTile } from '@shared/workspace/layout';
import { SIDE_WIDTH, maxSideWidth } from '@shared/workspace/sizes';
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

  it('closes, splits and swaps through actions', () => {
    const store = useWorkspace.getState();
    store.close('t-watch');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).not.toContain('"watch"');
    store.split('t-board', 'col', 'watch');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).toContain('"panel":"watch"');
    store.swap('t-board', 'down');
    const root = useWorkspace.getState().workspaces[0].layout;
    expect(findTile(root, 't-board')?.panel).toBe('watch');
    expect(useWorkspace.getState().history).toHaveLength(3);
  });

  it('keeps slots unique and refuses fewer than three', () => {
    useWorkspace.getState().setSlots(['tedpix', 'tedpix', 'breadth']);
    expect(useWorkspace.getState().workspaces[0].slots).toEqual(DEFAULT_SLOTS);
    useWorkspace.getState().setSlots(['tedpix', 'retailValue', 'breadth', 'boardVolume', 'marketTrades', 'tedpix']);
    expect(useWorkspace.getState().workspaces[0].slots).toHaveLength(5);
    expect(new Set(useWorkspace.getState().workspaces[0].slots).size).toBe(5);
  });

  it('converts an invalid persisted layout to the default and keeps the other fields', () => {
    const ws = sanitizeWorkspace({
      version: 1,
      workspaces: [{
        layout: { kind: 'tile' },
        slots: ['tedpix', 'boardVolume', 'marketTrades'],
        chartOpen: false,
        sideWidth: 300,
      }],
    });
    expect(ws?.layout).toEqual(DEFAULT_LAYOUT);
    expect(ws?.slots).toEqual(['tedpix', 'boardVolume', 'marketTrades']);
    expect(ws?.chartOpen).toBe(false);
    expect(ws?.sideWidth).toBe(300);
    expect(sanitizeWorkspace(null)).toBeNull();
    expect(sanitizeWorkspace({ version: 1, workspaces: [] })).toBeNull();
  });

  it('resets to the default layout', () => {
    useWorkspace.getState().close('t-watch');
    useWorkspace.getState().resetLayout();
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });

  it.each(['symbol', 'chart'])('converts a stored %s layout to the two-pane default on rehydrate', async (panel) => {
    localStorage.setItem('bors-workspace-v1', JSON.stringify({
      version: 1,
      state: {
        version: 1,
        activeWorkspaceId: 'ws-tablo',
        activeSymbol: '10',
        pinned: {},
        workspaces: [{
          id: 'ws-tablo', name: 'تابلوخوانی', slots: DEFAULT_SLOTS, chartOpen: true, updatedAt: 1,
          layout: {
            kind: 'split', id: 's-root', dir: 'row', ratio: 0.68,
            first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
            second: { kind: 'tile', id: 't-old', panel, follow: true },
          },
        }],
      },
    }));
    await useWorkspace.persist.rehydrate();
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
    expect(useWorkspace.getState().activeSymbol).toBe('10');
    expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(320);
    expect(useWorkspace.getState().workspaces[0].chartShare).toBe(0.6);
  });

  it('caps the sidebar so both panes keep their minimum width', () => {
    expect(maxSideWidth(1280)).toBe(331);
    expect(maxSideWidth(1366)).toBe(417);
    expect(maxSideWidth(1920)).toBe(SIDE_WIDTH.max);
    expect(maxSideWidth(900)).toBe(SIDE_WIDTH.min);
  });

  it('starts with the default sizes and open groups', () => {
    const ws = useWorkspace.getState().workspaces[0];
    expect([ws.sideWidth, ws.dockHeight, ws.chartShare]).toEqual([320, 200, 0.6]);
    expect(ws.fundamentalsOpen).toBe(true);
    expect(ws.sideCollapsed).toBe(false);
  });

  it('clamps every persisted size', () => {
    useWorkspace.getState().setSideWidth(100);
    expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(SIDE_WIDTH.min);
    useWorkspace.getState().setSideWidth(900);
    expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(SIDE_WIDTH.max);
    useWorkspace.getState().setDockHeight(10);
    expect(useWorkspace.getState().workspaces[0].dockHeight).toBe(160);
    useWorkspace.getState().setChartShare(0.9);
    expect(useWorkspace.getState().workspaces[0].chartShare).toBe(0.75);
    useWorkspace.getState().setFundamentalsOpen(false);
    useWorkspace.getState().setSideCollapsed(true);
    expect(useWorkspace.getState().workspaces[0].fundamentalsOpen).toBe(false);
    expect(useWorkspace.getState().workspaces[0].sideCollapsed).toBe(true);
  });

  it('moves a stored version-2 chart share to the wider default once, and respects a version-3 choice', () => {
    expect(sanitizeWorkspace({
      version: 2,
      workspaces: [{ layout: DEFAULT_LAYOUT, slots: DEFAULT_SLOTS, chartShare: 0.45 }],
    })?.chartShare).toBe(0.6);
    expect(sanitizeWorkspace({
      version: 3,
      workspaces: [{ layout: DEFAULT_LAYOUT, slots: DEFAULT_SLOTS, chartShare: 0.55 }],
    })?.chartShare).toBe(0.55);
  });

  it('fills the new keys for a version-1 payload and rejects an unknown version', () => {
    const ws = sanitizeWorkspace({
      version: 1,
      workspaces: [{ layout: DEFAULT_LAYOUT, slots: DEFAULT_SLOTS }],
    });
    expect(ws?.sideWidth).toBe(320);
    expect(ws?.dockHeight).toBe(200);
    expect(ws?.chartShare).toBe(0.6);
    expect(ws?.fundamentalsOpen).toBe(true);
    expect(ws?.sideCollapsed).toBe(false);
    expect(sanitizeWorkspace({ version: 4, workspaces: [{ layout: DEFAULT_LAYOUT }] })).toBeNull();
  });
});
