// features/technical/lib/chartSync.ts -- باس همگام‌سازی کراس‌هیر/زوم بین چند چارت (Split View)
// خالص و مستقل از DOM: هر چارت با یک id ثبت می‌شود و فرمان‌های دیگران را می‌گیرد.
// نسخهٔ singleton بر اساس groupId نگه داشته می‌شود تا چارت‌های یک گروه به هم وصل شوند.

export type SyncCommand =
  | { kind: 'crosshair'; timestamp: number | null }
  | { kind: 'range'; barSpace: number; anchorTimestamp: number | null };

export type SyncMember = (cmd: SyncCommand) => void;

export class ChartSyncBus {
  private members = new Map<string, SyncMember>();

  register(id: string, fn: SyncMember): () => void {
    this.members.set(id, fn);
    return () => {
      this.members.delete(id);
    };
  }

  /** فرمان را به همهٔ اعضای دیگر می‌فرستد (فرستنده حذف می‌شود تا حلقه نشود) */
  broadcast(fromId: string, cmd: SyncCommand): void {
    for (const [id, fn] of this.members) {
      if (id === fromId) continue;
      try {
        fn(cmd);
      } catch {
        // یک عضو خراب نباید بقیه را متوقف کند
      }
    }
  }

  size(): number {
    return this.members.size;
  }

  clear(): void {
    this.members.clear();
  }
}

const buses = new Map<string, ChartSyncBus>();

/** باس مشترک یک گروه (مثلاً چارت‌های Split View) */
export function syncBus(groupId: string): ChartSyncBus {
  let b = buses.get(groupId);
  if (!b) {
    b = new ChartSyncBus();
    buses.set(groupId, b);
  }
  return b;
}

/** فقط برای تست: پاک کردن همهٔ باس‌ها */
export function resetSyncBuses(): void {
  buses.clear();
}
