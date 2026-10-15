// features/portfolio/routes/TradingPage.tsx
// چرا این صفحه هست: دوِ پنلِ آماده درِ برنامه مقصدِ مستقلِ ناوبری نداشتند.
// `ExecutionPanel` تنها ازِ درونِ «دیده‌بان بازار» دیده می‌شد (`WatchSummaryPanel.tsx:95`
// که `WatchMarketWorkspace` درِ تب‌هایِ سرخطی/بازارِ دفترچۀِ یکِ نماد mount می‌کند) —
// یعنی اول باید نمادِ خودت را درِ آنِ صفحّه باز می‌کردی. `BotPanel` هم تنها درِ
// انتهایِ صفحۀِ پرتفوی بود. مأموریت (۱۴۰۵-۰۷-۲۳): یکِ مقصدِ روشن درِ ناوبری برایِ هرِ دو،
// بی‌بازطراحیِ موتورِ سفارش وِ بی‌منطقِ اجراییِ دوم. هرِ دوِ پنل همان‌جا مصرف می‌شوند
// که هستند؛ اینِ صفحه هیچِ پنلِ تقلبیِ دیگری نمی‌سازد.
//
//-paper: کاغذی پیش‌فرضِ خودِ سرویس است (`/api/execution/status` وِ
// `/api/bot/status` را همان برمی‌گرداند) وِ اینِ صفحه هیچِ قفلی را باز نمی‌کند؛
// فقط نشان می‌دهد. اجرایِ واقعی نیازمندِ نشستِ معتبر + capabilityهایِ اعلام‌شده
// + تأییدِ صریحِ کاربر درِ خودِ پنل است.

import { useMemo, useState } from 'react';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import type { MarketRow } from '@shared/types/marketRow';
import { BotPanel } from '../components/BotPanel';
import { ExecutionPanel } from '../components/ExecutionPanel';

type Tab = 'execution' | 'bot';

const TABS: { id: Tab; label: string; testid: string }[] = [
  { id: 'execution', label: 'سرخطی و اجرای سفارش', testid: 'trade-tab-execution' },
  { id: 'bot', label: 'ربات معاملاتی', testid: 'trade-tab-bot' },
];

// فهرستِ نماد کوتاه نگه داشته می‌شود: اینِ صفحه میزبانِ پنل است، نه تابلو.
const PICKER_LIMIT = 40;

export default function TradingPage() {
  const { data, isLoading, isError } = useMarketFeed();
  const rows = useMemo(() => data?.data ?? [], [data]);
  const [tab, setTab] = useState<Tab>('execution');
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState<string | null>(null);

  const candidates = useMemo(() => {
    const q = query.trim();
    const list = q ? rows.filter((r) => (r.symbol ?? '').includes(q)) : rows;
    return list.slice(0, PICKER_LIMIT);
  }, [rows, query]);

  // بی‌انتخاب، نمادِ اولِ تابلو؛ پس پنل همیشه یکِ هندسه دارد وِ «چیزی انتخاب کنید»
  // تنها وقتی دیده می‌شود که تابلو واقعاً داده ندارد.
  const row: MarketRow | null = useMemo(
    () => rows.find((r) => r.symbol === picked) ?? rows[0] ?? null,
    [rows, picked],
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-col gap-2 p-2 sm:p-3" data-testid="trading-page">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-sm font-black text-text-primary">معامله</h1>
        <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label="بخش‌هایِ معامله">
          {TABS.map((t) => {
            const on = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={on}
                data-testid={t.testid}
                onClick={() => setTab(t.id)}
                className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-colors ${
                  on
                    ? 'border-accent-blue/60 bg-accent-blue/10 text-accent-blue'
                    : 'border-border-c bg-bg-card/40 text-text-secondary hover:text-text-primary'
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </header>

      <p className="text-3xs leading-4 text-text-muted" data-testid="trading-mode-note">
        کاغذی پیش‌فرض است. اجرایِ واقعی فقط باِ نشستِ معتبرِ کارگزاری، قابلیتِ اعلام‌شدۀ
        خودِ سرویس وِ تأییدِ صریحِ شما درِ همینِ پنل ممکن می‌شود؛ بازِ کردنِ اینِ صفحه هیچِ
        سفارشی نمی‌فرستد وِ هیچِ رباتی را اجرا نمی‌کند.
      </p>

      {tab === 'execution' ? (
        <div className="flex min-h-0 min-w-0 flex-col gap-2 lg:flex-row">
          <section
            className="w-full shrink-0 rounded-xl border border-border-c bg-bg-card/30 p-2 lg:w-56"
            aria-label="انتخابِ نماد"
          >
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست‌وجویِ نماد"
              aria-label="جست‌وجویِ نماد"
              data-testid="trade-symbol-search"
              className="w-full rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
            />
            <ul className="mt-1.5 flex max-h-64 flex-col gap-0.5 overflow-y-auto" data-testid="trade-symbol-list">
              {candidates.map((r) => {
                const on = row?.symbol === r.symbol;
                return (
                  <li key={r.symbol} className="shrink-0">
                    <button
                      type="button"
                      onClick={() => setPicked(r.symbol)}
                      aria-pressed={on}
                      data-testid={`trade-symbol-${r.symbol}`}
                      className={`w-full rounded-lg px-2 py-1 text-start text-2xs transition-colors ${
                        on ? 'bg-accent-blue/10 font-black text-accent-blue' : 'text-text-secondary hover:bg-bg-card'
                      }`}
                    >
                      {r.symbol}
                    </button>
                  </li>
                );
              })}
              {candidates.length === 0 ? (
                <li className="px-2 py-1 text-3xs text-text-muted" data-testid="trade-symbol-empty">
                  {isLoading ? 'تابلو درِ حالِ بارگذاری است' : isError ? 'تابلو باز نمی‌شود' : 'نمادی باِ اینِ نام نیست'}
                </li>
              ) : null}
            </ul>
          </section>

          {row ? (
            <div className="min-w-0 flex-1">
              <ExecutionPanel symbol={row.symbol} row={row} />
            </div>
          ) : (
            <p className="text-2xs text-text-muted" data-testid="trade-execution-unavailable">
              تا تابلو داده نداشته باشد، پنلِ معامله نمادی برایِ نشان دادن ندارد.
            </p>
          )}
        </div>
      ) : (
        <BotPanel />
      )}
    </div>
  );
}
