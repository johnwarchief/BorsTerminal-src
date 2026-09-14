// shared/components/EmptyState.tsx -- حالت خالی یکدست
export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border-c bg-bg-secondary p-10 text-center">
      <div className="text-sm font-bold text-text-primary">{title}</div>
      {hint ? <div className="text-xs text-text-secondary">{hint}</div> : null}
    </div>
  );
}
