import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id: customId, ...props }, ref) => {
    const generatedId = React.useId();
    const id = customId ?? generatedId;
    return (
      <div className="inline-flex items-center gap-2 select-none">
        <input
          ref={ref}
          id={id}
          type="checkbox"
          className={cn(
            'h-4 w-4 shrink-0 rounded border border-border-c bg-bg-card/90 text-accent-blue',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
            'disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer accent-accent-blue',
            className,
          )}
          {...props}
        />
        {label && (
          <label htmlFor={id} className="text-2xs font-medium text-text-secondary cursor-pointer hover:text-text-primary">
            {label}
          </label>
        )}
      </div>
    );
  },
);
Checkbox.displayName = 'Checkbox';
