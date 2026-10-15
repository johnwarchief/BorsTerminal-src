// features/market/components/MarketChartSection.tsx -- نمودارِ پیشرفته درِ «وضعیت بازار» (صفحۀ ۵)
//
// مرجع صفحۀ ۵ یک چارتِ تمام‌قد با دیده‌بان و تابلو است. قاعدۀ مأموریت صریح است:
// «از موتورِ چارتِ واقعیِ موجود استفاده کن؛ نمودارِ ثابت یا تصویرِ تزئینی
// جایگزینِ آن نیست». پس همین‌جا همان `KLineChartWrapper` نشسته است — نه یک
// SVGِ کندل‌نما، و نه یک iframe به تبِ تکنیکال.
//
// چرا نشستنِ *همان* کامپوننت و نه کپیِ مسیرش: چارت خودش `/api/chart/{symbol}`
// را می‌خواند، زنجیرۀ تعدیلِ سرور را می‌پزد، تایم‌فریم و مبنایِ تعدیل و
// موتورِ رندر را از `fts.chart.settings.v1` می‌خواند و نوارِ ابزارش را خودش
// می‌سازد. پیاده‌سازیِ دوبارۀ آن درِ این تب یعنی دو منبعِ حقیقت برایِ «همان
// کندل» — و دقیقاً همان چیزی که درِ فاز ۵F بستیم، یکی‌کردنِ مسیرِ تعدیل بود.
//
// جست‌وجویِ نماد این‌جا دوباره ساخته نمی‌شود: `SymbolSearchModal` درِ نوارِ ابزارِ
// خودِ موتور است (`KLineChartWrapper.tsx:2816`) و همان `/api/market` را می‌خواند.
// کاری که این‌جا اضافه می‌شود «انتخابِ سریع از داده‌هایِ واقعیِ همین صفحه» است:
// دیده‌بانِ کاربر (`/api/watchlist`) و نمادهای پرتراکنشِ همین تابلو
// (`/api/mstat/mainwatch`) — هیچ‌کدام فهرستِ دست‌نویس یا نمادِ بی‌ردیفِ بانک
// (BTCUSD/XAUTBHR مرجع) نیستند.
import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';
import { useUserWatchlist } from '@shared/api/userWatchlist';
import { useMstatMainwatch } from '../api/useMarketStatusFeed';
import { StatusError, StatusLoading, StatusNoData, StatusSection } from './StatusShell';
import { TONE_CLASS, toneOf } from '../lib/tones';

const NnChart = lazy(() => import('@features/technical/nahayatnegar/components/KLineChartWrapper'));

// ارتفاعِ میزبان = کفِ ارتفاعِ خودِ موتور چارت (`.nahayat-negar-container` با
// `min-height:520px`). با ۴۲۰px، ۱۰۲pxِ پایینِ چارت درِ میزبانِ `overflow-hidden`
// بریده می‌شد و هیچ اسکرولی به آن نمی‌رسید (سنجشِ ۱۳۶۶×۷۶۸: lost=102px).
const CHART_H = 'h-[520px] w-full';

export function MarketChartSection({ initialSymbol = 'فولاد' }: { initialSymbol?: string }) {
  const [symbol, setSymbol] = useState(initialSymbol);
  const watch = useUserWatchlist();
  const board = useMstatMainwatch('all');

  const pick = useCallback((s: string) => {
    if (s) setSymbol(s);
  }, []);

  const rows = useMemo(() => board.data?.rows ?? [], [board.data]);
  const current = useMemo(() => rows.find((r) => r.symbol === symbol) ?? null, [rows, symbol]);
  // قیمت‌ها از ردیفِ واقعیِ تابلو به موتور می‌رسند؛ بی‌ردیف `null` می‌ماند تا
  // خودِ چارت بگوید «دادۀ تابلو نرسیده»، نه اینکه صفر جا بزند.
  const boardRow = useMemo(
    () =>
      current
        ? {
            p_last: current.p_last,
            p_closing: current.p_closing,
            percent_change: current.pct_close ?? current.pct_last,
          }
        : null,
    [current],
  );
  const active = useMemo(
    () =>
      [...rows]
        .sort((a, b) => (b.trades ?? 0) - (a.trades ?? 0))
        .slice(0, 8)
        .map((r) => ({ symbol: r.symbol, name: r.name, pct: r.pct_close ?? r.pct_last })),
    [rows],
  );

  return (
    <StatusSection
      testId="ms-chart"
      title="نمودارِ پیشرفتهٔ همین نماد"
      hint="موتورِ چارتِ واقعیِ برنامه (klinecharts / nahayatnegar) — تایم‌فریم، مبنایِ تعدیل و ابزارها کار می‌کنند"
      asof={board.data?.asof}
      badge="جست‌وجویِ نماد، تایم‌فریم و مبنایِ تعدیل درِ نوارِ ابزارِ خودِ موتور است؛ این‌جا تنظیمِ دومی نساخته می‌شود"
      toolbar={
        <div className="flex flex-wrap items-center gap-2" data-testid="ms-chart-toolbar">
          <span className="rounded-lg border border-border-c bg-bg-secondary px-2 py-1 text-2xs font-black text-text-primary" data-testid="ms-chart-symbol">
            {symbol}
          </span>
          <span className="text-3xs text-text-muted" title="از ردیفِ واقعیِ تابلو، نه از حدس">
            {current?.name || 'بی‌نام از تابلو'}
          </span>
          <Link
            to={`/technical/${encodeURIComponent(symbol)}`}
            data-testid="ms-chart-open-technical"
            className="ms-auto rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs font-bold text-text-secondary hover:text-accent-blue"
            title="نمونۀ کاملِ ابزارها، لایه‌های FTS و بازپخش در تب تکنیکال"
          >
            بازکردن در تب تکنیکال
          </Link>
        </div>
      }
    >
      <div className="grid grid-cols-1 gap-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,240px)]">
        <div
          className={`relative min-w-0 overflow-hidden rounded-lg border border-border-c ${CHART_H}`}
          data-testid="ms-chart-host"
        >
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-2xs text-text-muted" data-testid="ms-chart-loading">
                در حال بارگذاری چارت...
              </div>
            }
          >
            <NnChart
              initialSymbol={symbol}
              initialName={current?.name ?? symbol}
              boardRow={boardRow}
              onSymbolChange={(s) => pick(s.symbol)}
            />
          </Suspense>
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex min-w-0 flex-col gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
            <h4 className="text-2xs font-black text-text-primary">
              دیده‌بان{watch.count ? ` (${toFaDigits(watch.count)})` : ''}
            </h4>
            {watch.loading && !watch.ready ? (
              <StatusLoading testId="ms-chart-watch" />
            ) : watch.failed ? (
              <StatusError testId="ms-chart-watch" onRetry={watch.refresh} />
            ) : !watch.rows.length ? (
              <p data-testid="ms-chart-watch-empty" className="text-3xs text-text-muted">
                دیده‌بان خالی است — نمادی از ستارۀ ردیف‌هایِ تابلو اضافه کن.
                {watch.message ? ` (${watch.message})` : ''}
              </p>
            ) : (
              <ul className="flex min-w-0 flex-col gap-0.5" data-testid="ms-chart-watch-list">
                {watch.rows.slice(0, 10).map((r) => (
                  <li key={r.norm}>
                    <button
                      type="button"
                      data-testid={`ms-chart-watch-${r.symbol}`}
                      onClick={() => pick(r.symbol)}
                      className={`w-full truncate rounded px-1 py-0.5 text-start text-2xs hover:bg-bg-secondary ${
                        symbol === r.symbol ? 'font-black text-accent-blue' : 'text-text-primary'
                      }`}
                    >
                      {r.symbol}
                      <span className="text-3xs text-text-muted"> {r.name || ''}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
            <h4 className="text-2xs font-black text-text-primary" title="بر پایۀ تعدادِ معاملاتِ همین نشست">
              پرتراکنشِ همین تابلو
            </h4>
            {board.isLoading && !board.data ? (
              <StatusLoading testId="ms-chart-board" />
            ) : board.isError && !board.data ? (
              <StatusError testId="ms-chart-board" onRetry={() => void board.refetch()} />
            ) : active.length ? (
              <BoardSummaryCard testId="ms-chart-board-list" rows={active} current={symbol} onPick={pick} />
            ) : (
              <StatusNoData testId="ms-chart-board" />
            )}
          </div>
        </div>
      </div>

      <p className="text-3xs text-text-muted" data-testid="ms-chart-footnote">
        چارتِ همین صفحه همان موتورِ تبِ تکنیکال است (نه تصویر و نه نمودارِ ثابت).
        لایه‌های FTS و بازپخش درِ تب تکنیکال می‌مانند تا یک تحلیلِ دوم درِ این تب
        ساخته نشود.
      </p>
    </StatusSection>
  );
}

/** ردیف‌هایِ فشردهٔ تابلو برایِ کنارِ نمودار (صفحۀ ۵ «تابلو» با درصد) — کلیک، نمادِ چارت را عوض می‌کند */
export function BoardSummaryCard({
  testId,
  rows,
  current = null,
  onPick,
}: {
  testId: string;
  rows: { symbol: string; pct: number | null | undefined; name?: string | null }[];
  current?: string | null;
  onPick?: (symbol: string) => void;
}) {
  if (!rows.length) return <StatusNoData testId={testId} />;
  return (
    <ul className="grid grid-cols-1 gap-0.5" data-testid={testId}>
      {rows.map((r) => {
        const tone = toneOf(r.pct ?? null);
        return (
          <li key={r.symbol}>
            <button
              type="button"
              data-testid={`${testId}-row-${r.symbol}`}
              disabled={!onPick}
              onClick={() => onPick?.(r.symbol)}
              title={r.name || undefined}
              className={`flex w-full items-baseline justify-between gap-1 rounded border px-1.5 py-1 text-start ${
                current === r.symbol
                  ? 'border-accent-blue/50 bg-accent-blue/10'
                  : 'border-border-c bg-bg-secondary/40'
              } ${onPick ? 'hover:border-accent-blue' : 'cursor-default'}`}
            >
              <span className="truncate text-2xs font-bold text-text-primary">{r.symbol}</span>
              <span className={`num-text text-2xs font-bold ${TONE_CLASS[tone].text}`}>
                {fmtPct(r.pct ?? null)}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
