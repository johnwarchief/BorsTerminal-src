import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { fmtInt } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { computeFeedStatus } from '@shared/lib/feedFreshness';
import { csvBlobParts, csvFilename, csvTextWithMeta, saveBlob } from '@shared/lib/tableExport';
import { useBoard } from '../api/useBoard';
import { BoardTable } from '../components/BoardTable';
import { BoardToolbar } from '../components/BoardToolbar';
import { TapeBar } from '../components/TapeBar';
import { boardExportTable } from '../lib/boardExport';
import { evaluateBoard } from '../lib/boardFilters';
import { defaultColumns, PROFILES, SORT_LABEL, sortRows, type ProfileKey, type SortDir, type SortKey } from '../lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { tapeLabel } from '../lib/tapeFilters';
import { useMarketPrefs } from '../stores/prefs';

interface Props {
  selectedKey: string | null;
  onSelect: (row: MarketRow, boardDay: number | null) => void;
  onActivate: (row: MarketRow, boardDay: number | null) => void;
  onFocusSearch?: () => void;
}

export function BoardPanel({ selectedKey, onSelect, onActivate, onFocusSearch }: Props) {
  const pollMs = useMarketPrefs((s) => s.pollMs);
  const board = useBoard(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);

  const profile = useMarketPrefs((s) => s.profile);
  const density = useMarketPrefs((s) => s.density);
  const quickFilters = useMarketPrefs((s) => s.quickFilters);
  const quickLogic = useMarketPrefs((s) => s.quickLogic);
  const assetTypes = useMarketPrefs((s) => s.assetTypes);
  const filters = useMarketPrefs((s) => s.filters);
  const columns = useMarketPrefs((s) => s.visibleColumns);
  const setProfile = useMarketPrefs((s) => s.setProfile);
  const setDensity = useMarketPrefs((s) => s.setDensity);
  const toggleColumn = useMarketPrefs((s) => s.toggleColumn);
  const toggleQuickFilter = useMarketPrefs((s) => s.toggleQuickFilter);
  const clearQuickFilters = useMarketPrefs((s) => s.clearQuickFilters);
  const setQuickLogic = useMarketPrefs((s) => s.setQuickLogic);
  const setAssetTypes = useMarketPrefs((s) => s.setAssetTypes);
  const setFilters = useMarketPrefs((s) => s.setFilters);
  const setPollMs = useMarketPrefs((s) => s.setPollMs);
  const savedViews = useMarketPrefs((s) => s.savedViews);
  const saveNamedView = useMarketPrefs((s) => s.saveView);
  const restoreNamedView = useMarketPrefs((s) => s.restoreView);
  const deleteNamedView = useMarketPrefs((s) => s.deleteView);

  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('value');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const boardDay = board.data?.meta?.d_even ?? null;

  const sectors = useMemo(() => [...new Set(
    rows.map((row) => row.sector_name).filter((sector): sector is string => typeof sector === 'string' && sector.length > 0),
  )].sort((a, b) => a.localeCompare(b, 'fa')), [rows]);

  const evaluation = useMemo(() => evaluateBoard(rows, {
    query,
    assetTypes,
    quickFilters,
    quickLogic,
    ...filters,
    filterConfig: DEFAULT_TAPE_FILTER_CONFIG,
  }), [rows, query, assetTypes, quickFilters, quickLogic, filters]);

  const visible = useMemo(
    () => sortRows(evaluation.visible, sortKey, sortDir),
    [evaluation.visible, sortKey, sortDir],
  );

  const feedStatus = useMemo(() => computeFeedStatus({
    status: board.status,
    dataUpdatedAt: board.dataUpdatedAt,
    dataChangedAt: board.data?.rev_at,
    liveCount: board.data?.live_count,
    totalCount: board.data?.count,
    now: Date.now(),
  }), [board.status, board.dataUpdatedAt, board.data]);

  function pickProfile(next: ProfileKey) {
    setProfile(next);
    const cols = defaultColumns(next);
    if (!(cols as string[]).includes(sortKey)) {
      setSortKey(cols.includes('value') ? 'value' : 'last');
      setSortDir('desc');
    }
  }

  function pickSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((dir) => (dir === 'desc' ? 'asc' : 'desc'));
      return;
    }
    setSortKey(key);
    setSortDir(key === 'symbol' ? 'asc' : 'desc');
  }

  function saveView(name: string) {
    saveNamedView(name, {
      query,
      sortKey,
      sortDir,
      profile,
      density,
      quickFilters,
      quickLogic,
      assetTypes,
      visibleColumns: columns,
      filters,
      pollMs,
    });
  }

  function applyView(name: string) {
    const state = restoreNamedView(name);
    if (!state) return;
    setQuery(state.query);
    setSortKey(state.sortKey);
    setSortDir(state.sortDir);
  }

  function exportBoard() {
    if (!board.data) return;
    const table = boardExportTable(visible, columns, DEFAULT_TAPE_FILTER_CONFIG);
    const meta: [string, string][] = [
      ['منبع', '/api/market'],
      ['روز تابلو', String(board.data.meta?.d_even ?? '—')],
      ['آخرین همگام‌سازی', board.data.meta?.last_sync ?? '—'],
      ['بازبینی', String(board.data.rev ?? '—')],
      ['پروفایل', PROFILES[profile].label],
      ['مرتب‌سازی', `${SORT_LABEL[sortKey]} · ${sortDir === 'desc' ? 'نزولی' : 'صعودی'}`],
      ['جستجو', query.trim() || '—'],
      ['فیلترهای تابلوخوانی', quickFilters.length
        ? `${quickFilters.map(tapeLabel).join('، ')} · ${quickLogic === 'and' ? 'همه' : 'حداقل یکی'}`
        : '—'],
      ['ردیف‌ها', fmtInt(visible.length)],
    ];
    saveBlob(
      new Blob(csvBlobParts(csvTextWithMeta(table, meta)), { type: 'text/csv;charset=utf-8' }),
      csvFilename('تابلوخوانی'),
    );
  }

  if (board.isError && !board.data) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 bg-bg">
        <span className="t-115 text-text-2">خوراکِ تابلو نمی‌رسد — ‎/api/market</span>
        <span className="max-w-[520px] text-center t-10 text-text-3">
          {String((board.error as Error)?.message ?? 'خطای نامشخص')}
        </span>
        <button
          type="button"
          onClick={() => void board.refetch()}
          className="mt-1 h-7 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-3 t-10 text-text hover:border-line-strong"
        >
          تلاشِ دوباره
        </button>
      </div>
    );
  }

  if (board.isLoading || !board.data) {
    return (
      <div className="flex min-h-0 flex-1 flex-col" aria-busy="true" aria-label="در حالِ بارگذاری تابلو">
        <div className="h-[37px] shrink-0 border-b border-line bg-panel" />
        <div className="h-[33px] shrink-0 border-b border-line bg-panel" />
        <div className="flex-1 space-y-1 overflow-hidden bg-bg p-2">
          {Array.from({ length: 16 }, (_, i) => (
            <div key={i} className="h-[30px] animate-pulse rounded-[var(--radius-xs)] bg-panel-2" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div data-density={density} className="grid min-h-0 flex-1 grid-rows-[37px_33px_minmax(0,1fr)]">
        <div className="min-w-0">
          <BoardToolbar
            query={query}
            onQuery={setQuery}
            profile={profile}
            onProfile={pickProfile}
            density={density}
            onDensity={setDensity}
            columns={columns}
            onToggleColumn={toggleColumn}
            assetTypes={assetTypes}
            onAssetTypes={setAssetTypes}
            filters={filters}
            onFilters={setFilters}
            sectors={sectors}
            pollMs={pollMs}
            onPollMs={setPollMs}
            savedViews={savedViews}
            onSaveView={saveView}
            onApplyView={applyView}
            onDeleteView={deleteNamedView}
            onExport={exportBoard}
            onFocusSearch={onFocusSearch}
          />
        </div>
        <div className="min-w-0">
          <TapeBar
            counts={evaluation.counts}
            unevaluated={evaluation.unevaluated}
            hiddenCounts={evaluation.hiddenCounts}
            baseCount={evaluation.baseCount}
            active={quickFilters}
            logic={quickLogic}
            onToggle={toggleQuickFilter}
            onClear={clearQuickFilters}
            onLogic={setQuickLogic}
          />
        </div>
        <div className="flex min-h-0 min-w-0 flex-col bg-panel">
          {visible.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-1 text-text-3">
              <b className="t-115 font-bold text-text-2">ردیفی با این فیلتر نیست</b>
              <span className="t-10">فیلترها، نوع دارایی یا جستجو را تغییر بده.</span>
            </div>
          ) : (
            <BoardTable
              rows={visible}
              columns={columns}
              sortKey={sortKey}
              sortDir={sortDir}
              density={density}
              filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
              selectedKey={selectedKey}
              resetKey={`${profile}|${query}|${quickFilters.join(',')}|${quickLogic}|${assetTypes.join(',')}|${JSON.stringify(filters)}|${sortKey}|${sortDir}`}
              onSort={pickSort}
              onSelect={(row) => onSelect(row, boardDay)}
              onActivate={(row) => onActivate(row, boardDay)}
            />
          )}
        </div>
      </div>

      <div
        data-testid="market-footer"
        className="flex h-[26px] shrink-0 items-center gap-3 border-t border-line bg-panel px-3 t-9 text-text-3"
      >
        <span data-testid="feed-state" role="status" className="flex min-w-0 items-center gap-1.5 text-text-2" title={feedStatus.label}>
          <i className={clsx('h-1.5 w-1.5 flex-none rounded-full', feedStatus.tone)} aria-hidden />
          <span className="max-w-[380px] truncate">{feedStatus.label}</span>
        </span>
        <span dir="ltr">/api/market</span>
        <span>·</span>
        <span>ارزش = میلیارد ریال</span>
        <span>·</span>
        <span>ارزش بازار = همت</span>
        <span>·</span>
        <span>حجم = م / هـ</span>
        <span className="ms-auto num" data-testid="board-count" aria-live="polite">
          {fmtInt(visible.length)} از {fmtInt(rows.length)}
        </span>
      </div>
    </div>
  );
}
