import { useEffect, useState, type ReactNode } from 'react';
import clsx from 'clsx';
import { PANEL_LABEL, PANEL_MIN, type MoveDir, type SplitDir, type TilePanel } from './layout';

interface Props {
  id: string;
  panel: TilePanel;
  focused: boolean;
  canAddWatch: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  children: ReactNode;
}

export function TileFrame(props: Props) {
  const { id, panel, focused, canAddWatch, onFocus, onClose, onSplit, onSwap, children } = props;
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [menu]);

  return (
    <div
      data-tile-id={id}
      data-tile-focused={focused ? 'true' : 'false'}
      data-testid={`tile-${id}`}
      style={{ minWidth: PANEL_MIN[panel].w, minHeight: PANEL_MIN[panel].h }}
      className={clsx('relative flex h-full min-h-0 w-full min-w-0 flex-col bg-panel',
        focused && 'outline outline-1 outline-accent')}
    >
      <div
        data-tile-header
        tabIndex={0}
        role="group"
        aria-label={PANEL_LABEL[panel]}
        data-testid={`tile-header-${id}`}
        onFocus={() => onFocus(id)}
        onMouseDown={() => onFocus(id)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft') { event.preventDefault(); onSwap(id, 'left'); }
          if (event.key === 'ArrowRight') { event.preventDefault(); onSwap(id, 'right'); }
          if (event.key === 'ArrowUp') { event.preventDefault(); onSwap(id, 'up'); }
          if (event.key === 'ArrowDown') { event.preventDefault(); onSwap(id, 'down'); }
        }}
        className="flex h-7 flex-none items-center gap-1.5 border-b border-line bg-panel-2 px-2 t-10 text-text-2"
      >
        <span className="font-bold">{PANEL_LABEL[panel]}</span>
        {focused ? (
          <span data-testid={`tile-hint-${id}`} className="t-9 text-text-3">
            با ←→↑↓ جابه‌جا کن
          </span>
        ) : null}
        <div className="ms-auto flex items-center gap-1">
          {canAddWatch ? (
            <button
              type="button"
              data-testid={`tile-menu-${id}`}
              aria-label="کارهای پنل"
              className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
              onClick={(event) => { event.stopPropagation(); setMenu((open) => !open); }}
            >
              ⋯
            </button>
          ) : null}
          {panel !== 'board' ? (
            <button
              type="button"
              data-testid={`tile-close-${id}`}
              aria-label="بستنِ پنل"
              className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
              onClick={() => onClose(id)}
            >
              ×
            </button>
          ) : null}
        </div>
      </div>

      {menu && canAddWatch ? (
        <div className="absolute z-20 mt-7 rounded-[var(--radius-sm)] border border-line bg-panel p-1 t-9"
          onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            data-testid="tile-add-watch"
            className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
            onClick={() => { setMenu(false); onSplit(id, 'col', 'watch'); }}
          >
            افزودنِ دیده‌بان
          </button>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
