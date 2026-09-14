// features/technical/components/FtsStatusCard.tsx -- بج وضعیت استراتژی FTS
import type { AgentSignal } from '@contracts/signal';
import type { TechnicalPayload } from '@contracts/technical';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';

export type FtsStatus = 'gate_rejected' | 'jet_active' | 'choch_warning' | 'awaiting_break';

export function resolveFtsStatus(
  signal: AgentSignal<TechnicalPayload> | null,
  gateBlocked: boolean,
): FtsStatus {
  if (gateBlocked) return 'gate_rejected';
  const setups = signal?.payload.setups ?? [];
  if (setups.includes('breakout')) return 'jet_active';
  if (setups.includes('choch')) return 'choch_warning';
  return 'awaiting_break';
}

const STATUS_META: Record<FtsStatus, { label: string; tone: 'red' | 'green' | 'yellow' | 'blue' }> = {
  gate_rejected: { label: 'مردود در گیت ریسک', tone: 'red' },
  jet_active: { label: 'پرواز فعال', tone: 'green' },
  choch_warning: { label: 'هشدار CHoCH', tone: 'yellow' },
  awaiting_break: { label: 'در انتظار شکست خط آبی', tone: 'blue' },
};

export function FtsStatusCard({
  signal,
  gateBlocked,
  jetPrice,
}: {
  signal: AgentSignal<TechnicalPayload> | null;
  gateBlocked: boolean;
  jetPrice: number | null;
}) {
  const status = resolveFtsStatus(signal, gateBlocked);
  const meta = STATUS_META[status];
  return (
    <div className="glass-panel panel-in p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">وضعیت FTS</h3>
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </div>
      <div className="mt-2 flex flex-col gap-1 text-xs text-text-secondary">
        {jetPrice != null ? (
          <span>
            خط آبی پرواز: <span className="num font-bold text-neon-cyan">{toFaDigits(jetPrice.toFixed(0))}</span>
          </span>
        ) : (
          <span>خط آبی محاسبه نشد</span>
        )}
        {signal?.score != null ? (
          <span>
            امتیاز همگرایی: <span className="num font-bold text-text-primary">{toFaDigits(signal.score)}</span>
          </span>
        ) : null}
        {signal ? <span>{signal.rationale}</span> : <span>در انتظار داده...</span>}
      </div>
    </div>
  );
}
