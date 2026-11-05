import { toFaDigits } from '@shared/lib/fa';

const faFixed1 = (v: number | null | undefined): string =>
  v == null ? '—' : toFaDigits(v.toFixed(1)).replace('.', '٫');

export function PeDots({ pe, median, peers }: { pe: number | null | undefined; median: number | null | undefined; peers: number | null | undefined }) {
  const max = Math.max(pe ?? 0, median ?? 0, 1) * 1.2;
  const x = (v: number) => (v / max) * 100;
  return (
    // R-UNSLOP-2: برچسب «همتاها» از متنِ SVGِ ۴واحدی (≈۸px روی صفحه) به کپشنِ HTMLِ ۱۲px رفت؛
    // نمودار فقط شکل است و عددِ خوانا بیرونِ جعبهٔ مقیاس زندگی می‌کند.
    <div className="flex h-full min-h-0 flex-col gap-1">
      <svg viewBox="0 0 100 18" role="img" aria-label={`P/E ${faFixed1(pe)} در برابر میانهٔ ${faFixed1(median)}`} className="min-h-0 w-full flex-1 overflow-visible">
        <line className="fd-chart-tick" x1="0" y1="9" x2="100" y2="9" />
        {median != null ? <line className="fd-th-line" x1={x(median)} y1="4" x2={x(median)} y2="14" /> : null}
        {pe != null ? <circle className="fd-chart-fill" cx={x(pe)} cy="9" r="3" /> : null}
      </svg>
      {peers != null ? <span className="fd-meta truncate text-[var(--fd-text-3)]">{toFaDigits(peers)} همتا</span> : null}
    </div>
  );
}
