import { useState } from 'react';
import { NavLink } from 'react-router';
import { useUiStore } from '@shared/stores/uiStore';
import { useAuthStore } from '@shared/stores/authStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { MEDIA_SMALL } from '@shared/lib/breakpoints';
import { ThemeToggle } from './ThemeToggle';
import { UserSettingsModal } from '@widgets/UserSettingsModal';
import { UpdateManagerModal } from '@widgets/UpdateManagerModal';
import {
  ChevronIcon,
  FundamentalIcon,
  MarketIcon,
  MasterIcon,
  PortfolioIcon,
  StatusIcon,
  TechnicalIcon,
  TreeIcon,
} from '@shared/components/Icons';

interface NavItem {
  to: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  end?: boolean;
  /** زیرِ آیتمِ همسایه نشان داده می‌شود (دیده‌بان: تبِّ مستقلِ زیرِ پرتفوی) */
  sub?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

// آزمودنی: رسیدۀ ناوبری از همین فایل خوانده می‌شود تا «منوی مستقل» ثابت شود
export const NAV_SECTIONS: NavSection[] = [
  {
    title: 'فضای تحلیل',
    items: [
      // رأیِ مالک (۱۴۰۵-۰۷-۲۰): «وضعیت بازار» اولین تب است، و
      // «تابلوخوانی / بازار» دیگر «/بازار» ندارد -- چون وضعیتِ بازار از درونِ
      // تابلو به مقصدی مستقل رفته است.
      { to: '/market-status', icon: StatusIcon, label: 'وضعیت بازار', end: true },
      { to: '/market', icon: MarketIcon, label: 'تابلوخوانی', end: false },
      { to: '/technical', icon: TechnicalIcon, label: 'تکنیکال', end: false },
      { to: '/fundamental', icon: FundamentalIcon, label: 'بنیادی', end: false },
      // رأیِ مالک (۱۴۰۵-۰۷-۲۲): «مرکز اعلان» تبِّ اصلی نیست — زنگِ نوارِ بالا
      // همان صفحّه را باز می‌کند، پس مقصد درِ routes.tsx می‌ماند و ازِ ناوبری
      // بیرون می‌آید.
    ],
  },
  {
    title: 'غربالگری FTS',
    items: [
      // رأیِ واژگانِ مالک (۱۴۰۵-۰۷-۱۷): این تب «استراتژی FTS» صدا می‌زند. نامِ
      // گروه همان «غربالگری FTS» می‌ماند (عنوانِ صفحه درِ نوارِ بالا هم همین)،
      // پس «استراتژی FTS» نامِ خودِ جدولِ غربالگری است و «درخت استراتژی» نامِ
      // نقشۀ راه — دو مقصد، دو نام.
      { to: '/master', icon: MasterIcon, label: 'استراتژی FTS', end: false },
      { to: '/strategy-tree', icon: TreeIcon, label: 'درخت استراتژی', end: false },
    ],
  },
  {
    title: 'سرمایه و دارایی',
    items: [
      { to: '/portfolio', icon: PortfolioIcon, label: 'مدیریت پرتفوی', end: false },
      // مأموریت ۱۴۰۵-۰۷-۲۳: سرخطی/اجرایِ سفارش (که تا این دور فقط ازِ درونِ
      // دفترچۀِ نمادِ «دیده‌بان بازار» دیده می‌شد) وِ رباتِ معاملاتی (که فقط درِ
      // انتهایِ پرتفوی بود) یکِ مقصدِ مستقلِ ناوبری می‌گیرند. هرِ دوِ پنل همانِ
      // کامپوننت‌هایِ موجودند — نه کپیِ دوم.
      { to: '/trade', icon: PortfolioIcon, label: 'سرخطی و ربات', end: true },
      // رأیِ مالک (1405-07-20): دیده‌بان از درونِ پرتفوی بیرون آمد و تبِّ مستقل شد،
      // ولی همان‌جا زیرِ گروهِ «سرمایه و دارایی» و با دندانه نشان داده می‌شود که
      // تعلقش به پرتفوی گم نشود.
      { to: '/watch', icon: StatusIcon, label: 'دیده‌بان بازار', end: true, sub: true },
    ],
  },
];

export function Sidebar() {
  // ریسپانسیو: در نمایشگر کوچک (<۱۲۸۰px) به‌طور خودکار جمع می‌شود؛
  // کاربر می‌تواند با دکمهٔ بالای نوار، جمع/باز بودن را دستی تعیین کند.
  const isSmall = useMediaQuery(MEDIA_SMALL);
  const collapsedOverride = useUiStore((s) => s.sidebarCollapsed);
  const setSidebarCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  const collapsed = collapsedOverride ?? isSmall;

  const username = useAuthStore((s) => s.username);
  const logout = useAuthStore((s) => s.logout);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);

  return (
    <aside
      aria-label="نوار کناری"
      data-shell="sidebar"
      data-collapsed={collapsed ? 'true' : undefined}
      className={`glass-panel sticky top-0 flex h-screen shrink-0 flex-col gap-2.5 overflow-y-auto rounded-none border-y-0 border-e border-border-c transition-[width] duration-200 ease-out ${
        collapsed ? 'w-[var(--sidebar-w-collapsed)] items-center p-2' : 'w-[var(--sidebar-w)] px-2.5 py-3'
      }`}
    >
      {/* Brand Header */}
      <div className={`flex items-center gap-2 ${collapsed ? 'flex-col gap-2' : ''}`}>
        <div className="neon-edge-cyan flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] bg-gradient-to-br from-neon-cyan to-blue-600 text-xs font-black text-black">
          ب
        </div>
        <div className={collapsed ? 'hidden' : 'min-w-0'}>
          <span className="block text-xs font-black text-text-primary truncate">ترمینال بورس</span>
          <span className="block text-[9px] tracking-wider text-text-muted truncate">FTS v2.1</span>
        </div>
        <button
          type="button"
          onClick={() => setSidebarCollapsed(!collapsed)}
          aria-label={collapsed ? 'بازکردن نوار کناری' : 'جمع‌کردن نوار کناری'}
          aria-expanded={!collapsed}
          className="ms-auto shrink-0 rounded-lg border border-[var(--hairline)] p-1 text-text-muted transition-colors hover:border-border-accent hover:text-accent-blue"
        >
          <ChevronIcon size={13} className={collapsed ? 'rotate-180' : ''} />
        </button>
      </div>

      {/* Nav Items grouped by Section */}
      <nav className={`flex flex-col gap-2 ${collapsed ? 'w-full' : ''}`}>
        {NAV_SECTIONS.map((sec, secIdx) => (
          <div key={sec.title} className="flex flex-col gap-0.5">
            {!collapsed ? (
              <div className="px-2 pt-1 pb-0.5 text-[10px] font-black uppercase tracking-wider text-text-muted select-none">
                {sec.title}
              </div>
            ) : secIdx > 0 ? (
              <div className="my-1 w-full border-t border-border-c/40" />
            ) : null}

            {sec.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={item.label}
                aria-label={item.label}
                data-testid={item.sub ? 'nav-sub-watch' : undefined}
                className={({ isActive }) =>
                  `group relative flex items-center overflow-hidden rounded-lg border border-transparent text-nav font-bold transition-all duration-200 ${item.sub && !collapsed ? 'ms-3 text-2xs' : ''} ${
                    collapsed ? 'justify-center px-0 py-2.5' : 'justify-start px-2 py-2'
                  } ${
                    isActive
                      ? 'border-[var(--hairline)] bg-accent-blue/12 text-accent-blue shadow-[inset_0_0_12px_rgba(56,189,248,0.12)]'
                      : 'text-text-secondary hover:bg-bg-card/60 hover:text-accent-blue'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`absolute bottom-1 start-0 top-1 w-[2.5px] rounded-full bg-neon-cyan transition-opacity duration-200 ${
                        isActive ? 'opacity-100 shadow-[0_0_8px_var(--neon-cyan)]' : 'opacity-0'
                      }`}
                    />
                    {collapsed ? (
                      <item.icon size={19} />
                    ) : (
                      <span className="flex items-center gap-2">
                        <item.icon size={18} />
                        <span>{item.label}</span>
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer Controls & User Settings */}
      <div className={`mt-auto flex flex-col gap-2 ${collapsed ? 'w-full items-center' : ''}`}>
        {collapsed ? (
          <div className="flex flex-col items-center gap-1.5 py-1">
            <ThemeToggle compact />
            <button
              type="button"
              onClick={() => setUpdateOpen(true)}
              data-testid="app-update-btn"
              className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-text-secondary transition-all hover:border-neon-cyan hover:text-neon-cyan"
              title="به‌روزرسانی ترمینال"
              aria-label="به‌روزرسانی ترمینال"
            >
              🚀
            </button>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              data-testid="user-settings-btn"
              className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue"
              title={`تنظیمات کاربر: ${username}`}
            >
              ⚙
            </button>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-accent-red transition-all hover:border-accent-red/40 hover:bg-accent-red/10"
              title="خروج از حساب"
            >
              ⎋
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/50 p-2 backdrop-blur">
            <div className="flex items-center justify-between gap-1 pb-1.5 border-b border-border-c/50">
              <button
                type="button"
                onClick={() => setSettingsOpen(true)}
                data-testid="user-settings-btn"
                className="flex items-center gap-1.5 truncate text-2xs font-bold text-text-primary hover:text-accent-blue transition-colors"
                title="تنظیمات کاربر"
              >
                <span className="text-accent-blue">⚙</span>
                <span className="truncate max-w-[85px]">{username}</span>
              </button>
              <button
                type="button"
                onClick={logout}
                className="rounded border border-transparent px-1 text-2xs text-accent-red hover:border-accent-red/40 hover:bg-accent-red/10 transition-colors"
                title="خروج از حساب"
              >
                خروج ⎋
              </button>
            </div>
            <div className="flex items-center justify-between gap-1 pt-1.5">
              <ThemeToggle compact />
              <button
                type="button"
                onClick={() => setUpdateOpen(true)}
                data-testid="app-update-btn"
                className="flex items-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1 text-[11px] font-bold text-text-secondary transition-all hover:border-neon-cyan hover:text-neon-cyan"
                title="مدیریت و بررسی به‌روزرسانی سیستم"
              >
                <span>🚀</span>
                <span>به‌روزرسانی</span>
              </button>
            </div>
          </div>
        )}
      </div>

      <UserSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <UpdateManagerModal open={updateOpen} onClose={() => setUpdateOpen(false)} />
    </aside>
  );
}
