// features/technical/components/FtsToolbar.tsx -- کلیدهای لایه FTS بالای چارت
import { useFtsConfigStore, type FtsLayerKey } from '../stores/ftsConfigStore';

const ITEMS: { key: FtsLayerKey; label: string }[] = [
  { key: 'showMAs', label: 'مووینگ ها' },
  { key: 'showJetTrigger', label: 'خط آبی' },
  { key: 'showChoch', label: 'خط چین قرمز' },
  { key: 'showFibZones', label: 'کمربند فیبو' },
  { key: 'showSetupMarkers', label: 'مارکر ستاپ' },
  { key: 'enforceRiskGates', label: 'گیت ریسک' },
  { key: 'showFtsCard', label: 'کارت وضعیت' },
];

export function FtsToolbar() {
  const toggle = useFtsConfigStore((s) => s.toggle);
  const showMAs = useFtsConfigStore((s) => s.showMAs);
  const showJetTrigger = useFtsConfigStore((s) => s.showJetTrigger);
  const showChoch = useFtsConfigStore((s) => s.showChoch);
  const showFibZones = useFtsConfigStore((s) => s.showFibZones);
  const showSetupMarkers = useFtsConfigStore((s) => s.showSetupMarkers);
  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const showFtsCard = useFtsConfigStore((s) => s.showFtsCard);
  const states: Record<FtsLayerKey, boolean> = {
    showMAs,
    showJetTrigger,
    showChoch,
    showFibZones,
    showSetupMarkers,
    enforceRiskGates,
    showFtsCard,
  };

  return (
    <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-3" role="toolbar" aria-label="کنترل لایه های FTS">
      {ITEMS.map((it) => {
        const on = states[it.key];
        return (
          <button
            key={it.key}
            type="button"
            onClick={() => toggle(it.key)}
            aria-pressed={on}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
              on
                ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:text-text-secondary'
            }`}
          >
            {it.label}: {on ? 'روشن' : 'خاموش'}
          </button>
        );
      })}
    </div>
  );
}
