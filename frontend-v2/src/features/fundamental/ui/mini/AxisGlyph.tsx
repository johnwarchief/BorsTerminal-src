import { statusFa, type AxisStatus } from '../../lib/axisMeta';

export function AxisGlyph({ statuses, labels }: { statuses: AxisStatus[]; labels: string[] }) {
  return (
    <div className="fd-glyph flex h-full items-end justify-center gap-0.5" role="img" aria-label={`پنج محور: ${statuses.map((s, i) => `${labels[i]} ${statusFa(s)}`).join('، ')}`}>
      {statuses.map((status, i) => {
        const h = status === 'pass' ? 22 : status === 'fail' ? 16 : status === 'na' ? 8 : 12;
        return <span key={i} className={`w-1 rounded-sm is-${status}`} style={{ height: h }} title={`${labels[i]} — ${statusFa(status)}`} />;
      })}
    </div>
  );
}
