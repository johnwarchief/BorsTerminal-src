import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';
import { useUiStore, type Theme } from '@shared/stores/uiStore';
import { Topbar } from './Topbar';

const NAV = [
  { path: '/market', label: 'بازار', icon: 'grid', live: true },
  { path: '/market-status', label: 'وضعیت بازار', icon: 'pulse', live: false },
  { path: '/technical', label: 'تکنیکال', icon: 'chart', live: false },
  { path: '/fundamental', label: 'بنیادی', icon: 'file', live: false },
  { path: '/watch', label: 'دیده‌بان', icon: 'eye', live: false },
  { path: '/portfolio', label: 'پرتفوی', icon: 'pie', live: false },
  { path: '/strategy-tree', label: 'درخت استراتژی', icon: 'tree', live: false },
  { path: '/master', label: 'مستر', icon: 'compass', live: false },
  { path: '/engine-lab', label: 'آزمایشگاه', icon: 'flask', live: false },
  { path: '/notifications', label: 'اعلان‌ها', icon: 'bell', live: false },
  { path: '/sarkhati', label: 'سرخطی', icon: 'bolt', live: false },
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
  menu: 'M4 7h16M4 12h16M4 17h16',
};

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={PATHS[name] ?? PATHS.grid} />
    </svg>
  );
}

const THEMES: { key: Theme; label: string; dot: string }[] = [
  { key: 'brass', label: 'برنجی', dot: '#c9a45c' },
  { key: 'warm', label: 'روشنِ گرم', dot: '#efece4' },
  { key: 'terminal', label: 'ترمینال', dot: '#46e08a' },
  { key: 'cool', label: 'روشنِ سرد', dot: '#2f6f9f' },
];

export function AppShell() {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const setTheme = useUiStore((s) => s.setTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div data-rail={collapsed ? 'collapsed' : 'open'} className="flex h-full">
      <aside className="flex w-[var(--rail-w)] shrink-0 flex-col border-s border-line bg-panel">
        <div className="flex h-[52px] items-center gap-2.5 border-b border-line px-3">
          <span
            className="grid h-7 w-7 shrink-0 place-items-center rounded-[var(--radius-sm)] text-accent-ink"
            style={{ background: 'var(--accent)' }}
            aria-hidden
          >
            <Icon name="bolt" size={15} />
          </span>
          {!collapsed && (
            <div className="min-w-0 leading-tight">
              <div className="t-125 truncate font-extrabold">بورس‌ترمینال</div>
              <div className="t-9 tracking-[0.16em] text-text-3" dir="ltr">
                FTS DECISION DESK
              </div>
            </div>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-1.5" aria-label="ناوبری اصلی">
          {NAV.map((item) =>
            item.live ? (
              <NavLink
                key={item.path}
                to={item.path}
                title={item.label}
                className={({ isActive }) =>
                  clsx(
                    'flex h-[30px] items-center gap-2 rounded-[var(--radius-sm)] px-2',
                    't-11 whitespace-nowrap',
                    isActive
                      ? 'bg-panel-3 text-text'
                      : 'text-text-2 hover:bg-panel-2 hover:text-text',
                  )
                }
              >
                <Icon name={item.icon} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ) : (
              <span
                key={item.path}
                title={`${item.label} — در مرحلهٔ بعد`}
                aria-disabled
                className={clsx(
                  'flex h-[30px] cursor-not-allowed items-center gap-2 rounded-[var(--radius-sm)] px-2',
                  't-11 whitespace-nowrap text-text-3/70',
                )}
              >
                <Icon name={item.icon} />
                {!collapsed && <span>{item.label}</span>}
              </span>
            ),
          )}
        </nav>

        <div className="border-t border-line p-2">
          {!collapsed && <div className="t-9 mb-1.5 font-bold text-text-3">پوسته</div>}
          <div className={clsx('grid gap-1', collapsed ? 'grid-cols-1' : 'grid-cols-2')}>
            {THEMES.map((t) => (
              <button
                key={t.key}
                type="button"
                data-testid={`theme-${t.key}`}
                onClick={() => setTheme(t.key)}
                aria-pressed={theme === t.key}
                title={t.label}
                className={clsx(
                  'flex h-6 items-center gap-1.5 rounded-[var(--radius-sm)] px-1.5 t-95',
                  theme === t.key
                    ? 'bg-panel-3 text-text'
                    : 'text-text-3 hover:bg-panel-2 hover:text-text',
                )}
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full border border-white/20"
                  style={{ background: t.dot }}
                  aria-hidden
                />
                {!collapsed && <span className="truncate">{t.label}</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-line p-1.5">
          <button
            type="button"
            onClick={toggleSidebar}
            title={collapsed ? 'باز کردنِ نوار' : 'جمع کردنِ نوار'}
            className="flex h-7 w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] t-10 text-text-3 hover:bg-panel-2 hover:text-text"
          >
            <Icon name="menu" size={15} />
            {!collapsed && <span>جمع کردن</span>}
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
