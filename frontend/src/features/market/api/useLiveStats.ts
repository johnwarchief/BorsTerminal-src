// features/market/api/useLiveStats.ts — خوردِ «وضعیت بازار»: ضربانِ خودِ بک‌اند
//
// چرا یکِ درخواستِ جدا با وجودِ Market Feed مشترک: `/api/market` به کاربر *تابلو*
// می‌دهد (ردیف‌ها)، ولی هیچ‌وقت نمی‌گوید حلقۀِ تیکِ خودِ سرور کجاست — خنک‌شدنِ ۴۲۹،
// حالتِ گوش‌دادن، شمارۀِ نشست، یا این‌که اصلاً امروز روزِ معاملاتی است. این‌ها
// داوریِ «چرا عدد عوض نشد» است و فقط سرور می‌داند؛ از همین‌جا خوانده می‌شود تا
// UI حدسِ ساعتِ خودش را نزند. پاسخِ کوچکِ JSON است (نه ۵ مگابایت) و فقط هر
// ۱۵ ثانیه یک‌بار.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';

export type LiveStatsWindow = {
  market_open?: boolean | null;
  sync_window?: boolean | null;
  tick_writes?: boolean | null;
  market_open_error?: string;
  sync_window_error?: string;
  tick_writes_error?: string;
};

export type LiveStatsTick = {
  cooldown_remaining_s?: number | null;
  cooldown_level?: number | null;
  listening?: boolean | null;
  since_change_s?: number | null;
  since_probe_s?: number | null;
  quiet_limit_s?: number | null;
  listen_poll_s?: number | null;
  after_hours?: boolean | null;
  requests_open?: boolean | null;
  cycle?: { ok?: number; empty?: number; slow_over_10s?: number; last_s?: number; max_s?: number };
  timeout_s?: number[] | null;
  error?: string;
};

export type LiveStatsUniverse = {
  at?: number | null;
  revision?: number | null;
  market_open?: boolean | null;
  observed_rows?: number | null;
  counts?: Record<string, number>;
  error?: string;
};

export type LiveStats = {
  status: string;
  data?: {
    cycles?: number;
    rows_seen?: number;
    rows_written?: number;
    nochange_cycles?: number;
    last_cycle_s?: number;
    last_changed?: number;
    started_at?: number;
    revision?: number;
    sync_count?: number;
    session_day?: number;
    symbols?: number;
    last_cycle_at?: string | null;
    board_cache?: boolean;
    board_rows?: number;
    delta_mirror_rows?: number;
    window?: LiveStatsWindow;
    tick?: LiveStatsTick;
    universe?: LiveStatsUniverse;
  };
};

export const LIVE_STATS_KEY = ['live-stats'] as const;

export function useLiveStats(enabled = true) {
  return useQuery<LiveStats, Error>({
    queryKey: LIVE_STATS_KEY,
    queryFn: ({ signal }) => http<LiveStats>('/api/live-stats', { signal }),
    // پنلِ وضعیت نباید بازار را بمباران کند: ۱۵ ثانیه، و بیرونِ نشست آرام‌تر.
    refetchInterval: enabled ? 15_000 : false,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
    retry: 1,
    enabled,
  });
}
