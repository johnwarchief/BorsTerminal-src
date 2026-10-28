import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { faNum, fmtInt } from '@shared/lib/fa';
import { useBoard } from '@features/market/api/useBoard';
import { useMarketPrefs } from '@features/market/stores/prefs';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { panelsInOrder } from '@shared/workspace/layout';
import { useWorkspace } from '@shared/workspace/store';
import { useUiStore } from '@shared/stores/uiStore';

const STORAGE_KEY = 'bors-sidebar-symbol-v1';

interface ShowState { chart: boolean; fundamental: boolean }

function readShow(): ShowState {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<ShowState>;
    return { chart: raw.chart !== false, fundamental: raw.fundamental !== false };
  } catch {
    return { chart: true, fundamental: true };
  }
}

export function SidebarSymbol({ collapsed }: { collapsed: boolean }) {
  const activeSymbol = useWorkspace((state) => state.activeSymbol);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  if (!activeSymbol) {
    return collapsed ? null : (
      <div data-testid="sidebar-symbol" className="border-t border-line p-2 t-9 text-text-3">
        برای چارت و پنج شاخصِ بنیادی، روی یک ردیفِ تابلو کلیک کن.
      </div>
    );
  }

  if (collapsed) {
    return (
      <div className="border-t border-line p-1.5">
        <button type="button" data-testid="sidebar-symbol" onClick={toggleSidebar}
          title="باز کردنِ پنلِ نماد"
          className="grid h-7 w-full place-items-center rounded-[var(--radius-sm)] t-9 text-text-2 hover:bg-panel-2">
          نماد
        </button>
      </div>
    );
  }

  return <SymbolBody symbol={activeSymbol} />;
}

function SymbolBody({ symbol }: { symbol: string }) {
  const pollMs = useMarketPrefs((state) => state.pollMs);
  const board = useBoard(pollMs);
  const [show, setShow] = useState<ShowState>(readShow);

  const row = useMemo(
    () => (board.data?.data ?? []).find((item) => (item.ins_code?.trim() || item.symbol) === symbol) ?? null,
    [board.data, symbol]);

  function toggle(key: keyof ShowState) {
    setShow((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* ذخیره‌نشدن نمایش را نمی‌شکند */ }
      return next;
    });
  }

  function openChartTile() {
    const workspace = useWorkspace.getState();
    const tiles = panelsInOrder(workspace.workspaces[0].layout);
    const host = tiles.find((tile) => tile.panel === 'symbol') ?? tiles.find((tile) => tile.panel === 'board');
    if (host) workspace.split(host.id, 'col', 'chart');
  }

  if (!row) {
    return (
      <div data-testid="sidebar-symbol" className="border-t border-line p-2 t-9 text-text-3">
        این نماد در تابلو نیست.
      </div>
    );
  }

  const pct = row.percent_change;

  return (
    <div data-testid="sidebar-symbol" className="flex min-h-0 flex-col border-t border-line">
      <div className="flex flex-none items-baseline gap-1.5 px-2 pt-1.5">
        <b className="min-w-0 truncate t-115 font-extrabold text-text">{row.symbol}</b>
        <span className="num ms-auto t-10 font-bold text-text-2">{fmtInt(row.p_last ?? row.p_closing)}</span>
        <span className={clsx('num t-9', pct == null ? 'text-text-3' : pct > 0 ? 'text-up' : pct < 0 ? 'text-down' : 'text-flat')}>
          {pct == null ? '—' : `${pct > 0 ? '▲' : pct < 0 ? '▼' : '•'} ${faNum(Math.abs(pct))}٪`}
        </span>
      </div>

      <div className="flex flex-none items-center gap-1 px-2 py-1" role="group" aria-label="نمایشِ پنلِ نماد">
        <button type="button" data-testid="sidebar-show-chart" aria-expanded={show.chart}
          onClick={() => toggle('chart')}
          className={clsx('tape-btn', show.chart && 'is-on')}>
          چارت
        </button>
        <button type="button" data-testid="sidebar-show-fundamental" aria-expanded={show.fundamental}
          onClick={() => toggle('fundamental')}
          className={clsx('tape-btn', show.fundamental && 'is-on')}>
          بنیادی · ۵ شاخص
        </button>
        <button type="button" data-testid="sidebar-open-chart-tile" onClick={openChartTile}
          title="باز کردنِ چارت در کاشیِ میزکار"
          className="ms-auto rounded-[var(--radius-xs)] px-1 t-9 text-text-3 hover:bg-panel-2 hover:text-text">
          کاشی ↗
        </button>
      </div>

      {show.chart ? (
        <div data-testid="sidebar-chart" className="h-[150px] flex-none border-y border-line">
          <ChartPanel symbol={row.symbol} />
        </div>
      ) : null}

      {show.fundamental ? <FundamentalCards symbol={row.symbol} /> : null}
    </div>
  );
}
