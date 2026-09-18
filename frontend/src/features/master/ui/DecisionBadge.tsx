// features/master/ui/DecisionBadge.tsx -- بج تصمیم نهایی با ۴ وضعیت قطعی
// خرید پله‌ای · نوسانگیری با ریسک بالا · تحت پایش/انتظار · رد قطعی (وتو)
import { Badge } from '@shared/components/Badge';
import type { DefiniteDecision } from '../lib/strictGates';

const TONE: Record<DefiniteDecision['action'], 'green' | 'yellow' | 'blue' | 'red'> = {
  ladder_buy: 'green',
  high_risk_swing: 'yellow',
  watch: 'blue',
  veto: 'red',
  veto_gate1: 'red',
  veto_gate2: 'red',
};

export function DecisionBadge({ decision }: { decision: DefiniteDecision }) {
  return (
    <div className="flex flex-col gap-1.5" aria-label="حکم نهایی سخت‌گیرانه">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TONE[decision.action]}>{decision.label}</Badge>
        <span className="text-2xs text-text-muted">
          {decision.allGatesPassed ? 'هر ۴ فیلتر سبز' : 'بدون میانگین خطی — قواعد قطعی'}
        </span>
      </div>
      <p className="text-2xs leading-5 text-text-secondary">{decision.reason}</p>
    </div>
  );
}
