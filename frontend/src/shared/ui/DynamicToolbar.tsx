// shared/ui/DynamicToolbar.tsx -- نوارِ ابزارِ دوصفحه‌ای با عرضِ متحرک
//
// برداشت از @uselayouts/dynamic-toolbar. ایدهٔ اصلی‌اش این است: یک قرص که
// به‌جایِ نشان‌دادنِ همهٔ کنترل‌ها، دو «صفحه» دارد و هنگامِ جابه‌جایی
// *عرضِ خودش* را هم با اسپرینگ به اندازهٔ صفحهٔ تازه می‌رساند. نتیجه این
// است که نوار همیشه دقیقاً به‌اندازهٔ محتوایش است، نه به‌اندازهٔ شلوغ‌ترین
// حالتش.
//
// چرا اینجا لازم بود: نوارِ فیلترهایِ تابلوخوانی رویِ ۱۳۶۶ پیکسل به چهار
// ردیف می‌شکست و ~۹۵ پیکسل از ارتفاع را می‌خورد — ارتفاعی که در صفحه‌ای
// با جدولِ ۵۴۲۷ ردیفی گران است.
//
// تفاوت با نسخهٔ اصلی: آنجا عرض از `useMeasure` می‌آید که یک وابستگیِ
// دیگر است. اینجا با ResizeObserverِ خودِ مرورگر اندازه می‌گیریم — همان
// کار، بی‌پکیجِ اضافه. در نبودِ ResizeObserver (WebViewِ قدیمی) نوار به
// عرضِ خودکار می‌افتد و فقط انیمیشن را از دست می‌دهد، نه کارکرد را.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { motion } from 'motion/react';
import { cn } from './cn';

const SPRING = { type: 'spring', stiffness: 320, damping: 34, mass: 0.8 } as const;

/** عرضِ زنده‌ی یک المان. صفر یعنی «هنوز نسنجیده‌ایم». */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof ResizeObserver === 'undefined') {
      setW(el.getBoundingClientRect().width);
      return;
    }
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function DynamicToolbar({
  primary,
  secondary,
  primaryLabel = 'فیلترها',
  secondaryLabel = 'تنظیمات',
  className,
  testId = 'dynamic-toolbar',
}: {
  primary: ReactNode;
  secondary: ReactNode;
  primaryLabel?: string;
  secondaryLabel?: string;
  className?: string;
  testId?: string;
}) {
  const [onSecondary, setOnSecondary] = useState(false);
  const [aRef, aW] = useWidth<HTMLDivElement>();
  const [bRef, bW] = useWidth<HTMLDivElement>();
  const measured = aW > 0 && bW > 0;
  // تا پیش از نخستین اندازه‌گیری هیچ انیمیشنی نباید اجرا شود، وگرنه نوار
  // در بارگذاری از صفر باز می‌شود و «می‌پرد».
  const [ready, setReady] = useState(false);
  useEffect(() => { if (measured) setReady(true); }, [measured]);

  const toggle = useCallback(() => setOnSecondary((v) => !v), []);
  const width = measured ? (onSecondary ? bW : aW) : undefined;

  return (
    <div className={cn('flex items-center gap-2', className)} data-testid={testId}>
      <motion.div
        className="relative overflow-hidden rounded-xl border border-border-c bg-bg-card/60"
        animate={width != null ? { width } : undefined}
        transition={ready ? SPRING : { duration: 0 }}
        data-page={onSecondary ? 'secondary' : 'primary'}
      >
        <motion.div
          className="flex w-max"
          // جابه‌جایی با transform است نه با عوض‌کردنِ محتوا: هر دو صفحه
          // در DOM می‌مانند، پس فوکوس و حالتِ کنترل‌ها از بین نمی‌رود.
          animate={{ x: onSecondary ? aW : 0 }}
          transition={ready ? SPRING : { duration: 0 }}
          style={{ direction: 'rtl' }}
        >
          <div ref={aRef} className="flex shrink-0 items-center gap-2 px-2 py-1.5"
               aria-hidden={onSecondary || undefined} data-testid={`${testId}-primary`}>
            {primary}
          </div>
          <div ref={bRef} className="flex shrink-0 items-center gap-2 px-2 py-1.5"
               aria-hidden={!onSecondary || undefined} data-testid={`${testId}-secondary`}>
            {secondary}
          </div>
        </motion.div>
      </motion.div>

      <button
        type="button"
        onClick={toggle}
        aria-pressed={onSecondary}
        data-testid={`${testId}-toggle`}
        title={onSecondary ? `بازگشت به ${primaryLabel}` : `نمایشِ ${secondaryLabel}`}
        className="shrink-0 rounded-xl border border-border-c bg-bg-card/60 px-2.5 py-1.5 text-2xs font-bold text-text-secondary transition-colors hover:border-border-accent hover:text-accent-blue"
      >
        {onSecondary ? primaryLabel : secondaryLabel}
      </button>
    </div>
  );
}
