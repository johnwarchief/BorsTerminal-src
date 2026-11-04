import { toFaDigits } from '@shared/lib/fa';

const faFixed1 = (v: number | null | undefined): string =>
  v == null ? '—' : toFaDigits(v.toFixed(1)).replace('.', '٫');

export function PeDots({ pe, median, peers }: { pe: number | null | undefined; median: number | null | undefined; peers: number | null | undefined }) {
  const max = Math.max(pe ?? 0, median ?? 0, 1) * 1.2;
  const x = (v: number) => (v / max) * 100;
  return (
    <svg viewBox="0 0 100 18" role="img" aria-label={`P/E ${faFixed1(pe)} در برابر میانهٔ ${faFixed1(median)}`} className="h-full w-full overflow-visible">
      <line className="fd-chart-tick" x1="0" y1="9" x2="100" y2="9" />
      {median != null ? <line className="fd-th-line" x1={x(median)} y1="4" x2={x(median)} y2="14" /> : null}
      {pe != null ? <circle className="fd-chart-fill" cx={x(pe)} cy="9" r="3" /> : null}
      {peers != null ? <text x="0" y="17" className="fd-chart-text" fontSize="4">{toFaDigits(peers)} همتا</text> : null}
    </svg>
  );
}
