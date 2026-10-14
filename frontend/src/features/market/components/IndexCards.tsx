// features/market/components/IndexCards.tsx -- کارت‌هایِ شاخص + sparkline (صفحۀ ۶ و ۷)
//
// سه کارت از مرجع: «کل بورس»، «کل هم وزن»، «قیمت وزنی ارزشی». هر سه از
// `market_index` می‌آیند — همان GetMarketOverviewِ رسمیِ بورس که درِ
// `test_tsetmc.save_market_index` نوشته می‌شود. پس هیچ شاخصی در رابط
// بازتعریف نشده: کارتِ سوم (قیمتِ وزنی) فرمولش را از پاسخ می‌خواند
// (`q_tot_cap ÷ q_tot_tran`) و همان متن زیرش می‌نشیند.
//
// نکته‌ای که ادعایِ «زنده» را جلو می‌گیرد: sparkline فقط روزهایی را دارد که
// شاخصِ رسمی در این بانک ذخیره شده (امروز ۱۳ روز). `history_points` از خودِ
// پاسخ می‌آید و زیرِ کارت نوشته می‌شود — بازه‌ای که نبود، وعده داده نمی‌شود.
import { Link } from 'react-router';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { Sparkline } from './Sparkline';
import { StatusError, StatusLoading, StatusNoData, SourceNotice, StatusSection } from './StatusShell';
import type { IndexCardsFeed } from '../api/useMarketPanels';
import { TONE_CLASS, toneOf } from '../lib/tones';

/** تنها شاخصی که موتور چارتِ موجود واقعاً می‌شناسد (`KLineChartWrapper.tsx:618`).
 *  کلیدهایِ دیگر لینک نمی‌گیرند: نشانیِ بی‌کندل ساختن کنترلِ مرده است. */
const CHART_ROUTE: Record<string, string> = {
  tedpix: `/technical/${encodeURIComponent('شاخص کل')}`,
};

export function IndexCards({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: IndexCardsFeed;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const cards = data?.cards ?? [];
  return (
    <StatusSection
      testId="ms-index-cards"
      title="کارت‌های شاخص"
      hint="شاخصِ کل، هم‌وزن و قیمتِ وزنیِ ارزشی — از همان ردیفِ رسمیِ بورس"
      asof={null}
      badge={data?.source ? `منبع: ${data.source}` : undefined}
    >
      {isError && !data ? (
        <StatusError testId="ms-index-cards" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <StatusLoading testId="ms-index-cards" />
      ) : !cards.length ? (
        <StatusNoData testId="ms-index-cards" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {cards.map((c) => {
              const tone = toneOf(c.tone);
              const tc = TONE_CLASS[tone];
              return (
                <div
                  key={c.key}
                  data-testid={`index-card-${c.key}`}
                  className={`flex min-w-0 flex-col gap-1 rounded-lg border bg-bg-card px-2 py-1.5 ${tc.border}`}
                >
                  <div className="flex items-baseline justify-between gap-1">
                    <span className="text-2xs font-black text-text-primary">{c.label}</span>
                    <span className="num-text text-3xs text-text-muted">{c.unit}</span>
                  </div>
                  {c.available ? (
                    <>
                      <span className={`num text-sm font-black ${tc.text}`}>
                        {fmtInt(c.value ?? null)}
                      </span>
                      <div className="flex flex-wrap items-center gap-x-2 text-3xs">
                        <span className="num-text text-text-secondary">
                          تغییر: {c.change == null ? '—' : fmtInt(c.change)}
                        </span>
                        <span className={`num-text font-bold ${tc.text}`}>
                          {fmtPct(c.pct ?? null)}
                        </span>
                      </div>
                      <div className="flex items-end justify-between gap-1">
                        <Sparkline
                          testId={`index-spark-${c.key}`}
                          values={c.spark ?? []}
                          tone={tone}
                          label={c.label}
                        />
                        {CHART_ROUTE[c.key] ? (
                          <Link
                            to={CHART_ROUTE[c.key]}
                            data-testid={`index-card-chart-${c.key}`}
                            className="rounded border border-border-c px-1.5 py-0.5 text-3xs font-bold text-text-secondary hover:text-accent-blue"
                            title="نمودارِ کاملِ همین شاخص"
                          >
                            نمودار
                          </Link>
                        ) : (
                          // «هم‌وزن» و «قیمتِ وزنی» کندلِ مستقلِ خودشان را درِ موتور
                          // چارت ندارند؛ لینکِ مرده نمی‌سازیم (مرحلۀ ۴: هر کنترل
                          // باید واقعاً کار کند).
                          <span
                            data-testid={`index-card-nochart-${c.key}`}
                            className="text-3xs text-text-muted"
                            title="این شاخص نمودارِ کندلِ مستقل ندارد؛ فقط سریِ روزانۀ خودش ثبت می‌شود"
                          >
                            بی‌کندل
                          </span>
                        )}
                      </div>
                      {c.formula ? (
                        <p className="num-text text-3xs text-text-muted" title="مبنایِ عدد">
                          {c.formula}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <p
                      data-testid={`index-card-missing-${c.key}`}
                      className="rounded border border-dashed border-border-c px-2 py-1.5 text-3xs text-text-muted"
                    >
                      این شاخص در این نشست نرسیده — عددی ساخته نمی‌شود.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          <p className="num-text text-3xs text-text-muted" data-testid="ms-index-cards-span">
            {toFaDigits(data?.history_points ?? 0)} روزِ شاخصِ رسمی در بانک · ارزشِ بازار:{' '}
            {data?.market_total_b_toman != null
              ? `${toFaDigits(data.market_total_b_toman.toFixed(0))} میلیارد تومان (${data.market_total_source})`
              : 'بی‌داده'}
            {data?.note ? ` · ${data.note}` : ''}
          </p>
          <SourceNotice testId="ms-index-cards" items={data?.blockers} kind="blocker" />
        </>
      )}
    </StatusSection>
  );
}
