// shared/stores/marketStore.ts -- تنظیمات پولینگ تابلو بازار
import { create } from 'zustand';

/** بازه به روزرسانی تابلو -- هم ارز اسلایدر 1 ثانیه تا 30 دقیقه */
export const POLL_MIN_MS = 1_000;
export const POLL_MAX_MS = 30 * 60_000;
export const POLL_DEFAULT_MS = 60_000;

type MarketState = {
  /** فاصله پولینگ به میلی ثانیه */
  refetchIntervalMs: number;
  /** توقف موقت پولینگ (مثلا وقتی تب مخفی است) */
  paused: boolean;
  setRefetchIntervalMs: (ms: number) => void;
  setPaused: (p: boolean) => void;
};

function clampPoll(ms: number): number {
  if (!Number.isFinite(ms)) return POLL_DEFAULT_MS;
  return Math.min(POLL_MAX_MS, Math.max(POLL_MIN_MS, Math.round(ms)));
}

const STORAGE_KEY = 'bors-poll-ms';

function initialPoll(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw != null) return clampPoll(Number(raw));
  } catch {
    // نادیده بگیر
  }
  return POLL_DEFAULT_MS;
}

export const useMarketStore = create<MarketState>((set) => ({
  refetchIntervalMs: initialPoll(),
  paused: false,
  setRefetchIntervalMs: (ms) => {
    const v = clampPoll(ms);
    try {
      localStorage.setItem(STORAGE_KEY, String(v));
    } catch {
      // نادیده بگیر
    }
    set({ refetchIntervalMs: v });
  },
  setPaused: (p) => set({ paused: p }),
}));
