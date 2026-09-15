// shared/lib/useMediaQuery.ts -- هوک واکنشی پرسوجوی مدیا (فاز ۲)
import { useEffect, useState } from 'react';

function supported(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function';
}

/** در محیطهای بدون matchMedia (مثل jsdom) امن است و false برمیگرداند. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() => (supported() ? window.matchMedia(query).matches : false));

  useEffect(() => {
    if (!supported()) return undefined;
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches);
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
    mql.addListener(onChange);
    return () => mql.removeListener(onChange);
  }, [query]);

  return matches;
}