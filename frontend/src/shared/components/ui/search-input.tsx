import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { SearchIcon, XIcon, LoaderIcon } from '@shared/components/Icons';

export interface SearchInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'defaultValue' | 'onChange' | 'size' | 'type'> {
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  /** پس از مکث تایپ، فشردن Enter یا پاک کردن ورودی فراخوانی می‌شود */
  onSearch?: (value: string) => void;
  debounce?: number;
  /** نمایش اسپینر در زمان لود نتایج */
  loading?: boolean;
  size?: 'sm' | 'md';
  /** برچسب کلید میانبر در انتها (مثلا Ctrl+K) */
  shortcut?: string;
}

/**
 * ورودی جست‌وجو (برگرفته از VibafarsiUI)
 * ذره‌بین در ابتدای متن (راست در RTL)، دکمه پاک‌کردن با کلید Escape یا کلیک ضربدر، و کلید میانبر.
 */
export function SearchInput({
  value,
  defaultValue = '',
  onChange,
  onSearch,
  debounce = 250,
  loading,
  size = 'md',
  shortcut,
  placeholder = 'جست‌وجو...',
  className,
  disabled,
  onKeyDown,
  ...props
}: SearchInputProps) {
  const [internal, setInternal] = React.useState(defaultValue);
  const v = value ?? internal;
  const ref = React.useRef<HTMLInputElement>(null);
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const set = React.useCallback(
    (next: string, immediate = false) => {
      if (value === undefined) setInternal(next);
      onChange?.(next);
      if (!onSearch) return;
      if (timer.current) clearTimeout(timer.current);
      if (immediate || !next) onSearch(next);
      else timer.current = setTimeout(() => onSearch(next), debounce);
    },
    [value, onChange, onSearch, debounce],
  );

  React.useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const sm = size === 'sm';

  return (
    <div
      className={cn(
        'flex w-full items-center gap-2 rounded-lg border border-border-c/70 bg-bg-card/60 text-xs transition-colors',
        'focus-within:border-accent-blue focus-within:ring-1 focus-within:ring-accent-blue/40',
        sm ? 'h-7.5 px-2.5' : 'h-9 px-3',
        disabled && 'cursor-not-allowed opacity-50',
        className,
      )}
    >
      {loading ? (
        <LoaderIcon size={14} className="text-text-muted" />
      ) : (
        <SearchIcon size={14} className="text-text-muted" />
      )}
      <input
        ref={ref}
        type="search"
        inputMode="search"
        enterKeyHint="search"
        autoComplete="off"
        value={v}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => set(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') set(v, true);
          if (e.key === 'Escape' && v) {
            e.preventDefault();
            set('', true);
          }
          onKeyDown?.(e);
        }}
        className="h-full min-w-0 flex-1 bg-transparent text-text-primary outline-none placeholder:text-text-muted [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-cancel-button]:hidden [&::-webkit-search-decoration]:hidden"
        {...props}
      />
      {v ? (
        <button
          type="button"
          aria-label="پاک کردن"
          tabIndex={-1}
          disabled={disabled}
          onClick={() => {
            set('', true);
            ref.current?.focus();
          }}
          className="flex h-4.5 w-4.5 shrink-0 cursor-pointer items-center justify-center rounded-full text-text-muted transition-colors hover:bg-bg-secondary hover:text-text-primary"
        >
          <XIcon size={12} />
        </button>
      ) : shortcut ? (
        <kbd
          dir="ltr"
          className="hidden shrink-0 rounded border border-border-c/70 bg-bg-secondary px-1.5 font-mono text-3xs text-text-muted sm:inline-block"
        >
          {shortcut}
        </kbd>
      ) : null}
    </div>
  );
}
