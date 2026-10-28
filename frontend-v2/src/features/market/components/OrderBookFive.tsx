import { useMemo } from 'react';
import clsx from 'clsx';
import { fmtInt, toFaDigits } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useOrderBook, type OrderBookLevel } from '../api/useOrderBook';

type Side = 'buy' | 'sell';
type Freshness = 'current' | 'stale' | 'unverified';
const LEVEL_SLOTS = [0, 1, 2, 3, 4];

function freshnessOf(bookDay: number | null | undefined, boardDay: number | null | undefined): Freshness {
  if (bookDay == null || boardDay == null) return 'unverified';
  return bookDay === boardDay ? 'current' : 'stale';
}

function barPct(volume: number | null, max: number): number {
  if (!max || !volume) return 0;
  return Math.min(100, Math.round((volume / max) * 100));
}

function syncStamp(when?: string | null): string | null {
  const match = /^\d{4}-\d{2}-\d{2} (\d{2}:\d{2})/.exec(when ?? '');
  return match ? toFaDigits(match[1]) : null;
}

function BookColumn({ levels, side, max, testId, freshness }: {
  levels: OrderBookLevel[];
  side: Side;
  max: number;
  testId: string;
  freshness: Freshness;
}) {
  const tone = side === 'buy' ? 'text-up' : 'text-down';
  const bg = side === 'buy' ? 'bg-up/10' : 'bg-down/10';
  return (
    <div className="flex min-w-0 flex-col gap-px" data-testid={`${testId}-side-${side}`}>
      <div className={clsx('rounded-[var(--radius-xs)] px-1 py-0.5 text-center t-9 font-bold', bg, tone)}>
        {side === 'buy' ? 'تقاضا' : 'عرضه'}
      </div>
      <div className="grid grid-cols-3 gap-x-1 px-1 t-85 font-bold text-text-3">
        <span className="text-center">تعداد</span>
        <span className="text-center">حجم</span>
        <span className="text-end">قیمت</span>
      </div>
      {LEVEL_SLOTS.map((index) => {
        const level = levels[index];
        const price = level ? (side === 'buy' ? level.buy_px : level.sell_px) : null;
        const volume = level ? (side === 'buy' ? level.buy_vol : level.sell_vol) : null;
        const count = level ? (side === 'buy' ? level.buy_cnt : level.sell_cnt) : null;
        const hasPrice = price != null && price > 0;
        const state = !hasPrice ? (level ? 'empty' : 'no-row') : freshness === 'current' ? 'live' : freshness;
        return (
          <div
            key={index}
            className="relative grid grid-cols-3 items-center gap-x-1 overflow-hidden rounded-[var(--radius-xs)] px-1 py-1"
            data-testid={`${testId}-level-${side}-${index + 1}`}
            data-state={state}
          >
            {hasPrice ? (
              <span
                aria-hidden
                className={clsx('absolute inset-y-0', side === 'buy' ? 'start-0' : 'end-0', bg, freshness !== 'current' && 'opacity-40')}
                style={{ width: `${barPct(volume, max)}%` }}
              />
            ) : null}
            <span className="num relative text-center t-9 text-text-3">
              {hasPrice && count != null ? toFaDigits(count) : '—'}
            </span>
            <span className="num relative text-center t-10 text-text">
              {hasPrice && volume != null ? fmtInt(volume) : '—'}
            </span>
            <span className={clsx('num relative text-end t-105 font-bold', hasPrice && freshness === 'current' ? tone : 'text-text-3')}>
              {hasPrice && price != null ? fmtInt(price) : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function OrderBookFive({ symbol, insCode, boardDay, testId = 'order-book' }: {
  symbol: string;
  insCode?: string | null;
  boardDay?: number | null;
  testId?: string;
}) {
  const query = useOrderBook(symbol, insCode);
  const levels = useMemo(() => (query.data?.levels ?? []).slice(0, 5), [query.data]);
  const max = useMemo(() => levels.reduce(
    (current, level) => Math.max(current, level.buy_vol, level.sell_vol),
    0,
  ), [levels]);
  const bookDay = query.data?.session?.d_even ?? null;
  const freshness = freshnessOf(bookDay, boardDay);
  const stamp = syncStamp(query.data?.session?.updated_at);
  const totals = query.data?.totals;

  return (
    <div
      className="flex min-w-0 flex-col gap-1.5"
      data-testid={testId}
      data-symbol={symbol}
      data-freshness={freshness}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-1.5">
        <h4 className="t-105 font-bold text-text">پنج مظنه <span className="text-accent-2">{symbol}</span></h4>
        <span className="t-85 text-text-3">{stamp ? `همگامِ ${stamp}` : 'زمان ثبت نشده'}</span>
      </div>
      {query.isPending ? <span className="t-95 text-text-3" role="status">در حال خواندن صف‌ها…</span> : null}
      {query.isError ? <span className="t-95 text-down">دفتر سفارش نرسید؛ داده‌ای ساخته نشد.</span> : null}
      {!query.isPending && !query.isError && levels.length === 0 ? (
        <span className="t-95 leading-relaxed text-text-3">
          {query.data?.message ?? 'پنج سطر این نماد در تابلو ثبت نشده؛ صفر نیست.'}
        </span>
      ) : null}
      {levels.length > 0 && freshness !== 'current' ? (
        <p
          data-testid="order-book-session-note"
          role="status"
          className="rounded-[var(--radius-xs)] border border-warn/35 bg-warn/5 px-2 py-1 t-85 leading-relaxed text-warn"
        >
          {freshness === 'stale'
            ? `عمقِ کهنه از نشستِ ${jalaliFromYmd(bookDay)}؛ با نشستِ ${jalaliFromYmd(boardDay)} یکی نیست و جمع‌های تابلو نمایش داده نشد.`
            : 'نشستِ این عمق ثبت نشده؛ تازگیِ آن تأیید نشد و جمع‌های تابلو نمایش داده نشد.'}
        </p>
      ) : null}
      {levels.length > 0 ? (
        <>
          <div className="grid grid-cols-1 gap-2" data-testid={`${testId}-rows`}>
            <BookColumn levels={levels} side="buy" max={max} testId={testId} freshness={freshness} />
            <BookColumn levels={levels} side="sell" max={max} testId={testId} freshness={freshness} />
          </div>
          {freshness === 'current' ? (
            <div data-testid="order-book-totals" className="flex flex-col gap-0.5 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 py-1 t-85">
              <div className="flex items-center justify-between">
                <span className="text-text-3">جمع تقاضا</span>
                <span className="num font-bold text-up">
                  {totals?.buy_vol != null ? fmtInt(totals.buy_vol) : '—'}
                  {totals?.buy_cnt != null ? <span className="font-normal text-text-3"> ({toFaDigits(totals.buy_cnt)} سفارش)</span> : null}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-3">جمع عرضه</span>
                <span className="num font-bold text-down">
                  {totals?.sell_vol != null ? fmtInt(totals.sell_vol) : '—'}
                  {totals?.sell_cnt != null ? <span className="font-normal text-text-3"> ({toFaDigits(totals.sell_cnt)} سفارش)</span> : null}
                </span>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
