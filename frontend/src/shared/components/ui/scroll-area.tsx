import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  maxHeight?: string | number;
}

export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, maxHeight, style, ...props }, ref) => (
    <div
      ref={ref}
      style={{ maxHeight, ...style }}
      className={cn('relative overflow-auto overscroll-contain scrollbar-thin scrollbar-thumb-border-c', className)}
      {...props}
    >
      {children}
    </div>
  ),
);
ScrollArea.displayName = 'ScrollArea';
