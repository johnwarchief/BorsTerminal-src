import { useSearchParams } from 'react-router';
import { FtsFunnelOverview } from './FtsFunnelOverview';
import FtsFunnelStageView from './FtsFunnelStageView';
import { FtsProcessStepper } from './FtsProcessStepper';
import FtsFunnelAllStages from './FtsFunnelAllStages';
import type { FunnelStageKey } from '../lib/ftsFunnel';

export const FUNNEL_SNAP_KEY = 'bors.funnel.snapshot.v1';

export function FtsFunnelStages({ preset }: { preset?: 'swing' | 'trend' | 'hourglass' | 'custom' }) {
  const [params] = useSearchParams();
  const stage = params.get('stage') as FunnelStageKey | null;

  if (stage === 'handover') {
    return <FtsFunnelAllStages preset={preset ?? 'trend'} />;
  }
  if (stage === 'tape' || stage === 'technical' || stage === 'fundamental') {
    return <FtsFunnelStagePageFrame stage={stage} preset={preset} />;
  }
  return <FtsFunnelOverview />;
}

function FtsFunnelStagePageFrame({
  stage,
  preset,
}: {
  stage: Exclude<FunnelStageKey, 'handover'>;
  preset?: 'swing' | 'trend' | 'hourglass' | 'custom';
}) {
  return (
    <div className="flex w-full flex-col gap-4">
      <FtsFunnelStageView stage={stage} />
    </div>
  );
}

export default FtsFunnelStages;
