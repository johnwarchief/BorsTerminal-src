import { useUiStore } from '@shared/stores/uiStore';

export function ThemeToggle() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-3 py-1.5 text-xs font-bold text-text-primary transition-all duration-200 hover:border-border-accent hover:text-accent-blue"
      aria-label="تغییر تم"
    >
      {theme === 'dark' ? '☀ روشن' : '☾ تاریک'}
    </button>
  );
}
