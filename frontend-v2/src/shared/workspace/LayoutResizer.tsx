import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';

export interface ResizeRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LayoutResizerProps {
  orientation: 'vertical' | 'horizontal';
  value: number;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  label: string;
  testId: string;
  increaseKey: 'ArrowLeft' | 'ArrowRight' | 'ArrowUp' | 'ArrowDown';
  decreaseKey: 'ArrowLeft' | 'ArrowRight' | 'ArrowUp' | 'ArrowDown';
  fromPointer: (rect: ResizeRect, clientX: number, clientY: number) => number;
  onChange: (value: number) => void;
  measure?: () => ResizeRect | null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function LayoutResizer(props: LayoutResizerProps) {
  const {
    orientation, value, min, max, step, defaultValue, label, testId,
    increaseKey, decreaseKey, fromPointer, onChange, measure,
  } = props;
  const host = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!dragging) return;
    const move = (event: MouseEvent) => {
      if (event.buttons === 0) {
        setDragging(false);
        return;
      }
      const rect = measure
        ? measure()
        : (host.current?.parentElement?.getBoundingClientRect() ?? null);
      if (!rect) return;
      onChange(clamp(fromPointer(rect, event.clientX, event.clientY), min, max));
    };
    const stop = () => setDragging(false);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', stop);
    window.addEventListener('blur', stop);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', stop);
      window.removeEventListener('blur', stop);
    };
  }, [dragging, measure, fromPointer, min, max, onChange]);

  return (
    <div
      ref={host}
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      aria-valuenow={Number(clamp(value, min, max).toFixed(2))}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-testid={testId}
      className={clsx(
        'group relative z-10 flex-none bg-line hover:bg-accent focus-visible:bg-accent focus-visible:outline-none',
        orientation === 'vertical' ? 'w-px cursor-col-resize' : 'h-px cursor-row-resize',
      )}
      onDoubleClick={() => onChange(clamp(defaultValue, min, max))}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          onChange(clamp(defaultValue, min, max));
          return;
        }
        if (event.key === increaseKey) {
          event.preventDefault();
          onChange(clamp(value + step, min, max));
          return;
        }
        if (event.key === decreaseKey) {
          event.preventDefault();
          onChange(clamp(value - step, min, max));
        }
      }}
      onMouseDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        host.current?.focus();
        setDragging(true);
      }}
    >
      <span className={clsx(
        'absolute bg-transparent',
        orientation === 'vertical' ? 'inset-y-0 -start-1 -end-1' : 'inset-x-0 -top-1 -bottom-1',
      )} />
    </div>
  );
}
