import clsx from 'clsx';
import { NavLink } from 'react-router-dom';
import { toFaDigits } from '@shared/lib/fa';
import { useUiStore, type Theme } from '@shared/stores/uiStore';
import { Icon } from './icons';
import { HelpBlock } from './HelpBlock';
import { SidebarSymbol } from './SidebarSymbol';

interface Item { path: string; label: string; icon: string; live?: boolean }
interface Group { title: string; items: Item[] }

const GROUPS: Group[] = [
  { title: 'فضای تحلیل', items: [
    { path: '/market', label: 'بازار', icon: 'grid', live: true },
    { path: '/technical', label: 'تکنیکال', icon: 'chart' },
    { path: '/fundamental', label: 'بنیادی', icon: 'file' },
    { path: '/market-status', label: 'وضعیت بازار', icon: 'pulse' },
  ] },
  { title: 'کشف فرصت', items: [
    { path: '/opportunities', label: 'فرصت‌ها', icon: 'compass' },
    { path: '/fts-screen', label: 'غربالگری FTS', icon: 'funnel' },
  ] },
  { title: 'سرمایه و اجرا', items: [
    { path: '/watch', label: 'دیده‌بان', icon: 'eye' },
    { path: '/portfolio', label: 'پرتفوی', icon: 'pie' },
    { path: '/sarkhati', label: 'سرخطی', icon: 'bolt' },
  ] },
];

const THEMES: { key: Theme; label: string; dot: string }[] = [
  { key: 'brass', label: 'برنجی', dot: '#c9a45c' },
  { key: 'warm', label: 'روشنِ گرم', dot: '#efece4' },
  { key: 'terminal', label: 'ترمینال', dot: '#46e08a' },
  { key: 'cool', label: 'روشنِ سرد', dot: '#2f6f9f' },
];

export function Sidebar({ notificationCount = 0 }: { notificationCount?: number }) {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const setTheme = useUiStore((s) => s.setTheme);

  return (
    <aside className="flex w-[var(--rail-w)] shrink-0 flex-col border-s border-line bg-panel">
      <div className="flex h-[52px] items-center gap-2.5 border-b border-line px-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-[var(--radius-sm)] text-accent-ink"
          style={{ background: 'var(--accent)' }} aria-hidden>
          <Icon name="bolt" size={15} />
        </span>
        {!collapsed ? (
          <div className="min-w-0 leading-tight">
            <div className="t-125 truncate font-extrabold">بورس‌ترمینال</div>
            <div className="t-9 tracking-[0.16em] text-text-3" dir="ltr">FTS DECISION DESK</div>
          </div>
        ) : null}
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-1.5" aria-label="ناوبری اصلی">
        {GROUPS.map((group) => (
          <div key={group.title} className="mb-1">
            {!collapsed ? <div className="px-2 pb-0.5 t-9 font-bold text-text-3">{group.title}</div> : null}
            {group.items.map((item) => (
              item.live ? (
                <NavLink key={item.path} to={item.path} title={item.label}
                  className={({ isActive }) => clsx(
                    'flex h-[30px] items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap',
                    isActive ? 'bg-panel-3 text-text' : 'text-text-2 hover:bg-panel-2 hover:text-text',
                  )}>
                  <Icon name={item.icon} />
                  {!collapsed ? <span>{item.label}</span> : null}
                </NavLink>
              ) : (
                <span key={item.path} title={`${item.label} — بعدی`} aria-disabled
                  className="flex h-[30px] cursor-not-allowed items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap text-text-3/70">
                  <Icon name={item.icon} />
                  {!collapsed ? <span>{item.label}</span> : null}
                </span>
              )
            ))}
          </div>
        ))}

        <NavLink to="/notifications" title="اعلان‌ها"
          className={({ isActive }) => clsx(
            'mt-auto flex h-[30px] items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap',
            isActive ? 'bg-panel-3 text-text' : 'text-text-2 hover:bg-panel-2 hover:text-text',
          )}>
          <Icon name="bell" />
          {!collapsed ? <span>اعلان‌ها</span> : null}
          {notificationCount > 0 ? (
            <span data-testid="notif-badge"
              className="num ms-auto rounded-full bg-accent px-1.5 t-9 font-bold text-accent-ink">
              {toFaDigits(notificationCount)}
            </span>
          ) : null}
        </NavLink>
      </nav>

      <SidebarSymbol collapsed={collapsed} />

      <HelpBlock collapsed={collapsed} />

      <div className="border-t border-line p-2">
        {!collapsed ? <div className="mb-1.5 t-9 font-bold text-text-3">پوسته</div> : null}
        <div className={clsx('grid gap-1', collapsed ? 'grid-cols-1' : 'grid-cols-2')}>
          {THEMES.map((item) => (
            <button key={item.key} type="button" data-testid={`theme-${item.key}`}
              onClick={() => setTheme(item.key)} aria-pressed={theme === item.key} title={item.label}
              className={clsx('flex h-6 items-center gap-1.5 rounded-[var(--radius-sm)] px-1.5 t-95',
                theme === item.key ? 'bg-panel-3 text-text' : 'text-text-3 hover:bg-panel-2 hover:text-text')}>
              <span className="h-2.5 w-2.5 shrink-0 rounded-full border border-white/20"
                style={{ background: item.dot }} aria-hidden />
              {!collapsed ? <span className="truncate">{item.label}</span> : null}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-line p-1.5">
        <button type="button" onClick={toggleSidebar}
          title={collapsed ? 'باز کردنِ نوار' : 'جمع کردنِ نوار'}
          className="flex h-7 w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] t-10 text-text-3 hover:bg-panel-2 hover:text-text">
          <Icon name="menu" size={15} />
          {!collapsed ? <span>جمع کردن</span> : null}
        </button>
      </div>
    </aside>
  );
}
