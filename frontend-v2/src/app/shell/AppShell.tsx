import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';
import { useUiStore } from '@shared/stores/uiStore';

const NAV = [
  { path: '/market', label: 'تابلو', icon: 'grid' },
  { path: '/market-status', label: 'وضعیت بازار', icon: 'pulse' },
  { path: '/technical', label: 'تکنیکال', icon: 'chart' },
  { path: '/fundamental', label: 'بنیادی', icon: 'file' },
  { path: '/watch', label: 'دیده‌بان', icon: 'eye' },
  { path: '/portfolio', label: 'پرتفوی', icon: 'pie' },
  { path: '/strategy-tree', label: 'درخت استراتژی', icon: 'tree' },
  { path: '/master', label: 'مستر', icon: 'compass' },
  { path: '/engine-lab', label: 'آزمایشگاه', icon: 'flask' },
  { path: '/notifications', label: 'اعلان‌ها', icon: 'bell' },
  { path: '/sarkhati', label: 'سرخطی', icon: 'bolt' },
] as const;

const PATHS: Record<string, string> = {
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  pulse: 'M3 12h4l2-6 3 12 2-6h5',
  chart: 'M4 19V5M4 19h16M7 15l4-4 3 2 4-6',
  file: 'M14 3H6v18h12V8zM14 3v5h5M8 13h8M8 17h5',
  eye: 'M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6zM12 9.4a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2z',
  pie: 'M12 3a9 9 0 1 0 9 9h-9zM15 3.5A9 9 0 0 1 20.5 9H15z',
  tree: 'M12 3v5M6 21v-4h12v4M12 8v5M6 17v-2h12v2',
  compass: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM15.5 8.5l-2 5-5 2 2-5z',
  flask: 'M9 3h6M10 3v5l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3',
  bell: 'M18 9a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7z',
};

function Icon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[name] ?? PATHS.grid} />
    </svg>
  );
}

export function AppShell() {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const setTheme = useUiStore((s) => s.setTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div className="flex h-full">
      <aside
        className={clsx(
          'flex shrink-0 flex-col border-s border-line bg-panel transition-[width] duration-150',
          collapsed ? 'w-12' : 'w-[208px]',
        )}
      >
        <div className="flex h-11 items-center gap-2 border-b border-line px-3">
          <button
            type="button"
            onClick={toggleSidebar}
            title={collapsed ? 'باز کردنِ نوار' : 'جمع کردنِ نوار'}
            className="rounded p-1 text-text-2 hover:bg-panel-2 hover:text-text"
          >
            <Icon name="grid" />
          </button>
          {!collapsed && <span className="text-[12px] font-bold text-accent">بورس‌ترمینال</span>}
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-1.5">
          {NAV.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              title={item.label}
              className={({ isActive }) =>
                clsx(
                  'flex h-8 items-center gap-2 rounded px-2 text-[11.5px]',
                  isActive
                    ? 'bg-panel-3 text-text'
                    : 'text-text-2 hover:bg-panel-2 hover:text-text',
                )
              }
            >
              <Icon name={item.icon} />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line p-2">
          <button
            type="button"
            onClick={() => setTheme(theme === 'brass' ? 'light' : 'brass')}
            title="تغییرِ تم"
            className="flex h-8 w-full items-center justify-center gap-2 rounded text-[11px] text-text-2 hover:bg-panel-2 hover:text-text"
          >
            <Icon name="compass" />
            {!collapsed && <span>{theme === 'brass' ? 'تمِ روشن' : 'تمِ تیره'}</span>}
          </button>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}
