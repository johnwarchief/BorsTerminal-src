import '@testing-library/jest-dom/vitest';

// jsdom ResizeObserver ندارد؛ رپر چارت برای ریسپانسیو بودن به آن نیاز دارد.
class ResizeObserverStub {
  observe(): void {
    /* no-op */
  }
  unobserve(): void {
    /* no-op */
  }
  disconnect(): void {
    /* no-op */
  }
}
if (typeof globalThis.ResizeObserver === 'undefined') {
  (globalThis as Record<string, unknown>).ResizeObserver = ResizeObserverStub;
}

// ── پالی‌فیلِ jsdom برایِ پریمیتیوهایِ Radix (۱٫۰٫۶۶) ──
// Radix رویِ Pointer Events سوار است و منویش را با pointerdown باز می‌کند.
// jsdom این سه متد و scrollIntoView را ندارد، پس بی‌این‌ها هر تستِ
// dropdown/dialog/tooltip با TypeError می‌افتد — نه به‌خاطرِ باگِ کامپوننت.
if (typeof Element !== 'undefined') {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
}
// Radix Content با ResizeObserver جایِ پاپ‌آپ را می‌سنجد.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
