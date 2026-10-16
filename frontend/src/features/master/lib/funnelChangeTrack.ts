/* features/master/lib/funnelChangeTrack.ts — «همین حالا چه چیزی عوض شد»
 *
 * قیف هر چندِ ثانیه دوباره خوانده می‌شود و ردیف‌ها جابه‌جا می‌شوند. بی‌این
 * ردیابی کاربر تنها عددِ کلِ سرِ ستون را می‌بیند و نمی‌فهمد *کدام* حکم تازه
 * عوض شده — یعنی «زنده بودن» دیده نمی‌شود.
 *
 * هیچ داوریِ تازه‌ای اینجا ساخته نمی‌شود: وضعیتِ همان ردیف با وضعیتِ دورۀ
 * پیشین مقایسه می‌شود و بس. نه آستانه‌ای، نه وزنی.
 *
 * چرا ref/Map و نه state: نوشتنِ نتیجه درِ همان render حلقۀ بی‌پایانِ React
 * می‌سازد (همان ریشۀ WS-V-1). پس مقایسه درِ render فقط می‌خواند و ثبتِ
 * وضعیتِ تازه درِ useEffectِ بعد از commit انجام می‌شود. */
import { useEffect, useMemo } from 'react';
import type { FunnelEntry, FunnelStageKey, StageStatus } from './ftsFunnel';

type Snap = Map<string, StageStatus>;

export type StageDelta = { passed: number; ruled: number };

const lastStatus = new Map<FunnelStageKey, Snap>();
const lastCounts = new Map<FunnelStageKey, StageDelta>();

/** ردیف‌هایی که حکمشان نسبت به دورۀ پیشین عوض شده + چگونۀ تغییرِ شمارِ گام.
 *  `entries`/`counts` باید از همان پاسخِ قیف بیایند (تازگیِ یکسان با جدول).
 *  مقایسه درِ render فقط می‌خواند؛ ثبتِ وضعیتِ تازه درِ useEffectِ بعد از
 *  commit انجام می‌شود، پس دو دورۀ «پیشین» هرگز درِ یک render جابه‌جا نمی‌شوند. */
export function useVerdictChanges(
  stageKey: FunnelStageKey,
  entries: FunnelEntry[],
  counts: StageDelta,
): { changed: Set<string>; delta: StageDelta | null } {
  const changed = useMemo(() => {
    const out = new Set<string>();
    const prev = lastStatus.get(stageKey);
    if (!prev) return out;
    for (const e of entries) {
      const before = prev.get(e.symbol);
      const now = e.status[stageKey];
      if (before !== undefined && now !== undefined && before !== now) out.add(e.symbol);
    }
    return out;
  }, [entries, stageKey]);

  const delta = useMemo<StageDelta | null>(() => {
    const prev = lastCounts.get(stageKey);
    if (!prev) return null;
    return { passed: counts.passed - prev.passed, ruled: counts.ruled - prev.ruled };
  }, [counts.passed, counts.ruled, stageKey]);

  useEffect(() => {
    const m: Snap = new Map();
    for (const e of entries) m.set(e.symbol, e.status[stageKey]);
    lastStatus.set(stageKey, m);
    lastCounts.set(stageKey, counts);
  }, [entries, counts, stageKey]);

  return { changed, delta };
}

/** تنها برایِ تست: حالتِ ماژول را بی‌ریخت می‌کند تا دو سنجش به هم نپیچند. */
export function __resetVerdictChangesForTests() {
  lastStatus.clear();
  lastCounts.clear();
}
