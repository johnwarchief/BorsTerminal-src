import { useLocation } from 'react-router';
import { ThemeToggle } from './ThemeToggle';
import { PALETTE_OPEN_EVENT } from './CommandPalette';

const TITLES: Record<string, string> = {
  '/market': 'تابلو بازار',
  '/fundamental': 'تحلیل بنیادی',
  '/technical': 'تحلیل تکنیکال',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'ایجنت ارشد',
};

export function Topbar() {
  const { pathname } = useLocation();
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';

  return (
    <header className="glass-strip sticky top-0 z-40 mb-1 flex items-center justify-between px-5 py-3">
      <h1 className="text-base font-black text-text-primary">
        {title}
        <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent-green align-middle" />
      </h1>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
          className="num hidden items-center gap-2 rounded-lg border border-border-c bg-bg-card/60 px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-accent hover:text-accent-blue md:flex"
          aria-label="باز کردن پالت فرمان"
        >
          <span className="text-neon-cyan">⌘</span> جستجو
          <kbd className="rounded border border-border-c px-1.5 py-0.5 text-[10px] text-text-muted">Ctrl+K</kbd>
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}
