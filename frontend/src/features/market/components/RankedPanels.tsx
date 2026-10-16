// features/market/components/RankedPanels.tsx -- پنل‌های رتبه‌بندی‌شده (صفحۀ ۸ و ۹)
//
// مرجع چهار پنلِ صفحۀ ۸ و دو پنلِ صفحۀ ۹ را با یک شکل می‌دهد: عنوان، کلیدِ
// دامنه، پنج رکورد، نام + نماد، مقدارِ معیار با یکا، قیمت/درصد، و میله‌ای که
// طولش از خودِ همان مقدار می‌آید. یک کامپوننتِ عمومی به‌جای شش کامپوننتِ
// نیمه‌مخالف — ولی «عمومی» به معنیِ یکِ جدولِ مخلوط نیست: هر پنل قراردادِ
// خودش را از سرور می‌خواند (`unit`, `formula`, `value_field`).
//
// دو نکته که اشتباه‌کردنش رایج است:
// · طولِ میله از `bar_pct` خودِ ردیف است (سرور نسبت را بر بیشینهٔ همان پنل
//   زده)، پس مقیاسِ پنلِ «ارزش» با پنلِ «حجم» قاطی نمی‌شود و طولِ میله می‌تواند
//   در تست با مقدارِ ردیف برابری شود.
// · «اثر بر شاخص» درصدِ رشدِ قیمت نیست. عنوان، یکا و فرمول از پاسخ می‌آیند و
//   برچسبِ «تقریبی» با پسماندِ اعلام‌شده (`reconciliation`) زیرِ پنل می‌نشیند.
import { Link } from 'react-router';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { TONE_CLASS, toneOf } from '../lib/tones';
import { SourceNotice, StatusError, StatusLoading, StatusNoData, ValueBar } from './StatusShell';
import type { PanelReason, RankedPanel } from '../api/useMarketPanels';

export function RankedPanelCard({
  panel,
  testId,
  footer,
}: {
  panel: RankedPanel;
  testId: string;
  footer?: React.ReactNode;
}) {
  const rows = panel.rows ?? [];
  return (
    <div
      data-testid={testId}
      className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border-c bg-bg-card px-2 py-1.5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <h4 className="text-2xs font-black text-text-primary" title={panel.formula ?? undefined}>
          {panel.title}
        </h4>
        <span className="num-text text-3xs text-text-muted">{panel.unit}</span>
      </div>

      {rows.length ? (
        <ol className="flex min-w-0 flex-col gap-1">
          {rows.map((r) => {
            const tone = toneOf(r.tone);
            // مقدارِ ستونِ معیار را سرور نام‌گذاری می‌کند (`value_field`)؛ بی‌نامِ
            // تهی هیچ ردیفی «صفر» خوانده نمی‌شود، خط تیره می‌ماند.
            const value = panel.value_field
              ? (r as Record<string, unknown>)[panel.value_field]
              : undefined;
            return (
              <li
                key={`${panel.key}-${r.ins_code ?? r.symbol}-${r.rank}`}
                data-testid={`${testId}-row-${r.symbol}`}
                className="flex min-w-0 flex-col gap-0.5"
              >
                <div className="flex flex-wrap items-baseline gap-x-1.5 text-2xs">
                  <span className="num-text w-4 shrink-0 text-text-muted">
                    {toFaDigits(r.rank ?? 0)}
                  </span>
                  <Link
                    to={`/technical/${encodeURIComponent(r.symbol)}`}
                    data-testid={`${testId}-link-${r.symbol}`}
                    className="font-black text-text-primary hover:text-accent-blue"
                  >
                    {r.symbol}
                  </Link>
                  <span className="num-text ms-auto font-bold" title={panel.unit ?? undefined}>
                    {typeof value === 'number' ? toFaDigits(value.toFixed(1)) : '—'}
                  </span>
                  <span className={`num-text text-3xs font-bold ${TONE_CLASS[tone].text}`}>
                    {fmtPct(r.pct ?? null)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <ValueBar testId={`${testId}-bar-${r.symbol}`} pct={r.bar_pct} tone={r.tone} />
                  <span className="num-text shrink-0 text-3xs text-text-muted">
                    {fmtInt(r.p_closing ?? null)}
                  </span>
                </div>
                <span className="truncate text-3xs text-text-muted" title={r.name ?? undefined}>
                  {r.name ?? '—'}
                  {r.industry ? ` · ${r.industry}` : ''}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p
          data-testid={`${testId}-empty`}
          className="rounded border border-dashed border-border-c px-2 py-1.5 text-3xs text-text-muted"
        >
          {panel.note ?? 'ردیفی نرسیده — در این دامنه مقدارِ سنجیده‌شدنی نیست.'}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-2 text-3xs text-text-muted">
        <span data-testid={`${testId}-candidates`}>
          از {toFaDigits(panel.candidates ?? 0)} نامزد · «{panel.value_field}»
        </span>
        {panel.formula ? (
          <span className="min-w-0 basis-full whitespace-normal break-words leading-4 sm:max-w-[70%] sm:basis-auto" title={panel.formula} data-testid={`${testId}-formula`}>
            {panel.formula}
          </span>
        ) : null}
      </div>
      {footer}
    </div>
  );
}

/** صفحۀ ۸: چهار پنل + پسماندِ اعلام‌شدۀ اثرِ شاخص */
export function TopListsGrid({
  panels,
  isLoading,
  isError,
  onRetry,
  reconciliation,
  blockers,
  testId = 'ms-toplists',
}: {
  panels?: RankedPanel[] | null;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  reconciliation?: { sum_of_impacts?: number | null; official_index_change?: number | null; rel_diff_pct?: number | null; meaning?: string | null } | null;
  blockers?: PanelReason[] | null;
  testId?: string;
}) {
  if (isError) return <StatusError testId={testId} onRetry={onRetry} />;
  if (isLoading && !panels?.length) return <StatusLoading testId={testId} />;
  if (!panels?.length) return <StatusNoData testId={testId} />;
  return (
    <>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 2xl:grid-cols-4">
        {panels.map((p) => (
          <RankedPanelCard key={p.key} panel={p} testId={`${testId}-${p.key}`} />
        ))}
      </div>
      {reconciliation ? (
        <p
          className="num-text rounded-lg border border-dashed border-border-c px-2 py-1 text-3xs text-text-muted"
          data-testid={`${testId}-reconciliation`}
          title={reconciliation.meaning ?? undefined}
        >
          جمعِ اثرها {toFaDigits(reconciliation.sum_of_impacts?.toFixed(0) ?? '—')} در برابرِ{' '}
          تغییرِ رسمیِ شاخص {toFaDigits(reconciliation.official_index_change?.toFixed(0) ?? '—')} ⇒{' '}
          پسماند {toFaDigits(reconciliation.rel_diff_pct?.toFixed(1) ?? '—')}٪.{' '}
          {reconciliation.meaning}
        </p>
      ) : null}
      <SourceNotice testId={testId} items={blockers} kind="blocker" />
    </>
  );
}
