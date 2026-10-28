import { useRef, type RefObject } from 'react';
import clsx from 'clsx';
import { ratioFromPointer, type SplitDir } from './layout';

interface Props {
  dir: SplitDir;
  container: RefObject<HTMLElement | null>;
  onRatio: (ratio: number) => void;
}

export function Splitter({ dir, container, onRatio }: Props) {
  const dragging = useRef(false);

  return (
    <div
      role="separator"
      aria-orientation={dir === 'row' ? 'vertical' : 'horizontal'}
      tabIndex={-1}
      className={clsx('group relative z-10 flex-none bg-line hover:bg-accent',
        dir === 'row' ? 'w-px cursor-col-resize' : 'h-px cursor-row-resize')}
      onPointerDown={(event) => {
        dragging.current = true;
        (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!dragging.current) return;
        const rect = container.current?.getBoundingClientRect();
        if (!rect || rect.width === 0) return;
        onRatio(ratioFromPointer(rect, dir, event.clientX, event.clientY));
      }}
      onPointerUp={() => { dragging.current = false; }}
      onPointerCancel={() => { dragging.current = false; }}
    >
      <span className={clsx('absolute bg-transparent',
        dir === 'row' ? 'inset-y-0 -start-1 -end-1' : 'inset-x-0 -top-1 -bottom-1')} />
    </div>
  );
}
