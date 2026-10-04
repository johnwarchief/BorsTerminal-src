// shared/lib/useDialogA11y.ts -- رفتار مشترکِ تمام پنجره‌ها
// Escape (capture، حتی اگر focus از پنل بیرون رفته باشد) + تلهٔ Tab +
// focus اولیه + بازگردانی focus به عنصرِ پیش از باز شدن + قفل اسکرول شمارنده‌دار.
// قفلِ اسکرول روی بدنه است؛ زنجیرۀ اسکرولِ داخلِ پنجره با overscroll-contain
// در خودِ پنل‌ها بسته می‌شود (پسِ این هوک).
import { useEffect, useRef } from 'react';

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

let lockCount = 0;
let bodyOverflowBefore = '';

function lockBodyScroll() {
  if (lockCount === 0) {
    bodyOverflowBefore = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  lockCount += 1;
}

function unlockBodyScroll() {
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) document.body.style.overflow = bodyOverflowBefore;
}

function usable(el: HTMLElement): boolean {
  return !el.hidden && !el.hasAttribute('disabled') && el.getAttribute('tabindex') !== '-1';
}

export function useDialogA11y<T extends HTMLElement>({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const panelRef = useRef<T | null>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    let cleanupRaf: (() => void) | null = null;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const placeFocus = () => {
      if (panel.contains(document.activeElement)) return false;
      const first = panel.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? panel).focus({ preventScroll: true });
      return panel.contains(document.activeElement);
    };
    if (!placeFocus()) {
      // در Chromium گاهی focusِ هم‌زمان با commitِ همان رندر رد می‌شود
      // (inert/visibility تازه‌از‌بین‌رفته)؛ قابِ بعد امتحان دوباره.
      const raf = requestAnimationFrame(() => {
        placeFocus();
      });
      cleanupRaf = () => cancelAnimationFrame(raf);
    }
    lockBodyScroll();

    const focusables = () =>
      Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(usable);

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        panel.focus({ preventScroll: true });
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (!panel.contains(active)) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus({ preventScroll: true });
        return;
      }
      if (e.shiftKey && (active === first || active === panel)) {
        e.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus({ preventScroll: true });
      }
    };

    // پنجرۀ capture چون اولین مقصدِ هر رویدادی window است، Escape/Tab از هر
    // جایی (حتی خودِ body) به تله می‌رسد؛ شنوندهٔ document رویدادی را که مستقیم
    // روی window هدف‌گیری می‌شود (fireEvent در تست) نمی‌بیند.
    window.addEventListener('keydown', onKey, true);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      cleanupRaf?.();
      unlockBodyScroll();
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };
  }, [open]);

  return panelRef;
}
