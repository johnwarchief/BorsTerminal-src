import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { faNum, fmtInt } from '@shared/lib/fa';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

const PASS_KEYS = ['i1_pass', 'i2_pass', 'i3_pass', 'i4_pass', 'i5_pass'] as const;

interface Props {
  rows: readonly ScreenerCoreRow[];
  onSelect: (symbol: string) => void;
}

export function FundamentalScreenTable({ rows, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('');
  const parentRef = useRef<HTMLDivElement>(null);

  const sectors = useMemo(() => [...new Set(
    rows.map((row) => row.sector_name).filter((s): s is string => Boolean(s)),
  )].sort((a, b) => a.localeCompare(b, 'fa')), [rows]);

  const filtered = useMemo(() => {
    const q = query.trim();
    return rows
      .filter((row) => (sector ? row.sector_name === sector : true))
      .filter((row) => (q
        ? row.symbol.includes(q) || (row.name ?? '').includes(q)
        : true))
      .slice()
      .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  }, [rows, query, sector]);

  const virtual = filtered.length > 200;
  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 30,
    overscan: 12,
    enabled: virtual,
  });
  const virtualItems = virtual ? virtualizer.getVirtualItems() : [];
  const bodyHeight = virtual ? virtualizer.getTotalSize() : 0;

  const renderRow = (row: ScreenerCoreRow) => (
    <div
      key={row.symbol}
      role="button"
      tabIndex={0}
      data-testid={`fundamental-row-${row.symbol}`}
      onClick={() => onSelect(row.symbol)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(row.symbol);
        }
      }}
      className="grid h-[30px] cursor-pointer grid-cols-[minmax(110px,1.2fr)_minmax(100px,1fr)_150px_70px_minmax(120px,1fr)] items-center gap-2 border-b border-line/60 px-2 t-10 hover:bg-panel-2 focus:bg-panel-2 focus:outline-none"
    >
      <span className="flex min-w-0 items-baseline gap-1">
        <b className="font-bold text-text">{row.symbol}</b>
        {row.name ? <span className="truncate t-85 text-text-3">{row.name}</span> : null}
      </span>
      <span className="truncate text-text-2">{row.sector_name ?? '—'}</span>
      <span className="flex items-center gap-1" aria-label="پنج شاخص">
        {PASS_KEYS.map((key, index) => {
          const pass = row[key];
          return (
            <span
              key={key}
              data-testid={`fundamental-chip-${row.symbol}-${index + 1}`}
              data-pass={pass === true ? 'true' : pass === false ? 'false' : 'na'}
              title={`${faNum(index + 1)}: ${pass === true ? 'قبول' : pass === false ? 'رد' : 'بی‌نظر'}`}
              className={`grid h-4 w-4 place-items-center rounded-[3px] border t-85 ${
                pass === true
                  ? 'border-up/45 bg-up/15 text-up'
                  : 'border-line bg-panel-2 text-text-3'
              }`}
            >
              {pass === true ? '✓' : '—'}
            </span>
          );
        })}
      </span>
      <span className="num text-center font-bold text-text">
        {row.score == null ? '—' : faNum(row.score, 0)}
      </span>
      <span className="truncate text-text-3">
        {row.excluded
          ? <span data-testid={`fundamental-excluded-${row.symbol}`} className="rounded-[3px] border border-warn/40 bg-warn/10 px-1 text-warn">خارج از پنج‌شاخص</span>
          : (row.verdict ?? '—')}
      </span>
    </div>
  );

  return (
    <div data-testid="fundamental-screen-table" className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-none flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <input
          data-testid="fundamental-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="جستجو در نماد یا نام…"
          aria-label="جستجوی بنیادی"
          className="h-[26px] min-w-[160px] flex-1 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 t-10 text-text outline-none placeholder:text-text-3 focus:border-line-strong"
        />
        <select
          aria-label="فیلتر صنعت بنیادی"
          value={sector}
          onChange={(event) => setSector(event.target.value)}
          className="h-[26px] max-w-[220px] rounded-[var(--radius-sm)] border border-line bg-panel-2 px-1.5 t-10 text-text outline-none focus:border-line-strong"
        >
          <option value="">همه صنایع</option>
          {sectors.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <span data-testid="fundamental-count" className="num t-9 text-text-3">
          {fmtInt(filtered.length)} از {fmtInt(rows.length)}
        </span>
      </div>

      <div className="grid h-[27px] flex-none grid-cols-[minmax(110px,1.2fr)_minmax(100px,1fr)_150px_70px_minmax(120px,1fr)] items-center gap-2 border-b border-line-strong bg-panel-2 px-2 t-9 font-bold text-text-3">
        <span>نماد</span>
        <span>صنعت</span>
        <span>پنج شاخص</span>
        <span className="text-center">امتیاز</span>
        <span>وضعیت</span>
      </div>

      <div ref={parentRef} className="min-h-0 flex-1 overflow-auto">
        {filtered.length === 0 ? (
          <p data-testid="fundamental-empty" className="p-3 t-10 text-text-3">ردیفی با این فیلتر نیست.</p>
        ) : virtual ? (
          <div style={{ height: bodyHeight, position: 'relative' }}>
            {virtualItems.map((item) => {
              const row = filtered[item.index];
              return row ? (
                <div key={item.key} style={{ position: 'absolute', insetInline: 0, top: item.start }}>
                  {renderRow(row)}
                </div>
              ) : null;
            })}
          </div>
        ) : filtered.map(renderRow)}
      </div>
    </div>
  );
}
