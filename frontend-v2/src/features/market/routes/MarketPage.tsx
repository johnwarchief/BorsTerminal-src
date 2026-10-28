import { useCallback, useEffect, useRef, useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useUiStore } from '@shared/stores/uiStore';
import { useBoard } from '../api/useBoard';
import { StatusStrip } from '../components/StatusStrip';
import { QuickDrawer } from '../components/QuickDrawer';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { useMarketPrefs } from '../stores/prefs';
import { BoardPanel } from '../panels/BoardPanel';

export function MarketPage() {
  const pollMs = useMarketPrefs((s) => s.pollMs);
  const board = useBoard(pollMs);
  const rows = board.data?.data ?? [];
  const statusMode = useUiStore((s) => s.statusMode);
  const setStatusMode = useUiStore((s) => s.setStatusMode);
  const [selectedRow, setSelectedRow] = useState<MarketRow | null>(null);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const drawerWasOpen = useRef(false);
  const selectedKey = selectedRow ? (selectedRow.ins_code?.trim() || selectedRow.symbol) : null;

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawerOpen]);

  useEffect(() => {
    if (drawerWasOpen.current && !drawerOpen && returnFocus.current?.isConnected) {
      returnFocus.current.focus({ preventScroll: true });
    }
    drawerWasOpen.current = drawerOpen;
  }, [drawerOpen]);

  function openRow(row: MarketRow, day: number | null) {
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setSelectedRow(row);
    setBoardDay(day);
    setDrawerOpen(true);
  }

  const focusBoardSearch = useCallback(() => {
    returnFocus.current = null;
    setDrawerOpen(false);
    window.setTimeout(() => {
      const input = document.getElementById('board-search');
      if (!(input instanceof HTMLInputElement)) return;
      input.focus();
      input.select();
    }, 0);
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {board.data ? <StatusStrip feed={board.data} rows={rows} mode={statusMode} onMode={setStatusMode} /> : null}
      <div className="flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <BoardPanel
            selectedKey={drawerOpen ? selectedKey : null}
            onSelect={openRow}
            onActivate={openRow}
            onFocusSearch={focusBoardSearch}
          />
        </div>
        {drawerOpen && selectedRow ? (
          <div className="min-h-0 w-[380px] flex-none border-s border-line">
            <QuickDrawer
              row={selectedRow}
              filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
              boardDay={boardDay ?? undefined}
              onClose={() => setDrawerOpen(false)}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
