import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import clsx from 'clsx';
import { changePct, fmtHemmat, fmtInt, fmtPct, fmtShare } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { TAPES, tapeOn } from '../lib/tapeFilters';
import { SORT_LABEL, type SortDir, type SortKey } from '../lib/boardSort';

const COLS = '120px 150px 90px 84px 96px 110px 88px 1fr';
const HEADERS: SortKey[] = ['symbol', 'last', 'change', 'value', 'volume'];

interface Props {
  rows: readonly MarketRow[];
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
}

function changeClass(pct: number | null): string {
  if (pct == null) return 'text-text-3';
  if (pct > 0) return 'text-up';
  if (pct < 0) return 'text-down';
  return 'text-flat';
}

export function BoardTable({ rows, sortKey, sortDir, onSort }: Props) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 30,
    overscan: 14,
  });

  return (
    <div ref={parentRef} data-testid="board-table" className="min-h-0 flex-1 overflow-auto">
      <div className="min-w-[980px]">
        <div
          className="sticky top-0 z-10 grid h-8 items-center border-b border-line bg-panel-2 px-2 text-[10.5px] text-text-3"
          style={{ gridTemplateColumns: COLS }}
        >
          <span>نماد</span>
          <span>صنعت</span>
          {HEADERS.slice(1).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => onSort(key)}
              className={clsx('text-start hover:text-text', sortKey === key && 'text-accent')}
            >
              {SORT_LABEL[key]}
              {sortKey === key ? (sortDir === 'desc' ? ' ▼' : ' ▲') : ''}
              {key === 'value' ? ' (همت)' : ''}
            </button>
          ))}
          <span>حقیقیِ خرید</span>
          <span>نشان‌ها</span>
        </div>

        <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = rows[item.index];
            const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
            const activeTapes = TAPES.filter((t) => tapeOn(row, t.key));
            return (
              <div
                key={row.ins_code ?? `${row.symbol}-${item.index}`}
                data-testid="board-row"
                className="absolute inset-x-0 grid h-[30px] items-center border-b border-line/50 px-2 text-[11.5px] hover:bg-panel-2"
                style={{ transform: `translateY(${item.start}px)`, gridTemplateColumns: COLS }}
              >
                <span className="truncate font-semibold" title={row.name ?? row.symbol}>
                  {row.symbol}
                </span>
                <span className="truncate text-text-2" title={row.sector_name ?? ''}>
                  {row.sector_name ?? '—'}
                </span>
                <span className="num">{fmtInt(row.p_last ?? row.p_closing)}</span>
                <span className={clsx('num', changeClass(pct))} dir="ltr">
                  {fmtPct(pct)}
                </span>
                <span className="num text-text-2">{fmtHemmat(row.q_tot_cap)}</span>
                <span className="num text-text-2">{fmtInt(row.q_tot_tran)}</span>
                <span className="num text-text-2">{fmtShare(row.retail_buy_pct)}</span>
                <span className="flex items-center gap-1 overflow-hidden">
                  {activeTapes.map((t) => (
                    <span
                      key={t.key}
                      title={t.label}
                      className="inline-block h-[6px] w-[6px] shrink-0 rounded-full bg-accent"
                    />
                  ))}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
