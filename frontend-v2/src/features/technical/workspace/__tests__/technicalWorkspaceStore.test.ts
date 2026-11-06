import { beforeEach, describe, expect, it } from 'vitest';
import { useTechnicalWorkspaceStore } from '../technicalWorkspaceStore';
import { chartShareOf } from '../presets';

describe('technical workspace store', () => {
  beforeEach(() => {
    localStorage.clear();
    useTechnicalWorkspaceStore.getState().reset();
  });

  it('seeds three modes and restores a saved layout', () => {
    const s = useTechnicalWorkspaceStore.getState();
    expect(s.layouts.analysis.length).toBeGreaterThan(0);
    expect(s.layouts.scan.length).toBeGreaterThan(0);
    expect(s.layouts.research.length).toBeGreaterThan(0);
    const before = s.layouts.analysis[0]!.root;
    s.setMode('scan');
    s.setMode('analysis');
    s.saveLayout('My analysis');
    expect(useTechnicalWorkspaceStore.getState().layouts.analysis.some((l) => l.name === 'My analysis')).toBe(true);
    s.loadLayout(useTechnicalWorkspaceStore.getState().layouts.analysis[0]!.id);
    expect(useTechnicalWorkspaceStore.getState().layouts.analysis[0]!.root).toEqual(before);
  });

  it('keeps the chart at the spec minimum share in every preset', () => {
    const s = useTechnicalWorkspaceStore.getState();
    expect(chartShareOf(s.layouts.analysis[0]!.root)).toBeGreaterThanOrEqual(0.6);
    expect(chartShareOf(s.layouts.scan[0]!.root)).toBeGreaterThanOrEqual(0.55);
    expect(chartShareOf(s.layouts.research[0]!.root)).toBeGreaterThanOrEqual(0.5);
  });

  it('docks and closes through the shared layout actions without losing the chart', () => {
    const store = useTechnicalWorkspaceStore.getState();
    const chartTile = Object.entries(store.panelKindsOf(store.root)).find(([, kind]) => kind === 'chart')![0];
    store.split(chartTile, 'col', 'scanner');
    expect(Object.values(useTechnicalWorkspaceStore.getState().panelKindsOf(useTechnicalWorkspaceStore.getState().root)))
      .toContain('scanner');
    const scannerTile = Object.entries(useTechnicalWorkspaceStore.getState().panelKindsOf(useTechnicalWorkspaceStore.getState().root))
      .find(([, kind]) => kind === 'scanner')![0];
    useTechnicalWorkspaceStore.getState().close(scannerTile);
    expect(Object.values(useTechnicalWorkspaceStore.getState().panelKindsOf(useTechnicalWorkspaceStore.getState().root)))
      .not.toContain('scanner');
  });

  it('undoes and redoes a docking change', () => {
    const store = useTechnicalWorkspaceStore.getState();
    const before = store.root;
    const chartTile = Object.entries(store.panelKindsOf(store.root)).find(([, kind]) => kind === 'chart')![0];
    store.split(chartTile, 'col', 'scanner');
    const after = useTechnicalWorkspaceStore.getState().root;
    expect(after).not.toEqual(before);
    useTechnicalWorkspaceStore.getState().undo();
    expect(useTechnicalWorkspaceStore.getState().root).toEqual(before);
    useTechnicalWorkspaceStore.getState().redo();
    expect(useTechnicalWorkspaceStore.getState().root).toEqual(after);
  });
});
