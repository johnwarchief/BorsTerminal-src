// features/fundamental/components/RiskGatesPanel.tsx -- چهار دروازه ریسک از کارت
import { Badge } from '@shared/components/Badge';
import { industryGateDetail, industryGateTone } from '../lib/industryGate';

export function RiskGatesPanel({
  excluded,
  reasons,
  pricingMode,
  mcapStale,
}: {
  excluded: boolean;
  reasons: string[];
  pricingMode: string | null;
  mcapStale: boolean;
}) {
  return (
    <div className="glass-panel panel-in p-4">
      <h3 className="mb-2 text-sm font-black text-text-primary">دروازه های ریسک</h3>
      <div className="flex flex-wrap gap-2">
        <Badge tone={excluded ? 'red' : 'green'}>{excluded ? 'حذف از غربالگری' : 'مجاز در غربالگری'}</Badge>
        {/* وضعیت صنعت با همان متن/رنگ کارت FTS و drill-down شاخص ۵ */}
        {pricingMode ? <Badge tone={industryGateTone(pricingMode)}>{industryGateDetail(pricingMode)}</Badge> : null}
        {mcapStale ? <Badge tone="yellow">ارزش بازار کهنه</Badge> : <Badge tone="green">ارزش بازار تازه</Badge>}
      </div>
      {reasons.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {reasons.map((r, i) => (
            <li key={i} className="text-xs text-accent-red">
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
