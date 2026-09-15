import { NavLink } from 'react-router';
import { useUiStore } from '@shared/stores/uiStore';
import {
  ChevronIcon,
  FundamentalIcon,
  MarketIcon,
  MasterIcon,
  PortfolioIcon,
  TechnicalIcon,
} from '@shared/components/Icons';

const NAV_ITEMS = [
  { to: '/market', icon: MarketIcon, label: 'تابلو بازار', end: false },
  { to: '/fundamental', icon: FundamentalIcon, label: 'تحلیل بنیادی', end: false },
  { to: '/technical', icon: TechnicalIcon, label: 'تحلیل تکنیکال', end: false },
  { to: '/portfolio', icon: PortfolioIcon, label: 'مدیریت پرتفوی', end: false },
  { to: '/master', icon: MasterIcon, label: 'ایجنت ارشد', end: false },
];

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebarCollapsed = useUiStore((s) => s.toggleSidebarCollapsed);

  return (
    <aside
      aria-label="نوار کناری"
      data-collapsed={collapsed ? 'true' : undefined}
      className={`glass-panel sticky top-0 flex h-screen shrink-0 flex-col gap-6 overflow-y-auto rounded-none border-y-0 border-r-0 transition-[width] duration-200 ease-out ${
        collapsed ? 'w-[var(--sidebar-w-collapsed)] items-center p-2' : 'w-[var(--sidebar-w)] p-5'
      }`}
    >
      <div className={`flex items-center gap-3 ${collapsed ? 'flex-col gap-2' : ''}`}>
        <div className="neon-edge-cyan flex h-10 w-10 items-center justify-center rounded-[10px] bg-gradient-to-br from-neon-cyan to-blue-600 text-lg font-black text-black">
          ب
        </div>
        <div className={collapsed ? 'hidden' : ''}>
          <span className="block text-sm font-bold text-text-primary">ترمینال بورس</span>
          <span className="block text-2xs tracking-wide text-text-muted">CYBER TERMINAL v1</span>
        </div>
        <button
          type="button"
          onClick={toggleSidebarCollapsed}
          aria-label={collapsed ? 'بازکردن نوار کناری' : 'جمعکردن نوار کناری'}
          aria-expanded={!collapsed}
          className="ml-auto shrink-0 rounded-lg border border-[var(--hairline)] p-1 text-text-muted transition-colors hover:border-border-accent hover:text-accent-blue"
        >
          <ChevronIcon size={16} className={collapsed ? 'rotate-180' : ''} />
        </button>
      </div>
      <nav className={`flex flex-col gap-1.5 ${collapsed ? 'w-full' : ''}`}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            title={item.label}
            aria-label={item.label}
            className={({ isActive }) =>
              `group relative flex items-center overflow-hidden rounded-lg border border-transparent text-sm font-semibold transition-all duration-200 ${collapsed ? 'justify-center px-0 py-3' : 'justify-end px-3 py-2.5'} ${
                isActive
                  ? 'border-[var(--hairline)] bg-accent-blue/12 text-accent-blue shadow-[inset_0_0_12px_rgba(56,189,248,0.12)]'
                  : 'text-text-secondary hover:bg-bg-card/60 hover:text-accent-blue'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`absolute bottom-1.5 right-0 top-1.5 w-[2px] rounded-full bg-neon-cyan transition-opacity duration-200 ${
                    isActive ? 'opacity-100 shadow-[0_0_8px_var(--neon-cyan)]' : 'opacity-0'
                  }`}
                />
                {collapsed ? <item.icon size={18} /> : item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className={`mt-auto rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3 text-2xs leading-5 text-text-muted ${collapsed ? 'hidden' : ''}`}>
        میانبر سریع: <kbd className="num rounded border border-border-c px-1">Ctrl</kbd> +
        <kbd className="num mr-1 rounded border border-border-c px-1">K</kbd>
        <span className="block">جستجوی نماد و پرش بین نماها</span>
      </div>
    </aside>
  );
}
