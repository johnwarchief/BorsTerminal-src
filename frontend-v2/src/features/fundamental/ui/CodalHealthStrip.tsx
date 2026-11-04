import { faNum } from '@shared/lib/fa';
import type { CodalHealth } from '../api/useCodalHealth';

interface Props {
  health: CodalHealth | undefined;
  loading?: boolean;
}

function num(v: number | null | undefined): string {
  return typeof v === 'number' && Number.isFinite(v) ? faNum(v, 0) : '—';
}

export function CodalHealthStrip({ health, loading }: Props) {
  if (loading) {
    return <p data-testid="codal-health-loading" className="t-85 text-text-3">سلامت خط کدال در حال خواندن…</p>;
  }
  if (!health || health.status !== 'success') {
    return (
      <p data-testid="codal-health-unavailable" className="t-85 text-text-3">
        وضعیت سلامت کدال در دسترس نیست{health?.message ? ` — ${health.message}` : ''}
      </p>
    );
  }

  const queue = health.queue;
  return (
    <div data-testid="codal-health" className="flex flex-wrap items-center gap-1.5 t-85 text-text-3">
      <span className="font-bold text-text-2">کدال</span>
      <span data-testid="codal-health-queued" className="rounded-[3px] border border-line bg-panel-2 px-1">
        صف {num(queue?.queued)}
      </span>
      <span className="rounded-[3px] border border-line bg-panel-2 px-1">
        ناموفق {num(queue?.failed)}
      </span>
      <span className="rounded-[3px] border border-line bg-panel-2 px-1">
        قرنطینه {num(queue?.quarantined)}
      </span>
      <span className="rounded-[3px] border border-line bg-panel-2 px-1">
        نمادهای در انتظار {num(health.dirty_symbols)}
      </span>
      {health.gap_flag ? (
        <span className="rounded-[3px] border border-warn/40 bg-warn/10 px-1 text-warn">شکاف فید</span>
      ) : null}
      {health.last_successful_sync?.at ? (
        <span>آخرین sync موفق: {health.last_successful_sync.at}</span>
      ) : (
        <span>sync موفقی ثبت نشده</span>
      )}
      {health.last_data_update ? <span>آخرین داده: {health.last_data_update}</span> : null}
    </div>
  );
}
