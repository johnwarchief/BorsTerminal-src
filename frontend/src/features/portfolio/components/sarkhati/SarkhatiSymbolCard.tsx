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
import { Badge } from '@shared/components/Badge';
import { fmtInt, fmtPct } from '@shared/lib/fmt';
import { matchFa, normalizeFa } from '@shared/lib/normalizeFa';
import type { MarketFeed, MarketRow } from '@shared/types/marketRow';

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
    <div className="glass-panel rounded-2xl p-2.5" data-testid="sarkhati-symbol-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">نمادِ سفارش</h4>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="جست‌وجویِ نماد یا نامِ شرکت در تابلو"
          aria-label="جست‌وجویِ نماد"
          data-testid="sarkhati-symbol-search"
          className="min-w-[180px] flex-1 rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary placeholder:text-text-muted"
        />
      </div>

      {feedErr ? (
        <p className="mt-1 text-3xs text-accent-red" data-testid="sarkhati-feed-error">
          فیدِ تابلو نرسید — تا رسیدنِ ردیفِ معتبر هیچ نمادی انتخاب نمی‌شود.
        </p>
      ) : null}

      {q.trim() && !feedErr ? (
        matches.length === 0 ? (
          <p className="mt-1 text-3xs text-text-muted" data-testid="sarkhati-symbol-none">
            درِ تابلویِ امروز چیزی با این نام نیست.
          </p>
        ) : (
          <ul className="mt-1 flex flex-col gap-0.5" data-testid="sarkhati-symbol-results">
            {matches.map((r) => (
              <li key={r.ins_code ?? r.symbol}>
                <button
                  type="button"
                  onClick={() => { onSelect(r.symbol); setQ(''); }}
                  data-testid={`sarkhati-symbol-pick-${r.symbol}`}
                  className="flex w-full flex-wrap items-baseline gap-2 rounded-lg border border-transparent px-2 py-1 text-start text-2xs hover:border-border-c hover:bg-bg-card"
                >
                  <span className="num font-black text-text-primary">{r.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-text-secondary" title={r.name ?? ''}>
                    {r.name ?? '—'}
                  </span>
                  <span className="num text-text-muted">
                    {r.p_last != null ? fmtInt(r.p_last) : '—'}
                  </span>
                  <span className={`num ${
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

      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1"
        data-testid="sarkhati-symbol-facts">
        <span className="num text-sm font-black text-text-primary" data-testid="sarkhati-chosen-symbol">
          {symbol || '—'}
        </span>
        {symbol && row == null && !feedErr ? (
          <Badge tone="yellow" title="ردیفی در فیدِ همین نشست نیست">در تابلو نیست</Badge>
        ) : row?.is_live === false ? (
          <Badge tone="yellow">آخرین داده</Badge>
        ) : row ? (
          <Badge tone="green">زنده</Badge>
        ) : null}
        <span className="min-w-0 max-w-[260px] truncate text-2xs text-text-secondary"
          title={row?.name ?? ''} data-testid="sarkhati-symbol-name">
          {row?.name || '—'}
        </span>
      </div>

      <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-3xs sm:grid-cols-4">
        <Fact label="آخرین" value={row?.p_last != null ? fmtInt(row.p_last) : '—'} />
        <Fact label="پایانیِ امروز" value={row?.p_closing != null ? fmtInt(row.p_closing) : '—'} />
        <Fact label="حدِ مجازِ پایین (تابلو)"
          value={row?.tmin != null && row.tmin > 0 ? fmtInt(row.tmin) : 'بی‌داده'} />
        <Fact label="وضعیتِ معاملاتی"
          value={row?.stop_state ? 'متوقف' : (row?.st_title || (row ? 'معمولی' : '—'))} />
      </div>
      <p className="mt-1 text-3xs leading-4 text-text-muted" data-testid="sarkhati-band-note">
        داوریِ حدِ مجاز، سقفِ حجم و تازگیِ داده درِ «پیش‌فرودِ» خودِ سرویس انجام
        می‌شود — رابط عددِ تازه‌ای برایِ آن نمی‌سازد.
      </p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex flex-wrap items-baseline gap-1">
      <span className="text-text-muted">{label}:</span>
      <span className="num font-bold text-text-primary">{value}</span>
    </span>
  );
}

/** ارزشِ تخمینی = قیمت × حجم، باِ واحدِ صریح؛ رشتهٔ بی‌عدد ⇒ «—» نه صفر */
export function estValue(price: string, qty: string): string {
  const p = Number(price.replace(/[٬]/g, ''));
  const q = Number(qty.replace(/[٬]/g, ''));
  if (!Number.isFinite(p) || !Number.isFinite(q) || p <= 0 || q <= 0) return '—';
  return `${fmtInt(p * q)} ریال`;
}
