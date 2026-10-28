import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import clsx from 'clsx';
import { changePct, faNum, fmtInt, fmtMcap, fmtPct, fmtPe, fmtPrice, fmtValue, fmtVolume, toFaDigits, tone } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import {
  COLUMNS,
  gridTemplate,
  isSortable,
  type ColumnKey,
  type SortDir,
  type SortKey,
} from '../lib/columns';
import type { TapeFilterConfig } from '../lib/tapeAlgorithms';
import { patternBadges } from '../lib/tapeBadges';
import { buyPerCapitaMt, buySellShare, sellPerCapitaMt } from '../lib/tapeFts';
import { lastCloseDiff } from '../lib/tapePatterns';
import type { Density } from '../stores/prefs';

const ROW_HEIGHTS: Record<Density, [number, number]> = {
  compact: [30, 34],
  normal: [36, 40],
  comfortable: [44, 48],
};

const BADGE_CAP: Record<Density, number> = { compact: 2, normal: 3, comfortable: 4 };

function useRowHeight(density: Density): number {
  const [wide, setWide] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 2200px)').matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(min-width: 2200px)');
    const on = () => setWide(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  const [base, large] = ROW_HEIGHTS[density];
  return wide ? large : base;
}

function BuySellValue({ row }: { row: MarketRow }) {
  const buy = buyPerCapitaMt(row);
  const sell = sellPerCapitaMt(row);
  const share = buySellShare(buy, sell);
  return (
    <span data-testid="tape-buy-sell" className="flex min-w-0 flex-col gap-0.5">
      <span className="flex min-w-0 items-baseline justify-between gap-1 t-85 leading-none">
        <span className="num text-up">{buy == null ? '—' : `${faNum(buy, 1)} م.ت`}</span>
        <span className="num text-down">{sell == null ? '—' : `${faNum(sell, 1)} م.ت`}</span>
      </span>
      <span className="flex min-w-0 items-center gap-1">
        <span aria-hidden className="flex h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-panel-3">
          {share != null && (
            <>
              <span className="bg-up" style={{ width: `${share * 100}%` }} />
              <span className="bg-down" style={{ width: `${(1 - share) * 100}%` }} />
            </>
          )}
        </span>
        <span className="num shrink-0 t-9 text-text-2">
          {row.buyer_power == null ? '—' : `${toFaDigits(row.buyer_power.toFixed(2))}×`}
        </span>
      </span>
    </span>
  );
}

interface Props {
  rows: readonly MarketRow[];
  columns: readonly ColumnKey[];
  sortKey: SortKey;
  sortDir: SortDir;
  density: Density;
  filterConfig: TapeFilterConfig;
  selectedKey: string | null;
  resetKey: string;
  onSort: (key: SortKey) => void;
  onSelect: (row: MarketRow) => void;
}

export function BoardTable({
  rows,
  columns,
  sortKey,
  sortDir,
  density,
  filterConfig,
  selectedKey,
  resetKey,
  onSort,
  onSelect,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const rowH = useRowHeight(density);
  const template = gridTemplate(columns);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const focusPending = useRef(false);
  const focusWithin = useRef(false);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowH,
    overscan: 14,
  });
  const virtualItems = virtualizer.getVirtualItems();

  useEffect(() => {
    virtualizer.measure();
  }, [rowH, virtualizer]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
    focusPending.current = false;
    setFocusedIndex(0);
  }, [resetKey]);

  useEffect(() => {
    setFocusedIndex((current) => {
      const next = Math.min(current, Math.max(0, rows.length - 1));
      if (next !== current && focusWithin.current) focusPending.current = true;
      return next;
    });
  }, [rows.length]);

  useEffect(() => {
    if (!focusPending.current) return;
    const target = scrollRef.current?.querySelector<HTMLElement>(`[data-board-index="${focusedIndex}"]`);
    if (!target) return;
    target.focus({ preventScroll: true });
    focusPending.current = false;
  });

  function moveFocus(index: number) {
    if (rows.length === 0) return;
    const next = Math.max(0, Math.min(rows.length - 1, index));
    focusPending.current = true;
    setFocusedIndex(next);
    virtualizer.scrollToIndex(next, { align: 'auto' });
  }

  return (
    <div
      ref={scrollRef}
      data-testid="board-table"
      role="table"
      aria-label="تابلوی بازار"
      aria-rowcount={rows.length + 1}
      onFocusCapture={() => { focusWithin.current = true; }}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) focusWithin.current = false;
      }}
      className="min-h-0 flex-1 overflow-auto"
    >
      <div
        role="row"
        data-testid="board-head"
        className="sticky top-0 z-[3] grid h-[27px] min-w-full items-center border-b border-line-strong bg-panel-2"
        style={{ gridTemplateColumns: template }}
      >
        {columns.map((key) => {
          const def = COLUMNS[key];
          const sortable = isSortable(key);
          const active = sortable && sortKey === key;
          return (
            <div key={key} role="columnheader" className="h-full min-w-0">
              {sortable ? (
                <button
                  type="button"
                  data-sort={key}
                  onClick={() => onSort(key)}
                  title={def.hint}
                  className={clsx(
                    'flex h-full w-full items-center gap-[3px] whitespace-nowrap px-[9px] t-9 font-bold tracking-[0.02em]',
                    def.num && 'justify-end',
                    active ? 'text-accent' : 'text-text-3 hover:text-text-2',
                  )}
                >
                  {def.label}
                  {active && <span className="text-[8px]">{sortDir === 'desc' ? '▼' : '▲'}</span>}
                </button>
              ) : (
                <span className="flex h-full items-center whitespace-nowrap px-[9px] t-9 font-bold tracking-[0.02em] text-text-3">
                  {def.label}
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }} className="min-w-full">
        {virtualItems.map((item) => {
          const row = rows[item.index];
          if (!row) return null;
          const selected = (row.ins_code?.trim() || row.symbol) === selectedKey;
          const badges = patternBadges(row, filterConfig);
          const shown = badges.slice(0, BADGE_CAP[density]);
          const hidden = badges.slice(BADGE_CAP[density]);
          const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
          const pctTone = tone(pct);
          const diff = lastCloseDiff(row);
          const diffPct = diff == null ? null : diff * 100;
          const diffTone = tone(diffPct);
          const lastTone = tone(row.percent_last);

          return (
            <div
              key={row.ins_code ?? `${row.symbol}-${item.index}`}
              role="row"
              data-testid="board-row"
              data-board-index={item.index}
              data-selected={selected}
              aria-selected={selected}
              aria-rowindex={item.index + 2}
              tabIndex={item.index === focusedIndex ? 0 : -1}
              onFocus={() => setFocusedIndex(item.index)}
              onClick={() => onSelect(row)}
              onKeyDown={(event) => {
                if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
                  event.preventDefault();
                  moveFocus(
                    event.key === 'ArrowDown' ? item.index + 1
                      : event.key === 'ArrowUp' ? item.index - 1
                        : event.key === 'Home' ? 0
                          : rows.length - 1,
                  );
                  return;
                }
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelect(row);
                }
              }}
              className="board-row absolute inset-x-0 grid items-center"
              style={{ height: rowH, fontSize: 'var(--row-fs)', transform: `translateY(${item.start}px)`, gridTemplateColumns: template }}
            >
              {columns.map((key) => {
                if (key === 'symbol') {
                  return (
                    <div key={key} role="cell" className="min-w-0 overflow-hidden px-[9px]">
                      <div className="flex min-w-0 flex-col leading-[1.25]">
                        <span className="overflow-hidden text-ellipsis whitespace-nowrap text-[11px] font-bold text-text">
                          {row.symbol}
                        </span>
                        <span className="overflow-hidden text-ellipsis whitespace-nowrap t-9 text-text-3">
                          {row.name ?? '—'}
                        </span>
                      </div>
                    </div>
                  );
                }
                if (key === 'patterns') {
                  return (
                    <div key={key} role="cell" className="flex min-w-0 items-center gap-[2px] overflow-hidden px-[9px]">
                      {shown.length > 0 ? shown.map((badge) => (
                        <span key={badge.key} data-testid={`badge-${badge.key}`} className="sym-badge" title={badge.title}>
                          {badge.label}
                        </span>
                      )) : <span className="text-text-3">—</span>}
                      {hidden.length > 0 && (
                        <span className="flex-none t-85 text-text-3" title={hidden.map((badge) => badge.title).join('\n')}>
                          +{fmtInt(hidden.length)}
                        </span>
                      )}
                    </div>
                  );
                }
                if (key === 'buy_sell') {
                  return <div key={key} role="cell" className="min-w-0 overflow-hidden px-[9px]"><BuySellValue row={row} /></div>;
                }

                let content: ReactNode;
                let className = 'num min-w-0 overflow-hidden whitespace-nowrap px-[9px] text-end';
                switch (key) {
                  case 'last':
                    content = fmtPrice(row.p_last ?? row.p_closing);
                    className += ' font-semibold text-text';
                    break;
                  case 'close':
                    content = fmtPrice(row.p_closing);
                    className += ' text-text-2';
                    break;
                  case 'last_vs_close':
                    content = fmtPct(diffPct);
                    className += clsx(
                      ' font-bold',
                      diffTone === 'up' ? ' text-up' : diffTone === 'down' ? ' text-down' : ' text-flat',
                    );
                    break;
                  case 'pct_close':
                    content = fmtPct(pct);
                    className += clsx(
                      ' font-bold',
                      pctTone === 'up' ? ' text-up' : pctTone === 'down' ? ' text-down' : ' text-flat',
                    );
                    break;
                  case 'pct_last':
                    content = fmtPct(row.percent_last);
                    className += clsx(
                      ' font-bold',
                      lastTone === 'up' ? ' text-up' : lastTone === 'down' ? ' text-down' : ' text-flat',
                    );
                    break;
                  case 'volume':
                    content = fmtVolume(row.q_tot_tran);
                    className += ' text-text-2';
                    break;
                  case 'value':
                    content = fmtValue(row.q_tot_cap);
                    className += ' text-text-2';
                    break;
                  case 'trades':
                    content = fmtInt(row.z_tot_tran);
                    className += ' text-text-2';
                    break;
                  case 'vol_ratio':
                    content = row.vol_ratio == null ? '—' : `${faNum(row.vol_ratio, 1)}×`;
                    className += ' text-text-2';
                    break;
                  case 'pe':
                    content = fmtPe(row.pe);
                    className += ' text-text-2';
                    break;
                  case 'mcap':
                    content = fmtMcap(row.mcap);
                    className += ' text-text-2';
                    break;
                  default:
                    content = '—';
                }

                return <div key={key} role="cell" className={className}>{content}</div>;
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
