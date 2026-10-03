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
  /** نمادی که مکان‌نما مالِ سریِ اوست — بازپخش درِ میانهٔ نمادِ دیگر بی‌معنا است */
  owner: string | null;
  start: (cursor: number) => void;
  stop: () => void;
  setCursor: (i: number) => void;
  togglePlay: () => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (ms: number) => void;
  /** با عوض‌شدنِ نماد: اگر بازپخش مالِ نمادِ دیگری بود خاموش می‌شود و خانه تازه می‌گیرد */
  rehome: (symbol: string) => void;
};

export const useReplayStore = create<ReplayState>((set, get) => ({
  active: false,
  cursor: 0,
  playing: false,
  speedMs: REPLAY_DEFAULT_SPEED,
  owner: null,
  start: (cursor) => set({ active: true, cursor: Math.max(0, cursor), playing: false }),
  stop: () => set({ active: false, playing: false, owner: null }),
  setCursor: (i) => set({ cursor: Math.max(0, i) }),
  togglePlay: () => set((s) => ({ playing: !s.playing })),
  setPlaying: (p) => set({ playing: p }),
  setSpeed: (ms) => set({ speedMs: ms }),
  rehome: (symbol) => {
    const s = get();
    if (s.active && s.owner && s.owner !== symbol) {
      set({ active: false, playing: false, owner: symbol });
      return;
    }
    set({ owner: symbol });
  },
}));
