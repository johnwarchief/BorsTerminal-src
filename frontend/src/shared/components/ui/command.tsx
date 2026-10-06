import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { Dialog, DialogContent } from './dialog';

export type CommandProps = React.HTMLAttributes<HTMLDivElement>;

export const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex h-full w-full flex-col overflow-hidden rounded-xl bg-bg-secondary text-text-primary',
        className,
      )}
      {...props}
    />
  ),
);
Command.displayName = 'Command';

export interface CommandDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

export function CommandDialog({ open, onOpenChange, children }: CommandDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 max-w-2xl shadow-2xl border-border-c/80">
        <Command>{children}</Command>
      </DialogContent>
    </Dialog>
  );
}

export interface CommandInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  onValueChange?: (value: string) => void;
}

export const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  ({ className, value, onValueChange, onChange, ...props }, ref) => (
    <div className="flex items-center gap-2 border-b border-border-c/70 px-3 py-2">
      <span className="text-neon-cyan select-none" aria-hidden>
        ⌘
      </span>
      <input
        ref={ref}
        value={value}
        onChange={(e) => {
          onChange?.(e);
          onValueChange?.(e.target.value);
        }}
        className={cn(
          'flex h-8 w-full rounded-md bg-transparent text-xs text-text-primary outline-none placeholder:text-text-muted disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      />
    </div>
  ),
);
CommandInput.displayName = 'CommandInput';

export const CommandList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="listbox"
      className={cn('max-h-[380px] overflow-y-auto overscroll-contain p-1.5 scrollbar-thin', className)}
      {...props}
    />
  ),
);
CommandList.displayName = 'CommandList';

export const CommandEmpty = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  (props, ref) => (
    <div ref={ref} className="py-6 text-center text-xs text-text-muted" {...props} />
  ),
);
CommandEmpty.displayName = 'CommandEmpty';

export interface CommandGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  heading?: React.ReactNode;
}

export const CommandGroup = React.forwardRef<HTMLDivElement, CommandGroupProps>(
  ({ className, heading, children, ...props }, ref) => (
    <div ref={ref} className={cn('overflow-hidden p-1 text-text-primary', className)} {...props}>
      {heading && (
        <div className="px-2 py-1 text-3xs font-black uppercase tracking-wider text-text-muted select-none">
          {heading}
        </div>
      )}
      {children}
    </div>
  ),
);
CommandGroup.displayName = 'CommandGroup';

export const CommandSeparator = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('-mx-1 my-1 h-px bg-border-c/50', className)} {...props} />
  ),
);
CommandSeparator.displayName = 'CommandSeparator';

export interface CommandItemProps extends React.HTMLAttributes<HTMLDivElement> {
  disabled?: boolean;
  selected?: boolean;
  onSelect?: () => void;
}

export const CommandItem = React.forwardRef<HTMLDivElement, CommandItemProps>(
  ({ className, disabled = false, selected = false, onSelect, onClick, ...props }, ref) => (
    <div
      ref={ref}
      role="option"
      aria-selected={selected}
      aria-disabled={disabled}
      onClick={(e) => {
        if (disabled) return;
        onClick?.(e);
        onSelect?.();
      }}
      className={cn(
        'relative flex cursor-pointer select-none items-center justify-between rounded-lg px-2.5 py-2 text-xs outline-none transition-colors duration-100',
        selected
          ? 'bg-accent-blue/15 text-accent-blue font-bold shadow-2xs'
          : 'text-text-secondary hover:bg-bg-card/70 hover:text-text-primary',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
      {...props}
    />
  ),
);
CommandItem.displayName = 'CommandItem';

export const CommandShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
  <span className={cn('ms-auto text-3xs tracking-widest text-text-muted border border-border-c rounded px-1 py-0.5 font-mono', className)} {...props} />
);
CommandShortcut.displayName = 'CommandShortcut';
