import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  num?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', num = false, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          'flex h-8 w-full rounded-lg border border-border-c bg-bg-card/70 px-2.5 py-1 text-xs text-text-primary shadow-2xs transition-colors',
          'placeholder:text-text-muted',
          'focus-visible:border-border-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          num && 'num',
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = 'Input';
