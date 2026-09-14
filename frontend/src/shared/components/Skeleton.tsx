// shared/components/Skeleton.tsx -- اسکلتون بارگذاری سبک (بدون پکیج جدید)
type Round = 'sm' | 'md' | 'lg' | 'xl' | 'full';

const RADIUS: Record<Round, string> = {
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  xl: 'rounded-xl',
  full: 'rounded-full',
};

/** یک بلوک اسکلتون؛ اندازه و چیدمان از className می آید. */
export function Skeleton({ className = '', rounded = 'md' }: { className?: string; rounded?: Round }) {
  return (
    <span
      aria-hidden="true"
      className={`block animate-pulse bg-text-muted/15 ${RADIUS[rounded]} ${className}`}
    />
  );
}

/** چند خط اسکلتون برای حالت «در حال بارگذاری» متن. */
export function SkeletonLines({
  lines = 3,
  className = '',
  label = 'در حال بارگذاری',
}: {
  lines?: number;
  className?: string;
  label?: string;
}) {
  const n = Math.max(1, lines);
  return (
    <div role="status" aria-busy="true" aria-label={label} className={`flex w-full flex-col gap-2 ${className}`}>
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} className={i === n - 1 ? 'h-3 w-3/5' : 'h-3 w-full'} />
      ))}
    </div>
  );
}
