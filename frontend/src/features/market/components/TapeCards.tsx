// features/market/components/TapeCards.tsx -- نمایِ کارتِ تابلو برایِ گوشی
//
// بندِ ۲.۱ مأموریتِ System ۲: «جدول درِ گوشی به‌اندازه‌ای فشرده یاِ بریده است که
// اطلاعات عملاً قابلِ استفاده نیست». جدولِ اصلی `min-w-[1150px]` است، یعنی درِ
// ۳۹۰px حدودِ ۷۶۰px اسکرولِ افقی دارد وِ نمادِ بعدی ازِ دید بیرون می‌ماند. کارت
// همانِ داده را درِ جریانِ عمودیِ خودش می‌گذارد: نماد + نام، آخرین، تغییر٪،
// پایانی/اختلاف٪، حجم/تعداد/ارزش وِ بج‌هایِ الگو.
//
// سه چیزی که عمداً *جدید* نیست:
//  • ترتیب: آرایه را والد (`TapeTable`) باِ همانِ `sortVal` مرتب می‌کند؛ اینِ نما
//    فقطِ نمایش می‌دهد. دوِ مرجعِ ترتیب، همانِ اشتباهی است که درِ سرخطی نمی‌خواهیم.
//  • رنگ/عدد/تاریخ: همانِ `fmtInt`/`fmtPct`/`pctTone`/`FlashNum` ردیفِ دسکتاپ.
//  • بج‌ها: همانِ `patternBadges` وِ `MicroBadge` -- «همون برچسب‌های تابلوخوانی».
//
// مرتب‌سازی درِ گوشی هم درِ دسترس می‌ماند: یکِ `select` باِ سرستون‌هایِ خودِ
// `HEADERS` وِ یکِ کلیدِ جهت، باِ ارتفاعِ لمسیِ ۴۰px+.
import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { MarketRow } from '@shared/types/marketRow';
import { billionRialText, fmtInt, fmtPct, toBillionRial, toFaDigits } from '@shared/lib/fmt';
import { lastCloseDiff } from '../lib/tapePatterns';
import { patternBadges } from '../lib/tapeBadges';
import { HEADERS, type SortKey } from '../lib/tapeColumns';
import { LIMIT_PCT, useTapeStore } from '../stores/tapeStore';
import { MicroBadge } from './MicroBadge';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import WatchlistStar from '@shared/components/WatchlistStar';
import { pctTone, rowTooltip } from '../lib/tapeRowTone';

/** قدِ تخمینیِ کارت -- باِ `estimateSize` یکی می‌ماند تاِ پیمایشِ مجازی نپرد. */
export const CARD_H = 124;

export function TapeCards({
  rows, selected, onSelect, sortKey, desc, onSort,
}: {
  rows: MarketRow[];
  selected: string;
  onSelect: (s: string) => void;
  sortKey: SortKey;
  desc: boolean;
  onSort: (k: SortKey) => void;
}) {
  const tapeFilterConfig = useTapeStore((st) => st.tapeFilterConfig);
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => CARD_H,
    overscan: 8,
  });
  const sortable = HEADERS.filter((h) => h.key != null);

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="tape-cards">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border-c bg-bg-card/95 px-2 py-1.5 backdrop-blur">
        <label className="flex min-w-0 flex-1 items-center gap-2 text-3xs text-text-muted">
          <span className="shrink-0">مرتب‌سازی</span>
          <select
            value={sortKey}
            onChange={(e) => onSort(e.target.value as SortKey)}
            data-testid="tape-cards-sort"
            className="min-h-[40px] w-full min-w-0 rounded-lg border border-border-c bg-bg-primary px-2 text-2xs text-text-primary"
          >
            {sortable.map((h) => (
              <option key={String(h.key)} value={String(h.key)}>{h.label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          data-testid="tape-cards-direction"
          title={desc ? 'بیشترین اول' : 'کمترین اول'}
          className="min-h-[40px] shrink-0 rounded-lg border border-border-c px-3 text-2xs font-bold text-text-secondary"
        >
          {desc ? '↓ بیشترین' : '↑ کمترین'}
        </button>
      </div>

      <div ref={parentRef} data-testid="tape-cards-scroll" className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((v) => {
            const row = rows[v.index];
            const pct = row.percent_change;
            const diff = lastCloseDiff(row);
            const atLimitUp = pct != null && pct >= LIMIT_PCT;
            const atLimitDown = pct != null && pct <= -LIMIT_PCT;
            const badges = patternBadges(row, tapeFilterConfig);
            const isSelected = row.symbol === selected;
            return (
              <div key={String(row.symbol)} className="absolute inset-x-0 top-0 w-full will-change-transform"
                   style={{ height: `${v.size}px`, transform: `translateY(${v.start}px)` }}>
                <div
                  role="button"
                  tabIndex={0}
                  data-testid={`board-card-${row.symbol}`}
                  aria-current={isSelected ? 'true' : undefined}
                  title={rowTooltip(row)}
                  onClick={() => row.symbol && onSelect(row.symbol)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (row.symbol) onSelect(row.symbol);
                    }
                  }}
                  className={`mx-2 my-1 flex min-h-[112px] cursor-pointer flex-col gap-y-2 justify-between rounded-xl border px-2.5 py-2 text-start ${
                    isSelected
                      ? 'border-accent-blue bg-accent-blue/15'
                      : 'border-border-c bg-bg-card/60 active:bg-bg-card'
                  } ${atLimitUp ? 'border-s-4 border-s-accent-green' : atLimitDown ? 'border-s-4 border-s-accent-red' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="flex min-w-0 items-center gap-1.5">
                        <SymbolSelectBox symbol={String(row.symbol ?? '')} name={String(row.name ?? '')}
                                         insCode={row.ins_code ?? null} />
                        <WatchlistStar symbol={String(row.symbol ?? '')} name={String(row.name ?? '')} />
                        <span className="text-sm font-black text-text-primary">{row.symbol}</span>
                      </span>
                      <span className="line-clamp-1 text-3xs text-text-muted" title={row.name ?? undefined}>
                        {row.name ?? ''}
                      </span>
                    </div>
                    <div className="flex shrink-0 flex-col items-end">
                      <span className="num text-base font-black leading-tight text-text-primary"
                            data-card-field="price">
                        {fmtInt(row.p_last ?? null)}
                      </span>
                      <span className={`num text-2xs font-black ${pctTone(pct)}`}
                            data-card-field="pct">
                        {pct == null ? '-' : fmtPct(pct)}
                      </span>
                    </div>
                  </div>

                  <div className="num-text grid grid-cols-3 gap-x-2 text-3xs text-text-muted">
                    <span>پایانی <b className="num font-bold text-text-secondary">
                      {row.p_closing == null ? '-' : fmtInt(row.p_closing)}</b></span>
                    <span>اختلاف٪ <b className={`num font-bold ${pctTone(diff == null ? null : diff * 100)}`}>
                      {diff == null ? '-' : fmtPct(diff * 100)}</b></span>
                    <span>حجم/ماه <b className="num font-bold text-text-secondary">
                      {row.vol_ratio == null ? '-' : toFaDigits(row.vol_ratio.toFixed(1))}</b></span>
                  </div>

                  <div className="num-text grid grid-cols-3 gap-x-2 text-3xs text-text-muted">
                    <span>حجم <b className="num font-bold text-text-secondary">{fmtInt(row.tvol)}</b></span>
                    <span>تعداد <b className="num font-bold text-text-secondary">
                      {row.z_tot_tran == null ? '-' : fmtInt(row.z_tot_tran)}</b></span>
                    <span>ارزش <b className="num font-bold text-text-secondary"
                                   data-card-field="value">
                      {billionRialText(toBillionRial(row.q_tot_cap))}</b></span>
                  </div>

                  {badges.length ? (
                    <span data-testid={`tape-card-patterns-${row.symbol}`}
                          className="flex min-w-0 flex-wrap items-center gap-1">
                      {badges.map((bd) => (
                        <MicroBadge key={bd.key} pattern={bd.pattern} tone={bd.tone} title={bd.title}>
                          {bd.label}
                        </MicroBadge>
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
