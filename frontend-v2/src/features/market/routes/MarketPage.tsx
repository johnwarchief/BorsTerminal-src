import { useMemo, useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useWorkspace } from '@shared/workspace/store';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';
import { findTile, type TilePanel } from '@shared/workspace/layout';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { SnapshotStrip } from '../components/SnapshotStrip';
import { BoardPanel } from '../panels/BoardPanel';
import { SymbolPanel } from '../panels/SymbolPanel';
import { WatchPanel } from '../panels/WatchPanel';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { useMarketPrefs } from '../stores/prefs';

type Tab = 'symbol' | 'watch';

function identityOf(row: MarketRow): string {
  return row.ins_code?.trim() || row.symbol;
}

export function MarketPage() {
  const layout = useWorkspace((state) => state.workspaces[0].layout);
  const chartOpen = useWorkspace((state) => state.workspaces[0].chartOpen);
  const activeSymbol = useWorkspace((state) => state.activeSymbol);
  const pinned = useWorkspace((state) => state.pinned);
  const setActiveSymbol = useWorkspace((state) => state.setActiveSymbol);
  const setChartOpen = useWorkspace((state) => state.setChartOpen);
  const split = useWorkspace((state) => state.split);
  const close = useWorkspace((state) => state.close);
  const swap = useWorkspace((state) => state.swap);
  const setRatio = useWorkspace((state) => state.setRatio);
  const toggleFollow = useWorkspace((state) => state.toggleFollow);

  const pollMs = useMarketPrefs((state) => state.pollMs);
  const setFilters = useMarketPrefs((state) => state.setFilters);
  const board = useBoard(pollMs);
  const snapshot = useMarketSnapshot(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);
  const [selectedRow, setSelectedRow] = useState<MarketRow | null>(null);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('symbol');
  const narrow = useMediaQuery('(max-width: 1279px)');

  useTileKeyboard(layout);

  const symbolRow = useMemo(() => {
    if (!activeSymbol) return null;
    return rows.find((row) => identityOf(row) === activeSymbol) ?? null;
  }, [rows, activeSymbol]);

  function symbolFor(tileId: string): MarketRow | null {
    const tile = findTile(layout, tileId);
    const key = tile && !tile.follow ? (pinned[tileId] ?? null) : activeSymbol;
    if (!key) return null;
    return rows.find((row) => identityOf(row) === key) ?? null;
  }

  function selectRow(row: MarketRow, day: number | null) {
    setSelectedRow(row);
    setBoardDay(day);
    setActiveSymbol(identityOf(row));
  }

  function selectWatchRow(insCode: string) {
    setActiveSymbol(insCode);
    const row = rows.find((item) => identityOf(item) === insCode);
    if (row) setSelectedRow(row);
  }

  function renderPanel(panel: TilePanel, tileId: string) {
    const tileRow = symbolFor(tileId);
    if (panel === 'board') {
      return (
        <BoardPanel
          selectedKey={activeSymbol}
          onSelect={selectRow}
          onActivate={selectRow}
        />
      );
    }
    if (panel === 'symbol') {
      return (
        <SymbolPanel
          row={tileRow ?? selectedRow}
          boardDay={boardDay ?? board.data?.meta?.d_even ?? null}
          chartOpen={chartOpen}
          onToggleChart={() => setChartOpen(!chartOpen)}
        />
      );
    }
    if (panel === 'watch') {
      return (
        <WatchPanel
          rows={rows}
          filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
          onSelect={selectWatchRow}
          onPickSector={(sector) => setFilters({ sector })}
        />
      );
    }
    return tileRow ? <ChartPanel symbol={tileRow.symbol} /> : (
      <div className="grid h-full place-items-center t-95 text-text-3">برای چارت، نمادی انتخاب کن.</div>
    );
  }

  if (narrow) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <SnapshotStrip rows={rows} snapshot={snapshot.data} />
        <div className="flex min-h-0 flex-1">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <BoardPanel selectedKey={activeSymbol} onSelect={selectRow} onActivate={selectRow} />
          </div>
          {activeSymbol ? (
            <div className="flex min-h-0 w-[340px] flex-none flex-col border-s border-line">
              <div className="flex flex-none gap-1 border-b border-line px-2 py-1" role="tablist">
                {([['symbol', 'نماد'], ['watch', 'دیده‌بان‌ها']] as const).map(([id, label]) => (
                  <button key={id} type="button" role="tab" aria-selected={tab === id}
                    data-testid={`narrow-tab-${id}`} onClick={() => setTab(id)} className="tape-btn">
                    {label}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                {tab === 'symbol'
                  ? <SymbolPanel row={symbolRow} boardDay={boardDay} chartOpen={chartOpen} onToggleChart={() => setChartOpen(!chartOpen)} />
                  : <WatchPanel rows={rows} filterConfig={DEFAULT_TAPE_FILTER_CONFIG} onSelect={selectWatchRow} onPickSector={(sector) => setFilters({ sector })} />}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SnapshotStrip rows={rows} snapshot={snapshot.data} />
      <div className="min-h-0 flex-1">
        <WorkspaceShell
          layout={layout}
          renderPanel={renderPanel}
          onClose={close}
          onSplit={split}
          onSwap={swap}
          onToggleFollow={toggleFollow}
          onRatio={setRatio}
        />
      </div>
    </div>
  );
}
