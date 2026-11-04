import { faNum, toFaDigits } from '@shared/lib/fa';
import type { CodalHealth } from '../api/useCodalHealth';

interface Props {
  health: CodalHealth | undefined;
  loading?: boolean;
}

function num(v: number | null | undefined): string {
  return typeof v === 'number' && Number.isFinite(v) ? faNum(v, 0) : '—';
}

/** R103: مهرهای زمانی بدونِ رقمِ لاتین در سطحِ فارسی. */
function faText(value: string | null | undefined): string {
  return value ? toFaDigits(value) : '—';
}

export function CodalHealthStrip({ health, loading }: Props) {
  if (loading) {
    return <p data-testid="codal-health-loading" className="t-85 text-[var(--fd-text-3)]">سلامت خط کدال در حال خواندن…</p>;
  }
  if (!health || health.status !== 'success') {
    return (
      <p data-testid="codal-health-unavailable" className="t-85 text-[var(--fd-text-3)]">
        وضعیت سلامت کدال در دسترس نیست{health?.message ? ` — ${health.message}` : ''}
      </p>
    );
  }

  const queue = health.queue;
  return (
    <div data-testid="codal-health" className="flex flex-wrap items-center gap-1.5 t-85 text-[var(--fd-text-3)]">
      <span className="font-bold text-[var(--fd-text-2)]">کدال</span>
      <span data-testid="codal-health-queued" className="rounded-[3px] border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-1">
        صف {num(queue?.queued)}
      </span>
      <span className="rounded-[3px] border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-1">
        ناموفق {num(queue?.failed)}
      </span>
      <span className="rounded-[3px] border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-1">
        قرنطینه {num(queue?.quarantined)}
      </span>
      <span className="rounded-[3px] border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-1">
        نمادهای در انتظار {num(health.dirty_symbols)}
      </span>
      {health.gap_flag ? (
        <span className="rounded-[3px] border border-[var(--fd-warn)] px-1 text-[var(--fd-warn)]">شکاف فید</span>
      ) : null}
      {health.last_successful_sync?.at ? (
        <span>آخرین همگام‌سازی موفق: {faText(health.last_successful_sync.at)}</span>
      ) : (
        <span>همگام‌سازی موفقی ثبت نشده</span>
      )}
      {health.last_data_update ? <span>آخرین داده: {faText(health.last_data_update)}</span> : null}
    </div>
  );
}
