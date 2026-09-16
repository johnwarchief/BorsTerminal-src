// shared/lib/useMediaQuery.ts -- هوک واکنشی پرسوجوی مدیا (فاز ۲)
import { useCallback, useSyncExternalStore } from 'react';

function supported(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function';
}

function subscribeTo(query: string, cb: () => void): () => void {
  if (!supported()) return () => {};
  const mql = window.matchMedia(query);
  if (typeof mql.addEventListener === 'function') {
    mql.addEventListener('change', cb);
    return () => mql.removeEventListener('change', cb);
  }
  mql.addListener(cb);
  return () => mql.removeListener(cb);
}

/** در محیطهای بدون matchMedia (مثل jsdom) امن است و false برمیگرداند. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback((cb: () => void) => subscribeTo(query, cb), [query]);
  const getSnapshot = useCallback(() => (supported() ? window.matchMedia(query).matches : false), [query]);
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}