// features/technical/components/ReplayBar.tsx -- نوار بازپخش کندل (Bar Replay) سبک TradingView
// کاربر با اسلایدر یک کندل گذشته را انتخاب می‌کند؛ کندل‌های بعد پنهان می‌شوند و با
// Play/Pause/کندل بعد/قبل به‌صورت کندل‌به‌کندل جلو می‌رود (بک‌تست دستی).
import { REPLAY_SPEEDS } from '../lib/replay';
import { toFaDigits } from '@shared/lib/fmt';
import { useReplayStore } from '../stores/replayStore';

export function ReplayBar({ total }: { total: number }) {
  const active = useReplayStore((s) => s.active);
  const cursor = useReplayStore((s) => s.cursor);
  const playing = useReplayStore((s) => s.playing);
  const speedMs = useReplayStore((s) => s.speedMs);
  const start = useReplayStore((s) => s.start);
  const stop = useReplayStore((s) => s.stop);
  const setCursor = useReplayStore((s) => s.setCursor);
  const togglePlay = useReplayStore((s) => s.togglePlay);
  const setSpeed = useReplayStore((s) => s.setSpeed);

  const max = Math.max(0, total - 1);
  const cur = Math.min(Math.max(0, cursor), max);

  if (!active) {
    return (
      <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-2.5" data-testid="replay-bar">
        <span className="text-[11px] font-bold text-text-secondary">بازپخش</span>
        <button
          type="button"
          data-testid="replay-start"
          disabled={total < 2}
          onClick={() => start(max)}
          className="rounded-full border border-border-accent bg-bg-card px-3 py-1 text-xs font-bold text-accent-blue transition-colors hover:bg-accent-blue/15 disabled:opacity-40"
        >
          شروع بازپخش
        </button>
        <span className="text-[10px] text-text-muted">
          {total < 2 ? 'دادهٔ کافی برای بازپخش نیست' : 'شروع از آخرین کندل؛ سپس با اسلایدر به عقب برگردان و پخش کن'}
        </span>
      </div>
    );
  }

  return (
    <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-2.5" data-testid="replay-bar">
      <span className="text-[11px] font-bold text-text-secondary">بازپخش</span>
      <button
        type="button"
        data-testid="replay-play"
        onClick={togglePlay}
        aria-pressed={playing}
        className={`rounded-full border px-3 py-1 text-xs font-bold transition-colors ${
          playing ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
        }`}
      >
        {playing ? 'توقف' : 'پخش'}
      </button>
      <button
        type="button"
        data-testid="replay-prev"
        onClick={() => setCursor(Math.max(0, cur - 1))}
        className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-xs text-text-secondary hover:text-accent-blue"
      >
        کندل قبل
      </button>
      <button
        type="button"
        data-testid="replay-next"
        onClick={() => setCursor(Math.min(max, cur + 1))}
        className="rounded-full border border-border-c bg-bg-card px-3 py-1 text-xs text-text-secondary hover:text-accent-blue"
      >
        کندل بعد
      </button>
      <label className="flex items-center gap-1 text-[10px] text-text-muted">
        موقعیت
        <input
          type="range"
          min={0}
          max={max}
          value={cur}
          data-testid="replay-slider"
          onChange={(e) => setCursor(Number(e.target.value))}
          className="h-1 w-40 accent-sky-400"
          aria-label="انتخاب کندل بازپخش"
        />
      </label>
      <label className="flex items-center gap-1 text-[10px] text-text-muted">
        سرعت
        <select
          data-testid="replay-speed"
          value={speedMs}
          onChange={(e) => setSpeed(Number(e.target.value))}
          className="rounded border border-border-c bg-bg-card px-1 py-0.5 text-[11px] text-text-secondary"
          aria-label="سرعت بازپخش"
        >
          {REPLAY_SPEEDS.map((ms) => (
            <option key={ms} value={ms}>
              {toFaDigits(1000 / ms)}×
            </option>
          ))}
        </select>
      </label>
      <span className="num text-[10px] text-text-muted" data-testid="replay-progress">
        کندل {toFaDigits(cur + 1)} از {toFaDigits(total)}
      </span>
      <button
        type="button"
        data-testid="replay-stop"
        onClick={stop}
        className="mr-auto rounded-full border border-border-c px-2.5 py-0.5 text-[11px] text-text-muted hover:border-accent-red/50 hover:text-accent-red"
      >
        خروج از بازپخش
      </button>
    </div>
  );
}
