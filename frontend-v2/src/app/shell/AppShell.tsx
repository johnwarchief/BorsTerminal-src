import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useUiStore } from '@shared/stores/uiStore';
import { useNotificationsFeed } from '@features/notifications/api/useNotifications';
import { readState, unreadCount } from '@features/notifications/lib/unread';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell() {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);
  const feed = useNotificationsFeed();
  const [read, setRead] = useState<Set<string>>(() => readState());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const sync = () => setRead(readState());
    window.addEventListener('bors:notif-read', sync);
    return () => window.removeEventListener('bors:notif-read', sync);
  }, []);

  const badge = unreadCount(feed.data?.items ?? [], read);

  return (
    <div data-rail={collapsed ? 'collapsed' : 'open'} className="flex h-full">
      <Sidebar notificationCount={badge} />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
