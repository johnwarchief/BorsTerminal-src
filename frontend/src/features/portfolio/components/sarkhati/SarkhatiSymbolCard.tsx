// features/portfolio/components/sarkhati/SarkhatiSymbolCard.tsx — انتخابِ نماد از
// دادهٔ معتبرِ بازار، نه ازِ حافظهٔ رابط
//
// ردیف‌ها از همان `useMarketFeedShared` می‌آیند که تابلو می‌خواند (یکِ کوئری، یک
// کلید — `shared/api/marketFeed.ts`). پس «نمادِ معتبر» یعنی ردیفی که *همین حالا*
// درِ تابلو هست؛ بی‌ردیف صریح گفته می‌شود، نه اینکه آخرینِ عددِ نمادِ دیگر زیرِ
// این سرستون بنشیند.
//
// چیزی که این کارت **نمی‌کند**: حدِ مجاز و سقفِ حجم را درِ رابط داوری نمی‌کند.
// آن داوری درِ `POST /api/execution/preflight` است و نتیجه‌اش همان‌جا خوانده
// می‌شود؛ اینجا فقط ستونِ خودِ تابلو (`tmin`) به‌عنوانِ زمینه نمایش داده می‌شود.
import { useMemo, useState } from 'react';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { fmtInt, fmtPct } from '@shared/lib/fmt';
import { matchFa, normalizeFa } from '@shared/lib/normalizeFa';
import type { MarketFeed, MarketRow } from '@shared/types/marketRow';
import { Chip, Field, Line, Note } from './parts';

const MAX_SUGGEST = 12;

function selectRows(f: MarketFeed): MarketRow[] {
  return f.data ?? [];
}

/**
 * ردیفِ نمادِ مؤثر از همان فید (selectِ باریک، بی‌درخواستِ دوم).
 * تطبیق **برابریِ** نرمال‌شده است نه زیررشته: «فولاد» نباید ردیفِ «آتيه06» را
 * (که نامِ شرکتش فولاد دارد) زیرِ این نماد بنشاند. یکِ صاحب برایِ این داوری —
 * صفحه هم همین تابع را import می‌کند، نه نسخۀِ دومِ خودش را.
 */
export function selectRowFor(target: string) {
  const want = normalizeFa(target || '');
  return (f: MarketFeed): MarketRow | null =>
    (f.data ?? []).find((r) => normalizeFa(String(r.symbol ?? '')) === want) ?? null;
}

export function SarkhatiSymbolCard({ symbol, row, onSelect }: {
  symbol: string;
  row: MarketRow | null;
  onSelect: (s: string) => void;
}) {
  const [q, setQ] = useState('');
  const rows = useMarketFeedShared(selectRows, 60_000);
  const matches = useMemo(() => {
    const needle = q.trim();
    if (!needle) return [];
    return (rows.data ?? [])
      .filter((r) => matchFa(r.symbol, needle) || matchFa(r.name, needle))
      .slice(0, MAX_SUGGEST);
  }, [rows.data, q]);
  const feedErr = rows.isError;

  return (
    <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2"
      data-testid="sarkhati-symbol-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="num text-base font-black leading-5 text-text-primary"
          data-testid="sarkhati-chosen-symbol">{symbol || '—'}</span>
        {symbol && row == null && !feedErr ? (
          <Chip tone="warn" title="ردیفی در فیدِ همین نشست نیست">در تابلو نیست</Chip>
        ) : row?.is_live === false ? (
          <Chip tone="warn">آخرین داده</Chip>
        ) : row ? (
          <Chip tone="ok">زنده</Chip>
        ) : null}
        <span className="min-w-0 max-w-[30ch] truncate text-2xs text-text-secondary"
          title={row?.name ?? ''} data-testid="sarkhati-symbol-name">
          {row?.name || '—'}
        </span>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="جست‌وجویِ نماد یا نامِ شرکت در تابلو"
          aria-label="جست‌وجویِ نماد"
          data-testid="sarkhati-symbol-search"
          className="ms-auto w-[min(22rem,100%)] rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary placeholder:text-text-muted"
        />
      </div>

      {feedErr ? (
        <Line kind="error" testId="sarkhati-feed-error">
          فیدِ تابلو نرسید — تا رسیدنِ ردیفِ معتبر هیچ نمادی انتخاب نمی‌شود.
        </Line>
      ) : null}

      {q.trim() && !feedErr ? (
        matches.length === 0 ? (
          <p className="mt-1 text-2xs text-text-muted" data-testid="sarkhati-symbol-none">
            درِ تابلویِ امروز چیزی با این نام نیست.
          </p>
        ) : (
          <ul className="sk-scroll mt-1 max-h-[9.5rem] overflow-y-auto rounded-lg border border-border-c/50"
            data-testid="sarkhati-symbol-results">
            {matches.map((r) => (
              <li key={r.ins_code ?? r.symbol}>
                <button
                  type="button"
                  onClick={() => { onSelect(r.symbol); setQ(''); }}
                  data-testid={`sarkhati-symbol-pick-${r.symbol}`}
                  className="flex w-full flex-wrap items-baseline gap-2 border-b border-border-c/30 px-2 py-1 text-start text-2xs last:border-0
                    hover:bg-bg-card"
                >
                  <span className="num font-black text-text-primary">{r.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-text-secondary" title={r.name ?? ''}>
                    {r.name ?? '—'}
                  </span>
                  <span className="num text-text-secondary">
                    {r.p_last != null ? fmtInt(r.p_last) : '—'}
                  </span>
                  <span className={`num font-bold ${
                    (r.percent_change ?? 0) > 0 ? 'text-accent-green'
                      : (r.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-muted'}`}>
                    {r.percent_change != null ? fmtPct(r.percent_change) : 'بی‌درصد'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}

      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5"
        data-testid="sarkhati-symbol-facts">
        <Field label="آخرین" value={row?.p_last != null ? fmtInt(row.p_last) : '—'} />
        <Field label="پایانیِ امروز" value={row?.p_closing != null ? fmtInt(row.p_closing) : '—'} />
        <Field label="حدِ مجازِ پایین (تابلو)"
          value={row?.tmin != null && row.tmin > 0 ? fmtInt(row.tmin) : 'بی‌داده'} />
        <Field label="وضعیتِ معاملاتی"
          value={row?.stop_state ? 'متوقف' : (row?.st_title || (row ? 'معمولی' : '—'))} />
      </div>

      <div className="mt-1">
        <Note label="چرا رابط حدِ مجاز را داوری نمی‌کند" testId="sarkhati-band-note">
          داوریِ حدِ مجاز، سقفِ حجم و تازگیِ داده درِ «پیش‌فرودِ» خودِ سرویس انجام
          می‌شود — رابط عددِ تازه‌ای برایِ آن نمی‌سازد. این ستون‌ها فقط زمینه‌اند.
        </Note>
      </div>
    </section>
  );
}

/** ارزشِ تخمینی = قیمت × حجم، باِ واحدِ صریح؛ رشتهٔ بی‌عدد ⇒ «—» نه صفر */
export function estValue(price: string, qty: string): string {
  const p = Number(price.replace(/[٬]/g, ''));
  const q = Number(qty.replace(/[٬]/g, ''));
  if (!Number.isFinite(p) || !Number.isFinite(q) || p <= 0 || q <= 0) return '—';
  return `${fmtInt(p * q)} ریال`;
}
