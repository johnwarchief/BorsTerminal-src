import type { AxisStatus } from '../../lib/axisMeta';

export function EpsBars({ series, status, height = 24, label }: {
  series: readonly (number | null)[] | null | undefined; status: AxisStatus; height?: number; label: string;
}) {
  const values = Array.isArray(series) ? series : [];
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  const width = 100;
  const barWidth = values.length ? Math.min(18, (width - 6) / values.length - 4) : 12;
  const gap = values.length > 1 ? (width - 6 - barWidth * values.length) / (values.length - 1) : 0;
  return (
    <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" role="img" aria-label={label} className="h-full w-full overflow-visible">
      {values.map((v, i) => {
        const h = Math.max(2, (Math.abs(v ?? 0) / max) * (height - 4));
        return <rect key={i} className={`fd-chart-bar is-${status}`} x={3 + i * (barWidth + gap)} y={height - h} width={barWidth} height={h} rx="1.5"><title>{v == null ? '—' : String(v)}</title></rect>;
      })}
      <line className="fd-chart-tick" x1="0" y1={height - 1} x2="100" y2={height - 1} />
    </svg>
  );
}
