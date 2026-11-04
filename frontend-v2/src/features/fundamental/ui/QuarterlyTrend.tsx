import { fmtInt } from '@shared/lib/fa';
import type { Quarter } from '../api/useQuarters';

interface Props {
  quarters: readonly Quarter[];
  loading?: boolean;
  error?: boolean;
}

export function QuarterlyTrend({ quarters, loading, error }: Props) {
  if (loading) {
    return <p data-testid="quarterly-loading" className="t-95 text-text-3">گزارش‌های فصلی در حال خواندن…</p>;
  }
  if (error) {
    return <p data-testid="quarterly-error" className="t-95 text-text-3">گزارش‌های فصلی نیامد؛ داده‌ای ساخته نشد.</p>;
  }
  if (!quarters.length) {
    return <p data-testid="quarterly-empty" className="t-95 text-text-3">گزارش فصلی/میان‌دوره‌ای برای این نماد ثبت نشده است.</p>;
  }
  return (
    <div data-testid="quarterly-trend" className="overflow-x-auto">
      <table className="w-full border-collapse t-9">
        <thead>
          <tr className="border-b border-line text-text-3">
            <th className="px-1 py-1 text-start font-bold">دوره</th>
            <th className="px-1 py-1 text-end font-bold">درآمد (م.ریال)</th>
            <th className="px-1 py-1 text-end font-bold">سود خالص (م.ریال)</th>
            <th className="px-1 py-1 text-end font-bold">EPS</th>
          </tr>
        </thead>
        <tbody>
          {quarters.map((q, index) => (
            <tr key={`${q.period_end ?? 'x'}-${index}`} data-testid={`quarter-row-${index}`}
              className="border-b border-line/60 last:border-0">
              <td className="px-1 py-1 text-text-2">
                {q.period_end ?? '—'}
                {q.period_months ? <span className="text-text-3"> · {q.period_months} ماهه</span> : null}
              </td>
              <td className="num px-1 py-1 text-end text-text-2">{q.revenue == null ? '—' : fmtInt(q.revenue)}</td>
              <td className="num px-1 py-1 text-end text-text-2">{q.net_profit == null ? '—' : fmtInt(q.net_profit)}</td>
              <td className="num px-1 py-1 text-end text-text-2">{q.basic_eps == null ? '—' : fmtInt(q.basic_eps)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
