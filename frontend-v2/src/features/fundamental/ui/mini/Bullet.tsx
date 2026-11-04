import { statusFa, type AxisStatus } from '../../lib/axisMeta';

export function Bullet({ value, max, threshold, status, height = 22, label }: {
  value: number | null; max: number; threshold: number | null; status: AxisStatus; height?: number; label: string;
}) {
  const ratio = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const th = threshold == null ? null : Math.max(0, Math.min(1, threshold / max));
  return (
    <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" role="img" aria-label={`${label} — ${statusFa(status)}`} className="h-full w-full overflow-visible">
      <rect className="fd-chart-track" x="0" y={height / 2 - 4} width="100" height="8" rx="3" />
      <rect className={`fd-chart-fill is-${status}`} x="0" y={height / 2 - 4} width={ratio * 100} height="8" rx="3" />
      {th == null ? null : <line className="fd-th-line" x1={th * 100} y1={height / 2 - 7} x2={th * 100} y2={height / 2 + 7} />}
    </svg>
  );
}
