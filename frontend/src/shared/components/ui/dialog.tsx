import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { useDialogA11y } from '@shared/lib/useDialogA11y';

interface DialogContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DialogContext = React.createContext<DialogContextValue | null>(null);

export interface DialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export function Dialog({ open: controlledOpen, defaultOpen = false, onOpenChange, children }: DialogProps) {
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
    <DialogContext.Provider value={{ open: isOpen, onOpenChange: handleOpenChange }}>
      {children}
    </DialogContext.Provider>
  );
}

export const DialogTrigger = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ onClick, children, ...props }, ref) => {
    const context = React.useContext(DialogContext);
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
DialogTrigger.displayName = 'DialogTrigger';

export interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  onClose?: () => void;
}

export const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, onClose, ...props }, externalRef) => {
    const context = React.useContext(DialogContext);
    const isOpen = context?.open ?? true;

    const handleClose = React.useCallback(() => {
      context?.onOpenChange(false);
      onClose?.();
    }, [context, onClose]);

    const panelRef = useDialogA11y<HTMLDivElement>({ open: isOpen, onClose: handleClose });

    if (!isOpen) return null;

    return (
      <div
        className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs overscroll-contain"
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
            'glass-panel scale-in relative w-full max-w-lg rounded-2xl border border-border-c bg-bg-secondary p-5 shadow-xl outline-none',
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
DialogContent.displayName = 'DialogContent';

export const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col space-y-1.5 pb-3 border-b border-border-c/40', className)} {...props} />
);
DialogHeader.displayName = 'DialogHeader';

export const DialogTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2 ref={ref} className={cn('text-sm font-black tracking-tight text-text-primary flex items-center justify-between', className)} {...props} />
  ),
);
DialogTitle.displayName = 'DialogTitle';

export const DialogDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('text-2xs text-text-muted mt-1', className)} {...props} />
  ),
);
DialogDescription.displayName = 'DialogDescription';

export const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex items-center justify-end gap-2 pt-3 border-t border-border-c/40 mt-4', className)} {...props} />
);
DialogFooter.displayName = 'DialogFooter';

export const DialogClose = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ onClick, className, children, ...props }, ref) => {
    const context = React.useContext(DialogContext);
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
          'rounded-lg border border-border-c/70 p-1 text-text-secondary hover:border-accent-blue/50 hover:text-accent-blue transition-colors',
          className,
        )}
        {...props}
      >
        {children ?? '✕'}
      </button>
    );
  },
);
DialogClose.displayName = 'DialogClose';
