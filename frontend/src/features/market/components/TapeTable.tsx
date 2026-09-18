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
  GOLDEN_HOUR_HINT,
  GOLDEN_HOUR_LABEL,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_HINT,
  detectBoxExit,
  detectGoldenHour,
  detectStrongHour,
  detectSweep,
  lastCloseDiff,
} from '../lib/tapePatterns';
import { FTS_VOL_RATIO_HOT, buyPerCapitaMt, sellPerCapitaMt } from '../lib/tapeFts';
import { resolveFtsStatus, type ScreenerRow } from '../api/useFtsScreener';
import { LIMIT_PCT } from '../stores/tapeStore';
import { RowBasketAction } from './RowBasketAction';
import { FtsStatusBadge } from './FtsStatusBadge';

type SortKey =
  | 'symbol'
  | 'percent_change'
  | 'tvol'
  | 'vol_ratio'
  | 'buy_pc'
  | 'sell_pc'
  | 'buyer_power'
  | 'last_vs_close'
  | 'p_last';

/** ۱۱ ستون بهینه‌شده: نماد/نام · آخرین · تغییر · حجم · نسبت حجم · سرانه خرید · سرانه فروش · قدرت خریدار · الگوی ساعت · وضعیت FTS · افزودن به سبد */
const ROW_GRID =
  'grid-cols-[minmax(105px,1.3fr)_minmax(65px,0.75fr)_minmax(52px,0.65fr)_minmax(62px,0.75fr)_minmax(55px,0.7fr)_minmax(52px,0.65fr)_minmax(52px,0.65fr)_minmax(52px,0.65fr)_minmax(148px,1.7fr)_minmax(60px,0.75fr)_minmax(54px,3.8rem)]';

const HEADERS: { key: SortKey; label: string }[] = [
  { key: 'symbol', label: 'نماد و نام' },
  { key: 'p_last', label: 'قیمت آخرین' },
  { key: 'percent_change', label: 'تغییر٪' },
  { key: 'tvol', label: 'حجم' },
  { key: 'vol_ratio', label: 'نسبت حجم ماه' },
  { key: 'buy_pc', label: 'سرانه خرید' },
  { key: 'sell_pc', label: 'سرانه فروش' },
  { key: 'buyer_power', label: 'قدرت خریدار' },
  { key: 'last_vs_close', label: 'الگوی ساعت' },
];

const NEG = Number.NEGATIVE_INFINITY;

function sortVal(r: MarketRow, key: SortKey): number | string {
  switch (key) {
    case 'symbol':
      return r.symbol ?? '';
    case 'p_last':
      return r.p_last ?? NEG;
    case 'percent_change':
      return r.percent_change ?? NEG;
    case 'tvol':
      return r.tvol ?? NEG;
    case 'vol_ratio':
      return r.vol_ratio ?? NEG;
    case 'buy_pc':
      return buyPerCapitaMt(r) ?? NEG;
    case 'sell_pc':
      return sellPerCapitaMt(r) ?? NEG;
    case 'buyer_power':
      return r.buyer_power ?? NEG;
    case 'last_vs_close':
      return lastCloseDiff(r) ?? NEG;
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
  violet: 'bg-[#8b5cf6]/25 text-[#ddd6fe] border border-[#8b5cf6]/40',
  amber: 'bg-accent-yellow/25 text-[#fef08a] border border-accent-yellow/45',
  cyan: 'bg-neon-cyan/20 text-[#a5f3fc] border border-neon-cyan/40',
  emerald: 'bg-accent-green/20 text-[#bbf7d0] border border-accent-green/40',
  green: 'bg-accent-green/20 text-[#bbf7d0] border border-accent-green/40',
  red: 'bg-accent-red/20 text-[#fecaca] border border-accent-red/40',
  gray: 'bg-bg-card/90 text-text-primary border border-border-c',
} as const;

type MicroTone = keyof typeof MICRO_TONES;

/** میکرو-بج متنی های‌دنسیتی با کنتراست و خوانایی بالا؛ جزئیات عددی در title (Tooltip) هر بج */
function MicroBadge({ pattern, tone, title, children }: { pattern: string; tone: MicroTone; title: string; children: React.ReactNode }) {
  return (
    <span
      data-testid={`badge-${pattern}`}
      data-pattern={pattern}
      title={title}
      className={`shrink-0 inline-flex items-center justify-center rounded-md px-1.5 py-0.5 text-[11px] font-bold leading-none tracking-tight shadow-2xs whitespace-nowrap select-none ${MICRO_TONES[tone]}`}
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
  else if (detectGoldenHour(r)) active.push('ساعت طلایی');
  else if (r.f_clock) active.push('الگوی ساعت');
  if (detectSweep(r)) active.push('کف‌روبی');
  if (detectBoxExit(r)) active.push('خروج از باکس');
  if (active.length) bits.push(`اعتبار الگو: ${active.join('، ')}`);
  return bits.join(' · ');
}

const TapeRow = memo(function TapeRow({
  row,
  selected,
  onSelect,
  renderBasketAction,
  ftsMap,
}: {
  row: MarketRow;
  selected: boolean;
  onSelect: (s: string) => void;
  renderBasketAction?: (symbol: string) => ReactNode;
  ftsMap: Map<string, ScreenerRow>;
}) {
  const diff = lastCloseDiff(row);
  const strongHour = detectStrongHour(row);
  const goldenHour = !strongHour && detectGoldenHour(row);
  const sweep = detectSweep(row);
  const boxExit = detectBoxExit(row);
  const pct = row.percent_change;
  const atLimitUp = pct != null && pct >= LIMIT_PCT;
  const atLimitDown = pct != null && pct <= -LIMIT_PCT;
  const tooltip = rowTooltip(row);
  const volHot = row.vol_ratio != null && row.vol_ratio > FTS_VOL_RATIO_HOT;
  const volMult = row.vol_ratio != null ? `${toFaDigits(row.vol_ratio.toFixed(1))}× میانگین ماه` : '—';
  const buyPc = buyPerCapitaMt(row);
  const sellPc = sellPerCapitaMt(row);
  const fts = resolveFtsStatus(row, ftsMap);
  const badges: React.ReactNode[] = [];
  if (strongHour || goldenHour || row.f_clock)
    badges.push(
      <MicroBadge
        key="clock"
        pattern={strongHour ? 'strong-hour' : goldenHour ? 'golden-hour' : 'clock'}
        tone={goldenHour ? 'amber' : 'violet'}
        title={
          strongHour
            ? `${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}${diff != null ? ` · دلتا: ${fmtPct(diff * 100)}` : ''}`
            : goldenHour
              ? `${GOLDEN_HOUR_LABEL} — ${GOLDEN_HOUR_HINT}`
              : `الگوی ساعت: پایانی بالاتر از آخرین${diff != null ? ` · اختلاف آخرین و پایانی: ${fmtPct(diff * 100)}` : ''}`
        }
      >
        {strongHour ? 'ساعت' : goldenHour ? 'ساعت طلایی' : 'ساعت'}
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
      className={`grid w-full min-w-[800px] ${ROW_GRID} cursor-pointer items-center gap-2 border-b border-border-c/50 px-3 text-start text-sm ${
        selected ? 'bg-accent-blue/15' : 'odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/70'
      } ${atLimitUp ? 'border-s-2 border-s-accent-green' : atLimitDown ? 'border-s-2 border-s-accent-red' : ''}`}
      style={{ height: 36 }}
    >
      <span className="font-bold text-sm text-text-primary flex items-baseline gap-1.5 truncate">
        {row.symbol}
        <span className="truncate text-2xs font-normal text-text-muted">{row.name ?? ''}</span>
      </span>
      <span className="num text-text-primary font-bold">
        <FlashNum value={row.p_last} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className={`num font-bold ${pctTone(pct)}`}>
        <FlashNum value={pct} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className="num text-text-secondary">
        <FlashNum value={row.tvol} render={fmtInt} />
      </span>
      <span
        className={`num ${volHot ? 'font-bold text-accent-susp' : 'text-text-secondary'}`}
        title={volHot ? `حجم مشکوک FTS: بیش از ${toFaDigits(FTS_VOL_RATIO_HOT)} برابر میانگین ماهانه` : undefined}
      >
        <FlashNum value={row.vol_ratio} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)) + (v > FTS_VOL_RATIO_HOT ? '×' : ''))} />
      </span>
      <span className="num text-text-secondary" title="سرانه خرید حقیقی (میلیون تومان)">
        <FlashNum value={buyPc} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)))} />
      </span>
      <span className="num text-text-secondary" title="سرانه فروش حقیقی (میلیون تومان)">
        <FlashNum value={sellPc} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)))} />
      </span>
      <span className={`num ${row.buyer_power != null && row.buyer_power >= 1.5 ? 'text-accent-green' : 'text-text-secondary'}`}>
        <FlashNum value={row.buyer_power} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(2)))} />
      </span>
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="num shrink-0 text-text-muted font-medium text-xs">
          <FlashNum value={diff} render={(v) => (v == null ? '-' : fmtPct(v * 100))} />
        </span>
        <span className="flex min-w-0 items-center gap-1 overflow-x-auto no-scrollbar py-0.5">{badges}</span>
      </span>
      <span className="flex items-center justify-center">
        {row.symbol ? <FtsStatusBadge symbol={row.symbol} view={fts} /> : null}
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
  ftsMap,
}: {
  rows: MarketRow[];
  selected: string;
  onSelect: (s: string) => void;
  /**
   * اسلات تزریقیِ پوسته: پوسته (app/widgets) می‌تواند اینجا `SymbolBasketAction`
   * واقعی را بدهد. اگر ندهد، دکمهٔ سبک داخلی که قصد سبد را منتشر می‌کند استفاده می‌شود.
   */
  renderBasketAction?: (symbol: string) => ReactNode;
  /** نقشهٔ وضعیت FTS از /api/screener؛ اگر نباشد همهٔ ردیف‌ها N/A می‌شوند */
  ftsMap?: Map<string, ScreenerRow>;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('vol_ratio');
  const [desc, setDesc] = useState(true);
  const parentRef = useRef<HTMLDivElement>(null);
  const emptyFts = useMemo(() => new Map<string, ScreenerRow>(), []);
  const fts = ftsMap ?? emptyFts;

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
    estimateSize: () => 36,
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
      <div className="overflow-x-auto overscroll-x-contain">
        <div className={`sticky top-0 z-10 grid min-w-[800px] ${ROW_GRID} gap-2 bg-bg-card/95 px-3 py-2.5 text-start text-2xs font-bold text-text-secondary backdrop-blur`}>
          {HEADERS.map((h) => (
            <button
              key={h.key}
              type="button"
              onClick={() => toggle(h.key)}
              title={h.key === 'last_vs_close' ? 'الگوی ساعت — مرتب‌سازی بر اساس اختلاف آخرین/پایانی' : undefined}
              className="text-start hover:text-accent-blue transition-colors"
            >
              {h.label} {sortKey === h.key ? (desc ? '↓' : '↑') : ''}
            </button>
          ))}
          <span className="text-center">وضعیت FTS</span>
          <span className="text-center">افزودن به سبد</span>
        </div>
        <div ref={parentRef} className="h-[calc(100vh-260px)] min-h-[420px] overflow-y-auto overscroll-contain" data-testid="tape-scroll">
          <div className="relative w-full min-w-[780px]" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => {
            const row = sorted[v.index];
            return (
              <div
                key={row.symbol}
                className="absolute inset-x-0 top-0 w-full will-change-transform"
                style={{
                  height: `${v.size}px`,
                  transform: `translateY(${v.start}px)`,
                }}
              >
                <TapeRow
                  row={row}
                  selected={row.symbol === selected}
                  onSelect={onSelect}
                  renderBasketAction={renderBasketAction}
                  ftsMap={fts}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
    <div className="border-t border-border-c bg-bg-secondary/60 px-3 py-1 text-2xs text-text-muted">
      <span className="num font-bold">{toFaDigits(sorted.length)}</span> نماد
    </div>
  </div>
);
}
