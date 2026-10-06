import * as React from 'react';
import { cn } from '@shared/lib/cn';

export type BadgeVariant =
  | 'default'
  | 'secondary'
  | 'outline'
  | 'success'
  | 'destructive'
  | 'warning'
  | 'info'
  | 'cyan'
  | 'orange';

export type LegacyTone = 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'orange';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  tone?: LegacyTone;
  size?: 'default' | 'sm' | 'xs';
}

const TONE_TO_VARIANT: Record<LegacyTone, BadgeVariant> = {
  green: 'success',
  red: 'destructive',
  yellow: 'warning',
  blue: 'info',
  gray: 'secondary',
  orange: 'orange',
};

const VARIANT_STYLES: Record<BadgeVariant, string> = {
  default: 'bg-primary/15 text-primary border-primary/30',
  secondary: 'bg-bg-card text-text-secondary border-border-c',
  outline: 'bg-transparent text-text-primary border-border-c',
  success: 'bg-accent-green/15 text-accent-green border-accent-green/30',
  destructive: 'bg-accent-red/15 text-accent-red border-accent-red/30',
  warning: 'bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30',
  info: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
  cyan: 'bg-neon-cyan/15 text-neon-cyan border-neon-cyan/40 shadow-[0_0_8px_rgba(34,211,238,0.15)]',
  orange: 'bg-accent-susp-bg text-accent-susp border-accent-susp/30',
};

export function Badge({
  className,
  variant,
  tone,
  size = 'default',
  children,
  title,
  ...props
}: BadgeProps) {
  const resolvedVariant: BadgeVariant = variant ?? (tone ? TONE_TO_VARIANT[tone] : 'secondary');

  const sizeStyles = {
    default: 'px-2 py-0.5 text-2xs font-bold rounded-full',
    sm: 'px-1.5 py-0.2 text-3xs font-semibold rounded-md',
    xs: 'px-1 py-0 text-[10px] font-medium rounded',
  }[size];

  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 border select-none transition-colors duration-150',
        VARIANT_STYLES[resolvedVariant],
        sizeStyles,
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
