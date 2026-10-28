import clsx from 'clsx';
import { normalizeFa } from '@shared/lib/faSearch';
import { useUserWatchlist, useWatchlistToggle } from '../api/useWatchlist';

export function WatchlistButton({ symbol, name }: { symbol: string; name?: string }) {
  const query = useUserWatchlist();
  const toggle = useWatchlistToggle();
  const norm = normalizeFa(symbol);
  const listed = (query.data?.data ?? []).some((row) => normalizeFa(row.symbol) === norm);
  const unavailable = query.isError;
  const disabled = query.isPending || toggle.isPending || unavailable;
  const label = unavailable ? 'واچ‌لیست در دسترس نیست' : listed ? 'حذف از واچ‌لیست' : 'افزودن به واچ‌لیست';

  return (
    <div className="min-w-0">
      <button
        type="button"
        data-testid="watchlist-toggle"
        disabled={disabled}
        onClick={() => toggle.mutate({ symbol, name, remove: listed })}
        className={clsx(
          'h-7 w-full rounded-[var(--radius-sm)] border border-line bg-panel-2 t-10 font-bold text-text-2 hover:border-accent/60 hover:text-text disabled:cursor-not-allowed disabled:opacity-50',
          !disabled && !listed && 'liquid-rim',
        )}
      >
        {toggle.isPending ? 'در حال ثبت…' : label}
      </button>
      {toggle.isError ? (
        <p className="mt-1 t-85 text-down" role="alert">
          تغییر واچ‌لیست ثبت نشد؛ فهرست قبلی برگشت. {toggle.error.message}
        </p>
      ) : null}
    </div>
  );
}
