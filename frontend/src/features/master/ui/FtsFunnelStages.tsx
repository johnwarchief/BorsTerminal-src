import { useSearchParams } from 'react-router';
import { FtsFunnelOverview } from './FtsFunnelOverview';
import FtsFunnelStageView from './FtsFunnelStageView';
import { FtsProcessStepper } from './FtsProcessStepper';
import { FtsFunnelStages as FtsFunnelAllStages } from './FtsFunnelAllStages';
import type { FunnelStageKey, TreePreset } from '../lib/ftsFunnel';

export const FUNNEL_SNAP_KEY = 'bors.funnel.snapshot.v1';

const VALID_PRESETS: readonly TreePreset[] = ['swing', 'trend', 'hourglass', 'custom'];

export function FtsFunnelStages({ preset }: { preset?: TreePreset; onPresetChange?: (preset: Exclude<TreePreset, 'custom'>) => void }) {
  const [params] = useSearchParams();
  const stage = params.get('stage') as FunnelStageKey | null;
  const activePreset = VALID_PRESETS.includes(params.get('preset') as TreePreset)
    ? params.get('preset') as TreePreset
    : preset ?? 'trend';
  const symbol = params.get('symbol');

  if (stage === 'handover') {
    return (
      <div className="flex w-full flex-col gap-4" data-testid="fts-funnel-final-view">
        <FtsProcessStepper active="handover" preset={activePreset} symbol={symbol} />
        <FtsFunnelAllStages preset={activePreset} />
      </div>
    );
  }
  if (stage === 'tape' || stage === 'technical' || stage === 'fundamental') {
    return <FtsFunnelStageView stage={stage} />;
  }
  return <FtsFunnelOverview />;
}

export default FtsFunnelStages;
