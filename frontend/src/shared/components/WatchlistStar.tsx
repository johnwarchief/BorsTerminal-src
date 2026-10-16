// shared/components/WatchlistStar.tsx — ستارۀ «درِ واچ‌لیست» کنارِ نامِ نماد
//
// نشاندنِ دو نشان کنارِ هم (§۵ِ task):
//   ☑ = همین حالا انتخاب شده (موقتی، `selectedSymbolsStore`)
//   ★ = عضوِ واچ‌لیستِ ماندگارِ کاربر (`/api/watchlist`)
// این دو دو چیزند و این کامپوننت عمداً هیچ نقشی درِ انتخابِ موقت ندارد.
//
// کلیک رویِ ستاره به صفحۀ نماد نمی‌رود (ردیفِ تابلو هم کلیک دارد هم Space/Enter
// — `TapeTable.tsx:294-301`)؛ add/remove optimistic است و بی‌rfetchِ صفحه‌هایِ دیگر.
import { useIsWatchlisted, useWatchlistToggle, watchlistLabel } from '@shared/api/userWatchlist';

export default function WatchlistStar({
  symbol,
  name = '',
  className = '',
}: {
  symbol: string;
  name?: string;
  className?: string;
}) {
  const inList = useIsWatchlisted(symbol);
  const toggle = useWatchlistToggle();
  const label = watchlistLabel(symbol, inList);
  return (
    <button
      type="button"
      role="button"
      aria-pressed={inList}
      aria-label={label}
      title={label}
      data-testid={`watch-star-${symbol}`}
      data-in-list={inList ? '1' : '0'}
      disabled={toggle.isPending && toggle.variables?.symbol === symbol}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        toggle.mutate({ symbol, name, remove: inList });
      }}
      onKeyDown={(e) => {
        if (e.key === ' ' || e.key === 'Enter') {
          e.stopPropagation();
          e.preventDefault();
          toggle.mutate({ symbol, name, remove: inList });
        }
      }}
      // همان قاعدۀ جعبۀ انتخاب (رأیِ مالک ۱۴۰۵-۰۷-۱۷): با hoverِ ردیف یا focus
      // ظاهر می‌شود، و وقتی نماد عضو واچ‌لیست است همیشه دیده می‌شود — ستاره
      // همان‌جا نشانۀ «ماندگار بودن» است، پنهانش یعنی اطلاعاتِ دیدنی حذف شده.
      className={`-m-1 shrink-0 cursor-pointer px-1 text-sm leading-none transition-opacity duration-150 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 data-[in-list=1]:opacity-100 [@media(hover:none)]:opacity-100 motion-reduce:transition-none ${inList ? 'text-accent-amber' : 'text-text-muted hover:text-accent-amber'} ${className}`}
    >
      {inList ? '★' : '☆'}
    </button>
  );
}
