import { ComponentType, Suspense, useEffect, useState } from 'react';
import { Skeleton } from './Skeleton';

const RETRY_DELAYS_MS = [300, 1200, 3000];

// Chromium keeps a failed dynamic import in its module map, so a retry can
// reject without a network request. A fresh document is the only reliable
// retry; allow it once per route (60s) instead of looping on a broken chunk.
function reloadKey() {
  return 'bors:lazy-reload:' + location.pathname + location.hash;
}

/** Lazy بارگذاری ساده و بدون سربار react-router (کنترل کامل روی fallback فارسی) */
export function Lazy({
  load,
  fallback = (
    <div className="p-6" role="status" aria-live="polite">
      <span className="sr-only">در حال بارگذاری...</span>
      <div className="flex flex-col gap-2" aria-hidden="true">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  ),
}: {
  load: () => Promise<{ default: ComponentType }>;
  fallback?: React.ReactNode;
}) {
  const [Comp, setComp] = useState<ComponentType | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const key = reloadKey();

    const attempt = (index: number) => {
      load()
        .then((m) => {
          if (!alive) return;
          try {
            sessionStorage.removeItem(key);
          } catch { /* storage may be disabled */ }
          setComp(() => m.default);
        })
        .catch(() => {
          if (!alive) return;
          if (index < RETRY_DELAYS_MS.length) {
            timer = setTimeout(() => attempt(index + 1), RETRY_DELAYS_MS[index]);
            return;
          }
          let last = 0;
          try {
            last = Number(sessionStorage.getItem(key) || 0);
          } catch { /* storage may be disabled */ }
          if (Date.now() - last > 60000) {
            try {
              sessionStorage.setItem(key, String(Date.now()));
            } catch { /* storage may be disabled */ }
            location.reload();
            return;
          }
          setFailed(true);
        });
    };

    attempt(0);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  if (failed) {
    return (
      <div className="p-6" role="alert">
        <p className="mb-3">بارگذاری این بخش ناموفق ماند.</p>
        <button
          type="button"
          className="rounded border px-3 py-1.5"
          onClick={() => location.reload()}
        >
          تلاش دوباره
        </button>
      </div>
    );
  }

  return <Suspense fallback={fallback}>{Comp ? <Comp /> : fallback}</Suspense>;
}
