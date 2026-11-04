import type { AxisStatus } from '../../lib/axisMeta';

// status === 'pass' اگر رژیم رتبه دارد؛ برای رژیم فعال از is-pass/is-fail/is-unknown
export function RegimeGlyph({ regime, status }: { regime: string | null; status: AxisStatus }) {
  const order = ['free', 'neutral', 'mandatory'];
  const active = regime ? order.indexOf(regime) : -1;
  return (
    <div className="flex h-full items-center justify-center gap-1" role="img" aria-label={`رژیم ${regime ?? 'نامشخص'}`}>
      {order.map((key, i) => (
        <span key={key} className={`fd-regime-dot h-2 w-2 rounded-full ${i === active ? `is-active is-${status}` : ''}`} title={key} />
      ))}
    </div>
  );
}
