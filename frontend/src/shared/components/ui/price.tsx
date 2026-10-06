import { cn } from '@shared/lib/cn';
import { fmtInt, fmtPct } from '@shared/lib/fmt';

export interface PriceProps {
  amount: number;
  /** قیمت پایه/قبلی قبل از تغییر */
  original?: number;
  /** واحد پولی (پیش‌فرض: تومان) */
  unit?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizes = {
  sm: 'text-xs sm:text-sm',
  md: 'text-base sm:text-lg',
  lg: 'text-xl sm:text-2xl',
};

/**
 * نمایشگر قیمت مالی (برگرفته از VibafarsiUI)
 * تفکیک سه‌رقمی با «٬»، ارقام فارسی و واحد پولی جدا.
 */
export function Price({
  amount,
  original,
  unit = 'تومان',
  size = 'md',
  className,
}: PriceProps) {
  const diffPct =
    original && original > 0 ? ((amount - original) / original) * 100 : 0;

  return (
    <div className={cn('inline-flex flex-col', className)}>
      <span className="flex items-baseline gap-1.5">
        <span className={cn('num font-bold tabular-nums text-text-primary', sizes[size])}>
          {fmtInt(amount)}
        </span>
        {unit && <span className="text-2xs text-text-muted">{unit}</span>}
      </span>
      {original && original !== amount && (
        <span className="mt-0.5 flex items-center gap-1.5 text-3xs">
          <span className="num text-text-muted line-through tabular-nums">
            {fmtInt(original)}
          </span>
          <span
            className={cn(
              'num rounded px-1 py-0.2 text-[10px] font-bold tabular-nums',
              diffPct > 0 ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-red/15 text-accent-red',
            )}
          >
            {fmtPct(diffPct)}
          </span>
        </span>
      )}
    </div>
  );
}
