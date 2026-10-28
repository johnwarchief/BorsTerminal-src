import type { MarketRow } from '@shared/types/market';
import { useWorkspace, type CardId } from '@shared/workspace/store';
import type { MarketSnapshot } from '../api/useMarketSnapshot';
import { CARD_REGISTRY } from './cards/registry';
import { CardTile } from './cards/CardTile';

export function SnapshotStrip({ rows, snapshot }: { rows: readonly MarketRow[]; snapshot?: MarketSnapshot }) {
  const slots = useWorkspace((state) => state.workspaces[0].slots);
  const setSlots = useWorkspace((state) => state.setSlots);

  // چیدمان RTL است: خانهٔ ۰ سمتِ راست است، پس «به راست» یعنی یک خانه به عقب.
  function move(index: number, offset: number) {
    const next = [...slots];
    const target = index + offset;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target]!, next[index]!];
    setSlots(next);
  }

  function pick(index: number, id: CardId) {
    const next = slots.filter((slot) => slot !== id);
    next.splice(index, 1, id);
    setSlots(next);
  }

  return (
    <div data-testid="snapshot-strip" className="flex shrink-0 items-stretch gap-1.5 border-b border-line bg-panel px-2 py-1.5">
      {slots.map((id, index) => (
        <CardTile
          key={id}
          descriptor={CARD_REGISTRY[id]}
          context={{ rows, snapshot }}
          onMoveLeft={() => move(index, 1)}
          onMoveRight={() => move(index, -1)}
          onPick={(next) => pick(index, next as CardId)}
        />
      ))}
    </div>
  );
}
