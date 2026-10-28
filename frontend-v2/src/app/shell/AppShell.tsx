import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useUiStore } from '@shared/stores/uiStore';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell() {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div data-rail={collapsed ? 'collapsed' : 'open'} className="flex h-full">
      <Sidebar notificationCount={0} />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
