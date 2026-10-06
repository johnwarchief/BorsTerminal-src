import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { Popover, PopoverTrigger, PopoverContent } from './popover';

export const DropdownMenu = Popover;
export const DropdownMenuTrigger = PopoverTrigger;

export const DropdownMenuContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof PopoverContent>
>(({ className, ...props }, ref) => (
  <PopoverContent
    ref={ref}
    className={cn('min-w-[8rem] overflow-hidden p-1', className)}
    {...props}
  />
));
DropdownMenuContent.displayName = 'DropdownMenuContent';

export interface DropdownMenuItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  destructive?: boolean;
}

export const DropdownMenuItem = React.forwardRef<HTMLButtonElement, DropdownMenuItemProps>(
  ({ className, destructive = false, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      className={cn(
        'relative flex w-full cursor-pointer select-none items-center rounded-md px-2 py-1.5 text-2xs font-medium outline-none transition-colors text-start',
        destructive
          ? 'text-accent-red hover:bg-accent-red/15 focus:bg-accent-red/15'
          : 'text-text-primary hover:bg-bg-card hover:text-accent-blue focus:bg-bg-card focus:text-accent-blue',
        className,
      )}
      {...props}
    />
  ),
);
DropdownMenuItem.displayName = 'DropdownMenuItem';

export const DropdownMenuSeparator = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('-mx-1 my-1 h-px bg-border-c/50', className)} {...props} />
);
DropdownMenuSeparator.displayName = 'DropdownMenuSeparator';

export const DropdownMenuLabel = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('px-2 py-1 text-3xs font-black text-text-muted', className)} {...props} />
);
DropdownMenuLabel.displayName = 'DropdownMenuLabel';
