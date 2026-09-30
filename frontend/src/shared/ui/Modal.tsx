// shared/ui/Modal.tsx -- پوستهٔ مشترکِ مودال رویِ Radix Dialog
//
// چرا لازم شد: بازرسیِ ۱٫۰٫۶۶ نشان داد از هشت مودالِ برنامه، شش‌تا هیچ
// کلیدِ Escape نداشتند و هفت‌تا هیچ تلهٔ فوکوس. یعنی مودال باز می‌شد و
// کاربر با Tab از داخلش به دکمه‌هایِ صفحهٔ پشتی می‌رفت — جایی که نمی‌دید
// کجاست و کلیک‌کردنِ کورکورانه می‌توانست فیلترها را عوض کند.
//
// نوشتنِ دستیِ این‌ها آسان به‌نظر می‌رسد و نیست: تلهٔ فوکوس باید عناصرِ
// فوکوس‌پذیرِ زنده را بشناسد (نه مخفی‌ها، نه disabled‌ها)، فوکوس را هنگامِ
// بستن به همان دکمه‌ای برگرداند که بازش کرده، اسکرولِ پس‌زمینه را قفل کند
// بی‌اینکه عرضِ اسکرول‌بار چیدمان را بپراند، و `inert` را رویِ بقیهٔ صفحه
// بگذارد تا صفحه‌خوان هم پشتِ مودال را نخواند. Radix همهٔ این‌ها را دارد.
//
// هزینه: Dialog رویِ DropdownMenuِ موجود فقط ~۱ کیلوبایت gzip اضافه می‌کند،
// چون پورتال و dismissable-layer و focus-scope بینشان مشترک است.
import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { cn } from './cn';

/** بی‌جهش: این یک ترمینالِ مالی است، نه صفحهٔ تبلیغاتی. */
const SPRING = { type: 'spring', stiffness: 320, damping: 30, mass: 0.8 } as const;

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  testId = 'modal',
}: {
  open: boolean;
  onClose: () => void;
  /** نامِ دسترسی‌پذیر — همیشه لازم است، حتی اگر دیده نشود */
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    // forceMount + AnimatePresence: بی‌این، Radix محتوا را فوراً برمی‌دارد و
    // انیمیشنِ خروج هرگز دیده نمی‌شود.
    <AnimatePresence>
      {open ? (
        <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="fixed inset-0 z-[99999] bg-black/65 backdrop-blur-sm"
              />
            </Dialog.Overlay>

            <Dialog.Content asChild forceMount>
              <motion.div
                initial={{ opacity: 0, scale: 0.97, y: 8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97, y: 8 }}
                transition={SPRING}
                data-testid={testId}
                dir="rtl"
                className={cn(
                  'fixed left-1/2 top-1/2 z-[100000] flex max-h-[92vh] w-[calc(100vw-1.5rem)] max-w-2xl',
                  '-translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden',
                  'rounded-2xl border border-border-c/90 bg-bg-primary shadow-2xl',
                  'focus:outline-none',
                  className,
                )}
              >
                <div className="flex items-center justify-between gap-3 border-b border-border-c/60 px-4 py-2.5">
                  <div className="min-w-0">
                    <Dialog.Title className="truncate text-sm font-black text-text-primary">
                      {title}
                    </Dialog.Title>
                    {description ? (
                      <Dialog.Description className="truncate text-2xs text-text-muted">
                        {description}
                      </Dialog.Description>
                    ) : null}
                  </div>
                  <Dialog.Close
                    data-testid={`${testId}-close`}
                    aria-label="بستن"
                    className="shrink-0 rounded-lg p-1 text-text-muted transition-colors hover:bg-bg-card hover:text-accent-red focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                  >
                    <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  </Dialog.Close>
                </div>

                <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>

                {footer ? (
                  <div className="border-t border-border-c/60 px-4 py-2.5">{footer}</div>
                ) : null}
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      ) : null}
    </AnimatePresence>
  );
}
