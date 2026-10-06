import * as React from 'react';
import { cn } from '@shared/lib/cn';

export type SegmentedOption = {
  value: string;
  label: React.ReactNode;
  disabled?: boolean;
  'aria-label'?: string;
};

export interface SegmentedControlProps {
  options: SegmentedOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  size?: 'sm' | 'md';
  fullWidth?: boolean;
  className?: string;
  'aria-label'?: string;
}

/**
 * کنترل بخشی / چندگزینه‌ای (برگرفته از VibafarsiUI)
 * یک نشانگر لغزنده زیر گزینه فعال حرکت می‌کند.
 * موقعیت نشانگر مستقیماً از DOM اندازه گرفته می‌شود، بنابراین در RTL و LTR کاملاً دقیق می‌نشیند.
 */
export function SegmentedControl({
  options,
  value,
  defaultValue,
  onChange,
  size = 'md',
  fullWidth,
  className,
  'aria-label': ariaLabel,
}: SegmentedControlProps) {
  const [internal, setInternal] = React.useState(defaultValue ?? options[0]?.value ?? '');
  const selected = value ?? internal;
  const listRef = React.useRef<HTMLDivElement>(null);
  const [pill, setPill] = React.useState<{ x: number; w: number } | null>(null);

  const select = React.useCallback(
    (v: string) => {
      if (value === undefined) setInternal(v);
      onChange?.(v);
    },
    [value, onChange],
  );

  const measure = React.useCallback(() => {
    const root = listRef.current;
    if (!root) return;
    const el = root.querySelector<HTMLElement>(`[data-value="${CSS.escape(selected)}"]`);
    if (!el) return setPill(null);
    setPill({ x: el.offsetLeft, w: el.offsetWidth });
  }, [selected]);

  React.useLayoutEffect(measure, [measure, options.length, size, fullWidth]);

  React.useEffect(() => {
    const root = listRef.current;
    if (!root || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, [measure]);

  return (
    <div
      ref={listRef}
      role="radiogroup"
      aria-label={ariaLabel}
      onKeyDown={(e) => {
        const dir =
          e.key === 'ArrowLeft' || e.key === 'ArrowDown'
            ? 1
            : e.key === 'ArrowRight' || e.key === 'ArrowUp'
              ? -1
              : 0;
        if (!dir) return;
        e.preventDefault();
        const enabled = options.filter((o) => !o.disabled);
        const i = enabled.findIndex((o) => o.value === selected);
        const next = enabled[(i + dir + enabled.length) % enabled.length];
        if (!next) return;
        select(next.value);
        listRef.current?.querySelector<HTMLElement>(`[data-value="${CSS.escape(next.value)}"]`)?.focus();
      }}
      className={cn(
        'relative isolate auto-cols-fr grid-flow-col rounded-lg border border-border-c/60 bg-bg-card/70 p-0.5',
        fullWidth ? 'grid w-full' : 'inline-grid',
        className,
      )}
    >
      {pill && (
        <span
          aria-hidden="true"
          className="absolute inset-y-0.5 -z-10 rounded-md bg-accent-blue/15 border border-accent-blue/30 shadow-2xs transition-[transform,width] duration-200 ease-out"
          style={{ width: pill.w, left: 0, transform: `translateX(${pill.x}px)` }}
        />
      )}
      {options.map((o) => {
        const on = o.value === selected;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            data-value={o.value}
            aria-checked={on}
            aria-label={o['aria-label']}
            disabled={o.disabled}
            tabIndex={on ? 0 : -1}
            onClick={() => select(o.value)}
            className={cn(
              'relative cursor-pointer rounded-md font-bold whitespace-nowrap transition-colors duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/60',
              'disabled:cursor-not-allowed disabled:opacity-40 select-none',
              size === 'sm' ? 'h-6.5 px-2 text-2xs' : 'h-7.5 px-3 text-xs',
              on ? 'text-accent-blue font-black' : 'text-text-muted hover:text-text-primary',
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
