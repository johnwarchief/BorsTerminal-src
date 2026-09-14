// features/technical/stores/ftsConfigStore.ts -- کلیدهای نمایشی استراتژی FTS
import { create } from 'zustand';

export type FtsLayerKey =
  | 'showMAs'
  | 'showJetTrigger'
  | 'showChoch'
  | 'enforceRiskGates'
  | 'showFtsCard'
  | 'showFibZones'
  | 'showSetupMarkers';

type FtsFlags = Record<FtsLayerKey, boolean>;

type FtsConfigState = FtsFlags & {
  toggle: (k: FtsLayerKey) => void;
};

const STORAGE_KEY = 'bors-fts-config';

const DEFAULTS: FtsFlags = {
  showMAs: true,
  showJetTrigger: true,
  showChoch: true,
  enforceRiskGates: true,
  showFtsCard: true,
  showFibZones: true,
  showSetupMarkers: true,
};

function pickFlags(s: FtsFlags): FtsFlags {
  return {
    showMAs: s.showMAs,
    showJetTrigger: s.showJetTrigger,
    showChoch: s.showChoch,
    enforceRiskGates: s.enforceRiskGates,
    showFtsCard: s.showFtsCard,
    showFibZones: s.showFibZones,
    showSetupMarkers: s.showSetupMarkers,
  };
}

function initial(): FtsFlags {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<FtsFlags>;
    return { ...DEFAULTS, ...parsed };
  } catch {
    return { ...DEFAULTS };
  }
}

export const useFtsConfigStore = create<FtsConfigState>((set) => ({
  ...initial(),
  toggle: (k) =>
    set((s) => {
      const next = { ...pickFlags(s), [k]: !s[k] };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // نادیده بگیر
      }
      return { ...s, ...next };
    }),
}));
