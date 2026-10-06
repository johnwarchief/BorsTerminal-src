import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  rounded?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

export function Skeleton({ className, rounded = 'md', ...props }: SkeletonProps) {
  const radius = {
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    xl: 'rounded-xl',
    full: 'rounded-full',
  }[rounded];

  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse bg-text-muted/15', radius, className)}
      {...props}
    />
  );
}

export function SkeletonLines({
  lines = 3,
  className,
  label = 'در حال بارگذاری...',
}: {
  lines?: number;
  className?: string;
  label?: string;
}) {
  const n = Math.max(1, lines);
  return (
    <div role="status" aria-busy="true" aria-label={label} className={cn('flex w-full flex-col gap-2', className)}>
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} className={i === n - 1 ? 'h-3 w-3/5' : 'h-3 w-full'} />
      ))}
    </div>
  );
}
