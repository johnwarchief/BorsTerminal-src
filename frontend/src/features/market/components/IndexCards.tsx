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
import { FlashNum } from '@shared/components/FlashNum';
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
  // «ساعتِ داده» برایِ این بلوک وجود ندارد چون `market_index` فقط *روزِ* معاملۀ
  // همان ردیف را نگه می‌دارد (`asof_d_even`)؛ بی‌این، قابِ مشترک «بی‌داده» می‌گفت
  // در حالی که عددِ امروز رویِ صفحه است. روز ساخته نمی‌شود: نبودش ⇒ همان بی‌داده.
  const dayStamp = cards.find((c) => c.available)?.asof_d_even ?? null;
  return (
    <StatusSection
      testId="ms-index-cards"
      title="کارت‌های شاخص"
      hint="شاخصِ کل، هم‌وزن و قیمتِ وزنیِ ارزشی — از همان ردیفِ رسمیِ بورس"
      asof={dayStamp == null ? null : { d_even: dayStamp }}
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
          {/* یک ردیف، سه خانه؛ هر خانه «مقدار + تغییرِ مطلق + درصد + جهت + تازگی»
              را درِ همان سطر می‌گوید. پیش از این هر خانه پنج سطرِ عمودی داشت و
              بلوک 207 پیکسل ارتفاع می‌گرفت (سنجه: `_audit/market-tab-layout`).
              «مبنایِ عدد» از دیده به `title` رفت تا قدِ کارت کوتاه بماند، نه اینکه
              حذف شود — منبعِ هر رقم همچنان قابلِ بررسی است. */}
          <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-3">
            {cards.map((c) => {
              const tone = toneOf(c.tone);
              const tc = TONE_CLASS[tone];
              return (
                <div
                  key={c.key}
                  data-testid={`index-card-${c.key}`}
                  data-tone={tone}
                  className={`flex min-w-0 flex-wrap items-baseline gap-x-2.5 gap-y-1 rounded-lg border bg-bg-card px-2.5 py-1.5 ${tc.border}`}
                >
                  <span className="text-2xs font-black text-text-primary" title={c.formula ?? undefined}>
                    {c.label}
                    {c.unit ? <span className="num-text ms-1 text-3xs font-normal text-text-muted">{c.unit}</span> : null}
                  </span>
                  {c.available ? (
                    <>
                      {/* فلاشِ تغییرِ عدد از نوارِ نبض به این‌جا منتقل شد: کارت‌های
                          شاخص حالا تنها نمایشِ این دو عدد درِ تب‌اند، پس رفتارِ
                          «همین حالا عوض شد» باید باِ عدد بیاید، نه اینکه باِ حذفِ
                          ستونِ تکراری ازِ صفحه برود. */}
                      <FlashNum
                        value={c.value}
                        render={(v) => fmtInt(v)}
                        className={`num text-sm font-black leading-5 ${tc.text}`}
                        data-testid={`index-card-value-${c.key}`}
                        title={c.formula ? `مبنایِ عدد: ${c.formula}` : undefined}
                      />
                      <span className="num-text flex items-baseline gap-1.5 text-3xs">
                        <span
                          className={tc.text}
                          data-testid={`index-card-arrow-${c.key}`}
                          aria-hidden
                        >
                          {c.pct == null ? '' : c.pct > 0 ? '▲' : c.pct < 0 ? '▼' : '—'}
                        </span>
                        <span className="text-text-secondary" data-testid={`index-card-change-${c.key}`}>
                          تغییر {c.change == null ? '—' : fmtInt(c.change)}
                        </span>
                        <span className={`font-bold ${tc.text}`} data-testid={`index-card-pct-${c.key}`}>
                          {c.pct == null ? '—' : fmtPct(c.pct)}
                        </span>
                      </span>
                      <span className="ms-auto flex items-baseline gap-1.5">
                        <Sparkline
                          testId={`index-spark-${c.key}`}
                          values={c.spark ?? []}
                          width={84}
                          height={20}
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
                      </span>
                    </>
                  ) : (
                    <span
                      data-testid={`index-card-missing-${c.key}`}
                      className="rounded border border-dashed border-border-c px-2 py-0.5 text-3xs text-text-muted"
                    >
                      بدون داده — عددی ساخته نمی‌شود
                    </span>
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
