import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  label?: string;
  id?: string;
}

export function Switch({ checked, onCheckedChange, disabled = false, className, label, id: customId }: SwitchProps) {
  const generatedId = React.useId();
  const id = customId ?? generatedId;

  return (
    <div className="inline-flex items-center gap-2 select-none">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex h-4.5 w-8 shrink-0 cursor-pointer rounded-full border border-border-c transition-colors duration-200 ease-in-out outline-none',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
          'disabled:cursor-not-allowed disabled:opacity-40',
          checked ? 'bg-accent-blue border-accent-blue' : 'bg-bg-card',
          className,
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out mt-0.5',
            checked ? '-translate-x-4' : '-translate-x-0.5',
          )}
        />
      </button>
      {label && (
        <label htmlFor={id} className="text-2xs font-medium text-text-secondary cursor-pointer hover:text-text-primary">
          {label}
        </label>
      )}
    </div>
  );
}
