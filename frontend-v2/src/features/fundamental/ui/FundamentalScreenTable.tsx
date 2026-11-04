import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { fmtInt, toFaDigits } from '@shared/lib/fa';
import { downloadCsvWithMeta } from '@shared/lib/tableExport';
import { useFundamentalPrefs, type Density, type SortKey, type Surface } from '../stores/prefs';
import {
  AXES,
  formatAxisValue,
  statusFa,
  statusOf,
  thresholdOf,
  verdictFa,
  type AxisKey,
  type AxisStatus,
  type AxisThresholds,
} from '../lib/axisMeta';
import { EXCLUDE_LABEL, applyExcludeFilter, useExcludeAxes } from '../lib/exclusionFilter';
import { FundamentalAxisCell, STATUS_ICON } from './FundamentalAxisCell';
import { AxisGlyph } from './mini/AxisGlyph';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

const COLUMNS = '38px 154px repeat(5, minmax(112px, 1fr)) 62px 88px';
const VIRTUAL_THRESHOLD = 80;
const STATUSES: readonly AxisStatus[] = ['pass', 'fail', 'na', 'unknown'];

// رتبهٔ رژیم برای مرتب‌سازی محور ۵؛ رژیمِ نامعلوم null می‌ماند تا آخر بیاید.
const REGIME_RANK: Record<string, number> = { free: 0, neutral: 1, mandatory: 2 };

function lastEps(row: ScreenerCoreRow): number | null {
  return Array.isArray(row.eps_series) && row.eps_series.length
    ? row.eps_series[row.eps_series.length - 1] ?? null
    : null;
}

function sortValue(row: ScreenerCoreRow, key: SortKey): number | string | null {
  switch (key) {
    case 'symbol': return row.symbol;
    case 'score': return row.score ?? null;
    case 'growth': return row.rev_growth ?? null;
    // R29: محور ۲ با سال‌های موجود مرتب می‌شود، همان چیزی که ستون نشان می‌دهد.
    case 'eps': return row.eps_years_available ?? null;
    case 'margin': return row.gross_margin ?? null;
    // R16: محور ۴ فقط sales_to_mcap؛ هرگز profit_potential_pct.
    case 'sales': return row.sales_to_mcap ?? null;
    case 'industry': return REGIME_RANK[row.pricing_mode ?? ''] ?? null;
  }
}

function tiebreakValue(row: ScreenerCoreRow, key: SortKey): number | null {
  return key === 'eps' ? lastEps(row) : null;
}

function compareRows(a: ScreenerCoreRow, b: ScreenerCoreRow, key: SortKey, dir: 'asc' | 'desc'): number {
  const av = sortValue(a, key);
  const bv = sortValue(b, key);
  // ردیف‌های بی‌مقدار در هر دو جهت آخر می‌مانند.
  if (av == null || bv == null) {
    if (av == null && bv == null) return 0;
    return av == null ? 1 : -1;
  }
  const raw = typeof av === 'string' || typeof bv === 'string'
    ? String(av).localeCompare(String(bv), 'fa')
    : Number(av) - Number(bv);
  if (raw !== 0) return dir === 'asc' ? raw : -raw;
  const at = tiebreakValue(a, key);
  const bt = tiebreakValue(b, key);
  if (at == null || bt == null) {
    if (at == null && bt == null) return 0;
    return at == null ? 1 : -1;
  }
  return dir === 'asc' ? at - bt : bt - at;
}

function axisThresholdLabel(thresholds: AxisThresholds | null | undefined, axis: AxisKey): string {
  if (axis === 'eps') return '۳ سال';
  if (axis === 'industry') return 'رژیم';
  const threshold = thresholdOf(thresholds, axis);
  if (threshold == null) return '—';
  if (axis === 'sales') return `≥ ${toFaDigits(threshold.toFixed(2)).replace('.', '٫')}`;
  return `≥ ${toFaDigits(threshold)}٪`;
}

interface Props {
  rows: readonly ScreenerCoreRow[];
  thresholds?: AxisThresholds | null;
  onSelect: (symbol: string) => void;
  asOf?: string | null;
  settingsSlot?: ReactNode;
}

export function FundamentalScreenTable({ rows, thresholds, onSelect, asOf, settingsSlot }: Props) {
  const density = useFundamentalPrefs((state) => state.density);
  const surface = useFundamentalPrefs((state) => state.surface);
  const setDensity = useFundamentalPrefs((state) => state.setDensity);
  const sortKey = useFundamentalPrefs((state) => state.sortKey);
  const sortDir = useFundamentalPrefs((state) => state.sortDir);
  const setSort = useFundamentalPrefs((state) => state.setSort);
  const excludeAxes = useExcludeAxes();
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('');
  const [fading, setFading] = useState(false);
  const appearanceRef = useRef<{ density: Density; surface: Surface } | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const excluded = useMemo(() => applyExcludeFilter(rows, excludeAxes), [rows, excludeAxes]);

  const filtered = useMemo(() => {
    const needle = query.trim();
    return excluded.rows
      .filter((row) => (sector ? row.sector_name === sector : true))
      .filter((row) => (needle ? row.symbol.includes(needle) || (row.name ?? '').includes(needle) : true))
      .slice()
      .sort((a, b) => compareRows(a, b, sortKey, sortDir));
  }, [excluded.rows, query, sector, sortKey, sortDir]);

  const virtual = filtered.length > VIRTUAL_THRESHOLD;
  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => (density === 'comfortable' ? 88 : 38),
    // R84: overscan از ۱۴ به ۸ کم شد تا تعداد ردیف‌های سوارشده در هر به‌روزرسانی اسکرول
    // (و در نتیجه سلول‌ها/نمودارهای SVG) کم‌تر شود؛ رفتار دیداری تغییری نمی‌کند.
    overscan: 8,
    enabled: virtual,
  });
  const bodyHeight = virtual ? virtualizer.getTotalSize() : 0;
  useEffect(() => {
    if (virtual && parentRef.current) virtualizer.measure();
  }, [density, virtual, virtualizer]);

  // R78: تغییر density یا سطح یک‌بار محوِ ۱۶۰ms روی بدنهٔ جدول می‌زند؛
  // نصب اولیه و حالت کاهش حرکت از این dip مستثنا هستند و تایمر پاک می‌شود.
  useEffect(() => {
    const previous = appearanceRef.current;
    appearanceRef.current = { density, surface };
    if (!previous || (previous.density === density && previous.surface === surface)) return;
    const reduceMotion = typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;
    setFading(true);
    const timer = window.setTimeout(() => setFading(false), 160);
    return () => window.clearTimeout(timer);
  }, [density, surface]);

  const sectors = useMemo(() => [...new Set(
    rows.map((row) => row.sector_name).filter((value): value is string => Boolean(value)),
  )].sort((a, b) => a.localeCompare(b, 'fa')), [rows]);

  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' => (
    sortKey === key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'
  );

  const sortButton = (key: SortKey, label: string) => (
    <button
      type="button"
      onClick={() => setSort(key, sortKey === key && sortDir === 'desc' ? 'asc' : 'desc')}
      aria-label={`مرتب‌سازی ${label}`}
      className="inline-flex items-center gap-1 text-start focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--fd-accent)]"
    >
      {label}
      <span aria-hidden>{sortKey === key ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}</span>
    </button>
  );

  function exportCsv() {
    const columns = ['نماد', 'نام', 'صنعت شرکت', 'رشد', 'سودآوری', 'حاشیه', 'فروش/ارزش', 'صنعت', 'امتیاز', 'وضعیت'];
    const csvRows = filtered.map((row) => [
      row.symbol,
      row.name ?? '',
      row.sector_name ?? '',
      formatAxisValue(row.rev_growth ?? null, 'growth'),
      row.eps_years_available == null ? '—/۳' : `${toFaDigits(row.eps_years_available)}/۳`,
      formatAxisValue(row.gross_margin ?? null, 'margin'),
      formatAxisValue(row.sales_to_mcap ?? null, 'sales'),
      formatAxisValue(row.pricing_mode ?? null, 'industry'),
      row.score ?? '',
      verdictFa(row.verdict),
    ]);
    const meta: Array<[string, string]> = [
      ['آستانه رشد', String(thresholds?.growth_min ?? '—')],
      ['آستانه حاشیه', String(thresholds?.margin_min ?? '—')],
      ['آستانه فروش/ارزش', String(thresholds?.v10_sales_to_mcap_min ?? '—')],
      ['زمان اسکن', asOf ?? '—'],
    ];
    downloadCsvWithMeta('غربالگری-بنیادی', { columns, rows: csvRows }, meta);
  }

  const renderRow = (row: ScreenerCoreRow) => (
    <div
      key={row.symbol}
      role="row"
      tabIndex={0}
      data-testid={`fundamental-row-${row.symbol}`}
      onClick={() => onSelect(row.symbol)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(row.symbol);
        }
      }}
      className="fd-row grid cursor-pointer items-center border-b border-[var(--fd-line)] hover:bg-[var(--fd-panel-2)]"
      style={{ gridTemplateColumns: COLUMNS, minHeight: density === 'comfortable' ? 88 : 38 }}
    >
      <div role="cell" className="flex h-full items-center justify-center py-1">
        <AxisGlyph statuses={AXES.map((axis) => statusOf(row, axis.key))} labels={AXES.map((axis) => axis.short)} />
      </div>
      <div role="cell" className="min-w-0 px-2 py-1">
        <b className="block truncate text-[12px] font-medium text-[var(--fd-text)]">{row.symbol}</b>
        <span className="block truncate text-[9.5px] text-[var(--fd-text-3)]">{row.name ?? '—'} · {row.sector_name ?? '—'}</span>
        {row.i4_na ? (
          <span data-testid={`fundamental-bank-${row.symbol}`} className="mt-0.5 inline-block rounded border border-[var(--fd-line-strong)] px-1 text-[9px] text-[var(--fd-text-3)]">بانک / N/A</span>
        ) : null}
        {row.excluded ? (
          <span data-testid={`fundamental-excluded-${row.symbol}`} className="mt-0.5 inline-block rounded border border-[var(--fd-warn)] px-1 text-[9px] text-[var(--fd-warn)]">خارج از غربال</span>
        ) : null}
      </div>
      {AXES.map((axis) => <FundamentalAxisCell key={axis.key} row={row} axis={axis.key} thresholds={thresholds} />)}
      <div role="cell" className="text-center text-[12px] font-medium tabular-nums text-[var(--fd-text)]">
        {row.score == null ? '—' : `${toFaDigits(row.score)}/۵`}
      </div>
      <div role="cell" className="flex justify-center">
        <span
          data-testid={`fundamental-verdict-${row.symbol}`}
          className={`rounded border px-1 text-[9px] ${row.verdict === 'STRONG' ? 'border-[var(--fd-up)] text-[var(--fd-up)]' : row.verdict === 'REJECT' || row.verdict === 'EXCLUDED' ? 'border-[var(--fd-down)] text-[var(--fd-down)]' : 'border-[var(--fd-warn)] text-[var(--fd-warn)]'}`}
        >
          {verdictFa(row.verdict)}
        </span>
      </div>
    </div>
  );

  return (
    <div data-testid="fundamental-screen-table" className="flex min-h-0 flex-1 flex-col text-[var(--fd-text)]">
      <div className="flex flex-none flex-wrap items-center gap-2 border-b border-[var(--fd-line)] px-3 py-2">
        <input
          data-testid="fundamental-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="جستجو در نماد یا نام…"
          aria-label="جستجوی بنیادی"
          className="h-[26px] min-w-[150px] flex-1 rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] px-2 text-[11px] text-[var(--fd-text)] outline-none placeholder:text-[var(--fd-text-3)] focus:border-[var(--fd-line-strong)]"
        />
        <select
          aria-label="فیلتر صنعت"
          value={sector}
          onChange={(event) => setSector(event.target.value)}
          className="h-[26px] max-w-[210px] rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] px-1.5 text-[11px] text-[var(--fd-text)] outline-none focus:border-[var(--fd-line-strong)]"
        >
          <option value="">همه صنایع</option>
          {sectors.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <button type="button" data-testid="fundamental-export" onClick={exportCsv}
          className="tape-btn" title="خروجی CSV از ردیف‌های همین فیلتر">
          خروجی CSV
        </button>
        <div role="group" aria-label="تراکم جدول" className="inline-flex items-center gap-1">
          <button
            type="button"
            data-testid="fundamental-density-compact"
            aria-pressed={density === 'compact'}
            onClick={() => setDensity('compact')}
            className="tape-btn"
            title="ردیف‌های فشرده، بدون نمودار"
          >
            فشرده
          </button>
          <button
            type="button"
            data-testid="fundamental-density-comfortable"
            aria-pressed={density === 'comfortable'}
            onClick={() => setDensity('comfortable')}
            className="tape-btn"
            title="ردیف‌های راحت با نمودار محورها"
          >
            راحت
          </button>
        </div>
        {settingsSlot ?? <span />}
        <span data-testid="fundamental-count" className="num t-9 text-[var(--fd-text-3)]">
          {fmtInt(filtered.length)} از {fmtInt(rows.length)}
        </span>
        {excluded.hidden > 0 ? (
          <span
            data-testid="fundamental-hidden-count"
            title={excludeAxes.map((axis) => EXCLUDE_LABEL[axis]).join(' · ')}
            className="num t-9 text-[var(--fd-warn)]"
          >
            {fmtInt(excluded.hidden)} حذف‌شده
          </span>
        ) : null}
      </div>

      <div role="table" aria-label="جدول بنیادی" className="flex min-h-0 flex-1 flex-col">
        <div
          role="row"
          className="grid flex-none items-center border-b border-[var(--fd-line-strong)] bg-[var(--fd-panel-2)] px-1.5 text-[10px] text-[var(--fd-text-3)]"
          style={{ gridTemplateColumns: COLUMNS, minHeight: 55 }}
        >
          <span role="columnheader" aria-label="نمای پنج‌محور" className="text-center" />
          <span role="columnheader" aria-sort={ariaSort('symbol')} className="min-w-0 px-1.5">
            {sortButton('symbol', 'نماد')}
            <span className="block truncate text-[9px]">نام · صنعت</span>
          </span>
          {AXES.map((axis) => (
            <span key={axis.key} role="columnheader" aria-sort={ariaSort(axis.key)} className="min-w-0 px-1.5">
              <span className="flex items-baseline gap-1 text-[11px] text-[var(--fd-text)]">
                <span className="text-[9px] text-[var(--fd-text-3)]">{axis.num}</span>
                {sortButton(axis.key, axis.label)}
              </span>
              <span className="block truncate text-[9px]">{axisThresholdLabel(thresholds, axis.key)}</span>
            </span>
          ))}
          <span role="columnheader" aria-sort={ariaSort('score')} className="justify-self-center">
            {sortButton('score', 'امتیاز')}
          </span>
          <span role="columnheader" className="text-center">وضعیت</span>
        </div>

        <div ref={parentRef} className={`fd-scroll min-h-0 flex-1 overflow-auto${fading ? ' is-fading' : ''}`}>
          {filtered.length === 0 ? (
            <p data-testid="fundamental-empty" className="p-3 text-[11px] text-[var(--fd-text-3)]">ردیفی با این فیلتر نیست.</p>
          ) : virtual ? (
            <div role="rowgroup" style={{ height: bodyHeight, position: 'relative' }}>
              {virtualizer.getVirtualItems().map((item) => {
                const row = filtered[item.index];
                return row ? (
                  <div
                    key={item.key}
                    role="presentation"
                    data-index={item.index}
                    ref={virtualizer.measureElement}
                    style={{ position: 'absolute', insetInline: 0, top: item.start }}
                  >
                    {renderRow(row)}
                  </div>
                ) : null;
              })}
            </div>
          ) : (
            <div role="rowgroup">{filtered.map(renderRow)}</div>
          )}
        </div>
      </div>

      <div
        data-testid="fundamental-legend"
        className="flex flex-none flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-3 py-1.5 text-[9.5px] text-[var(--fd-text-3)]"
      >
        <span className="inline-flex items-center gap-1">
          <span aria-hidden className="inline-block w-4 border-t border-dashed border-[var(--fd-accent)]" />
          خط آستانه (خط‌چین)
        </span>
        {AXES.map((axis) => (
          <span key={axis.key} className="whitespace-nowrap">{axis.num} {axis.label}</span>
        ))}
        {STATUSES.map((status) => (
          <span key={status} className={`fd-status fd-status--${status} inline-flex items-center gap-0.5`}>
            <span aria-hidden>{STATUS_ICON[status]}</span> {statusFa(status)}
          </span>
        ))}
      </div>
    </div>
  );
}
