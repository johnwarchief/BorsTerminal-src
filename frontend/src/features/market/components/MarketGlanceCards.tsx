// features/market/components/MarketGlanceCards.tsx -- «نگاهی به بازار» (صفحۀ ۶)
//
// مرجع ردیفِ کارت‌هایِ نماد (خودرو، فولاد، فملی، شپنا، …) با پیکانِ «سهم ◀» برای
// جابه‌جاییِ پنجره دارد؛ انتخابِ کارت نمودارِ زیرِ آن را عوض می‌کند و کلیک،
// جزئیاتِ نماد را باز می‌کند. درِ BorsTerminal همین داده درِ `MainWatchTable`
// جدول است — ولی «جدول دارد» جای «نمایِ کارتیِ انتخاب‌شدنی» را نمی‌گیرد، پس
// اینجا همان ردیف‌ها به شکلِ کارت می‌نشینند و جدولِ موجود هم حذف نمی‌شود.
//
// داده از `/api/mstat/mainwatch` است (نه فهرستِ دستی): کارت‌ها بی‌درخواستِ تازه
// نمی‌سازند و بی‌ردیف، «بی‌داده» می‌گویند.
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { useMstatMainwatch, type MainWatchRow } from '../api/useMarketStatusFeed';
import { StatusError, StatusLoading, StatusNoData, StatusSection } from './StatusShell';
import { TONE_CLASS, toneOf } from '../lib/tones';

const PAGE = 8;

/** کارتِ کوچکِ کندلِ همین نشست — بدنةِ واقعی از پایانی/اولین/بیشترین/کمترین */
function MiniBars({ row }: { row: MainWatchRow }) {
  const lo = Math.min(row.p_min ?? Infinity, row.p_first ?? Infinity, row.p_closing ?? Infinity);
  const hi = Math.max(row.p_max ?? -Infinity, row.p_first ?? -Infinity, row.p_closing ?? -Infinity);
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) {
    return <span className="text-3xs text-text-muted">بدنه‌ای برایِ کشیدن نیست</span>;
  }
  const y = (v: number | null | undefined) => (1 - ((v ?? lo) - lo) / (hi - lo)) * 22;
  const up = (row.p_closing ?? 0) >= (row.p_first ?? 0);
  return (
    <svg width="26" height="24" viewBox="0 0 26 24" aria-hidden className="shrink-0">
      <line x1="13" y1={y(row.p_max)} x2="13" y2={y(row.p_min)} stroke="var(--text-muted)" strokeWidth="1" />
      <rect
        x="9"
        y={Math.min(y(row.p_first), y(row.p_closing))}
        width="8"
        height={Math.max(1, Math.abs(y(row.p_closing) - y(row.p_first)))}
        fill={up ? 'var(--accent-green)' : 'var(--accent-red)'}
        opacity="0.85"
      />
    </svg>
  );
}

export function MarketGlanceCards() {
  const { data, isLoading, isError, refetch } = useMstatMainwatch('eq_all');
  const rows = data?.rows ?? [];
  const [start, setStart] = useState(0);

  const window = useMemo(() => rows.slice(start, start + PAGE), [rows, start]);
  const maxStart = Math.max(0, rows.length - PAGE);

  return (
    <StatusSection
      testId="ms-glance"
      title="نگاهی به بازار"
      hint="کارتِ همان نمادهایی که موتورِ نبض انتخاب کرده — انتخاب، نمودارِ پایین را عوض می‌کند"
      asof={data?.asof}
      badge={data ? `مبنای انتخاب: ${data.sort_col} (${data.rows?.length ?? 0} ردیف از ${data.total ?? 0})` : undefined}
      toolbar={
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            data-testid="ms-glance-prev"
            disabled={start <= 0}
            onClick={() => setStart((s) => Math.max(0, s - PAGE))}
            className="rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs font-bold text-text-secondary disabled:opacity-40"
          >
            ◀ سهم
          </button>
          <span className="num-text text-3xs text-text-muted" data-testid="ms-glance-page">
            {toFaDigits(Math.min(start + 1, rows.length))}–{toFaDigits(Math.min(start + PAGE, rows.length))}
            {' / '}
            {toFaDigits(rows.length)}
          </span>
          <button
            type="button"
            data-testid="ms-glance-next"
            disabled={start >= maxStart}
            onClick={() => setStart((s) => Math.min(maxStart, s + PAGE))}
            className="rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs font-bold text-text-secondary disabled:opacity-40"
          >
            بعد ▶
          </button>
        </div>
      }
    >
      {isError && !data ? (
        <StatusError testId="ms-glance" onRetry={() => void refetch()} />
      ) : isLoading && !data ? (
        <StatusLoading testId="ms-glance" />
      ) : !window.length ? (
        <StatusNoData testId="ms-glance" />
      ) : (
        <div
          className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-8"
          data-testid="ms-glance-grid"
        >
          {window.map((r) => {
            const tone = toneOf(r.pct_close);
            return (
              <div
                key={r.ins_code ?? r.symbol}
                data-testid={`glance-card-${r.symbol}`}
                data-tone={tone}
                className={`flex min-w-0 flex-col gap-1 rounded-lg border bg-bg-card px-2 py-1.5 ${TONE_CLASS[tone].border}`}
              >
                <div className="flex items-baseline justify-between gap-1">
                  <Link
                    to={`/technical/${encodeURIComponent(r.symbol)}`}
                    data-testid={`glance-link-${r.symbol}`}
                    className="truncate text-2xs font-black text-text-primary hover:text-accent-blue"
                  >
                    {r.symbol}
                  </Link>
                  <MiniBars row={r} />
                </div>
                <span className="num text-2xs text-text-secondary">{fmtInt(r.p_closing ?? null)}</span>
                <span className={`num-text text-2xs font-bold ${TONE_CLASS[tone].text}`} data-testid={`glance-pct-${r.symbol}`}>
                  {fmtPct(r.pct_close ?? null)}
                </span>
                <span className="truncate text-3xs text-text-muted" title={r.name ?? undefined}>
                  {r.name}
                </span>
                <span className="num-text text-3xs text-text-muted">
                  ارزش {fmtInt(r.val_b_toman ?? null)} · حجم {fmtInt(r.vol_b_shares ?? null)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </StatusSection>
  );
}
