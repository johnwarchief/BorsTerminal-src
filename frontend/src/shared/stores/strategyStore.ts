// shared/stores/strategyStore.ts -- افق استراتژی سرمایه‌گذاری FTS (سراسری)
// نوسان‌گیر (swing) / روندگیر (trend) / ساعت شنی (hourglass)
import { create } from 'zustand';
import type { StrategyHorizon } from '@features/master/lib/ftsPipelineEvaluator';

const STORAGE_KEY = 'fts.strategy.horizon.v1';

export type StrategyState = {
  horizon: StrategyHorizon;
  setHorizon: (h: StrategyHorizon) => void;
};

function getSavedHorizon(): StrategyHorizon {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw === 'swing' || raw === 'trend' || raw === 'hourglass') {
        return raw;
      }
    }
  } catch {
    // Local storage unavailable
  }
  return 'trend';
}

export const useStrategyStore = create<StrategyState>((set) => ({
  horizon: getSavedHorizon(),
  setHorizon: (horizon: StrategyHorizon) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem(STORAGE_KEY, horizon);
      }
    } catch {
      // Local storage unavailable
    }
    set({ horizon });
  },
}));
