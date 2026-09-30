// shared/ui/Select.tsx -- فهرستِ بازشویِ نرم، رویِ Radix DropdownMenu
//
// چرا جایگزینِ <select>ِ بومی شد: پاپ‌آپِ سلکتِ بومی را خودِ ویندوز می‌کشد.
// `color-scheme: dark` رنگش را درست کرد ولی بیشتر از آن نمی‌شود کرد — نه
// انیمیشن می‌گیرد، نه جستجو، نه آیکون، نه عرضِ دلخواه، و در فهرستِ ۴۰تاییِ
// صنایع کاربر باید کورکورانه اسکرول کند.
//
// چرا Radix و نه div دست‌ساز: چیزی که یک dropdownِ درست لازم دارد و نوشتنش
// هفته‌ها طول می‌کشد — تله‌کردنِ فوکوس، بازگرداندنِ فوکوس به دکمه، پورتال تا
// از overflow بیرون بزند، بستن با Escape و کلیکِ بیرون، تایپ‌کردن برایِ پرش،
// جهت‌دهیِ خودکار وقتی نزدیکِ لبهٔ صفحه است، و aria درست. Radix همهٔ این‌ها
// را دارد و ۸٫۸ کیلوبایت gzip برایِ چهار پریمیتیو می‌گیرد.
//
// انیمیشن با data-state خودِ Radix انجام می‌شود، نه با motion: باز و بسته‌شدن
// یک fade + scale کوتاه است و ارزشِ ۴۲ کیلوبایت را ندارد.
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useMemo, useState } from 'react';
import { cn } from './cn';

export type SelectOption = { value: string; label: string; hint?: string };

export function Select({
  value,
  options,
  onChange,
  ariaLabel,
  placeholder = 'انتخاب…',
  className,
  /** از این تعداد به بالا، جعبهٔ جستجو ظاهر می‌شود */
  searchThreshold = 8,
  testId = 'ui-select',
}: {
  value: string;
  options: readonly SelectOption[];
  onChange: (v: string) => void;
  ariaLabel: string;
  placeholder?: string;
  className?: string;
  searchThreshold?: number;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');

  const current = options.find((o) => o.value === value) ?? null;
  const searchable = options.length >= searchThreshold;

  const shown = useMemo(() => {
    const needle = q.trim();
    if (!needle) return options;
    // جستجویِ سادهٔ زیررشته‌ای — فهرستِ صنایع کوتاه است و نیازی به fuzzy نیست.
    // عمداً حساس به «ی/ي» و «ک/ك» نیست چون کاربر با صفحه‌کلیدِ عربی هم تایپ می‌کند.
    const norm = (s: string) => s.replace(/[يﻱ]/g, 'ی').replace(/[كﻙ]/g, 'ک');
    const n = norm(needle);
    return options.filter((o) => norm(o.label).includes(n));
  }, [options, q]);

  return (
    <DropdownMenu.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ(''); // بازِ بعدی نباید فیلترِ قبلی را به ارث ببرد
      }}
    >
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          data-testid={testId}
          className={cn(
            'flex items-center justify-between gap-1.5 rounded-lg border border-border-c bg-bg-card/60 px-2.5 py-1 text-xs font-bold text-text-primary',
            'transition-colors hover:border-border-accent hover:text-accent-blue',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
            'data-[state=open]:border-border-accent data-[state=open]:text-accent-blue',
            className,
          )}
        >
          <span className="truncate">{current?.label ?? placeholder}</span>
          <svg
            className="size-3 shrink-0 opacity-70 motion-safe:transition-transform motion-safe:duration-200 group-data-[state=open]:rotate-180"
            viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          data-testid={`${testId}-content`}
          className={cn(
            'z-[100000] max-h-[min(22rem,60vh)] min-w-[var(--radix-dropdown-menu-trigger-width)] overflow-y-auto',
            'rounded-xl border border-border-c bg-popover p-1 shadow-2xl',
            // انیمیشنِ باز/بسته با حالتِ خودِ Radix — بی‌جاوااسکریپتِ اضافه
            'motion-safe:data-[state=open]:animate-in motion-safe:data-[state=closed]:animate-out',
            'motion-safe:data-[state=open]:fade-in-0 motion-safe:data-[state=closed]:fade-out-0',
            'motion-safe:data-[state=open]:zoom-in-95 motion-safe:data-[state=closed]:zoom-out-95',
            'motion-safe:duration-150',
          )}
        >
          {searchable ? (
            // onKeyDown را نگه می‌داریم وگرنه Radix تایپ را «پرش به آیتم»
            // می‌فهمد و حروف داخلِ جعبه نمی‌نشیند.
            <div className="sticky top-0 z-[1] bg-popover p-1 pb-1.5" onKeyDown={(e) => e.stopPropagation()}>
              <input
                autoFocus
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="جستجو…"
                aria-label="جستجو در فهرست"
                data-testid={`${testId}-search`}
                className="w-full rounded-lg border border-border-c bg-bg-primary px-2 py-1 text-xs text-text-primary outline-none placeholder:text-text-muted focus:border-border-accent"
              />
            </div>
          ) : null}

          {shown.length === 0 ? (
            <p className="px-2 py-3 text-center text-2xs text-text-muted">چیزی پیدا نشد</p>
          ) : (
            shown.map((o) => (
              <DropdownMenu.Item
                key={o.value}
                onSelect={() => onChange(o.value)}
                title={o.hint}
                data-testid={`${testId}-item-${o.value}`}
                className={cn(
                  'flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs outline-none',
                  'data-[highlighted]:bg-bg-card data-[highlighted]:text-text-primary',
                  o.value === value ? 'font-bold text-accent-blue' : 'text-text-secondary',
                )}
              >
                {/* جایِ تیک همیشه رزرو است تا انتخاب‌شدن متن را جابه‌جا نکند */}
                <span className="w-3 shrink-0 text-accent-blue">{o.value === value ? '✓' : ''}</span>
                <span className="truncate">{o.label}</span>
              </DropdownMenu.Item>
            ))
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
