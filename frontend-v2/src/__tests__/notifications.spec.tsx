import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LEVEL_LABEL, unreadCount } from '@features/notifications/lib/unread';
import { NotificationsPage } from '@features/notifications/ui/NotificationsPage';
import { useNotificationSources, useNotificationsFeed } from '@features/notifications/api/useNotifications';

vi.mock('@features/notifications/api/useNotifications', () => ({
  useNotificationsFeed: vi.fn(),
  useNotificationSources: vi.fn(),
}));

const items = [
  { id: '1', level: 'high', title: 'صورت مالی', symbol: 'الف', publish_date: '1405/08/06', kind: 'statements' },
  { id: '2', level: 'medium', title: 'مجمع', symbol: 'ب', publish_date: '1405/08/06', kind: 'assembly' },
  { id: '3', level: 'low', title: 'یادآوری', symbol: null, publish_date: '1405/08/05', kind: 'other' },
  { id: '4', level: 'unclassified', title: 'ناشناخته', symbol: null, publish_date: null, kind: 'other' },
];

afterEach(cleanup);

describe('notifications', () => {
  it('counts unread high and medium only', () => {
    expect(unreadCount(items as never, new Set())).toBe(2);
    expect(unreadCount(items as never, new Set(['1']))).toBe(1);
  });

  it('uses the backend level vocabulary', () => {
    expect(LEVEL_LABEL.high).toBe('بالا');
    expect(LEVEL_LABEL.unclassified).toBe('بی‌طبقه');
  });

  it('distinguishes an empty feed from an unreachable source', () => {
    vi.mocked(useNotificationsFeed).mockReturnValue({ data: { status: 'ok', items: [] }, isLoading: false, isError: false } as never);
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'ok', rows: 10 }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getByTestId('notif-empty').textContent).toContain('تازه‌ای نیست');

    cleanup();
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'unavailable', rows: 0, message: 'جدول نیست' }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getByTestId('notif-source-warning').textContent).toContain('در دسترس نیست');
  });

  it('filters by level', () => {
    vi.mocked(useNotificationsFeed).mockImplementation(((level?: string) => ({
      data: { status: 'ok', items: level ? items.filter((item) => item.level === level) : items },
      isLoading: false,
      isError: false,
    })) as never);
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'ok', rows: 10 }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getAllByTestId(/^notif-item-/)).toHaveLength(4);
    fireEvent.click(screen.getByTestId('notif-level-high'));
    expect(screen.getAllByTestId(/^notif-item-/)).toHaveLength(1);
  });
});
