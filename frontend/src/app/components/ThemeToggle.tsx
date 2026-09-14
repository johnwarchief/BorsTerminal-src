import { useUiStore } from '@shared/stores/uiStore';
import { MoonIcon, SunIcon } from '@shared/components/Icons';

export function ThemeToggle() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const toLight = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-3 py-1.5 text-xs font-bold text-text-primary transition-all duration-200 hover:border-border-accent hover:text-accent-blue"
      aria-label="تغییر تم"
    >
      {toLight ? <SunIcon size={14} /> : <MoonIcon size={14} />}
      <span>{toLight ? 'روشن' : 'تاریک'}</span>
    </button>
  );
}
