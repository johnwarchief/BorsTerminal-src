import { useRef, useState, type ReactNode } from 'react';
import { Splitter } from './Splitter';
import { TileFrame } from './TileFrame';
import type { LayoutNode, MoveDir, SplitDir, TilePanel } from './layout';

export interface WorkspaceShellProps {
  layout: LayoutNode;
  renderPanel: (panel: TilePanel, tileId: string) => ReactNode;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  onToggleFollow: (id: string) => void;
  onRatio: (splitId: string, ratio: number, width: number, height: number) => void;
}

export function WorkspaceShell(props: WorkspaceShellProps) {
  const { layout, renderPanel, onClose, onSplit, onSwap, onToggleFollow, onRatio } = props;
  const [focused, setFocused] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);

  function node(item: LayoutNode): ReactNode {
    if (item.kind === 'tile') {
      return (
        <TileFrame
          key={item.id}
          id={item.id}
          panel={item.panel}
          follow={item.follow}
          focused={focused === item.id}
          onFocus={setFocused}
          onClose={onClose}
          onSplit={onSplit}
          onSwap={onSwap}
          onToggleFollow={onToggleFollow}
        >
          {renderPanel(item.panel, item.id)}
        </TileFrame>
      );
    }

    const resize = (ratio: number) => {
      const rect = root.current?.getBoundingClientRect();
      onRatio(item.id, ratio, rect?.width ?? 0, rect?.height ?? 0);
    };

    return (
      <div
        key={item.id}
        className={item.dir === 'row' ? 'flex h-full min-h-0 min-w-0' : 'flex h-full min-h-0 min-w-0 flex-col'}
      >
        <div className="min-h-0 min-w-0" style={{ flex: `${item.ratio} 1 0%` }}>{node(item.first)}</div>
        <Splitter dir={item.dir} container={root} onRatio={resize} />
        <div className="min-h-0 min-w-0" style={{ flex: `${1 - item.ratio} 1 0%` }}>{node(item.second)}</div>
      </div>
    );
  }

  return <div ref={root} data-testid="workspace-shell" className="h-full min-h-0 w-full min-w-0">{node(layout)}</div>;
}
