import type { AxisStatus } from '../lib/axisMeta';

/**
 * R-UNSLOP-3: ستِ آیکنِ واقعیِ سطح بنیادی.
 * همه در جعبهٔ ۱۶پیکسلی، stroke 1.5، `currentColor` و بدونِ قلمِ متن — تا
 * کاراکترهایِ تیک، ضربدر، منفی، سؤال و فلش دیگر در RTL وارونه خوانده نشوند یا با قلمِ متن نجنگند.
 * آیکن‌ها aria-hidden‌اند؛ نامِ دسترس‌پذیر همیشه روی خودِ واژهٔ فارسی است.
 */
type IconProps = { className?: string };

function Icon({ d, className, closed }: IconProps & { d: string; closed?: boolean }) {
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox="0 0 16 16"
      className={`fd-icon ${className ?? ''}`}
      fill={closed ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}

export const Check = (props: IconProps) => <Icon {...props} d="M3 8.6 6.2 12 13 4.6" />;
export const Cross = (props: IconProps) => <Icon {...props} d="M4 4 12 12M12 4 4 12" />;
export const Minus = (props: IconProps) => <Icon {...props} d="M3.5 8h9" />;
/** وضعیتِ نامشخص: دایره با کمانِ سؤال‌نمای کوتاه — بی‌ادعای «نمی‌دانیم». */
export const Unknown = (props: IconProps) => (
  <svg
    aria-hidden
    focusable="false"
    viewBox="0 0 16 16"
    className={`fd-icon ${props.className ?? ''}`}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
  >
    <circle cx="8" cy="8" r="5.75" />
    <path d="M6.6 6.4a1.5 1.5 0 0 1 2.9.5c0 1-1.4 1.2-1.4 2.3" />
    <path d="M8.1 11.2h.05" />
  </svg>
);
/** جهتِ بازگشت در RTL: پیکان به سمتِ ابتداِ خط (راست). */
export const ArrowRight = (props: IconProps) => <Icon {...props} d="M4 8h8M8.8 4.4 12.4 8l-3.6 3.6" />;
export const TrendUp = (props: IconProps) => <Icon {...props} d="M3 11.6 7 7.4l2.4 2.2L13 5.4M9.6 5.4H13v3.4" />;
export const TrendDown = (props: IconProps) => <Icon {...props} d="M3 5.4 7 9.6l2.4-2.2L13 11.6M9.6 11.6H13V8.2" />;
export const TrendFlat = (props: IconProps) => <Icon {...props} d="M3 8h9M9.6 5.4 12.4 8l-2.8 2.6" />;

export const SortAsc = (props: IconProps) => <Icon {...props} d="M8 12.4V4M4.8 7.2 8 4l3.2 3.2" />;
export const SortDesc = (props: IconProps) => <Icon {...props} d="M8 3.6V12M4.8 8.8 8 12l3.2-3.2" />;
export const SortNone = (props: IconProps) => <Icon {...props} d="M8 12.6V3.4M5.4 5.6 8 3.2l2.6 2.4M5.4 10.4 8 12.8l2.6-2.4" />;

/** نگاشتِ وضعیت به آیکن؛ تنها منبعِ شکلِ وضعیت در سطح بنیادی. */
export const STATUS_GLYPH: Record<AxisStatus, (props: IconProps) => JSX.Element> = {
  pass: Check,
  fail: Cross,
  na: Minus,
  unknown: Unknown,
};

/**
 * R-UNSLOP-8: مهرِ وضعیتِ فارسی — واژه + یک نقطهٔ رنگیِ ۶پیکسلی.
 * همان نشانه در سلولِ جدول، سرصفحهٔ پنل، کوینتت و روبان. نقطه aria-hidden است
 * و رنگِ آن از `.fd-status--*` (همان currentColorِ واژه) می‌آید، پس هیچ حکمی
 * فقط با رنگ گفته نمی‌شود: واژهٔ فارسی همیشه حاضر است.
 * textContentِ خروجی دقیقاً خودِ واژه است (فاصلهٔ متنی ندارد).
 */
export function StatusMark({ status, word, title, className = '' }: {
  status: AxisStatus;
  word: string;
  title?: string | null;
  className?: string;
}) {
  return (
    <span
      className={`fd-status inline-flex min-w-0 items-center gap-1 fd-status--${status} ${className}`}
      title={title ?? undefined}
    >
      <span className="fd-status-dot" aria-hidden />{word}
    </span>
  );
}

/** آیکنِ وضعیت — فقط جایی که شکلِ گلیف لازم است (راهنمای جدول). */
export function StatusGlyph({ status, className = '' }: { status: AxisStatus; className?: string }) {
  const Glyph = STATUS_GLYPH[status];
  return <Glyph className={className} />;
}

/**
 * R-UNSLOP-3: نشانِ روندِ EPS — شکلِ SVG با نامِ فارسیِ روند روی خودش.
 * جهت با `data-trend` و `aria-label` گفته می‌شود، نه با کاراکترِ فلشِ متن.
 */
export function TrendMark({ trend }: { trend: 'up' | 'down' | 'flat' | null }) {
  if (trend == null) return null;
  const Glyph = trend === 'up' ? TrendUp : trend === 'down' ? TrendDown : TrendFlat;
  const word = trend === 'up' ? 'صعودی' : trend === 'down' ? 'نزولی' : 'بی‌تغییر';
  return (
    <span data-trend={trend} role="img" aria-label={`روند ${word}`} className="inline-flex items-center text-[var(--fd-text-3)]">
      <Glyph />
    </span>
  );
}
