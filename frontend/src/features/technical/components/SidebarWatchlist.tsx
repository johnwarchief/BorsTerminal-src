// features/technical/components/SidebarWatchlist.tsx -- تب ۱ سایدبار: دیده‌بان نمادها سبک تریدینگ‌ویو
// ردیف‌های متراکم‌تر، فونت مونو/تبولار، سبز زمردی (#089981) و قرمز ملایم (#f23645)
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
    <div className="flex flex-col h-full gap-1.5" data-testid="sidebar-watchlist">
      {/* جستجو */}
      <div className="relative">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="جستجوی نماد..."
          aria-label="جستجوی نماد در دیده‌بان"
          data-testid="sidebar-watch-search"
          className="w-full rounded border border-[var(--hairline)] bg-[var(--bg-primary)] px-2.5 py-1 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#2962ff] transition-colors"
        />
      </div>

      {/* سرستون ۳ گانه سبک تریدینگ‌ویو */}
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-1.5 px-2 py-1 text-[10px] font-bold text-[var(--text-muted)] border-b border-[var(--hairline)]">
        <span>نماد</span>
        <span className="text-end">آخرین قیمت</span>
        <span className="w-16 text-end">تغییر %</span>
      </div>

      {isLoading ? <span className="px-1 text-[11px] text-[var(--text-secondary)]">در حال دریافت دیده‌بان...</span> : null}
      {isError ? <span className="px-1 text-[11px] text-[#f23645]">خطا در دریافت تابلو بازار</span> : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <span className="px-1 text-[11px] text-[var(--text-muted)]" data-testid="sidebar-watch-empty">
          نمادی یافت نشد
        </span>
      ) : null}

      <ul className="flex flex-col divide-y divide-[var(--hairline)]/30 overflow-y-auto" data-testid="sidebar-watch-list">
        {rows.map((r) => {
          const up = (r.percent_change ?? 0) >= 0;
          return (
            <li key={r.ins_code ?? r.symbol}>
              <button
                type="button"
                onClick={() => onSelect(r.symbol)}
                title={r.name ?? ''}
                className="grid w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-1.5 px-2 py-1.5 text-start transition-colors hover:bg-[var(--bg-tertiary)]/70 cursor-pointer"
              >
                <div className="flex flex-col truncate">
                  <span className="truncate text-xs font-bold text-[var(--text-primary)]">{r.symbol}</span>
                  {r.name && <span className="truncate text-[10px] text-[var(--text-muted)] leading-tight">{r.name}</span>}
                </div>
                <span className="num font-mono tabular-nums text-xs font-semibold text-[var(--text-primary)]">
                  {fmtPrice(r.p_last ?? r.p_closing)}
                </span>
                <span
                  className={`num font-mono tabular-nums w-16 text-end text-[11px] font-bold ${
                    up ? 'text-[#089981]' : 'text-[#f23645]'
                  }`}
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
