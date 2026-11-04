import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { cardStatus } from '../../lib/cardStatus';
import { HistoryBars } from '../mini/HistoryBars';
import { AxisPanel, faFixed } from './AxisPanel';

export function HistoryPanel({ card }: { card: FtsCard }) {
  const history = card.history ?? [];
  const status = cardStatus(card, 'eps');
  const last = history.length ? history[history.length - 1] : null;
  return (
    <AxisPanel
      testId="panel-history"
      axis="eps"
      title="تاریخچهٔ گزارش‌ها"
      subtitle="ارقام گزارش‌شده/تجمعی؛ برچسب فصلی ندارد"
      status={status}
      value={history.length ? `${toFaDigits(history.length)} گزارش` : '—'}
      threshold="EPS"
      chart={<HistoryBars values={history.map((row) => row.eps ?? null)} labels={history.map((row) => (row.period_end ? toFaDigits(row.period_end) : ''))} status={status} />}
      rows={[
        ['آخرین دوره', last?.period_end ? toFaDigits(last.period_end) : '—'],
        ['EPS آخرین دوره', faFixed(last?.eps, 0)],
        ['درآمد آخرین دوره', faFixed(last?.revenue, 1)],
        ['تلفیقی', history.some((row) => row.consolidated) ? 'دارد' : '—'],
        ['حسابرسی‌شده', history.some((row) => row.audited) ? 'دارد' : '—'],
      ]}
      details={card.details?.['۲']}
    />
  );
}
