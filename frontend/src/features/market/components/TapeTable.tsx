// features/market/components/TapeTable.tsx -- جدول مجازی تابلو
// ردیف ها با React.memo و کلید نماد؛ فقط ردیف های دیدنی رندر می شوند.
import { memo, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { MarketRow } from '@shared/types/marketRow';
import { billionRialText, fmtInt, fmtPct, toBillionRial, toFaDigits } from '@shared/lib/fmt';
import { EmptyState } from '@shared/components/EmptyState';
import { FlashNum } from '@shared/components/FlashNum';
import { lastCloseDiff } from '../lib/tapePatterns';
import { FTS_VOL_RATIO_HOT, buyPerCapitaMt, sellPerCapitaMt } from '../lib/tapeFts';
import { HEADERS, sortVal, type SortKey } from '../lib/tapeColumns';
import { pctTone, rowTooltip } from '../lib/tapeRowTone';
import { patternBadges } from '../lib/tapeBadges';
import { BuySellCell } from './BuySellCell';
import { MicroBadge } from './MicroBadge';
import { TapeCards } from './TapeCards';
import { MEDIA_MOBILE } from '@shared/lib/breakpoints';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { LIMIT_PCT, useTapeStore } from '../stores/tapeStore';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import WatchlistStar from '@shared/components/WatchlistStar';

/**
 * دوازده ستونِ تابلو (۱۲). عرض‌ها از روی سنجشِ واقعیِ «پهنای لازمِ محتوا» در فونتِ
 * 16pxِ همین جدول گذاشته شده‌اند، نه حدس:
 * [نماد 150] [آخرین 66] [پایانی 66] [اختلاف٪ 60] [تغییر٪ 62] [آخرین٪ 62] [حجم 130] [تعداد 64]
 * [ارزش 58] [حجم/ماه 58] [خرید/فروش 118 — سرانه‌ها + نوارِ دوسُره + نسبت]
 * [الگو 142].
 * سه ستونِ «سرانۀ خرید / سرانۀ فروش / قدرتِ خریدار» در #146 به یک ستونِ دوسُره
 * جمع شد؛ در #172 خانهٔ «ساعت» دو ستون شد، چون عددِ اختلاف و بج‌هایِ الگو در یک
 * خانه به هم می‌چسبیدند و خواننده نمی‌فهمید عدد زیرِ کدام سرستون است. فاصلهٔ
 * ستون‌ها ۶→۴ و حاشیهٔ ردیف ۱۲→۸ آمد تا حدِ آستانهٔ عرض بالا نکند.
 */
const ROW_H = 34;
const ROW_GRID =
  'grid-cols-[minmax(240px,2.3fr)_minmax(66px,0.85fr)_minmax(66px,0.85fr)_minmax(60px,0.6fr)_minmax(62px,0.8fr)_minmax(62px,0.8fr)_minmax(104px,0.85fr)_minmax(56px,0.7fr)_minmax(56px,0.72fr)_minmax(56px,0.72fr)_minmax(150px,1.25fr)_minmax(104px,0.9fr)]';

/** کمترینِ عرضِ جدول = جمعِ مینیمم‌ها + فاصله‌ها + padding (زیرِ این، جدول افقی اسکرول می‌خورد) */
const TABLE_MIN_W = 'min-w-[1150px]';

/** سرستونِ بی‌مرتب‌سازی (کلیدِ null) — ستونِ بج‌ها عددی نیست که بشود مرتبش کرد */







export const TapeRow = memo(function TapeRow({
  row,
  selected,
  onSelect,
}: {
  row: MarketRow;
  selected: boolean;
  onSelect: (s: string) => void;
}) {
  const tapeFilterConfig = useTapeStore((s) => s.tapeFilterConfig);
  const diff = lastCloseDiff(row);
  const pct = row.percent_change;
  const atLimitUp = pct != null && pct >= LIMIT_PCT;
  const atLimitDown = pct != null && pct <= -LIMIT_PCT;
  const tooltip = rowTooltip(row);
  const volHot = row.vol_ratio != null && row.vol_ratio > FTS_VOL_RATIO_HOT;
  const buyPc = buyPerCapitaMt(row);
  const sellPc = sellPerCapitaMt(row);

  // بج‌های ستونِ «الگو» از lib می‌آیند: همان `tapeFilterVerdict` که چیپِ بالایِ
  // جدول می‌شمارد، تا عددِ چیپ و آنچه درِ ردیف دیده می‌شود یکی بماند.
  const badges = patternBadges(row, tapeFilterConfig);
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
      className={`group grid w-full ${ROW_GRID} cursor-pointer items-center gap-1 border-b border-border-c/50 px-2 text-start text-[13px] ${
        selected ? 'bg-accent-blue/15' : 'odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/70'
      } ${atLimitUp ? 'border-s-2 border-s-accent-green' : atLimitDown ? 'border-s-2 border-s-accent-red' : ''}`}
      style={{ height: ROW_H }}
    >
      <span className="font-bold text-[13px] text-text-primary flex items-center gap-1.5 truncate">
        {/* جعبۀ انتخاب داخلِ همان ستونِ نماد است، نه ستونِ تازه: `ROW_GRID` با
            افزودنِ یک فرزندِ مستقیمِ grid از جا درمی‌رود. */}
        <SymbolSelectBox symbol={String(row.symbol ?? '')} name={String(row.name ?? '')}
                         insCode={row.ins_code ?? null} />
        <WatchlistStar symbol={String(row.symbol ?? '')} name={String(row.name ?? '')} />
        {row.symbol}
        <span className="truncate text-xs font-normal text-text-muted" title={row.name ?? undefined}>{row.name ?? ''}</span>
      </span>
      {/* تراز ستون (fix): محتوای عددی با `.num` (direction:ltr) به‌صورت خودکار چپ‌چین می‌شد
          و زیر هدرِ راست‌چین نمی‌نشست؛ `text-end` آن را با لبهٔ راست (جای هدر) هم‌تراز می‌کند. */}
      <span className="num text-end text-text-primary font-bold">
        <FlashNum value={row.p_last} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.p_closing} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      {/* اختلافِ آخرین تا پایانی یک ستونِ عددیِ مستقل است (#172) و بغلِ پایانی
          می‌نشیند (#194): تا پیش از این کنارِ بج‌ها بود و خواننده نمی‌فهمید
          عددِ درصد زیرِ کدام سرستون است، یا با «آخرین» و «پایانی» چه ربطی دارد. */}
      <span className="num text-end text-text-secondary" title={`اختلاف آخرین و پایانی: ${diff == null ? '—' : fmtPct(diff * 100)}`}>
        <FlashNum value={diff} render={(v) => (v == null ? '-' : fmtPct(v * 100))} />
      </span>
      <span className={`num text-end font-bold ${pctTone(pct)}`}>
        <FlashNum value={pct} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className={`num text-end ${pctTone(row.percent_last)}`}>
        <FlashNum value={row.percent_last} render={(v) => (v == null ? '-' : fmtPct(v))} />
      </span>
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.tvol} render={fmtInt} />
      </span>
      {/* تعدادِ معاملات: بدونش «tno > ۵۰» و «qd1 > ۱۰۰» درِ فیلترها قابلِ
          ردیابی نبود. صفرِ جعلی نداریم؛ نبودنش «-» است. */}
      <span className="num text-end text-text-secondary">
        <FlashNum value={row.z_tot_tran} render={(v) => (v == null ? '-' : fmtInt(v))} />
      </span>
      <span className="num text-end text-text-secondary" title={row.q_tot_cap != null ? `${fmtInt(row.q_tot_cap)} ریال` : undefined}>
        <FlashNum value={toBillionRial(row.q_tot_cap)} render={billionRialText} />
      </span>
      <span
        className={`num text-end ${volHot ? 'font-bold text-accent-susp' : 'text-text-secondary'}`}
        title={volHot ? `حجم مشکوک FTS: بیش از ${toFaDigits(FTS_VOL_RATIO_HOT)} برابر میانگین ماهانه` : undefined}
      >
        <FlashNum value={row.vol_ratio} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(1)) + (v > FTS_VOL_RATIO_HOT ? '×' : ''))} />
      </span>
      <BuySellCell buyPc={buyPc} sellPc={sellPc} power={row.buyer_power} />
      {/* `flex-wrap` به‌جای `overflow-x-auto`: نوارِ بج هیچ‌وقت اسکرول
          افقی نمی‌شود؛ اگر روزی چهار بج با هم بیایند، در ارتفاعِ ۴۰
          ردیف می‌شکنند و دیده می‌شوند — نه اینکه پشتِ لبهٔ ستون پنهان
          شوند (باگِ گزارش‌شدهٔ کاربر: «برچسب‌ها قابل اسکرول‌اند»). */}
      <span data-testid="tape-patterns" className="flex min-w-0 flex-wrap items-center gap-0.5 overflow-hidden py-0.5">
        {badges.map((b) => (
          <MicroBadge key={b.key} pattern={b.pattern} tone={b.tone} title={b.title}>
            {b.label}
          </MicroBadge>
        ))}
      </span>
    </div>
  );
});

export function TapeTable({
  rows,
  selected,
  onSelect,
  isLoading,
  isError,
  onRetry,
  emptyNote,
  onClearFilters,
}: {
  rows: MarketRow[];
  selected: string;
  onSelect: (s: string) => void;
  /** وضعیتِ فید: جدولِ خالی نباید تقصیرِ فیلترِ کاربر باشد */
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  /** علتِ خالی‌ماندن با نامِ درها؛ بی‌آن «نبود» به «غلطِ فیلتر» ترجمه می‌شد */
  emptyNote?: string | null;
  onClearFilters?: () => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('vol_ratio');
  const [desc, setDesc] = useState(true);
  const isMobile = useMediaQuery(MEDIA_MOBILE);
  /** 'auto' = گوشی کارت، دسکتاپ جدول. کلیدِ دستی فقط درِ گوشی دیده می‌شود، چون
      درِ ۳۹۰px جدولِ کامل یعنی ~۷۶۰px اسکرولِ افقی. */
  const [view, setView] = useState<'auto' | 'table' | 'cards'>('auto');
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
    estimateSize: () => ROW_H,
    overscan: 12,
  });

  if (rows.length === 0) {
    // صادقانه: تا فید نرسیده یا خطا داده، «فیلتر شما غلط است» گفتن درست نیست.
    if (isError) {
      return (
        <EmptyState
          title="فیدِ تابلو برنگشت"
          hint="اینترنت یا سرویسِ تابلو را بررسی کن، دوباره تلاش کن"
          action={
            onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                data-testid="tape-retry"
                className="rounded-lg border border-accent-blue bg-accent-blue/10 px-3 py-1 text-xs font-bold text-accent-blue"
              >
                تلاش دوباره
              </button>
            ) : undefined
          }
        />
      );
    }
    if (isLoading) {
      return <EmptyState title="در حالِ خواندنِ تابلو…" hint="نخستین نشستِ داده کمی طول می‌کشد" />;
    }
    return (
      <EmptyState
        title="نمادی با این فیلترها نیست"
        hint={emptyNote || 'فیلترها را کم کن یا جستجو را پاک کن'}
        action={
          onClearFilters ? (
            <button
              type="button"
              onClick={onClearFilters}
              data-testid="tape-clear-filters"
              className="rounded-lg border border-accent-blue bg-accent-blue/10 px-3 py-1 text-xs font-bold text-accent-blue"
            >
              خاموش‌کردنِ فیلترها
            </button>
          ) : undefined
        }
      />
    );
  }

  const toggle = (k: SortKey) => {
    if (k === sortKey) setDesc((d) => !d);
    else {
      setSortKey(k);
      setDesc(true);
    }
  };

  const cardsMode = view === 'cards' || (view === 'auto' && isMobile);

  const segCls = (on: boolean) => `min-h-[40px] rounded-lg border px-3 text-2xs font-bold ${
    on ? 'border-accent-blue bg-accent-blue/15 text-accent-blue' : 'border-border-c text-text-secondary'}`;

  const viewToggle = isMobile ? (
    <div className="flex items-center gap-1 border-b border-border-c bg-bg-card/60 px-2 py-1"
         data-testid="tape-view-toggle">
      <button type="button" onClick={() => setView('cards')} aria-pressed={cardsMode}
              data-testid="tape-view-cards" className={segCls(cardsMode)}>
        کارتی
      </button>
      <button type="button" onClick={() => setView('table')} aria-pressed={!cardsMode}
              data-testid="tape-view-table" className={segCls(!cardsMode)}>
        جدولِ کامل (اسکرولِ افقی)
      </button>
    </div>
  ) : null;

  const footer = (
    <div className="border-t border-border-c bg-bg-secondary/60 px-3 py-1 text-2xs text-text-muted">
      <span className="num font-bold">{toFaDigits(sorted.length)}</span> نماد
    </div>
  );

  if (cardsMode) {
    return (
      <div className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl">
        {viewToggle}
        <TapeCards rows={sorted} selected={selected} onSelect={onSelect}
                   sortKey={sortKey} desc={desc} onSort={toggle} />
        {footer}
      </div>
    );
  }

  return (
    <div className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl">
      {viewToggle}
      <div className="flex min-h-0 flex-1 flex-col overflow-x-auto overscroll-x-contain">
        <div data-testid="tape-head" className={`sticky top-0 z-10 grid w-full ${TABLE_MIN_W} ${ROW_GRID} gap-1 bg-bg-card/95 px-2 py-2.5 text-start text-2xs font-bold text-text-secondary backdrop-blur`}>
          {HEADERS.map((h) => {
            const k = h.key;
            if (k == null) {
              return (
                <span key={h.label} title={h.hint} className="block w-full truncate text-start whitespace-nowrap">
                  {h.label}
                </span>
              );
            }
            return (
              <button
                key={k}
                type="button"
                onClick={() => toggle(k)}
                title={h.hint}
                className="block w-full truncate text-start whitespace-nowrap hover:text-accent-blue transition-colors"
              >
                {h.label} {sortKey === k ? (desc ? '↓' : '↑') : ''}
              </button>
            );
          })}
        </div>
        <div ref={parentRef} className="min-h-[420px] flex-1 overflow-y-auto overscroll-contain" data-testid="tape-scroll">
          <div className={`relative w-full ${TABLE_MIN_W}`} style={{ height: virtualizer.getTotalSize() }}>
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
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
    {footer}
  </div>
);
}
