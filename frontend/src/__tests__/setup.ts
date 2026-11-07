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

// jsdom IntersectionObserver هم ندارد و ناوبریِ چسبانِ «وضعیت بازار» با آن
// بخشِ قابل‌مشاهده را علامت می‌زند. استابِ ثبت‌کننده لازم است چون تستِ همان
// هایلایت باید callback را خودش با ورودیِ دلخواه صدا بزند (نه اینکه رفتارِ
// واقعیِ مرورگر در jsdom جا بزند).
type IoEntry = { isIntersecting: boolean; target: Element; intersectionRatio: number };
class IntersectionObserverStub {
  static instances: IntersectionObserverStub[] = [];
  entries: IoEntry[] = [];
  constructor(readonly cb: (entries: IoEntry[]) => void) {
    IntersectionObserverStub.instances.push(this);
  }
  observe(el: Element): void {
    this.entries.push({ isIntersecting: false, target: el, intersectionRatio: 0 });
  }
  unobserve(): void {
    /* no-op */
  }
  disconnect(): void {
    this.entries = [];
  }
  /** فقط درِ تست: همان چیزی که مرورگر با اسکرول واقعی می‌سازد */
  fire(entries: IoEntry[]): void {
    this.cb(entries);
  }
}
if (typeof globalThis.IntersectionObserver === 'undefined') {
  (globalThis as Record<string, unknown>).IntersectionObserver = IntersectionObserverStub;
}
