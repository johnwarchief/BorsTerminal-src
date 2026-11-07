// shared/components/OrderBookFive.tsx -- پنج مظنه، یک پیاده‌سازی برایِ همهٔ سطوح
//
// جای دو نسخۀِ نزدیک‌به‌مشابه (`features/technical/components/SidebarOrderBook`
// و `features/portfolio/components/WatchOrderBookPanel`) که هر دو همان
// `/api/order-book` را با دو queryKey و دو درخواستِ جدا می‌پرسیدند. سه مصرف:
// سایدبارِ چپ («جزئیات بازار»ِ نماد)، پنلِ میانیِ «دیده‌بان بازار»، و تبِ عمقِ
// سایدبارِ چارت.
//
// قواعدی که این فایل نگه می‌دارد (بند ۱.۱ مأموریت، رأیِ مالک 1405-07-20):
//  • هر سطر سه خانۀ **تعداد / حجم / قیمت** با سرستونِ روشن است؛ سرستون‌ها
//    ترتیبِ یکسان در دو سو دارند (ترتیبِ آینه‌ایِ مرجع درِ این دور قابل
//    بازبینی نبود، پس چیدمانِ حدسی نمی‌نشیند).
//  • خانه‌ای که تابلو آن را نفرستاده «—» است با وضعیتِ صریح (`data-state`)،
//    نه صفرِ بی‌صدا؛ صفِ تهی با صفی که نشده یکی نیست.
//  • تقاضا سبز، عرضه قرمز، نوارِ حجم نسبی به پرحجم‌ترین سطرِ همان پنج سطر.
//  • کندلِ روزِ در حالِ تشکیل بالایِ سرستون‌ها از خودِ ردیفِ تابلو رسم می‌شود.
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { useOrderBook, type OrderBookLevel } from '@shared/api/useOrderBook';
import { FormingCandleStrip, type CandleOHLC } from '@shared/components/FormingCandle';

type Side = 'buy' | 'sell';
const LEVEL_SLOTS = [0, 1, 2, 3, 4];

/** حجمِ این سطر نسبت به پرحجم‌ترین سطرِ همان پنج سطر (مبنایِ نوار) */
function barPct(vol: number | null, max: number): number {
  if (!max || !vol) return 0;
  return Math.min(100, Math.round((vol / max) * 100));
}

/** '2026-09-27 11:30:42' → ۱۱:۳۰ — فقط ساعت؛ d_even/h_even قالبِ ثابت ندارند */
function syncStamp(when?: string | null): string | null {
  const m = /^\d{4}-\d{2}-\d{2} (\d{2}:\d{2})/.exec(when ?? '');
  return m ? toFaDigits(m[1]) : null;
}

function cellText(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v === 0) return '۰';
  return fmtInt(v);
}

function BookColumn({
  levels, side, max, testId,
}: {
  levels: OrderBookLevel[];
  side: Side;
  max: number;
  testId: string;
}) {
  const tone = side === 'buy' ? 'text-accent-green' : 'text-accent-red';
  const bg = side === 'buy' ? 'bg-accent-green/10' : 'bg-accent-red/10';
  return (
    <div className="flex min-w-0 flex-col gap-px" data-testid={`${testId}-side-${side}`}>
      <div className={`rounded px-1 py-0.5 text-center text-3xs font-bold ${bg} ${tone}`}
           data-testid={`${testId}-head-${side}`}>
        {side === 'buy' ? 'تقاضا' : 'عرضه'}
      </div>
      {/* سرستونِ سه‌خانۀ همان سو */}
      <div className="grid grid-cols-3 gap-x-1 px-1 text-3xs font-bold text-text-muted"
           data-testid={`${testId}-cols-${side}`}>
        <span className="text-center">تعداد</span>
        <span className="text-center">حجم</span>
        <span className="text-end">قیمت</span>
      </div>
      {LEVEL_SLOTS.map((i) => {
        const ln = levels[i];
        const px = ln ? (side === 'buy' ? ln.buy_px : ln.sell_px) : null;
        const vol = ln ? (side === 'buy' ? ln.buy_vol : ln.sell_vol) : null;
        const cnt = ln ? (side === 'buy' ? ln.buy_cnt : ln.sell_cnt) : null;
        const live = px != null && px > 0;
        return (
          <div key={i} className="relative grid grid-cols-3 items-center gap-x-1 overflow-hidden rounded px-1 py-1"
               data-testid={`${testId}-level-${side}-${i + 1}`}
               data-state={live ? 'live' : ln ? 'empty' : 'no-row'}>
            {live ? (
              <span aria-hidden
                    className={`absolute inset-y-0 ${side === 'buy' ? 'start-0' : 'end-0'} ${bg}`}
                    style={{ width: `${barPct(vol ?? 0, max)}%` }} />
            ) : null}
            <span className="num relative text-center text-3xs leading-none text-text-muted"
                  title={live ? 'تعدادِ سفارشِ این سطر' : 'بی‌سطر'}>
              {live && cnt != null ? toFaDigits(String(cnt)) : '—'}
            </span>
            <span className="num relative text-center text-3xs text-text-primary"
                  title={live ? 'حجمِ سفارشِ این سطر (سهم)' : 'بی‌سطر'}>
              {live ? cellText(vol) : '—'}
            </span>
            <span className={`num relative text-end text-3xs font-bold ${live ? tone : 'text-text-muted'}`}
                  title={live ? 'قیمتِ این سطر (ریال)' : 'این سطرِ صف درِ تابلو ثبت نشده — صفر نمی‌نشیند'}>
              {live ? cellText(px) : '—'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function OrderBookFive({
  symbol, candle, compact = false, testId = 'order-book-five', className = '',
}: {
  symbol: string;
  /** ردیفِ تابلویِ همان نماد برایِ کندلِ در حالِ تشکیل (بی‌آن ⇒ بی‌کندل) */
  candle?: CandleOHLC | null;
  compact?: boolean;
  testId?: string;
  className?: string;
}) {
  const { data, isPending, isError } = useOrderBook(symbol);
  const levels = useMemo(() => (data?.levels ?? []).slice(0, 5), [data]);
  const max = useMemo(() => {
    let m = 0;
    for (const ln of levels) m = Math.max(m, ln.buy_vol, ln.sell_vol);
    return m;
  }, [levels]);
  const stamp = syncStamp(data?.session?.updated_at);
  const totals = data?.totals;

  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}
         data-testid={testId} data-symbol={symbol}>
      <div className="flex flex-wrap items-baseline justify-between gap-1.5">
        <h4 className={`font-black text-text-primary ${compact ? 'text-3xs' : 'text-xs'}`}>
          پنج مظنه {symbol ? <span className="text-accent-blue">{symbol}</span> : null}
        </h4>
        <span className="text-3xs text-text-muted" title="زمانِ آخرین همگام‌سازیِ تابلو برایِ این نماد">
          {stamp ? `همگامِ ساعتِ ${stamp}` : 'بی‌زمان'}
        </span>
      </div>

      {/* کندلِ روزِ در حالِ تشکیل — بالایِ سرستون‌ها (بند ۱.۱) */}
      {candle ? <FormingCandleStrip candle={candle} symbol={symbol} testId={`${testId}-candle`} /> : null}

      {isPending && symbol ? (
        <span className="text-2xs text-text-muted" data-testid={`${testId}-loading`}>
          در حالِ خواندنِ صف‌ها…
        </span>
      ) : null}
      {isError ? (
        <span className="text-2xs text-accent-red" data-testid={`${testId}-error`}>
          عمقِ بازار نمی‌رسد — این پنج سطر از خودِ تابلو خوانده می‌شود، نه ساخته
        </span>
      ) : null}

      {!isPending && !isError && levels.length === 0 ? (
        <span className="text-2xs leading-5 text-text-muted" data-testid={`${testId}-empty`}>
          {data?.message ?? 'پنج سطرِ این نماد درِ تابلو ثبت نشده — بعد از نخستین همگام‌سازیِ تابلو می‌آید'}
        </span>
      ) : null}

      {levels.length > 0 ? (
        <>
          {/* درِ سایدبارِ ۲۴۰پیکسلی دو سو کنارِ هم «تو هم» می‌افتند (رأیِ مالک
              1405-07-20: حجم و تعداد قابل دیدن نیستند)؛ آنجا هر سو تمامِ عرض
              را می‌گیرد، درِ پنلِ پهنِ دیده‌بان کنارِ هم می‌مانند. */}
          <div className={`grid gap-1 ${compact ? 'grid-cols-1' : 'grid-cols-2'}`}
               data-testid={`${testId}-rows`}>
            <BookColumn levels={levels} side="buy" max={max} testId={testId} />
            <BookColumn levels={levels} side="sell" max={max} testId={testId} />
          </div>
          <div className="flex flex-col gap-0.5 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1 text-3xs"
               data-testid={`${testId}-totals`}>
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ تقاضا</span>
              <span className="num font-bold text-accent-green">
                {totals?.buy_vol != null ? fmtInt(totals.buy_vol) : '—'}
                {totals?.buy_cnt != null ? (
                  <span className="font-normal text-text-muted"> ({toFaDigits(totals.buy_cnt)} سفارش)</span>
                ) : null}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ عرضه</span>
              <span className="num font-bold text-accent-red">
                {totals?.sell_vol != null ? fmtInt(totals.sell_vol) : '—'}
                {totals?.sell_cnt != null ? (
                  <span className="font-normal text-text-muted"> ({toFaDigits(totals.sell_cnt)} سفارش)</span>
                ) : null}
              </span>
            </div>
          </div>
          {!compact ? (
            <p className="text-3xs leading-4 text-text-muted">
              قیمت و حجم از blDsِ همین روزِ خودِ تابلو است؛ «—» یعنی آن سطر برایِ
              این نماد ثبت نشده، نه اینکه صف صفر باشد.
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
