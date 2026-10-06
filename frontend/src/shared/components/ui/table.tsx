import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  dense?: boolean;
}

export const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, dense = false, ...props }, ref) => (
    <div className="relative w-full overflow-auto overscroll-contain">
      <table
        ref={ref}
        className={cn(
          'w-full caption-bottom text-xs text-text-primary border-collapse',
          dense ? 'text-2xs' : 'text-xs',
          className,
        )}
        {...props}
      />
    </div>
  ),
);
Table.displayName = 'Table';

export const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <thead ref={ref} className={cn('[&_tr]:border-b border-border-c bg-bg-card/90 sticky top-0 z-10 backdrop-blur-xs', className)} {...props} />
  ),
);
TableHeader.displayName = 'TableHeader';

export const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />
  ),
);
TableBody.displayName = 'TableBody';

export const TableFooter = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tfoot
      ref={ref}
      className={cn('border-t border-border-c bg-bg-card font-bold text-text-secondary', className)}
      {...props}
    />
  ),
);
TableFooter.displayName = 'TableFooter';

export interface TableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  selected?: boolean;
}

export const TableRow = React.forwardRef<HTMLTableRowElement, TableRowProps>(
  ({ className, selected = false, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        'border-b border-border-c/40 transition-colors duration-100',
        'hover:bg-bg-card/60 cursor-default select-none',
        selected && 'bg-accent-blue/10 border-accent-blue/30',
        className,
      )}
      {...props}
    />
  ),
);
TableRow.displayName = 'TableRow';

export interface TableHeadProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  num?: boolean;
}

export const TableHead = React.forwardRef<HTMLTableCellElement, TableHeadProps>(
  ({ className, num = false, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        'h-7.5 px-2.5 py-1 text-2xs font-bold text-text-muted select-none whitespace-nowrap',
        num ? 'text-end' : 'text-start',
        className,
      )}
      {...props}
    />
  ),
);
TableHead.displayName = 'TableHead';

export interface TableCellProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  num?: boolean;
}

export const TableCell = React.forwardRef<HTMLTableCellElement, TableCellProps>(
  ({ className, num = false, ...props }, ref) => (
    <td
      ref={ref}
      className={cn(
        'px-2.5 py-1.5 align-middle whitespace-nowrap',
        num && 'text-end num',
        className,
      )}
      {...props}
    />
  ),
);
TableCell.displayName = 'TableCell';

export const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => (
    <caption ref={ref} className={cn('mt-3 text-3xs text-text-muted', className)} {...props} />
  ),
);
TableCaption.displayName = 'TableCaption';
