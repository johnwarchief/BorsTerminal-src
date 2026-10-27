import { useMemo, useState } from 'react';
import { fmtInt } from '@shared/lib/fa';
import { normalizeFa } from '@shared/lib/faSearch';
import { useBoard } from '../api/useBoard';
import { AssetFilter } from '../components/AssetFilter';
import { BoardTable } from '../components/BoardTable';
import { StatusStrip } from '../components/StatusStrip';
import { TapeBar } from '../components/TapeBar';
import { DEFAULT_ASSET_TYPES } from '../lib/assetDefaults';
import { classifyAssetType, type AssetType } from '../lib/assetType';
import { sortRows, type SortDir, type SortKey } from '../lib/boardSort';
import { matchesTapes, tapeCounts, type ScreenLogic, type TapeKey } from '../lib/tapeFilters';

const LOGIC_KEY = 'bors-screen-logic';

function loadLogic(): ScreenLogic {
  try {
    return window.localStorage.getItem(LOGIC_KEY) === 'or' ? 'or' : 'and';
  } catch {
    return 'and';
  }
}

export function MarketPage() {
  const board = useBoard();
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);

  const [query, setQuery] = useState('');
  const [assetTypes, setAssetTypes] = useState<AssetType[]>([...DEFAULT_ASSET_TYPES]);
  const [active, setActive] = useState<TapeKey[]>([]);
  const [logic, setLogic] = useState<ScreenLogic>(loadLogic);
  const [sortKey, setSortKey] = useState<SortKey>('value');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const counts = useMemo(() => tapeCounts(rows), [rows]);

  const visible = useMemo(() => {
    const q = normalizeFa(query);
    const filtered = rows.filter((row) => {
      if (!assetTypes.includes(classifyAssetType(row))) return false;
      if (!matchesTapes(row, active, logic)) return false;
      if (!q) return true;
      return normalizeFa(row.symbol).includes(q) || normalizeFa(row.name ?? '').includes(q);
    });
    return sortRows(filtered, sortKey, sortDir);
  }, [rows, query, active, logic, sortKey, sortDir, assetTypes]);

  function toggleTape(key: TapeKey) {
    setActive((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  function pickLogic(next: ScreenLogic) {
    setLogic(next);
    try {
      window.localStorage.setItem(LOGIC_KEY, next);
    } catch {
      // حافظهٔ محلی در دسترس نیست — انتخاب در همین نشست می‌ماند
    }
  }

  function onSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
      return;
    }
    setSortKey(key);
    setSortDir(key === 'symbol' ? 'asc' : 'desc');
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <StatusStrip feed={board.data} isLoading={board.isLoading} />
      <TapeBar
        counts={counts}
        active={active}
        logic={logic}
        onToggle={toggleTape}
        onLogic={pickLogic}
        onClear={() => setActive([])}
      />

      <div className="flex h-10 shrink-0 items-center gap-3 border-b border-line px-3">
        <h1 className="text-[13px] font-bold">تابلو</h1>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="جستجوی نماد…"
          className="h-7 w-56 rounded border border-line bg-panel px-2 text-[11.5px] outline-none placeholder:text-text-3 focus:border-line-strong"
        />
        <AssetFilter selected={assetTypes} onChange={setAssetTypes} />
        <span data-testid="board-count" className="num ms-auto text-[11px] text-text-3">
          {board.isLoading ? 'در حالِ بارگذاری…' : `${fmtInt(visible.length)} از ${fmtInt(rows.length)}`}
        </span>
      </div>

      {board.isError ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-[12px] text-text-2">
          <span>خوراکِ تابلو نمی‌رسد — {String((board.error as Error)?.message ?? '')}</span>
          <button
            type="button"
            onClick={() => void board.refetch()}
            className="rounded bg-panel-3 px-3 py-1 text-[11px] text-text hover:bg-line"
          >
            تلاشِ دوباره
          </button>
        </div>
      ) : board.isLoading ? (
        <div className="flex-1 space-y-1 p-2">
          {Array.from({ length: 18 }, (_, i) => (
            <div key={i} className="h-[28px] animate-pulse rounded bg-panel-2" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-[12px] text-text-3">
          ردیفی با این فیلترها نیست
        </div>
      ) : (
        <BoardTable rows={visible} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
      )}

      <div className="flex h-7 shrink-0 items-center gap-3 border-t border-line bg-panel px-3 text-[10.5px] text-text-3">
        <span>منبع: /api/market</span>
        <span>ارزش = ارزشِ معاملات (ریال) ÷ 10¹³</span>
      </div>
    </div>
  );
}
