import { useEffect } from 'react';
import { panelsInOrder, type LayoutNode } from './layout';
import { useWorkspace } from './store';

export function useTileKeyboard(layout: LayoutNode, options: { enabled?: boolean } = {}): void {
  const undo = useWorkspace((state) => state.undo);
  const enabled = options.enabled !== false;

  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        undo();
        return;
      }
      if (!event.altKey || event.ctrlKey || event.metaKey) return;
      const digit = /^Digit([1-4])$/.exec(event.code);
      if (!digit) return;
      const tile = panelsInOrder(layout)[Number(digit[1]) - 1];
      if (!tile) return;
      event.preventDefault();
      document
        .querySelector<HTMLElement>(`[data-tile-id="${tile.id}"] [data-tile-header]`)
        ?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled, layout, undo]);
}
