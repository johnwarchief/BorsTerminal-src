import { useLocation } from 'react-router';
import { PALETTE_OPEN_EVENT } from './CommandPalette';
import { SearchIcon } from '@shared/components/Icons';

const TITLES: Record<string, string> = {
  '/market': 'تابلوخوانی / بازار',
  '/technical': 'تحلیل تکنیکال',
  '/fundamental': 'تحلیل بنیادی',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'استراتژی FTS',
  '/strategy-tree': 'درخت استراتژی FTS',
};

export function Topbar() {
  const { pathname } = useLocation();
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';

  return (
    <header className="glass-strip sticky top-0 z-40 mb-1 flex h-9 items-center justify-between px-3 sm:px-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xs font-black text-text-primary sm:text-sm">
          {title}
        </h1>
        <span
          className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent-green"
          title="سیستم آنلاین و متصل"
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
          className="flex items-center gap-2 rounded-lg border border-border-c bg-bg-card/70 px-2.5 py-1 text-2xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue hover:bg-bg-card shadow-2xs"
          aria-label="باز کردن پالت فرمان"
        >
          <SearchIcon size={12} className="text-neon-cyan" />
          <span className="hidden sm:inline">جستجوی سریع نماد...</span>
          <span className="sm:hidden">جستجو</span>
          <kbd className="rounded border border-border-c/80 bg-bg-secondary px-1 py-0.2 text-[10px] text-text-muted">
            Ctrl+K
          </kbd>
        </button>
      </div>
    </header>
  );
}
