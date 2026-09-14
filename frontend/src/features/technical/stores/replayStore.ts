// features/technical/stores/replayStore.ts -- وضعیت بازپخش کندل (Bar Replay)
// جدا از ftsConfigStore نگه داشته شد تا تنظیمات نمایشی و وضعیت شبیه‌ساز قاطی نشوند.
import { create } from 'zustand';
import { REPLAY_DEFAULT_SPEED } from '../lib/replay';

type ReplayState = {
  /** فعال بودن حالت بازپخش */
  active: boolean;
  /** ایندکس آخرین کندل قابل مشاهده (داده بعد از آن پنهان است) */
  cursor: number;
  playing: boolean;
  speedMs: number;
  start: (cursor: number) => void;
  stop: () => void;
  setCursor: (i: number) => void;
  togglePlay: () => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (ms: number) => void;
};

export const useReplayStore = create<ReplayState>((set) => ({
  active: false,
  cursor: 0,
  playing: false,
  speedMs: REPLAY_DEFAULT_SPEED,
  start: (cursor) => set({ active: true, cursor: Math.max(0, cursor), playing: false }),
  stop: () => set({ active: false, playing: false }),
  setCursor: (i) => set({ cursor: Math.max(0, i) }),
  togglePlay: () => set((s) => ({ playing: !s.playing })),
  setPlaying: (p) => set({ playing: p }),
  setSpeed: (ms) => set({ speedMs: ms }),
}));
