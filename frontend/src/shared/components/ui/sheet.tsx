import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { useDialogA11y } from '@shared/lib/useDialogA11y';

interface SheetContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SheetContext = React.createContext<SheetContextValue | null>(null);

export interface SheetProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export function Sheet({ open: controlledOpen, defaultOpen = false, onOpenChange, children }: SheetProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : uncontrolledOpen;

  const handleOpenChange = React.useCallback(
    (newOpen: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(newOpen);
      }
      onOpenChange?.(newOpen);
    },
    [isControlled, onOpenChange],
  );

  return (
    <SheetContext.Provider value={{ open: isOpen, onOpenChange: handleOpenChange }}>
      {children}
    </SheetContext.Provider>
  );
}

export const SheetTrigger = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ onClick, children, ...props }, ref) => {
    const context = React.useContext(SheetContext);
    return (
      <button
        ref={ref}
        type="button"
        onClick={(e) => {
          onClick?.(e);
          context?.onOpenChange(true);
        }}
        {...props}
      >
        {children}
      </button>
    );
  },
);
SheetTrigger.displayName = 'SheetTrigger';

export interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: 'top' | 'bottom' | 'left' | 'right';
  onClose?: () => void;
}

export const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, side = 'left', children, onClose, ...props }, externalRef) => {
    const context = React.useContext(SheetContext);
    const isOpen = context?.open ?? true;

    const handleClose = React.useCallback(() => {
      context?.onOpenChange(false);
      onClose?.();
    }, [context, onClose]);

    const panelRef = useDialogA11y<HTMLDivElement>({ open: isOpen, onClose: handleClose });

    if (!isOpen) return null;

    const sideStyles = {
      top: 'inset-x-0 top-0 border-b',
      bottom: 'inset-x-0 bottom-0 border-t',
      left: 'inset-y-0 left-0 border-r w-full sm:max-w-md',
      right: 'inset-y-0 right-0 border-l w-full sm:max-w-md',
    }[side];

    return (
      <div
        className="fixed inset-0 z-[120] bg-black/60 backdrop-blur-xs overscroll-contain transition-opacity duration-200"
        onClick={handleClose}
        role="presentation"
      >
        <div
          ref={(node) => {
            (panelRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
            if (typeof externalRef === 'function') externalRef(node);
            else if (externalRef) (externalRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
          }}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'glass-panel fixed z-[121] flex flex-col bg-bg-secondary p-4 shadow-2xl transition-transform duration-200 ease-out outline-none',
            sideStyles,
            className,
          )}
          {...props}
        >
          {children}
        </div>
      </div>
    );
  },
);
SheetContent.displayName = 'SheetContent';

export const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col space-y-1 pb-3 border-b border-border-c/40', className)} {...props} />
);
SheetHeader.displayName = 'SheetHeader';

export const SheetTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2 ref={ref} className={cn('text-sm font-black text-text-primary flex items-center justify-between', className)} {...props} />
  ),
);
SheetTitle.displayName = 'SheetTitle';

export const SheetDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('text-2xs text-text-muted', className)} {...props} />
  ),
);
SheetDescription.displayName = 'SheetDescription';

export const SheetFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('mt-auto flex flex-col gap-2 pt-3 border-t border-border-c/40', className)} {...props} />
);
SheetFooter.displayName = 'SheetFooter';

export const SheetClose = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ onClick, className, children, ...props }, ref) => {
    const context = React.useContext(SheetContext);
    return (
      <button
        ref={ref}
        type="button"
        aria-label="بستن"
        onClick={(e) => {
          onClick?.(e);
          context?.onOpenChange(false);
        }}
        className={cn(
          'rounded-lg border border-border-c p-1 text-text-secondary hover:border-accent-blue/50 hover:text-accent-blue transition-colors',
          className,
        )}
        {...props}
      >
        {children ?? '✕'}
      </button>
    );
  },
);
SheetClose.displayName = 'SheetClose';
