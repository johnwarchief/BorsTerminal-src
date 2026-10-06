import * as React from 'react';
import { cn } from '@shared/lib/cn';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

export interface LiveNumberProps {
  /** مقدار اصلی و کانونی */
  value: number | null | undefined;
  /** مقدار قبلی (اختیاری؛ در صورت نبود خود مؤلفه آن را به خاطر می‌سپارد) */
  previousValue?: number | null;
  /** مدت زمان انیمیشن به میلی‌ثانیه (پیش‌فرض: ۵۵۰ms برای نمایش نرم، پیوسته و طبیعی) */
  duration?: number;
  /** تابع قالب‌بندی عدد (پیش‌فرض: جداکننده هزارگان و ارقام فارسی) */
  format?: (value: number) => string;
  /** واحد پولی یا فیزیکی که خارج از باکس متحرک قرار می‌گیرد و تکان نمی‌خورد */
  unit?: React.ReactNode;
  /** آیا هنگام تغییر مقدار فلاش بزند یا نه (پیش‌فرض: true) */
  flash?: boolean;
  /** حداقل تعداد ارقام رزروشده برای جلوگیری مطلق از Layout Shift */
  reserveDigits?: number;
  className?: string;
  style?: React.CSSProperties;
  'aria-label'?: string;
}

const defaultFormatter = (v: number): string => fmtInt(v);

/**
 * LiveNumber — نمایشگر عدد زنده برای بازار مالی
 * با الهام از VibafarsiUI و بهینه‌شده برای داده‌های برخط تابلو/مارکت.
 *
 * ویژگی‌ها:
 * - تغییر تدریجی (Smooth Transition) از مقدار قبلی به مقدار جدید (نه از صفر)
 * - در صورت تغییر سریع مقادیر، انیمیشن بدون ریست‌شدن از همان مقدار لحظه‌ای رندرشده به سمت هدف تازه ادامه می‌یابد
 * - تفکیک کامل انیمیشن مقدار از فلاش رنگی (فلاش مثبت/منفی بدون تداخل با RAF)
 * - مهار کامل Layout Shift با استفاده از لایه نامرئی رزروکننده عرض
 * - در مقادیر یکسان (SAME) هیچ RAF یا فلاشی تولید نمی‌شود
 * - برای null مستقیماً «-» و برای null→100 مستقیماً ۱۰۰ بدون شمارش از صفر درج می‌شود
 * - دسترس‌پذیری کامل برای صفحه‌خوان‌ها با اعلام مقدار کانونی نهایی
 * - سازگار با prefers-reduced-motion و پاکسازی بی‌نقص تایمرها در Unmount
 */
export function LiveNumber({
  value,
  previousValue,
  duration = 550,
  format = defaultFormatter,
  unit,
  flash = true,
  reserveDigits,
  className,
  style,
  'aria-label': ariaLabel,
}: LiveNumberProps) {
  const containerRef = React.useRef<HTMLSpanElement>(null);

  // مقدار نمایشی در لحظه
  const [displayValue, setDisplayValue] = React.useState<number | null>(value ?? null);

  const prevCanonicalRef = React.useRef<number | null | undefined>(previousValue ?? value);
  const currentInterpolatedRef = React.useRef<number | null>(value ?? null);
  const startValRef = React.useRef<number | null>(value ?? null);
  const isFirstMount = React.useRef(true);
  const rafRef = React.useRef<number>(0);
  const flashTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    // ۱. بار اول: مقدار اولیه بلافاصله بدون انیمیشن یا فلاش تنظیم می‌شود
    if (isFirstMount.current) {
      isFirstMount.current = false;
      prevCanonicalRef.current = value;
      currentInterpolatedRef.current = value ?? null;
      startValRef.current = value ?? null;
      setDisplayValue(value ?? null);
      return;
    }

    const prev = previousValue !== undefined ? previousValue : prevCanonicalRef.current;

    // ۲. اگر مقدار جدید خالی باشد (100 -> null)
    if (value == null) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      currentInterpolatedRef.current = null;
      prevCanonicalRef.current = null;
      startValRef.current = null;
      setDisplayValue(null);
      return;
    }

    // ۳. اگر از مقدار خالی به یک عدد می‌رسیم (null -> 100)، شمارش از صفر نداریم؛ بلافاصله عدد را می‌نشانیم
    if (prev == null || currentInterpolatedRef.current == null) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      currentInterpolatedRef.current = value;
      prevCanonicalRef.current = value;
      startValRef.current = value;
      setDisplayValue(value);
      return;
    }

    // ۴. اگر مقدار کانونی تغییر نکرده باشد (SAME)، هیچ انیمیشن یا فلاشی اجرا نمی‌شود
    if (value === prev) {
      return;
    }

    const isUp = value > prev;
    const isDown = value < prev;

    // ۵. اعمال فلاش جهتی کوتاه به گره DOM (کاملاً مجزا از انیمیشن مقدار)
    if (flash && (isUp || isDown) && containerRef.current) {
      const el = containerRef.current;
      el.classList.remove('live-flash-up', 'live-flash-down');
      // ایجاد Reflow کوچک برای ری‌استارت تمیز انیمیشن CSS بدون اثر روی React State
      void el.offsetWidth;
      el.classList.add(isUp ? 'live-flash-up' : 'live-flash-down');

      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      flashTimerRef.current = setTimeout(() => {
        el.classList.remove('live-flash-up', 'live-flash-down');
      }, 700);
    }

    // ۶. بررسی prefers-reduced-motion (با ایمنی کامل در تست‌های jsdom)
    const reducedMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion || duration <= 0) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      currentInterpolatedRef.current = value;
      prevCanonicalRef.current = value;
      startValRef.current = value;
      setDisplayValue(value);
      return;
    }

    // ۷. انیمیشن با requestAnimationFrame
    // مبدا حرکت: دقیقاً همان مقداری که در همین میکروثانیه رندر شده است (پوشش کامل آپدیت‌های سریع)
    const startVal = currentInterpolatedRef.current;
    startValRef.current = startVal;
    const targetVal = value;
    const startTime = performance.now();

    // همواره حداکثر یک RAF فعال داریم؛ هر انیمیشن قبلی را لغو می‌کنیم
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      // منحنی نرم و چشم‌نواز quadratic ease-out: حرکتی یکنواخت و خوانا بدون پرش یا توقف ناگهانی
      const eased = 1 - (1 - progress) * (1 - progress);
      const current = startVal + (targetVal - startVal) * eased;

      currentInterpolatedRef.current = current;

      if (progress >= 1) {
        currentInterpolatedRef.current = targetVal;
        setDisplayValue(targetVal);
      } else {
        setDisplayValue(current);
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    prevCanonicalRef.current = value;

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    };
  }, [value, previousValue, duration, flash]);

  // اگر مقدار تهی باشد، رندر بدون لایه رزرو جهت خروجی تمیز
  if (value == null) {
    return (
      <span
        ref={containerRef}
        role="text"
        aria-label={ariaLabel || 'بدون داده'}
        className={cn(
          'num inline-flex items-baseline tabular-nums rounded px-0.5 transition-colors',
          className,
        )}
        style={style}
      >
        <span data-testid="live-number-display">-</span>
      </span>
    );
  }

  // متون فرمت‌شده
  const formattedTarget = format(value);
  const formattedDisplay = displayValue != null ? format(displayValue) : formattedTarget;
  const formattedStart = startValRef.current != null ? format(startValRef.current) : '';

  // متن باکس رزروکننده عرض جهت مهار ۱۰۰٪ Layout Shift حتی در گذارهای بزرگ ارقام (مانند 1,000,000 به 999,999)
  const maxLen = Math.max(formattedTarget.length, formattedDisplay.length, formattedStart.length);
  let spacer =
    formattedTarget.length === maxLen
      ? formattedTarget
      : formattedStart.length === maxLen
        ? formattedStart
        : formattedDisplay;

  if (reserveDigits && reserveDigits > spacer.length) {
    spacer = spacer.padStart(reserveDigits, toFaDigits('۰'));
  }

  const accessibleText =
    ariaLabel || `${formattedTarget} ${typeof unit === 'string' ? unit : ''}`.trim();

  return (
    <span
      ref={containerRef}
      role="text"
      aria-label={accessibleText}
      className={cn(
        'num inline-flex items-baseline tabular-nums rounded px-0.5 transition-colors',
        className,
      )}
      style={style}
    >
      <span aria-hidden="true" className="relative inline-block">
        {/* لایه نامرئی رزروکننده فضا (تکنیک VibafarsiUI) برای مهار کامل پرش چیدمان */}
        <span
          data-testid="live-number-spacer"
          className="invisible select-none pointer-events-none"
        >
          {spacer}
        </span>
        {/* لایه نمایشی عدد متحرک در همان موقعیت */}
        <span data-testid="live-number-display" className="absolute inset-0 text-start">
          {formattedDisplay}
        </span>
      </span>

      {unit && (
        <span
          aria-hidden="true"
          className="ms-1 inline-block text-[0.8em] font-normal text-text-muted select-none"
        >
          {unit}
        </span>
      )}
    </span>
  );
}
