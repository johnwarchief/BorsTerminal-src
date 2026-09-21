// shared/components/FlashNum.tsx -- فلاش لطیف سلول بدون انهدام نودهای DOM و بدون رندر مضاعف
// بهینه‌سازی عملکرد (۶۰ FPS): استفاده از انیمیشن مستقیم DOM به جای تغییر key و setState
import { useEffect, useRef } from 'react';

export function FlashNum({
  value,
  render,
  className = '',
  style,
  ...rest
}: {
  value: number | null | undefined;
  render: (v: number | null | undefined) => string;
  className?: string;
  style?: React.CSSProperties;
  [key: string]: unknown;
}) {
  const prev = useRef(value);
  const spanRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const before = prev.current;
    if (before !== value && before != null && value != null && spanRef.current) {
      const cls = value > before ? 'flash-up' : 'flash-down';
      const el = spanRef.current;
      el.classList.remove('flash-up', 'flash-down');
      // بازنشانی لطیف انیمیشن بدون تخریب گره DOM
      void el.offsetWidth;
      el.classList.add(cls);
    }
    prev.current = value;
  }, [value]);

  return (
    <span
      ref={spanRef}
      className={`num inline-block rounded px-1 ${className}`}
      style={style}
      {...rest}
    >
      {render(value)}
    </span>
  );
}
