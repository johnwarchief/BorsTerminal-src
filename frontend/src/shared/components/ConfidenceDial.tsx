// shared/components/ConfidenceDial.tsx -- نمایش اعتماد داده
import type { Confidence } from '@contracts/signal';

const CONF: Record<Confidence, { label: string; tone: string; pct: number }> = {
  high: { label: 'بالا', tone: 'text-accent-green', pct: 90 },
  medium: { label: 'متوسط', tone: 'text-accent-yellow', pct: 60 },
  low: { label: 'کم', tone: 'text-accent-red', pct: 30 },
  nodata: { label: 'بدون داده', tone: 'text-text-muted', pct: 0 },
};

export function ConfidenceDial({ value }: { value: Confidence }) {
  const c = CONF[value];
  return (
    <span className="inline-flex items-center gap-2" title={`اعتماد: ${c.label}`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-bg-card">
        <span className={`block h-full rounded-full bg-current ${c.tone}`} style={{ width: `${c.pct}%` }} />
      </span>
      <span className={`text-xs font-semibold ${c.tone}`}>{c.label}</span>
    </span>
  );
}
