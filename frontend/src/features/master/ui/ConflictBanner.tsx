// features/master/ui/ConflictBanner.tsx -- هشدار تضاد با حاشیه ضربان دار
import type { AgentId } from '@contracts/signal';
import type { MasterVerdict } from '@contracts/master';
import { toFaDigits } from '@shared/lib/fmt';

const AGENT_FA: Record<AgentId, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'پرتفوی',
};

/** شدت شکاف افق: سهم شکاف از بیشینه ممکن (200) */
export function conflictSeverity(gap: number): 'high' | 'medium' | 'low' {
  if (gap >= 120) return 'high';
  if (gap >= 60) return 'medium';
  return 'low';
}

export function ConflictBanner({ verdict }: { verdict: MasterVerdict }) {
  if (!verdict.hasConflict || verdict.dissent.length === 0) return null;
  return (
    <div
      className="conflict-pulse panel-in relative overflow-hidden rounded-2xl border-2 border-accent-susp/70 bg-accent-susp-bg p-4"
      role="alert"
    >
      <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-transparent to-accent-susp/10" aria-hidden />
      <h3 className="mb-1 flex items-center gap-2 text-sm font-black text-accent-susp">
        <span className="inline-block h-2 w-2 animate-ping rounded-full bg-accent-susp" aria-hidden />
        هشدار تضاد افق زمانی
        {verdict.discardedSignalIds.length > 0 ? (
          <span className="num text-xs font-bold text-text-secondary">
            تنزیل اطمینان · {toFaDigits(verdict.discardedSignalIds.length)} سیگنال کنار گذاشته شده
          </span>
        ) : null}
      </h3>
      <ul className="flex flex-col gap-1">
        {verdict.dissent.map((d, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 text-xs leading-6 text-text-primary">
            <span className="rounded-full border border-accent-susp/30 bg-accent-susp-bg px-2 py-0.5 font-bold text-accent-susp">
              {AGENT_FA[d.agents[0]]} vs {AGENT_FA[d.agents[1]]}
            </span>
            {d.note} <span className="num text-text-secondary">(شکاف {toFaDigits(Math.round(d.gap))} از 200 · شدت {conflictSeverity(d.gap) === 'high' ? 'زیاد' : conflictSeverity(d.gap) === 'medium' ? 'متوسط' : 'کم'})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
