import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  delayMs?: number;
}

export function Tooltip({ content, children, side = 'top', className, delayMs = 150 }: TooltipProps) {
  const [visible, setVisible] = React.useState(false);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const id = React.useId();

  const show = () => {
    timerRef.current = setTimeout(() => setVisible(true), delayMs);
  };

  const hide = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  };

  const sideStyles = {
    top: 'bottom-full mb-1.5 left-1/2 -translate-x-1/2',
    bottom: 'top-full mt-1.5 left-1/2 -translate-x-1/2',
    left: 'right-full mr-1.5 top-1/2 -translate-y-1/2',
    right: 'left-full ml-1.5 top-1/2 -translate-y-1/2',
  }[side];

  if (!content) return children;

  return (
    <div className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {React.cloneElement(children, {
        'aria-describedby': visible ? id : undefined,
      })}
      {visible && (
        <div
          id={id}
          role="tooltip"
          className={cn(
            'pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border-c/90 bg-bg-secondary px-2 py-1 text-3xs font-medium text-text-primary shadow-lg',
            'panel-in select-none backdrop-blur-xs',
            sideStyles,
            className,
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
