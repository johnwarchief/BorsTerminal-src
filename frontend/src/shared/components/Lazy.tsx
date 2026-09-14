import { ComponentType, Suspense, useEffect, useState } from 'react';
import { Skeleton } from './Skeleton';

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

  useEffect(() => {
    let alive = true;
    load().then((m) => {
      if (alive) setComp(() => m.default);
    });
    return () => {
      alive = false;
    };
  }, [load]);

  return <Suspense fallback={fallback}>{Comp ? <Comp /> : fallback}</Suspense>;
}
