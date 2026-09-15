// features/technical/components/SidebarWatchlist.tsx -- تب ۱ سایدبار: دیده‌بان نمادها
// جستجو + لیست سبک (آخرین قیمت/درصد تغییر/نسبت حجم)؛ کلیک ⇒ همان نماد روی چارت.
import { useMemo, useState } from 'react';
import { toFaDigits, fmtPct } from '@shared/lib/fmt';
import { filterWatchlist, useWatchlistFeed } from '../api/useWatchlist';

function fmtPrice(p: number | null | undefined): string {
  return p == null || !Number.isFinite(p) ? '-' : toFaDigits(Math.round(p).toLocaleString('en-US'));
}

export function SidebarWatchlist({ onSelect }: { onSelect: (s: string) => void }) {
  const [q, setQ] = useState('');
  const { data, isLoading, isError } = useWatchlistFeed();
  const rows = useMemo(() => filterWatchlist(data?.data ?? [], q), [data, q]);

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-watchlist">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="جستجوی نماد..."
        aria-label="جستجوی نماد در دیده‌بان"
        data-testid="sidebar-watch-search"
        className="w-full rounded-lg border border-border-c bg-bg-card px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-border-accent"
      />

      {isLoading ? <span className="px-1 text-[11px] text-text-secondary">در حال دریافت دیده‌بان...</span> : null}
      {isError ? <span className="px-1 text-[11px] text-accent-red">خطا در دریافت تابلو بازار</span> : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <span className="px-1 text-[11px] text-text-muted" data-testid="sidebar-watch-empty">
          نمادی یافت نشد
        </span>
      ) : null}

      <ul className="flex flex-col gap-0.5" data-testid="sidebar-watch-list">
        {rows.map((r) => {
          const up = (r.percent_change ?? 0) >= 0;
          return (
            <li key={r.ins_code ?? r.symbol}>
              <button
                type="button"
                onClick={() => onSelect(r.symbol)}
                title={r.name ?? ''}
                className="grid w-full grid-cols-[1fr_auto_auto] items-center gap-2 rounded-lg border border-transparent px-2 py-0.5 text-right transition-colors hover:border-border-c hover:bg-bg-card"
              >
                <span className="truncate text-xs font-bold text-text-primary">{r.symbol}</span>
                <span className="num text-xs font-bold text-text-primary">{fmtPrice(r.p_last ?? r.p_closing)}</span>
                <span
                  className={`num w-14 text-left text-[11px] font-bold ${up ? 'text-accent-green' : 'text-accent-red'}`}
                >
                  {r.percent_change == null ? '-' : fmtPct(r.percent_change)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
