import { toFaDigits } from '@shared/lib/fa';
import { statusFa, type AxisStatus } from '../../lib/axisMeta';

/** R-P1-8: «شاهد» تُنِ خنثی است و هرگز «قبول/رد» اعلام نمی‌کند. */
export type HistoryBarTone = AxisStatus | 'evidence';

export function HistoryBars({ values, labels, status, label }: {
  values: Array<number | null>;
  labels: string[];
  status: HistoryBarTone;
  label?: string;
}) {
  // R-P1-8: نبودِ هر دو مقدار → وضعیتِ خالیِ صادق، نه میله‌های حداقلی.
  if (!values.some((value) => value != null)) {
    return (
      <p className="flex h-full items-center justify-center text-[9px] text-[var(--fd-text-3)]">
        {label ? `${label} — داده‌ای ثبت نشده` : 'داده‌ای برای نمایش ثبت نشده'}
      </p>
    );
  }
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  // عددِ دقیقِ هر میله؛ همان رشته در title و در نامِ قابل‌دسترس می‌نشیند تا دو مسیر وا نباشند.
  // (رشته دست‌نخورده می‌ماند: contract می‌گوید title عوض نشود، پس اعشار همان قلمِ قبلی است.)
  const figure = (v: number | null) => (v == null ? '—' : toFaDigits(String(v)));
  // R-P1-13 (Minor 3): `role="img"` گراف را presentational می‌کند، پس title هر میله هرگز
  // اعلام نمی‌شود. عددِ دقیق به نامِ ظرف منتقل می‌شود؛ پیشوندِ نامِ قبلی («تاریخچهٔ
  // گزارش‌ها …» / «فروش دورهٔ جاری و قبل») حفظ است تا پرس‌وجوهای موجود نِشکنند.
  const name = status === 'evidence'
    ? label ?? 'نمودار شاهد'
    : label ? `${label} — ${statusFa(status)}` : `تاریخچهٔ گزارش‌ها — ${statusFa(status)}`;
  const ariaLabel = `${name} — ${values.map((v, i) => `${labels[i] ? `${labels[i]}: ` : ''}${figure(v)}`).join('، ')}`;
  return (
    <div className="flex h-full gap-1" role="img" aria-label={ariaLabel}>
      {values.map((v, i) => {
        // R93: ناحیهٔ میله ارتفاع قطعی می‌گیرد تا ارتفاعِ درصدیِ میله حل شود
        // و میله‌ها در ستونِ auto-height ناپدید نشوند.
        // R-P1-12: کفِ مقدارِ غیرصفر از ۲٪ به ۸٪ رسید تا مقدارِ واقعیِ کوچک به شکلِ
        // خطِ باریک دیده نشود؛ تُنِ خنثیِ «شاهد» و حالتِ خالی دست‌نخورده‌اند.
        // R-P1-13 (Important 1): کفِ ۸٪ فقط برایِ مقدارِ واقعیِ کوچک است — «نبودِ مقدار» و
        // «صفرِ واقعی» میلهٔ صفرِ صادق می‌گیرند تا دادهٔ گم‌شده مانندِ یک فروشِ واقعیِ
        // کوچک نقاشی نشود (حالتِ خالیِ صادقِ R-P1-8).
        const pct = v == null || v === 0 ? 0 : Math.max(8, (Math.abs(v) / max) * 100);
        return (
          <div key={i} className="flex h-full min-w-0 flex-1 flex-col items-center gap-1" title={`${labels[i]} — ${figure(v)}`}>
            <span className="flex min-h-0 w-full flex-1 items-end">
              <span className={`fd-history-bar is-${status} w-full rounded-t-sm`} style={{ height: `${pct}%` }} />
            </span>
            <span className="w-full truncate text-center text-[9px] text-[var(--fd-text-3)]">{labels[i]}</span>
          </div>
        );
      })}
    </div>
  );
}
