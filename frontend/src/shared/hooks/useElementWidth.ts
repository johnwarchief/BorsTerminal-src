// shared/hooks/useElementWidth.ts -- عرضِ واقعیِ یک ظرف به پیکسل
// نمودارهای SVG داخل کارد چندتایی: اگر viewBox ثابت باشد و عرض با کلاس `w-full`
// بکِشَد، ارتفاع هم به همان نسبت درشت می‌شود (نمودار ۶۴۰×۲۰۰ روی ظرف ۱۲۰۰ پیکسلی
// ≈ ۳۷۵px ارتفاع) و فونت‌ها بی‌نسبت می‌مانند. با این قلاب، واحدِ viewBox = پیکسلِ
// CSS می‌شود؛ ارتفاع ثابت می‌ماند و نوشته‌ها در هر عرضی خوانا.
import { useEffect, useRef, useState } from 'react';

export function useElementWidth<T extends HTMLElement>(fallback = 560) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    let raf = 0;
    const read = () => {
      const w = Math.round(el.clientWidth);
      if (w > 0) setWidth((prev) => (Math.abs(prev - w) < 2 ? prev : w));
    };
    read();
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(read);
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);
  return [ref, width] as const;
}
