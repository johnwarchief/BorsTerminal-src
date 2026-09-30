// shared/components/VerticalTabs.tsx -- تبِ عمودی با شاخصِ لغزان
//
// چرا دستی و نه `@uselayouts/vertical-tabs`: آن نسخه `motion` +
// `@hugeicons/core-free-icons` (۸۰ مگابایت، ۲۴٬۲۹۳ فایل) + `clsx` +
// `tailwind-merge` می‌خواهد و رویِ زیربنایِ shadcn/Radix نوشته شده که این
// پروژه ندارد. مهم‌تر: `bors_entry._needs_software_rendering()` در همهٔ
// شاخه‌ها جز «GPUِ اختصاصی» True است، یعنی برنامه رویِ بیشترِ ماشین‌ها با
// `--disable-gpu --use-angle=swiftshader` بالا می‌آید. انیمیشنِ کتابخانه‌ایِ
// مبتنی بر لایه و blur دقیقاً همان‌جا می‌لنگد.
//
// پس شاخصِ لغزان اینجا فقط یک `transform: translateY` رویِ یک المانِ کوچک
// است که با متغیرِ CSS جابه‌جا می‌شود — بی‌اندازه‌گیریِ DOM، بی‌ResizeObserver،
// بی‌reflow. همهٔ تب‌ها هم‌ارتفاع‌اند، پس جایِ شاخص = شمارهٔ تب ÷ تعداد.
// در `prefers-reduced-motion` انتقال خاموش می‌شود.
import { useCallback, useId, useRef, type ReactNode } from 'react';

export type VerticalTabItem<K extends string> = {
  key: K;
  /** برچسبِ کوتاه — در ستونِ باریک می‌نشیند، پس بلند ننویس */
  label: string;
  /** آیکونِ متنی/ایموجی؛ جدا از label تا در حالتِ باریک تنها همین بماند */
  icon?: ReactNode;
  /** توضیحِ کامل برایِ title و صفحه‌خوان */
  hint?: string;
};

export function VerticalTabs<K extends string>({
  items,
  active,
  onChange,
  children,
  testId = 'vertical-tabs',
  ariaLabel,
}: {
  items: readonly VerticalTabItem<K>[];
  active: K;
  onChange: (k: K) => void;
  /** محتوایِ تبِ فعال — خودِ فراخوان تصمیم می‌گیرد چه رندر شود */
  children: ReactNode;
  testId?: string;
  ariaLabel: string;
}) {
  const uid = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const idx = Math.max(
    0,
    items.findIndex((t) => t.key === active),
  );

  // پیمایشِ صفحه‌کلیدِ استانداردِ tablist. بی‌این، تبِ عمودی برایِ کسی که
  // ماوس ندارد یک دیوار است.
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const n = items.length;
      if (n === 0) return;
      let next = -1;
      if (e.key === 'ArrowDown') next = (idx + 1) % n;
      else if (e.key === 'ArrowUp') next = (idx - 1 + n) % n;
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = n - 1;
      if (next < 0) return;
      e.preventDefault();
      onChange(items[next].key);
      // فوکوس باید دنبالِ انتخاب برود، وگرنه فلشِ بعدی از جایِ قبلی می‌شمارد
      const btns = listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
      btns?.[next]?.focus();
    },
    [idx, items, onChange],
  );

  return (
    <div className="flex min-h-0 flex-1 gap-0" data-testid={testId}>
      <div
        ref={listRef}
        role="tablist"
        aria-orientation="vertical"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className="relative w-[7.5rem] shrink-0 overflow-y-auto border-e border-border-c/60 bg-bg-secondary/40 py-1 sm:w-40 scrollbar-none"
      >
        {/* شاخصِ لغزان: یک نوار که فقط translate می‌شود. `--n` و `--i` از
            جاوااسکریپت می‌آیند ولی فقط به‌عنوانِ عدد — هیچ پیکسلی اینجا
            حساب نمی‌شود، پس تغییرِ اندازهٔ پنجره کاری لازم ندارد. */}
        <span
          aria-hidden="true"
          data-testid={`${testId}-indicator`}
          className="pointer-events-none absolute end-0 top-0 w-[3px] rounded-s bg-accent-blue motion-safe:transition-transform motion-safe:duration-200"
          style={{
            height: `calc(100% / ${items.length})`,
            transform: `translateY(calc(${idx} * 100%))`,
          }}
        />
        {items.map((t, i) => {
          const on = t.key === active;
          return (
            <button
              key={t.key}
              id={`${uid}-tab-${t.key}`}
              type="button"
              role="tab"
              aria-selected={on}
              aria-controls={`${uid}-panel`}
              // فقط تبِ فعال در ترتیبِ Tab است؛ بقیه با فلش. قاعدهٔ tablist.
              tabIndex={on ? 0 : -1}
              title={t.hint ?? t.label}
              data-active={on || undefined}
              onClick={() => onChange(t.key)}
              className={`flex w-full items-center gap-1.5 px-2.5 py-2 text-start text-xs font-bold transition-colors sm:px-3 ${
                on
                  ? 'bg-bg-primary/80 text-accent-blue'
                  : 'text-text-secondary hover:bg-bg-card/50 hover:text-text-primary'
              }`}
              style={{ height: `calc(100% / ${items.length})`, minHeight: '2.25rem' }}
              data-index={i}
            >
              {t.icon ? <span aria-hidden="true">{t.icon}</span> : null}
              <span className="truncate">{t.label}</span>
            </button>
          );
        })}
      </div>
      <div
        id={`${uid}-panel`}
        role="tabpanel"
        aria-labelledby={`${uid}-tab-${active}`}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5"
      >
        {children}
      </div>
    </div>
  );
}
