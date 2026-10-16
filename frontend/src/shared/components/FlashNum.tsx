// shared/components/FlashNum.tsx -- فلاشِ تغییرِ عدد، با منطقِ مشترکِ «تشخیصِ تغییرِ
// واقعی» و زمان‌بندیِ بیرونِ مؤلفه (CSS). دو ظاهرِ قابل‌انتخاب:
//   • variant="market"  (پیش‌فرض): فلاشِ جهت‌دارِ پس‌زمینه — سبز/قرمز. رنگ معنا دارد
//     (صعود/هبوط) و درِ تابلو، خرید/فروش، نبض بازار و پرتفوی به‌کار می‌رود.
//   • variant="neutral": فلاشِ آبیِ بی‌جهت رویِ خودِ عدد — فقط می‌گوید «همین حالا عوض
//     شد» و زیرِ یک ثانیه نرم به رنگِ عادیِ همان سلول برمی‌گردد. مخصوصِ «دیده‌بان».
// بهینه‌سازیِ عملکرد (۶۰ FPS): انیمیشنِ مستقیمِ DOM، بدونِ انهدامِ گره و بدونِ رندرِ مضاعف.
import { useEffect, useRef } from 'react';

export type FlashVariant = 'market' | 'neutral';

export function FlashNum({
  value,
  render,
  variant = 'market',
  className = '',
  style,
  ...rest
}: {
  value: number | null | undefined;
  render: (v: number | null | undefined) => string;
  variant?: FlashVariant;
  className?: string;
  style?: React.CSSProperties;
  [key: string]: unknown;
}) {
  const prev = useRef(value);
  const spanRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const before = prev.current;
    const el = spanRef.current;
    // فقط «تغییرِ واقعی» — نه هر رندرِ دوباره؛ و نه گذارِ null (رنگِ جهت ندارد).
    if (before !== value && before != null && value != null && el) {
      if (variant === 'neutral') {
        el.classList.remove('flash-neutral');
        // رنگِ عادیِ همین سلول (پیش از فلاش) خوانده می‌شود تا محو دقیقاً به همان
        // برگردد — چه متنِ معمولی باشد، چه سبز/قرمزِ ستونِ تغییر٪.
        el.style.setProperty('--flash-rest', getComputedStyle(el).color);
        void el.offsetWidth; // ری‌استارتِ تمیزِ انیمیشن درِ تغییراتِ متوالی
        el.classList.add('flash-neutral');
      } else {
        const cls = value > before ? 'flash-up' : 'flash-down';
        el.classList.remove('flash-up', 'flash-down');
        void el.offsetWidth;
        el.classList.add(cls);
      }
    }
    prev.current = value;
  }, [value, variant]);

  // فلاشِ market یک «جعبه» می‌خواهد (پس‌زمینه + گردی + کمی فضا)؛ فلاشِ neutral فقط
  // رنگِ متن است، پس جعبه ندارد و عرضِ ستونِ دیده‌بان را دست‌نخورده می‌گذارد.
  const boxCls = variant === 'market' ? 'rounded px-1' : '';

  return (
    <span
      ref={spanRef}
      className={`num inline-block ${boxCls} ${className}`}
      style={style}
      {...rest}
    >
      {render(value)}
    </span>
  );
}
