import { useState } from 'react';
import { useLocation } from 'react-router';
import { ThemeToggle } from './ThemeToggle';
import { PALETTE_OPEN_EVENT } from './CommandPalette';
import { SearchIcon } from '@shared/components/Icons';
import { useAuthStore } from '@shared/stores/authStore';
import { UserSettingsModal } from '@widgets/UserSettingsModal';
import { UpdateManagerModal } from '@widgets/UpdateManagerModal';

const TITLES: Record<string, string> = {
  '/market': 'تابلو بازار',
  '/fundamental': 'تحلیل بنیادی',
  '/technical': 'تحلیل تکنیکال',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'ایجنت ارشد',
};

export function Topbar() {
  const { pathname } = useLocation();
  const username = useAuthStore((s) => s.username);
  const logout = useAuthStore((s) => s.logout);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';

  return (
    <header className="glass-strip sticky top-0 z-40 mb-1 flex items-center justify-between px-3 py-3 sm:px-5">
      <h1 className="text-sm font-black text-text-primary sm:text-base">
        {title}
        <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent-green align-middle" />
      </h1>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
          className="hidden items-center gap-2 rounded-lg border border-border-c bg-bg-card/60 px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-accent hover:text-accent-blue md:flex"
          aria-label="باز کردن پالت فرمان"
        >
          <SearchIcon size={14} className="text-neon-cyan" />
          جستجو
          <kbd className="rounded border border-border-c px-1.5 py-0.5 text-2xs text-text-muted">Ctrl+K</kbd>
        </button>
        <button
          type="button"
          onClick={() => setUpdateOpen(true)}
          data-testid="app-update-btn"
          className="flex items-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1 text-2xs font-bold text-text-secondary transition-all hover:border-neon-cyan hover:text-neon-cyan"
          title="مدیریت و بررسی به‌روزرسانی سیستم"
          aria-label="به‌روزرسانی ترمینال"
        >
          <span className="text-neon-cyan">🚀</span>
          <span className="hidden md:inline">آپدیت</span>
        </button>
        <ThemeToggle />
        <div className="mr-1 flex items-center gap-1.5 border-r border-[var(--hairline)] pr-2">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            data-testid="user-settings-btn"
            className="flex items-center gap-1.5 rounded-lg border border-border-c bg-bg-card/60 px-2.5 py-1 text-2xs font-bold text-text-primary transition-all hover:border-border-accent hover:text-accent-blue"
            title="تنظیمات نام کاربری و رمز عبور"
          >
            <span className="text-accent-blue">⚙</span>
            <span className="hidden sm:inline">کاربر: {username}</span>
            <span className="sm:hidden">{username}</span>
          </button>
          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2.5 py-1 text-2xs font-bold text-accent-red transition-all hover:border-accent-red/40 hover:bg-accent-red/10"
            title="خروج از حساب کاربری"
          >
            خروج ⎋
          </button>
        </div>
      </div>

      <UserSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <UpdateManagerModal open={updateOpen} onClose={() => setUpdateOpen(false)} />
    </header>
  );
}
