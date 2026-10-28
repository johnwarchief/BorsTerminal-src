import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';

afterEach(cleanup);

function mount(overrides: Partial<Parameters<typeof WorkspaceShell>[0]> = {}) {
  return render(
    <WorkspaceShell
      layout={DEFAULT_LAYOUT}
      renderPanel={(panel) => <div data-testid={`body-${panel}`}>{panel}</div>}
      onClose={() => {}}
      onSplit={() => {}}
      onSwap={() => {}}
      onToggleFollow={() => {}}
      onRatio={() => {}}
      {...overrides}
    />,
  );
}

describe('WorkspaceShell', () => {
  it('renders every tile with its label', () => {
    mount();
    expect(screen.getByTestId('body-board')).toBeTruthy();
    expect(screen.getByTestId('body-symbol')).toBeTruthy();
    expect(screen.getByTestId('body-watch')).toBeTruthy();
    expect(screen.getByText('تابلو')).toBeTruthy();
    expect(screen.getByText('دیده‌بان‌ها')).toBeTruthy();
  });

  it('does not offer close on the board tile', () => {
    mount();
    expect(screen.queryByTestId('tile-close-t-board')).toBeNull();
    expect(screen.getByTestId('tile-close-t-watch')).toBeTruthy();
  });

  it('calls onClose and onSplit from the tile menu', () => {
    const onClose = vi.fn();
    const onSplit = vi.fn();
    mount({ onClose, onSplit });
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    fireEvent.click(screen.getByTestId('tile-menu-t-symbol'));
    fireEvent.click(screen.getByTestId('tile-split-t-symbol-col-chart'));
    expect(onClose).toHaveBeenCalledWith('t-watch');
    expect(onSplit).toHaveBeenCalledWith('t-symbol', 'col', 'chart');
  });

  it('marks the focused tile and exposes the arrow hint', () => {
    mount();
    const header = screen.getByTestId('tile-header-t-symbol');
    fireEvent.focus(header);
    expect(screen.getByTestId('tile-t-symbol').getAttribute('data-tile-focused')).toBe('true');
    expect(screen.getByTestId('tile-hint-t-symbol').textContent).toContain('جابه‌جا');
  });

  it('renders a separator per split', () => {
    mount();
    expect(screen.getAllByRole('separator')).toHaveLength(2);
  });
});
