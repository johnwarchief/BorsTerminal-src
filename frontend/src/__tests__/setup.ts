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
