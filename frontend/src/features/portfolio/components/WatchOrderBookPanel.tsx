// features/portfolio/components/WatchOrderBookPanel.tsx -- دفترِ سفارشِ پنج‌سطحیِ دیده‌بان
//
// پنج سطرحِ واقعیِ تقاضا/عرضه از `/api/order-book/{symbol}` (useWatchOrderBook).
// رنگِ قراردادیِ برنامه: تقاضا سبز، عرضه قرمز. با عوض شدنِ نماد، کلِ رندر از
// دادهٔ همانونِ همان کوئری می‌آید؛ پاسخِ با نمادِ دیگر (echo نخوردن) درِ لایۀ
// API دور ریخته می‌شود، پس صفحهٔ قبلی زیرِ سرستونِ جدید جا نمی‌ماند.
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { useWatchOrderBook, type WatchOrderBookLevel } from '../api/useWatchOrderBook';

type Side = 'buy' | 'sell';

/** حجمِ سفارش رویِ هر سطوح، نسبت به پرحجم‌ترین سطوحِ همان پنج سطر */
function barPct(vol: number, max: number): number {
  if (!max || !vol) return 0;
  return Math.min(100, Math.round((vol / max) * 100));
}

/** '2026-09-27 11:30:42' → ۱۱:۳۰ (فقط ساعت؛ تاریخِ d_even/h_even قالبِ ثابت ندارد) */
function syncStamp(when?: string | null): string | null {
  const m = /^\d{4}-\d{2}-\d{2} (\d{2}:\d{2})/.exec(when ?? '');
  return m ? toFaDigits(m[1]) : null;
}

function BookRows({ levels, side, max }: { levels: WatchOrderBookLevel[]; side: Side; max: number }) {
  return (
    <ul className="flex flex-col gap-px">
      {levels.slice(0, 5).map((ln, i) => {
        const px = side === 'buy' ? ln.buy_px : ln.sell_px;
        const vol = side === 'buy' ? ln.buy_vol : ln.sell_vol;
        const cnt = side === 'buy' ? ln.buy_cnt : ln.sell_cnt;
        const tone = side === 'buy' ? 'text-accent-green' : 'text-accent-red';
        return (
          <li key={i} className="relative flex items-center justify-between gap-1 overflow-hidden rounded px-1.5 py-1">
            <span
              aria-hidden
              className={`absolute inset-y-0 ${side === 'buy' ? 'start-0' : 'end-0'} ${
                side === 'buy' ? 'bg-accent-green/10' : 'bg-accent-red/10'
              }`}
              style={{ width: `${barPct(vol, max)}%` }}
            />
            <span className={`num relative text-[11px] font-bold ${tone}`}>{px ? fmtInt(px) : '—'}</span>
            <span className="num relative text-[10px] text-text-primary">{vol ? fmtInt(vol) : '—'}</span>
            <span className="num relative shrink-0 text-[10px] text-text-muted">{toFaDigits(cnt ?? 0)}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function WatchOrderBookPanel({ symbol }: { symbol: string }) {
  const { data, isPending, isError } = useWatchOrderBook(symbol);
  const levels = data?.levels ?? [];
  const max = useMemo(() => {
    let m = 0;
    for (const ln of levels) m = Math.max(m, ln.buy_vol, ln.sell_vol);
    return m;
  }, [levels]);
  const stamp = syncStamp(data?.session?.updated_at);
  const totals = data?.totals;

  return (
    <div className="glass-panel flex h-full min-w-0 flex-col gap-1.5 rounded-2xl p-2.5" data-testid="watch-orderbook" data-symbol={symbol}>
      <div className="flex flex-wrap items-baseline justify-between gap-1.5">
        <h4 className="text-xs font-black text-text-primary">
          عمقِ پنج‌سطحی <span className="text-accent-blue">{symbol || '—'}</span>
        </h4>
        <span className="text-3xs text-text-muted" title="زمانِ آخرین همگام‌سازیِ تابلو برایِ این نماد">
          {stamp ? `همگامِ ساعتِ ${stamp}` : 'بی‌زمان'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1 text-center text-3xs font-bold">
        <div className="rounded bg-accent-green/10 py-0.5 text-accent-green">تقاضا</div>
        <div className="rounded bg-accent-red/10 py-0.5 text-accent-red">عرضه</div>
      </div>

      {isPending && symbol ? <span className="text-2xs text-text-muted">در حال دریافتِ صف‌ها…</span> : null}
      {isError ? <span className="text-2xs text-accent-red" data-testid="watch-orderbook-error">خطا در دریافتِ عمقِ بازار</span> : null}

      {!isPending && !isError && (data == null || levels.length === 0) ? (
        <span className="text-2xs leading-5 text-text-muted" data-testid="watch-orderbook-empty">
          {data?.message ?? 'بدون داده — پنج سطوحِ این نماد ذخیره نشده؛ بعد از نخستین همگام‌سازیِ تابلو می‌آید'}
        </span>
      ) : null}

      {levels.length > 0 ? (
        <>
          <div className="grid grid-cols-2 gap-1" data-testid="watch-orderbook-rows">
            <BookRows levels={levels} side="buy" max={max} />
            <BookRows levels={levels} side="sell" max={max} />
          </div>
          <div className="flex flex-col gap-0.5 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1 text-3xs" data-testid="watch-orderbook-totals">
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ تقاضا</span>
              <span className="num font-bold text-accent-green">
                {totals?.buy_vol != null ? fmtInt(totals.buy_vol) : '—'}
                {totals?.buy_cnt != null ? <span className="font-normal text-text-muted"> ({toFaDigits(totals.buy_cnt)} سفارش)</span> : null}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ عرضه</span>
              <span className="num font-bold text-accent-red">
                {totals?.sell_vol != null ? fmtInt(totals.sell_vol) : '—'}
                {totals?.sell_cnt != null ? <span className="font-normal text-text-muted"> ({toFaDigits(totals.sell_cnt)} سفارش)</span> : null}
              </span>
            </div>
          </div>
          <p className="text-3xs leading-4 text-text-muted">قیمت‌ها ریال است. پنج سطوحِ اولِ هر صف، آن‌طور که تابلو می‌فرستد.</p>
        </>
      ) : null}
    </div>
  );
}
