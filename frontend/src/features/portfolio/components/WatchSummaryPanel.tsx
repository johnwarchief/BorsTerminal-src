// features/portfolio/components/WatchSummaryPanel.tsx -- خلاصۀ نماد + جایگاهِ پنلِ سرخطی
//
// چپ‌چینِ اطلاعات: همه از ردیفِ همان فیدِ مشترکِ تابلو (useMarketFeedShared) —
// هیچ درخواستِ تازهای برایِ چیزی که فید می‌فرستد زده نمی‌شود. «بی‌ردیفِ تابلو»
// صریح گفته می‌شود؛ دادهٔ نمادِ دیگری هرگز زیرِ این سرستون نمی‌نشیند (select
// بر اساسِ کلیدِ نرمالِ همان نماد).
//
// پنلِ سرخطی (`ExecutionPanel`): هیچ حالتی درِ این فایل اختراع نمی‌شود — سمت،
// قیمت، مقدار و تأیید به همان `api/execution.py` می‌روند و هر کنترل فقط با
// capabilityِ اعلام‌شدهٔ سرویس روشن می‌شود. بی‌نشست، «نشست بسته است» نوشته
// می‌شود؛ «Connected»ِ ظاهری درِ این رابط ساخته نمی‌شود.
import { Badge } from '@shared/components/Badge';
import { fmtInt, fmtPct, toFaDigits, billionRialText, toBillionRial } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';
import { ClientSharePct } from '@shared/components/ClientSharePct';
import { ExecutionPanel } from './ExecutionPanel';

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
          <span className="ms-auto"><Badge tone="gray">در تابلو نیست</Badge></span>
        ) : row?.is_live === false ? (
          <span className="ms-auto"><Badge tone="yellow">آخرین داده</Badge></span>
        ) : row ? (
          <span className="ms-auto"><Badge tone="green">زنده</Badge></span>
        ) : null}
      </div>

      {/* سرآمدِ قیمتی مثلِ چیدمانِ مرجع: عددِ درشتِ آخرین و تغییرِ همان کنارش */}
      <div className="flex flex-wrap items-baseline gap-x-2 rounded-lg bg-bg-card/60 px-2 py-1.5">
        <span className="num text-lg font-black leading-6 text-text-primary" data-testid="watch-summary-last">
          {row?.p_last != null ? fmtInt(row.p_last) : '—'}
        </span>
        <span className={`num text-2xs font-bold ${
          (row?.percent_change ?? 0) > 0 ? 'text-accent-green' : (row?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
        }`} data-testid="watch-summary-pct">
          {row?.percent_change != null ? fmtPct(row.percent_change) : 'بی‌درصد'}
        </span>
        <span className="num ms-auto text-3xs text-text-muted" data-testid="watch-summary-row-time">
          ساعتِ ردیف: {row?.row_h != null ? toFaDigits(String(Math.floor(row.row_h)).padStart(6, '0').slice(0, 4).replace(/(\d\d)(\d\d)/, '$1:$2')) : '—'}
        </span>
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
        {/* بند ۲ مأموریت + درخواستِ مالک (کنارِ نسبتِ خریدار/فروشنده درِ دیده‌بان):
            سهمِ حقیقی/حقوقی از **ارزشِ** خرید و فروش. همان ستون‌هایِ تابلو که
            `client_split.py` ساخته — دیده‌بان عددِ دوم نمی‌سازد. */}
        <ClientSharePct row={row} dense testId="watch-client-share" className="my-1" />
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

      {/* پنلِ معامله: همه از پاسخِ /api/execution/status — بی‌ادعایِ اتصال */}
      <ExecutionPanel symbol={symbol} row={row} />
    </div>
  );
}
