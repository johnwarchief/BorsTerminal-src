import { ComponentType, Suspense, useEffect, useState } from 'react';

/** Lazy بارگذاری ساده و بدون سربار react-router (کنترل کامل روی fallback فارسی) */
export function Lazy({
  load,
  fallback = <div className="p-6 text-text-secondary">در حال بارگذاری...</div>,
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
