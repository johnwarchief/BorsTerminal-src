import * as React from 'react';
import { cn } from '@shared/lib/cn';

export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          'flex h-8 w-full rounded-lg border border-border-c bg-bg-card/80 px-2.5 py-1 text-xs text-text-primary shadow-2xs transition-colors cursor-pointer',
          'focus-visible:border-border-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {children}
      </select>
    );
  },
);
Select.displayName = 'Select';
