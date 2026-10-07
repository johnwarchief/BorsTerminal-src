import { useSearchParams } from 'react-router';
import StrategyTreeOverview from '../ui/StrategyTreeOverview';
import StrategyTreeStageView from '../ui/StrategyTreeStageView';

export default function StrategyTreePage() {
  const [params] = useSearchParams();
  const page = params.get('page');
  if (page === 'F' || page === 'T' || page === 'S' || page === 'M') {
    return <StrategyTreeStageView zone={page} />;
  }
  return <StrategyTreeOverview />;
}
