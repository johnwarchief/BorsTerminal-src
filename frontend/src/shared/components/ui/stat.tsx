import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';
import { ArrowUpLeftIcon, ArrowDownLeftIcon } from '@shared/components/Icons';

export interface StatProps {
  label: React.ReactNode;
  value: React.ReactNode;
  unit?: React.ReactNode;
  /** تغییر درصدی نسبت به دوره قبل یا روز قبل */
  delta?: number;
  deltaLabel?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * کارت آماری مالی (برگرفته از VibafarsiUI)
 * با نمایش مقدار کلیدی و فلش‌های رو به بالا-چپ (جهت پیشروی در RTL) و رو به پایین.
 */
export function Stat({
  label,
  value,
  unit,
  delta,
  deltaLabel = 'تغییر روز',
  size = 'md',
  className,
}: StatProps) {
  const isUp = (delta ?? 0) > 0;
  const isDown = (delta ?? 0) < 0;

  return (
    <div
      className={cn(
        'min-w-0 overflow-hidden rounded-xl border border-border-c/70 bg-bg-card/60 backdrop-blur-xs transition-colors',
        size === 'sm' ? 'p-2.5' : size === 'lg' ? 'p-4 sm:p-5' : 'p-3.5',
        className,
      )}
    >
      <p className="text-2xs font-medium text-text-muted select-none">{label}</p>
      <div className="mt-1 flex items-end justify-between gap-2">
        <p
          className={cn(
            'min-w-0 font-bold leading-tight break-words text-text-primary',
            size === 'sm' ? 'text-sm' : size === 'lg' ? 'text-xl sm:text-2xl' : 'text-base sm:text-lg',
          )}
        >
          <span className="num tabular-nums">{typeof value === 'number' ? toFaDigits(value) : value}</span>
          {unit && (
            <span className="ms-1 inline-block text-2xs font-normal text-text-muted">
              {unit}
            </span>
          )}
        </p>

        {delta !== undefined && (
          <span
            className={cn(
              'inline-flex shrink-0 items-center gap-0.5 text-2xs font-bold tabular-nums',
              isUp ? 'text-accent-green' : isDown ? 'text-accent-red' : 'text-text-muted',
            )}
            title={String(deltaLabel)}
          >
            {isUp ? (
              <ArrowUpLeftIcon size={13} className="text-accent-green" />
            ) : isDown ? (
              <ArrowDownLeftIcon size={13} className="text-accent-red" />
            ) : null}
            <span>{fmtPct(delta)}</span>
          </span>
        )}
      </div>
    </div>
  );
}
