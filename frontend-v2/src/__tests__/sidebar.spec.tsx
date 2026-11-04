import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { Sidebar } from '@app/shell/Sidebar';
import { SHORTCUTS } from '@shared/workspace/shortcuts';
import { useUiStore } from '@shared/stores/uiStore';
import { useWorkspace } from '@shared/workspace/store';

beforeEach(() => {
  localStorage.clear();
  useUiStore.setState({ collapsed: false });
  useWorkspace.setState({ activeSymbol: null, pinned: {} });
});

afterEach(cleanup);

function mount(count = 0) {
  return render(<MemoryRouter><Sidebar notificationCount={count} /></MemoryRouter>);
}

describe('Sidebar', () => {
  it('shows the prototype groups and labels', () => {
    mount();
    expect(screen.getByText('فضای تحلیل')).toBeTruthy();
    expect(screen.getByText('کشف فرصت')).toBeTruthy();
    expect(screen.getByText('سرمایه و اجرا')).toBeTruthy();
    expect(screen.getByText('فرصت‌ها')).toBeTruthy();
    expect(screen.getByText('وضعیت بازار')).toBeTruthy();
  });

  it('marks unbuilt destinations as next-stage and built destinations as live', () => {
    mount();
    const watch = screen.getByText('دیده‌بان').closest('[aria-disabled]');
    expect(watch?.getAttribute('title')).toContain('بعدی');
    for (const name of [/^بازار$/, /^تکنیکال$/, /^بنیادی$/, /^وضعیت بازار$/]) {
      expect(screen.getByRole('link', { name })).toBeTruthy();
    }
  });

  it('shows the unread badge', () => {
    mount(7);
    expect(screen.getByTestId('notif-badge').textContent).toBe('۷');
  });

  it('lists every shortcut in the help block', () => {
    mount();
    for (const shortcut of SHORTCUTS) {
      expect(screen.getByTestId('help-block').textContent).toContain(shortcut.keys);
    }
  });

  it('keeps help reachable when collapsed', () => {
    useUiStore.setState({ collapsed: true });
    mount();
    fireEvent.click(screen.getByTestId('help-toggle'));
    expect(screen.getByTestId('help-block')).toBeTruthy();
  });
});
