// features/market/components/TapeTable.tsx -- جدول مجازی تابلو
// ردیف ها با React.memo و کلید نماد؛ فقط ردیف های دیدنی رندر می شوند.
import { memo, useMemo, useRef, useState, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { MarketRow } from '@shared/types/marketRow';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { EmptyState } from '@shared/components/EmptyState';
import { FlashNum } from '@shared/components/FlashNum';
import {
  BOX_EXIT_HINT,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_HINT,
  SWEEP_VOL_RATIO_MIN,
  detectBoxExit,
  detectStrongHour,
  detectSweep,
  lastCloseDiff,
} from '../lib/tapePatterns';
import { LIMIT_PCT } from '../stores/tapeStore';
import { RowBasketAction } from './RowBasketAction';

type SortKey = 'symbol' | 'percent_change' | 'tvol' | 'vol_ratio' | 'buyer_power' | 'last_vs_close' | 'p_last';

/** ۹ ستون: شماره + ۷ ستون داده + ستون اکشن سبد */
const ROW_GRID = 'grid-cols-[2rem_1.4fr_1fr_1fr_1.1fr_0.9fr_0.9fr_1.8fr_4rem]';

const HEADERS: { key: SortKey; label: string }[] = [
  { key: 'symbol', label: 'نماد' },
  { key: 'p_last', label: 'آخرین' },
  { key: 'percent_change', label: 'تغییر' },
  { key: 'tvol', label: 'حجم' },
  { key: 'vol_ratio', label: 'نسبت حجم' },
  { key: 'buyer_power', label: 'قدرت خریدار' },
  { key: 'last_vs_close', label: 'اختلاف آخرین/پایانی (Δ)' },
];

function sortVal(r: MarketRow, key: SortKey): number | string {
  switch (key) {
    case 'symbol':
      return r.symbol ?? '';
    case 'p_last':
      return r.p_last ?? Number.NEGATIVE_INFINITY;
    case 'percent_change':
      return r.percent_change ?? Number.NEGATIVE_INFINITY;
    case 'tvol':
      return r.tvol ?? Number.NEGATIVE_INFINITY;
    case 'vol_ratio':
      return r.vol_ratio ?? Number.NEGATIVE_INFINITY;
    case 'buyer_power':
      return r.buyer_power ?? Number.NEGATIVE_INFINITY;
    case 'last_vs_close':
      return lastCloseDiff(r) ?? Number.NEGATIVE_INFINITY;
  }
}

/** رنگ ردیف از روی جهت و صف -- فقط رنگ متن، بدون بکس‌های درشت */
function pctTone(pct: number | null | undefined): string {
  if (pct == null) return 'text-text-muted';
  if (pct >= LIMIT_PCT) return 'text-accent-green font-bold';
  if (pct > 0) return 'text-accent-green';
  if (pct <= -LIMIT_PCT) return 'text-accent-red font-bold';
  if (pct < 0) return 'text-accent-red';
  return 'text-text-secondary';
}

const MICRO_TONES = {
  violet: 'bg-[#8b5cf6]/15 text-[#c4b5fd]',
  amber: 'bg-accent-yellow/15 text-accent-yellow',
  cyan: 'bg-neon-cyan/15 text-neon-cyan',
  emerald: 'bg-accent-green/15 text-accent-green',
  green: 'bg-accent-green/15 text-accent-green',
  red: 'bg-accent-red/15 text-accent-red',
  gray: 'bg-bg-card text-text-muted',
} as const;

type MicroTone = keyof typeof MICRO_TONES;

/** میکرو-بج متنی های‌دنسیتی؛ جزئیات عددی در title (Tooltip) هر بج */
function MicroBadge({ pattern, tone, title, children }: { pattern: string; tone: MicroTone; title: string; children: React.ReactNode }) {
  return (
    <span
      data-testid={`badge-${pattern}`}
      data-pattern={pattern}
      title={title}
      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${MICRO_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** tooltip یکپارچهٔ ردیف: جزئیات عددی که از چشمِ بج‌ها برداشته شده */
export function rowTooltip(r: MarketRow): string {
  const bits: string[] = [];
  if (typeof r.vol_ratio === 'number' && Number.isFinite(r.vol_ratio)) {
    bits.push(`حجم ${toFaDigits(r.vol_ratio.toFixed(1))} برابر حجم ماهانه`);
  }
  const diff = lastCloseDiff(r);
  if (diff != null) bits.push(`اختلاف آخرین و پایانی ${fmtPct(diff * 100)}`);
  const active: string[] = [];
  if (detectStrongHour(r)) active.push(`ساعت قوی (${STRONG_CLOCK_HINT})`);
  else if (r.f_clock) active.push('الگوی ساعت');
  if (detectSweep(r)) active.push('کف‌روبی');
  if (detectBoxExit(r)) active.push('خروج از باکس');
  if (active.length) bits.push(`اعتبار الگو: ${active.join('، ')}`);
  return bits.join(' · ');
}

const TapeRow = memo(function TapeRow({
  row,
  index,
  selected,
  onSelect,
  renderBasketAction,
}: {
  row: MarketRow;
  index: number;
  selected: boolean;
  onSelect: (s: string) => void;
  renderBasketAction?: (symbol: string) => ReactNode;
}) {
  const diff = lastCloseDiff(row);
  const strongHour = detectStrongHour(row);
  const sweep = detectSweep(row);
  const boxExit = detectBoxExit(row);
  const pct = row.percent_change;
  const atLimitUp = pct != null && pct >= LIMIT_PCT;
  const atLimitDown = pct != null && pct <= -LIMIT_PCT;
  const tooltip = rowTooltip(row);
  const volHot = row.vol_ratio != null && row.vol_ratio >= SWEEP_VOL_RATIO_MIN;
  const volMult = row.vol_ratio != null ? `${toFaDigits(row.vol_ratio.toFixed(1))}× میانگین ماه` : '—';
  const badges: React.ReactNode[] = [];
  if (strongHour || row.f_clock)
    badges.push(
      <MicroBadge
        key="clock"
        pattern={strongHour ? 'strong-hour' : 'clock'}
        tone="violet"
        title={
          strongHour
            ? `${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}${diff != null ? ` · دلتا: ${fmtPct(diff * 100)}` : ''}`
            : `الگوی ساعت: پایانی بالاتر از آخرین${diff != null ? ` · اختلاف آخرین و پایانی: ${fmtPct(diff * 100)}` : ''}`
        }
      >
        ساعت
      </MicroBadge>,
    );
  if (row.f_susp) badges.push(<MicroBadge key="susp" pattern="susp" tone="amber" title={`حجم مشکوک: ${volMult}`} >مشکوک</MicroBadge>);
  if (row.f_jet) badges.push(<MicroBadge key="jet" pattern="jet" tone="cyan" title={`جت: شکست مقاومت با سرانه خرید ${row.buyer_power != null ? toFaDigits(row.buyer_power.toFixed(2)) : '—'}×`} >جت</MicroBadge>);
  if (sweep) badges.push(<MicroBadge key="sweep" pattern="sweep" tone="emerald" title={`کف‌روب: ${SWEEP_HINT}`} >کف‌روب</MicroBadge>);
  if (atLimitUp) badges.push(<MicroBadge key="lu" pattern="limit-up" tone="green" title="صف خرید (تغییر ≥ ۴.۹٪)" >صف+</MicroBadge>);
  if (atLimitDown) badges.push(<MicroBadge key="ld" pattern="limit-down" tone="red" title="صف فروش (تغییر ≤ −۴.۹٪)" >صف−</MicroBadge>);
  if (boxExit) badges.push(<MicroBadge key="box" pattern="box" tone="gray" title={BOX_EXIT_HINT} >باکس</MicroBadge>);
  if (row.is_live === false) badges.push(<MicroBadge key="off" pattern="off" tone="gray" title="بدون معاملهٔ امروز" >غیرزنده</MicroBadge>);
  return (
    <div
      role="button"
      tabIndex={0}
      data-testid="tape-row"
      onClick={() => row.symbol && onSelect(row.symbol)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (row.symbol) onSelect(row.symbol);
        }
      }}
      title={tooltip}
      className={`grid w-full ${ROW_GRID} cursor-pointer items-center gap-1 border-b border-border-c/50 px-2 text-right text-xs ${
        selected ? 'bg-accent-blue/15' : 'odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/70'
      } ${atLimitUp ? 'border-r-2 border-r-accent-green' : atLimitDown ? 'border-r-2 border-r-accent-red' : ''}`}
      style={{ height: 40 }}
    >
      <span className="num text-center text-[10px] text-text-muted">{toFaDigits(index + 1)}</span>
      <span className="font-bold text-text-primary">
        {row.symbol}
        <span className="block truncate text-[10px] font-normal text-text-muted">{row.name ?? ''}</span>
      </span>
      <span className="num text-text-primary">
        <FlashNum value={row.p_last} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className={pctTone(pct)}>
        <FlashNum value={pct} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className="num text-text-primary">
        <FlashNum value={row.tvol} render={fmtInt} />
      </span>
      <span className={`num ${volHot ? 'font-bold text-accent-susp' : 'text-text-secondary'}`}>
        <FlashNum value={row.vol_ratio} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)) + (v >= SWEEP_VOL_RATIO_MIN ? '×' : ''))} />
      </span>
      <span className={`num ${row.buyer_power != null && row.buyer_power >= 1.5 ? 'text-accent-green' : 'text-text-secondary'}`}>
        <FlashNum value={row.buyer_power} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(2)))} />
      </span>
      <span className="flex min-w-0 items-center gap-1">
        <span className="num shrink-0 text-text-muted">
          <FlashNum value={diff} render={(v) => (v == null ? '-' : fmtPct(v * 100))} />
        </span>
        <span className="flex min-w-0 items-center gap-1 overflow-hidden">{badges}</span>
      </span>
      <span className="flex items-center justify-center">
        {row.symbol
          ? renderBasketAction
            ? renderBasketAction(row.symbol)
            : <RowBasketAction symbol={row.symbol} />
          : null}
      </span>
    </div>
  );
});

export function TapeTable({
  rows,
  selected,
  onSelect,
  renderBasketAction,
}: {
  rows: MarketRow[];
  selected: string;
  onSelect: (s: string) => void;
  /**
   * اسلات تزریقیِ پوسته: پوسته (app/widgets) می‌تواند اینجا `SymbolBasketAction`
   * واقعی را بدهد. اگر ندهد، دکمهٔ سبک داخلی که قصد سبد را منتشر می‌کند استفاده می‌شود.
   */
  renderBasketAction?: (symbol: string) => ReactNode;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('vol_ratio');
  const [desc, setDesc] = useState(true);
  const parentRef = useRef<HTMLDivElement>(null);

  const sorted = useMemo(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      if (sortKey === 'symbol') {
        const va = a.symbol ?? '';
        const vb = b.symbol ?? '';
        return desc ? vb.localeCompare(va, 'fa') : va.localeCompare(vb, 'fa');
      }
      const va = sortVal(a, sortKey) as number;
      const vb = sortVal(b, sortKey) as number;
      return desc ? vb - va : va - vb;
    });
    return arr;
  }, [rows, sortKey, desc]);

  const virtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
    overscan: 12,
  });

  if (rows.length === 0) {
    return <EmptyState title="نمادی با این فیلترها نیست" hint="فیلترها را کم کن یا جستجو را پاک کن" />;
  }

  const toggle = (k: SortKey) => {
    if (k === sortKey) setDesc((d) => !d);
    else {
      setSortKey(k);
      setDesc(true);
    }
  };

  return (
    <div className="glass-panel overflow-hidden rounded-2xl">
      <div className={`sticky top-0 z-10 grid ${ROW_GRID} gap-1 bg-bg-card/95 px-2 py-2 text-right text-[11px] font-bold text-text-secondary backdrop-blur`}>
        <span className="text-center">#</span>
        {HEADERS.map((h) => (
          <button key={h.key} type="button" onClick={() => toggle(h.key)} className="text-right hover:text-accent-blue">
            {h.label} {sortKey === h.key ? (desc ? '↓' : '↑') : ''}
          </button>
        ))}
        <span className="text-center">سبد</span>
      </div>
      <div ref={parentRef} className="h-[calc(100vh-260px)] min-h-[420px] overflow-y-auto" data-testid="tape-scroll">
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => {
            const row = sorted[v.index];
            return (
              <div
                key={row.symbol}
                className="absolute right-0 top-0 w-full"
                style={{ transform: `translateY(${v.start}px)` }}
              >
                <TapeRow
                  row={row}
                  index={v.index}
                  selected={row.symbol === selected}
                  onSelect={onSelect}
                  renderBasketAction={renderBasketAction}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="border-t border-border-c bg-bg-secondary/60 px-3 py-1 text-[11px] text-text-muted num">
        {toFaDigits(sorted.length)} نماد
      </div>
    </div>
  );
}
