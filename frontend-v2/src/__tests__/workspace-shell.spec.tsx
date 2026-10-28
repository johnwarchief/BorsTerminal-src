import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_LAYOUT, type LayoutNode } from '@shared/workspace/layout';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';

const boardOnly: LayoutNode = { kind: 'tile', id: 't-board', panel: 'board', follow: false };

afterEach(cleanup);

function mount(overrides: Partial<Parameters<typeof WorkspaceShell>[0]> = {}) {
  return render(
    <WorkspaceShell
      layout={DEFAULT_LAYOUT}
      renderPanel={(panel) => <div data-testid={`body-${panel}`}>{panel}</div>}
      onClose={() => {}}
      onSplit={() => {}}
      onSwap={() => {}}
      onRatio={() => {}}
      {...overrides}
    />,
  );
}

describe('WorkspaceShell', () => {
  it('renders the board and the watch tile', () => {
    mount();
    expect(screen.getByTestId('body-board')).toBeTruthy();
    expect(screen.getByTestId('body-watch')).toBeTruthy();
    expect(screen.getByText('تابلو')).toBeTruthy();
    expect(screen.getByText('دیده‌بان‌ها')).toBeTruthy();
  });

  it('keeps the board unclosable and closes the watch tile', () => {
    const onClose = vi.fn();
    mount({ onClose });
    expect(screen.queryByTestId('tile-close-t-board')).toBeNull();
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(onClose).toHaveBeenCalledWith('t-watch');
  });

  it('offers the watch split only while the watch tile is absent', () => {
    const onSplit = vi.fn();
    const view = mount({ layout: boardOnly, onSplit });
    expect(screen.queryByTestId('tile-menu-t-board')).toBeTruthy();
    fireEvent.click(screen.getByTestId('tile-menu-t-board'));
    fireEvent.click(screen.getByTestId('tile-add-watch'));
    expect(onSplit).toHaveBeenCalledWith('t-board', 'col', 'watch');
    view.unmount();
    mount();
    expect(screen.queryByTestId('tile-menu-t-board')).toBeNull();
  });

  it('marks the focused tile and exposes the arrow hint', () => {
    mount();
    const header = screen.getByTestId('tile-header-t-watch');
    fireEvent.focus(header);
    expect(screen.getByTestId('tile-t-watch').getAttribute('data-tile-focused')).toBe('true');
    expect(screen.getByTestId('tile-hint-t-watch').textContent).toContain('جابه‌جا');
  });

  it('renders one separator for the board/watch split', () => {
    mount();
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });
});
