// features/portfolio/components/WatchSummaryPanel.tsx -- خلاصۀ نماد + جایگاهِ پنلِ ربات
//
// چپ‌چینِ اطلاعات: همه از ردیفِ همان فیدِ مشترکِ تابلو (useMarketFeedShared) —
// هیچ درخواستِ تازهای برایِ چیزی که فید می‌فرستد زده نمی‌شود. «بی‌ردیفِ تابلو»
// صریح گفته می‌شود؛ دادهٔ نمادِ دیگری هرگز زیرِ این سرستون نمی‌نشیند (select
// بر اساسِ کلیدِ نرمالِ همان نماد).
//
// پنلِ ربات: این نسخه فقط «قراردادِ UI» است — دکمه‌هایِ خرید/فروش حاضرند ولی
// کاملاً غیرفعال، چون آداپتورِ کارگزاری واقعی (`api/execution.py`) هنوز
// راه‌اندازی نشده. هیچ سفارشِ واقعی ازِ این صفحه بیرون نمی‌رود و هیچ stateای
// جزِ نمایشِ محلی عوض نمی‌شود. کدِ اتصالِ بعدی همین slot را پر می‌کند؛
// بازنویسیِ UI لازم نیست.
import { Badge } from '@shared/components/Badge';
import { fmtInt, fmtPct, toFaDigits, billionRialText, toBillionRial } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border-c/40 py-1 last:border-0">
      <span className="shrink-0 text-2xs text-text-muted">{label}</span>
      <span className="min-w-0 text-2xs font-bold text-text-primary">{children}</span>
    </div>
  );
}

export function WatchSummaryPanel({ symbol, row }: { symbol: string; row: MarketRow | null }) {
  const st = row?.st_title || row?.st_code || null;
  const stopped = row?.stop_state != null && row.stop_state !== '';

  return (
    <div className="glass-panel flex h-full min-w-0 flex-col gap-1.5 rounded-2xl p-2.5" data-testid="watch-summary" data-symbol={symbol}>
      <div className="flex flex-wrap items-baseline gap-1.5">
        <h4 className="text-xs font-black text-text-primary">خلاصۀِ نماد</h4>
        <span className="text-2xs font-bold text-accent-blue">{symbol || '—'}</span>
        {row == null && symbol ? (
          <span className="ms-auto"><Badge tone="gray">بی‌ردیفِ تابلو</Badge></span>
        ) : row?.is_live === false ? (
          <span className="ms-auto"><Badge tone="yellow">آخرینِ نشست</Badge></span>
        ) : row ? (
          <span className="ms-auto"><Badge tone="green">زنده</Badge></span>
        ) : null}
      </div>

      <p className="line-clamp-2 text-2xs leading-5 text-text-secondary" title={row?.name ?? ''}>
        {row?.name || '—'}{row?.sector_name ? ` · ${row.sector_name}` : ''}
      </p>

      <div className="flex flex-col">
        <InfoRow label="آخرین"><span className="num">{row?.p_last != null ? fmtInt(row.p_last) : '—'}</span></InfoRow>
        <InfoRow label="تغییر">
          <span className={`num ${
            (row?.percent_change ?? 0) > 0 ? 'text-accent-green' : (row?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
          }`}>{row?.percent_change != null ? fmtPct(row.percent_change) : '—'}</span>
        </InfoRow>
        <InfoRow label="پایانیِ امروز"><span className="num">{row?.p_closing != null ? fmtInt(row.p_closing) : '—'}</span></InfoRow>
        <InfoRow label="ابتدا / بیشترین / کمترین">
          <span className="num">
            {row?.p_first != null ? fmtInt(row.p_first) : '—'} / {row?.p_max != null ? fmtInt(row.p_max) : '—'} / {row?.p_min != null ? fmtInt(row.p_min) : '—'}
          </span>
        </InfoRow>
        <InfoRow label="حجم / ارزش"><span className="num">{row?.q_tot_tran != null ? fmtInt(row.q_tot_tran) : '—'} · {billionRialText(toBillionRial(row?.q_tot_cap))} میلیارد ریال</span></InfoRow>
        <InfoRow label="نسبتِ حجم"><span className="num">{row?.vol_ratio != null ? toFaDigits(row.vol_ratio.toFixed(2)) : '—'}</span></InfoRow>
        <InfoRow label="وضعیتِ معاملاتی">
          {stopped ? (
            <span className="text-accent-red" title={row?.stop_reasons ?? undefined}>متوقف</span>
          ) : st ? (
            st
          ) : (
            <span className="text-text-muted">موردی ثبت نشده</span>
          )}
        </InfoRow>
      </div>

      {/* ── جایگاهِ پنلِ تریدر/اجرا (الزاماً خالی و بی‌کارکرد) ── */}
      <div
        className="mt-auto rounded-xl border border-dashed border-border-c bg-bg-card/40 p-2"
        data-testid="watch-order-panel"
      >
        <div className="mb-1.5 flex items-center justify-between gap-1">
          <h5 className="text-2xs font-black text-text-secondary">پنلِ معامله</h5>
          <Badge tone="gray">اتصالِ ربات فعال نیست</Badge>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            disabled
            aria-disabled="true"
            data-testid="watch-order-buy"
            title="ارسالِ سفارشِ واقعی فعال نیست — آداپتورِ کارگزاری در دستِ ساخت است"
            className="cursor-not-allowed rounded-lg bg-accent-green/10 px-2 py-1.5 text-2xs font-black text-accent-green/50"
          >
            خرید
          </button>
          <button
            type="button"
            disabled
            aria-disabled="true"
            data-testid="watch-order-sell"
            title="ارسالِ سفارشِ واقعی فعال نیست — آداپتورِ کارگزاری در دستِ ساخت است"
            className="cursor-not-allowed rounded-lg bg-accent-red/10 px-2 py-1.5 text-2xs font-black text-accent-red/50"
          >
            فروش
          </button>
        </div>
        <p className="mt-1 text-3xs leading-4 text-text-muted">
          این جایگاهِ پنلِ تریدر است؛ تا راه‌اندازیِ اتصالِ کارگزاری هیچ سفارشی ازِ اینجا ارسال نمی‌شود.
        </p>
      </div>
    </div>
  );
}
