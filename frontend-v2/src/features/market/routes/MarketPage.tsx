import { useMemo, useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useWorkspace } from '@shared/workspace/store';
import { SIDE_WIDTH } from '@shared/workspace/sizes';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';
import type { TilePanel } from '@shared/workspace/layout';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';
import { BottomDock } from '@app/shell/BottomDock';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { SnapshotStrip } from '../components/SnapshotStrip';
import { BoardPanel } from '../panels/BoardPanel';
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
  const fundamentalsOpen = useWorkspace((state) => state.workspaces[0].fundamentalsOpen);
  const sideCollapsed = useWorkspace((state) => state.workspaces[0].sideCollapsed);
  const sideWidth = useWorkspace((state) => state.workspaces[0].sideWidth);
  const dockHeight = useWorkspace((state) => state.workspaces[0].dockHeight);
  const chartShare = useWorkspace((state) => state.workspaces[0].chartShare);
  const activeSymbol = useWorkspace((state) => state.activeSymbol);
  const setActiveSymbol = useWorkspace((state) => state.setActiveSymbol);
  const setChartOpen = useWorkspace((state) => state.setChartOpen);
  const setFundamentalsOpen = useWorkspace((state) => state.setFundamentalsOpen);
  const setSideCollapsed = useWorkspace((state) => state.setSideCollapsed);
  const setSideWidth = useWorkspace((state) => state.setSideWidth);
  const setDockHeight = useWorkspace((state) => state.setDockHeight);
  const setChartShare = useWorkspace((state) => state.setChartShare);
  const split = useWorkspace((state) => state.split);
  const close = useWorkspace((state) => state.close);
  const swap = useWorkspace((state) => state.swap);
  const setRatio = useWorkspace((state) => state.setRatio);

  const pollMs = useMarketPrefs((state) => state.pollMs);
  const setFilters = useMarketPrefs((state) => state.setFilters);
  const board = useBoard(pollMs);
  const snapshot = useMarketSnapshot(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('symbol');
  const narrow = useMediaQuery('(max-width: 1279px)');

  useTileKeyboard(layout);

  const symbolRow = useMemo(() => {
    if (!activeSymbol) return null;
    return rows.find((row) => identityOf(row) === activeSymbol) ?? null;
  }, [rows, activeSymbol]);

  function selectRow(row: MarketRow, day: number | null) {
    setBoardDay(day);
    setActiveSymbol(identityOf(row));
  }

  function selectWatchRow(insCode: string) {
    setActiveSymbol(insCode);
  }

  function renderPanel(panel: TilePanel) {
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
    return <BoardPanel selectedKey={activeSymbol} onSelect={selectRow} onActivate={selectRow} />;
  }

  const toggleChart = () => setChartOpen(!chartOpen);
  const toggleFundamentals = () => setFundamentalsOpen(!fundamentalsOpen);

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
                {tab === 'symbol' ? (
                  <SymbolSidebar
                    variant="narrow"
                    row={symbolRow}
                    symbolKey={activeSymbol}
                    boardDay={boardDay}
                    chartOpen={chartOpen}
                    fundamentalsOpen={fundamentalsOpen}
                    onToggleChart={toggleChart}
                    onToggleFundamentals={toggleFundamentals}
                  />
                ) : (
                  <WatchPanel
                    rows={rows}
                    filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
                    onSelect={selectWatchRow}
                    onPickSector={(sector) => setFilters({ sector })}
                  />
                )}
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
      <div className="flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <WorkspaceShell
              layout={layout}
              renderPanel={renderPanel}
              onClose={close}
              onSplit={split}
              onSwap={swap}
              onRatio={setRatio}
            />
          </div>
          <BottomDock
            symbol={symbolRow?.symbol ?? null}
            chartOpen={chartOpen}
            fundamentalsOpen={fundamentalsOpen}
            height={dockHeight}
            chartShare={chartShare}
            onToggleChart={toggleChart}
            onToggleFundamentals={toggleFundamentals}
            onHeightChange={setDockHeight}
            onChartShareChange={setChartShare}
          />
        </div>
        {sideCollapsed ? (
          <SymbolSidebar
            collapsed
            row={symbolRow}
            symbolKey={activeSymbol}
            boardDay={boardDay}
            chartOpen={chartOpen}
            fundamentalsOpen={fundamentalsOpen}
            onToggleChart={toggleChart}
            onToggleFundamentals={toggleFundamentals}
            onToggleCollapsed={() => setSideCollapsed(false)}
          />
        ) : (
          <>
            <LayoutResizer
              orientation="vertical"
              value={sideWidth}
              min={SIDE_WIDTH.min}
              max={SIDE_WIDTH.max}
              step={8}
              defaultValue={SIDE_WIDTH.default}
              label="عرض سایدبار نماد"
              testId="resize-sidebar"
              increaseKey="ArrowRight"
              decreaseKey="ArrowLeft"
              fromPointer={(rect, x) => x - rect.left}
              onChange={setSideWidth}
            />
            <div style={{ width: sideWidth }} className="flex min-h-0 flex-none flex-col border-s border-line bg-panel">
              <SymbolSidebar
                row={symbolRow}
                symbolKey={activeSymbol}
                boardDay={boardDay}
                chartOpen={chartOpen}
                fundamentalsOpen={fundamentalsOpen}
                onToggleChart={toggleChart}
                onToggleFundamentals={toggleFundamentals}
                onToggleCollapsed={() => setSideCollapsed(true)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
