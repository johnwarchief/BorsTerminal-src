// shared/components/CollapsibleSection.tsx -- بخشِ جمع‌شونده با انیمیشنِ روان
//
// چرا لازم شد: رویِ ۱۳۶۶×۷۶۸ داشبوردِ «نبضِ بازار» بیشترِ ارتفاع را می‌گیرد و
// جدولِ تابلو زیرِ خطِ تا می‌افتد. کاربر یا نبض می‌خواهد یا جدول — هر دو
// هم‌زمان جا نمی‌شوند.
//
// انیمیشنِ ارتفاع: `grid-template-rows: 0fr → 1fr`. این تنها راهِ خالصِ CSS
// برایِ انیمیشنِ «تا ارتفاعِ محتوا» است؛ `height: auto` قابلِ ترنزیشن نیست و
// راهِ جایگزین اندازه‌گیریِ DOM با ResizeObserver است که هم reflow می‌آورد هم
// با محتوایِ زندهٔ نبض (که هر چند ثانیه عوض می‌شود) دائم بازمحاسبه می‌شود.
// در `prefers-reduced-motion` ترنزیشن خاموش می‌شود.
//
// وضعیت در localStorage می‌ماند، وگرنه کاربر هر بار که تب عوض می‌کند دوباره
// باید جمعش کند.
import { useCallback, useEffect, useId, useState, type ReactNode } from 'react';

function read(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : v === '1';
  } catch {
    return fallback; // حالتِ خصوصی/سهمیهٔ پر — نباید رندر را بخواباند
  }
}

export function CollapsibleSection({
  title,
  storageKey,
  summary,
  defaultOpen = true,
  children,
  testId = 'collapsible',
}: {
  title: string;
  /** کلیدِ ماندگاری؛ بی‌آن هر بار باز می‌شود */
  storageKey: string;
  /** خلاصه‌ای که در حالتِ جمع هم دیده می‌شود — جمع‌شدن نباید کور کند */
  summary?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  testId?: string;
}) {
  const uid = useId();
  const [open, setOpen] = useState(() => read(storageKey, defaultOpen));

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, open ? '1' : '0');
    } catch {
      /* نوشتن ممکن نشد؛ فقط ماندگاری از دست می‌رود */
    }
  }, [open, storageKey]);

  const toggle = useCallback(() => setOpen((v) => !v), []);

  return (
    <section data-testid={testId} data-open={open || undefined}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={`${uid}-body`}
          data-testid={`${testId}-toggle`}
          title={open ? 'جمع‌کردن — جا برایِ جدول باز می‌شود' : 'بازکردن'}
          className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-xs font-black text-text-secondary transition-colors hover:bg-bg-card/60 hover:text-text-primary"
        >
          {/* فلش فقط می‌چرخد — یک transform، بی‌بازچینش */}
          <svg
            className={`size-3.5 motion-safe:transition-transform motion-safe:duration-200 ${open ? '' : 'rotate-90'}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
          <span>{title}</span>
        </button>
        {/* خلاصه فقط وقتی جمع است — در حالتِ باز، خودِ محتوا گویاست */}
        {!open && summary ? (
          <div className="min-w-0 flex-1 truncate" data-testid={`${testId}-summary`}>
            {summary}
          </div>
        ) : null}
      </div>

      <div
        id={`${uid}-body`}
        // grid با 0fr/1fr: ارتفاع بدونِ دانستنِ عددِ پیکسلی انیمیت می‌شود
        className={`grid motion-safe:transition-[grid-template-rows] motion-safe:duration-300 ${
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        {/* overflow-hidden روی فرزند لازم است وگرنه محتوا از شیارِ صفرِ
            گرید بیرون می‌زند و جمع‌شدن دیده نمی‌شود */}
        <div className="overflow-hidden">
          {/* padding داخل می‌ماند تا در حالتِ جمع هم به صفر برسد */}
          <div className={open ? 'pt-1.5' : ''} aria-hidden={!open}>
            {children}
          </div>
        </div>
      </div>
    </section>
  );
}
