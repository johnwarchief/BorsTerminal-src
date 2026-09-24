import { useUiStore } from '@shared/stores/uiStore';
import { MoonIcon, SunIcon } from '@shared/components/Icons';

export function ThemeToggle({ compact = false }: { compact?: boolean } = {}) {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const toLight = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`inline-flex items-center justify-center rounded-lg border border-[var(--hairline)] bg-bg-card/60 text-text-primary transition-all duration-200 hover:border-border-accent hover:text-accent-blue ${
        compact ? 'p-1.5 text-2xs' : 'gap-1.5 px-3 py-1.5 text-xs font-bold'
      }`}
      aria-label="تغییر تم"
      title={toLight ? 'تغییر به تم روشن' : 'تغییر به تم تاریک'}
    >
      {toLight ? <SunIcon size={14} /> : <MoonIcon size={14} />}
      {!compact && <span>{toLight ? 'روشن' : 'تاریک'}</span>}
    </button>
  );
}
