import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { fmtInt } from '@shared/lib/fmt';

export interface CounterProps {
  to: number;
  from?: number;
  duration?: number;
  /** قالب‌بندی عدد؛ پیش‌فرض: جداکننده هزارگان و ارقام فارسی */
  format?: (n: number) => string;
  /** واحد خارج از کادر متحرک قرار می‌گیرد تا هرگز تکان نخورد */
  unit?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * شمارنده انیمیشنی (برگرفته از VibafarsiUI)
 * هنگام ورود به دید کاربر (IntersectionObserver) با شتاب ملایم از from به to شمارش می‌کند.
 * مقدار نهایی برای رزرو عرض رندر می‌شود تا پرش چیدمان (Layout Shift) رخ ندهد.
 */
export function Counter({
  to,
  from = 0,
  duration = 1200,
  format = fmtInt,
  unit,
  className,
  style,
}: CounterProps) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const [v, setV] = React.useState(from);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;

    const reducedMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion || duration <= 0) {
      setV(to);
      return;
    }

    const run = () => {
      const start = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setV(Math.round(from + (to - from) * eased));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };

    if (typeof IntersectionObserver === 'undefined') {
      run();
      return;
    }

    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        run();
        io.disconnect();
      }
    });

    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [to, from, duration]);

  const maxVal = Math.max(Math.abs(to), Math.abs(from));
  const spacerText = format(maxVal);

  return (
    <span
      ref={ref}
      role="text"
      aria-label={`${format(to)} ${typeof unit === 'string' ? unit : ''}`.trim()}
      className={cn('num inline-flex items-baseline tabular-nums', className)}
      style={style}
    >
      <span aria-hidden="true" className="relative inline-block">
        <span className="invisible select-none pointer-events-none">{spacerText}</span>
        <span className="absolute inset-0 text-start">{format(v)}</span>
      </span>
      {unit && (
        <span aria-hidden="true" className="ms-1 text-[0.8em] font-normal text-text-muted select-none">
          {unit}
        </span>
      )}
    </span>
  );
}
