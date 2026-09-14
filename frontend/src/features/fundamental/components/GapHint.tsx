// features/fundamental/components/GapHint.tsx -- Tooltip علت شکاف داده
// هر برچسب «شکاف داده»/«بدون داده» که با GapHint رندر شود، با نگه‌داشتن
// ماوس علتِ ساده‌شدهٔ همان شکاف را نشان می‌دهد. علت از همان stateای
// ساخته می‌شود که شکاف را تولید کرده (تعداد فصل/سال موجود، نوع شرکت،
// فیلدهای null) — اگر قابل‌استنتاج نبود، پیام عمومی صادقانه می‌آید،
// نه مخفی‌کاری. پیاده‌سازی title ساده (سازگار با الگوی پروژه) + نشانگر ⓘ.
import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fmt';

/** ساخت علت شکاف از روی شمار دوره‌های موجود — بهترین تلاش از خود داده */
export function epsGapReason(opts: {
  available: number;
  required: number;
  quarters?: number;
  interimAvailable?: boolean;
}): string {
  const { available, required, quarters, interimAvailable } = opts;
  const fa = (n: number) => toFaDigits(n);
  if (available === 0) {
    return interimAvailable
      ? `هیچ سال مالی کاملِ EPS ثبت نشده (۰ از ${fa(required)}) — فقط میاندوره موجود است؛ سابقهٔ سالانه باید در کدال منتشر شود.`
      : `هیچ صورت مالی ۱۲ماههٔ EPS در کدال ثبت نشده (۰ از ${fa(required)} سال).`;
  }
  if (available < required) {
    const q = quarters != null && quarters > 0 ? ` دوره‌های فصلی ثبت‌شده: ${fa(quarters)}` : '';
    return `فقط ${fa(available)} سال از ${fa(required)} سالِ لازم موجود است — سابقهٔ کامل سه‌ساله برای قضاوت شاخص ۲ کافی نیست.${q}`;
  }
  return 'دادهٔ این بخش از گزارش‌های کدال/بک‌اند تکمیل نشده است.';
}

/** علت عمومی برای شکاف‌های بدون state جزئی‌تر */
export const GENERIC_GAP_REASON = 'دادهٔ این بخش از گزارش‌های کدال/بک‌اند تکمیل نشده است.';

/** علت N/A رشد فیزیکی — شرکت تولیدی نیست */
export const PHYSICAL_NA_REASON =
  'این شرکت خدماتی/مالی/هلدینگ است و گزارش فیزیکی/تناژ منتشر نمی‌کند؛ رشد فیزیکی برای آن معنا ندارد.';

/** علت غیب ارزش بازار/فروش سالانه */
export const VALUATION_GAP_REASON =
  'ارزش بازار لحظه‌ای یا فروش سالانه‌شده در دادهٔ فعلی در دسترس نیست — بدون این دو، نسبت‌های شاخص ۴ محاسبه نمی‌شود.';

export function GapHint({
  reason,
  children,
  className = '',
}: {
  reason: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`group relative inline-flex cursor-help items-center gap-1 ${className}`}
      title={reason}
      data-testid="gap-hint"
      tabIndex={0}
    >
      {children}
      <span aria-hidden className="text-[9px] leading-none text-text-muted transition-colors group-hover:text-accent-blue">
        ⓘ
      </span>
    </span>
  );
}
