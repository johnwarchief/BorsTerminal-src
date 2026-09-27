// features/technical/components/SidebarOrderBook.tsx -- تب ۴ سایدبار: پنج مظنه
// صفِ واقعیِ خرید و فروشِ همان نمادی که رویِ چارت است. تا پیش از این این پنل
// رویِ چارت شناور بود و سطرها را از قیمت و حجمِ کل *می‌ساخت*؛ حالا پنج خطِ
// واقعی از blDsِ خودِ تابلو خوانده می‌شود و بی‌داده، بی‌داده می‌ماند.
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { useOrderBook, type OrderBookLevel } from '../api/useOrderBook';

type Side = 'buy' | 'sell';

/** حجمِ سفارش رویِ هر خط، نسبت به پرحجم‌ترین خطِ همان پنج سطر */
function barPct(vol: number, max: number): number {
  if (!max || !vol) return 0;
  return Math.min(100, Math.round((vol / max) * 100));
}

/** '2026-09-27 11:30:42' → ۱۱:۳۰

 فقط ساعتِ همگام‌سازی نشان داده می‌شود: d_even/h_evenِ تابلو در بانکِ محلی
 یک قالبِ ثابت ندارند (نشستِ جاری میلادی نوشته می‌شود وقتی ردیف dEven
 نداشته باشد)، پس هیچ تاریخی از آن‌ها ساخته نمی‌شود. */
function syncStamp(when?: string | null): string | null {
  const m = /^\d{4}-\d{2}-\d{2} (\d{2}:\d{2})/.exec(when ?? '');
  return m ? toFaDigits(m[1]) : null;
}

function BookRows({ levels, side, max }: { levels: OrderBookLevel[]; side: Side; max: number }) {
  return (
    <ul className="flex flex-col gap-px">
      {levels.map((ln, i) => {
        const px = side === 'buy' ? ln.buy_px : ln.sell_px;
        const vol = side === 'buy' ? ln.buy_vol : ln.sell_vol;
        const cnt = side === 'buy' ? ln.buy_cnt : ln.sell_cnt;
        const tone = side === 'buy' ? 'text-[#089981]' : 'text-[#f23645]';
        return (
          <li key={i} className="relative flex items-center justify-between gap-1 overflow-hidden rounded px-1.5 py-1">
            <span
              aria-hidden
              className={`absolute inset-y-0 ${side === 'buy' ? 'right-0' : 'left-0'} ${
                side === 'buy' ? 'bg-[#089981]/10' : 'bg-[#f23645]/10'
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

export function SidebarOrderBook({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useOrderBook(symbol);
  const levels = data?.levels ?? [];
  const max = useMemo(() => {
    let m = 0;
    for (const ln of levels) m = Math.max(m, ln.buy_vol, ln.sell_vol);
    return m;
  }, [levels]);
  const stamp = syncStamp(data?.session?.updated_at);
  const totals = data?.totals;

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-orderbook">
      <div className="flex items-center justify-between gap-2 px-1">
        <span className="min-w-0 truncate text-xs font-bold text-text-primary">{symbol}</span>
        <span className="shrink-0 text-[10px] text-text-muted" title="زمانِ آخرین همگام‌سازیِ تابلو برایِ این نماد">
          {stamp ? `همگامِ ساعتِ ${stamp}` : 'بی‌زمان'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1 text-center text-[10px] font-bold text-text-secondary">
        <div className="rounded bg-[#089981]/10 py-0.5 text-[#089981]">تقاضا</div>
        <div className="rounded bg-[#f23645]/10 py-0.5 text-[#f23645]">عرضه</div>
      </div>

      {isLoading ? <span className="px-1 text-[11px] text-text-secondary">در حال خواندنِ صف‌ها...</span> : null}
      {isError ? <span className="px-1 text-[11px] text-accent-red">خطا در دریافتِ عمقِ بازار</span> : null}

      {!isLoading && !isError && levels.length === 0 ? (
        <span className="px-1 text-[11px] leading-5 text-text-muted" data-testid="sidebar-orderbook-empty">
          {data?.message ?? 'عمقِ پنج‌سطحی این نماد ذخیره نشده — بعد از نخستین همگام‌سازیِ تابلو می‌آید'}
        </span>
      ) : null}

      {levels.length > 0 ? (
        <>
          <div className="grid grid-cols-2 gap-1" data-testid="sidebar-orderbook-rows">
            <BookRows levels={levels} side="buy" max={max} />
            <BookRows levels={levels} side="sell" max={max} />
          </div>
          <div className="flex flex-col gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1.5 text-[10px]" data-testid="sidebar-orderbook-totals">
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ تقاضا</span>
              <span className="num font-bold text-[#089981]">
                {totals?.buy_vol != null ? fmtInt(totals.buy_vol) : '—'}
                {totals?.buy_cnt != null ? (
                  <span className="mr-1 font-normal text-text-muted">({toFaDigits(totals.buy_cnt)} سفارش)</span>
                ) : null}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-muted">جمعِ عرضه</span>
              <span className="num font-bold text-[#f23645]">
                {totals?.sell_vol != null ? fmtInt(totals.sell_vol) : '—'}
                {totals?.sell_cnt != null ? (
                  <span className="mr-1 font-normal text-text-muted">({toFaDigits(totals.sell_cnt)} سفارش)</span>
                ) : null}
              </span>
            </div>
          </div>
          <p className="px-1 text-[9px] leading-4 text-text-muted">
            قیمت‌ها ریال است. پنج سطرِ اولِ هر صف، آن‌طور که تابلو می‌فرستد.
          </p>
        </>
      ) : null}
    </div>
  );
}
