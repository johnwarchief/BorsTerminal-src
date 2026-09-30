// shared/ui/Tooltip.tsx -- راهنمایِ شناور رویِ Radix Tooltip
//
// چرا جایگزینِ `title=` بومی: صفتِ title را خودِ سیستم‌عامل می‌کشد، پس
// (۱) حدودِ یک ثانیه تأخیر دارد که قابلِ تنظیم نیست، (۲) بعد از چند ثانیه
// خودش محو می‌شود حتی اگر کاربر هنوز می‌خواند، (۳) رنگ و فونتش مالِ ویندوز
// است نه تمِ برنامه، (۴) با صفحه‌کلید اصلاً ظاهر نمی‌شود، و (۵) در متنِ
// چندخطیِ فارسی راست‌چین نمی‌شود.
//
// در این برنامه ۲۰۰+ جایِ `title=` هست که اغلبشان توضیحِ فرمولِ یک ستون‌اند
// — یعنی محتوایی که کاربر واقعاً می‌خواهد بخواند، نه یک برچسبِ کوتاه.
//
// `title` عمداً از المانِ فرزند برداشته نمی‌شود مگر صریح بگویید: اگر هر دو
// بمانند، کاربر دو راهنما می‌بیند.
import * as RT from '@radix-ui/react-tooltip';
import type { ReactNode } from 'react';
import { cn } from './cn';

/** یک Provider برایِ کلِ برنامه — تأخیرِ مشترک و رفتارِ «پرشِ سریع» بینِ
 *  دو راهنمایِ همسایه (اولی با تأخیر، بعدی‌ها فوری). */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <RT.Provider delayDuration={350} skipDelayDuration={200}>
      {children}
    </RT.Provider>
  );
}

export function Tooltip({
  content,
  children,
  side = 'top',
  className,
  testId = 'tooltip',
}: {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  testId?: string;
}) {
  if (!content) return <>{children}</>;
  return (
    // Provider اینجا هم هست، نه فقط در ریشهٔ برنامه.
    //
    // چرا: `RT.Root` بی‌Provider استثنا پرتاب می‌کند. یعنی هر مصرف‌کننده‌ای
    // که این کامپوننت را جایی بگذارد که Provider بالایش نیست — یا هر تستی
    // که فقط همان کامپوننت را رندر کند — با خطا می‌خوابد. یک کامپوننتِ
    // مشترک نباید چنین تله‌ای داشته باشد. (همین واقعاً ۱۹ تستِ قیف را
    // شکست، نه به‌خاطرِ باگِ آن‌ها.)
    //
    // هزینه‌اش: `skipDelayDuration` دیگر بینِ راهنماهایِ همسایه گروه
    // نمی‌شود، پس حرکت از یک سرستون به سرستونِ بعدی هر بار تأخیرِ کامل
    // می‌گیرد. در برابرِ «هرگز نترکد» معاملهٔ خوبی است.
    <RT.Provider delayDuration={350} skipDelayDuration={200}>
    <RT.Root>
      <RT.Trigger asChild>{children}</RT.Trigger>
      <RT.Portal>
        <RT.Content
          side={side}
          sideOffset={6}
          collisionPadding={8}
          dir="rtl"
          data-testid={testId}
          className={cn(
            'z-[100001] max-w-[32ch] rounded-lg border border-border-c bg-popover px-2 py-1.5',
            'text-2xs leading-5 text-text-primary shadow-xl',
            'motion-safe:data-[state=delayed-open]:animate-in motion-safe:data-[state=closed]:animate-out',
            'motion-safe:data-[state=delayed-open]:fade-in-0 motion-safe:data-[state=closed]:fade-out-0',
            'motion-safe:data-[state=delayed-open]:zoom-in-95 motion-safe:duration-120',
            className,
          )}
        >
          {content}
          <RT.Arrow className="fill-[var(--bg-secondary)]" width={10} height={5} />
        </RT.Content>
      </RT.Portal>
    </RT.Root>
    </RT.Provider>
  );
}
