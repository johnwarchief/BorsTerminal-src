// shared/components/EmptyState.tsx -- حالت خالی یکدست
import type { ReactNode } from 'react';

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  /** دکمهٔ بازی (مثلاً تلاشِ دوباره) — بدون آن حالت خالی فقط متنی است */
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border-c bg-bg-secondary p-10 text-center">
      <div className="text-sm font-bold text-text-primary">{title}</div>
      {hint ? <div className="text-xs text-text-secondary">{hint}</div> : null}
      {action ?? null}
    </div>
  );
}
