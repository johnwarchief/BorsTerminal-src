// features/portfolio/components/WatchlistSection.tsx — واچ‌لیست درِ «پرتفوی فعلی»
//
// رأیِ مالک (§۱ و §۶task): واچ‌لیست تبِ مستقلِ ناوبری نیست؛ داخلِ همان
// workspaceای است که کاربر واردش می‌شود: Portfolio ➔ پرتفوی فعلی ➔ Watchlist.
//
// داده از `/api/watchlist` است — همان `user_watchlists` بک‌اند؛ هیچ فهرستِ
// موازیِ تازه‌ای درِ فرانت نگهداری نمی‌شود (§۳۱). قیمت/تغییر/وضعیتِ نشست هم از
// همان فیڈِ مشترکِ تابلو می‌آید (`useMarketFeedShared`)، پس دیدنِ واچ‌لیست
// هیچ درخواستِ تازه‌ای به بازار اضافه نمی‌کند (§۸).
import { useMemo } from 'react';
import { useNavigate } from 'react-router';
import { EmptyState } from '@shared/components/EmptyState';
import { RetryAction } from '@shared/components/RetryAction';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { useUserWatchlist } from '@shared/api/userWatchlist';
import WatchlistStar from '@shared/components/WatchlistStar';

type FeedRow = Parameters<Parameters<typeof useMarketFeedShared>[0]>[0]['data'][number];
const EMPTY_MAP = new Map<string, FeedRow>();
import { useSymbolStore } from '@shared/stores/symbolStore';

/** `۱۴۰۵/۰۷/۱۶` از `added_at`ِ ISO سرور؛ بی‌تاریخ «—» (نه تاریخِ ساختگی) */
function addedLabel(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(d);
}

export default function WatchlistSection() {
  const { rows, count, limit, loading, failed, message, refresh } = useUserWatchlist();
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const navigate = useNavigate();
  // یک انتخاب از فیڈِ مشترکِ تابلو: بی‌درخواستِ تازه، فقط نگاشتِ نماد → ردیف
  const feedQ = useMarketFeedShared((f) => {
    const m = new Map<string, (typeof f.data)[number]>();
    for (const r of f.data ?? []) m.set(normalizeFa(String(r.symbol ?? '')), r);
    return m;
  }, 0);
  const byNorm = feedQ.data ?? EMPTY_MAP;
  const priced = useMemo(
    () => rows.map((r) => ({ ...r, feed: byNorm.get(normalizeFa(r.symbol)) ?? null })),
    [rows, byNorm],
  );

  return (
    <section
      className="flex flex-col gap-1 rounded-2xl border border-border-c bg-bg-card/40"
      data-testid="portfolio-watchlist"
    >
      <header className="flex flex-wrap items-center gap-2 border-b border-border-c/60 px-3 py-2">
        <h3 className="text-xs font-black text-text-primary sm:text-sm">واچ‌لیست</h3>
        <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-bold text-text-secondary">
          {toFaDigits(count)} سهم
        </span>
        {limit != null ? (
          <span className="num text-3xs text-text-muted" title="ظرفیتِ واچ‌لیستِ کاربر — سقفی که به تعدادِ نمادهایِ غربالگری ربطی ندارد">
            سقفِ کاربر: {toFaDigits(limit)}
          </span>
        ) : null}
        <button
          type="button"
          onClick={refresh}
          data-testid="portfolio-watchlist-refresh"
          className="ms-auto rounded-lg border border-border-c px-2 py-0.5 text-3xs font-bold text-text-secondary hover:border-accent-blue hover:text-accent-blue"
        >
          تازه‌سازی
        </button>
      </header>

      {loading ? (
        <p className="px-3 py-3 text-3xs text-text-muted">در حالِ خواندنِ واچ‌لیست…</p>
      ) : failed ? (
        <div className="px-3 py-3">
          <EmptyState title="واچ‌لیست نخوانده شد" hint={message ?? undefined}
                      action={<RetryAction onRetry={refresh} testId="portfolio-watchlist-retry" />} />
        </div>
      ) : priced.length === 0 ? (
        <p className="px-3 py-3 text-3xs text-text-muted" data-testid="portfolio-watchlist-empty">
          خالی است. درِ تابلوخوانی یا بنیادی رویِ ☆ کنارِ نماد بزن تا برایِ رصدِ
          روزهایِ بعد اینجا بماند.
        </p>
      ) : (
        <div className="max-h-[300px] overflow-y-auto">
          <table className="w-full table-fixed border-collapse text-xs">
            <colgroup>
              <col style={{ width: '26%' }} /><col style={{ width: '14%' }} />
              <col style={{ width: '12%' }} /><col style={{ width: '16%' }} />
              <col style={{ width: '18%' }} /><col style={{ width: '14%' }} />
            </colgroup>
            <thead className="sticky top-0 bg-bg-primary/95 text-3xs text-text-muted">
              <tr>
                <th className="px-2 py-1 text-start font-bold">نماد</th>
                <th className="px-2 py-1 text-end font-bold">آخرین</th>
                <th className="px-2 py-1 text-end font-bold">تغییر٪</th>
                <th className="px-2 py-1 text-start font-bold">وضعیتِ نشست</th>
                <th className="px-2 py-1 text-start font-bold">به فهرست از</th>
                <th className="px-2 py-1 text-end font-bold">اقدام</th>
              </tr>
            </thead>
            <tbody>
              {priced.map((r) => {
                const f = r.feed;
                const live = f ? (f.is_live === false ? 'آخرینِ نشست' : 'زنده') : 'بی‌ردیفِ تابلو';
                return (
                  <tr key={r.norm || r.symbol} className="group border-b border-border-c/40 last:border-0">
                    <td className="px-2 py-1 text-start">
                      <span className="flex items-center gap-1.5">
                        <WatchlistStar symbol={r.symbol} name={r.name} />
                        <button
                          type="button"
                          data-testid={`portfolio-watchlist-open-${r.symbol}`}
                          onClick={() => { setSymbol(r.symbol); navigate(`/master/${encodeURIComponent(r.symbol)}`); }}
                          className="truncate font-black text-text-primary hover:text-accent-blue"
                          title={`${r.name || ''} — باز کردنِ نماد`}
                        >
                          {r.symbol}
                        </button>
                      </span>
                    </td>
                    <td className="px-2 py-1 text-end">
                      <span className="num">{f?.p_last != null ? fmtInt(f.p_last) : '—'}</span>
                    </td>
                    <td className={`px-2 py-1 text-end ${
                      (f?.percent_change ?? 0) > 0 ? 'text-accent-green' : (f?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
                    }`}>
                      <span className="num">{f?.percent_change != null ? fmtPct(f.percent_change) : '—'}</span>
                    </td>
                    <td className="px-2 py-1 text-start text-3xs text-text-secondary">{live}</td>
                    <td className="num px-2 py-1 text-start text-3xs text-text-muted">{addedLabel(r.added_at)}</td>
                    <td className="px-2 py-1 text-end text-3xs text-text-muted">
                      {r.note ? <span title={r.note}>یادداشت دارد</span> : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
