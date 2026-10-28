import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { SHORTCUTS } from '@shared/workspace/shortcuts';
import { useWorkspace } from '@shared/workspace/store';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';

afterEach(cleanup);

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

function Harness() {
  useTileKeyboard(DEFAULT_LAYOUT);
  return (
    <div>
      <div data-tile-id="t-board"><div data-tile-header tabIndex={0} data-testid="h-board" /></div>
      <div data-tile-id="t-symbol"><div data-tile-header tabIndex={0} data-testid="h-symbol" /></div>
    </div>
  );
}

describe('tile keyboard', () => {
  it('lists the approved shortcuts in one registry', () => {
    expect(SHORTCUTS.map((s) => s.keys)).toEqual(['Alt+۱…۴', '←→↑↓', 'Ctrl+K', 'Ctrl+Z', 'Esc']);
  });

  it('focuses panels by their reading order with Alt+Digit', () => {
    render(<Harness />);
    fireEvent.keyDown(window, { key: '1', code: 'Digit1', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-board');
    fireEvent.keyDown(window, { key: '2', code: 'Digit2', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-symbol');
  });

  it('undoes the last layout change with Ctrl+Z', () => {
    render(<Harness />);
    useWorkspace.getState().split('t-symbol', 'col', 'chart');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).toContain('"chart"');
    fireEvent.keyDown(window, { key: 'z', code: 'KeyZ', ctrlKey: true });
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });
});
