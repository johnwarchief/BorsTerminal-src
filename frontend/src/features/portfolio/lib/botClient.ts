// features/portfolio/lib/botClient.ts — خوانندۀ /api/bot/*
//
// چرا جدا ازِ orderClient: آن فایل قراردادِ **سفارشِ دستی** است (پیش‌نمایش ←
// تأیید ← ارسال). این فایل قراردادِ **ربات** است: پیکربندی، اجرایِ دستیِ یکِ
// نشست، وضعیت، تاریخچه، توقف/ادامه. هر دو ازِ یکِ `http` می‌گذرند (fetchِ
// مستقیم درِ این مخزن ممنوع است) و هیچ‌کدام عددِ ساختگی نمی‌سازد: نبودِ پاسخ
// ⇒ undefined، نه صفر.
//
// قراردادِ وضعیت‌ها ازِ خودِ `api/bot.py` کپی شده، نه ازِ حدس:
//  status: ok | refused | halted | no_data | error
//  kill:   ARMED | HALTED | TRIPPED
import { useQuery, type QueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';

const CapabilitiesSchema = z.object({
  place: z.boolean().optional(),
  list_orders: z.boolean().optional(),
  order_state: z.boolean().optional(),
  queue_position: z.boolean().optional(),
  cancel: z.boolean().optional(),
  best_bid_ask: z.boolean().optional(),
  balances: z.boolean().optional(),
}).nullish();

const LiveGatesSchema = z.object({
  env_live: z.boolean().default(false),
  adapter: z.string().default('mock'),
  session: z.string().default('none'),
  capabilities: CapabilitiesSchema,
  live_capable: z.boolean().default(false),
  dry_run: z.boolean().default(true),
  all_open: z.boolean().default(false),
  error: z.string().nullish(),
}).nullish();

export const BotConfigSchema = z.object({
  enabled: z.boolean().default(false),
  mode: z.enum(['paper', 'live']).default('paper'),
  preset: z.string().default('trend'),
  chain: z.array(z.string()).default([]),
  fund_mode: z.string().default('standard'),
  logic: z.string().default('and'),
  sizing_fraction: z.number().default(0.05),
  max_orders: z.number().default(1),
  max_order_value: z.number().nullish(),
  max_symbol_exposure: z.number().nullish(),
  max_total_exposure: z.number().nullish(),
  max_daily_loss: z.number().nullish(),
  max_stale_sessions: z.number().default(1),
  start_cash: z.number().default(100_000_000),
  commission_bps: z.number().default(30),
  slippage_bps: z.number().default(10),
  max_volume_share: z.number().default(0.02),
  history_days: z.number().default(40),
  note: z.string().nullish(),
}).nullish();
export type BotConfig = z.infer<typeof BotConfigSchema>;

export const BotDecisionSchema = z.object({
  date: z.string(),
  signals: z.number(),
  dispatched: z.number(),
  rejected: z.number(),
  equity: z.number().nullish(),
  halt_state: z.string(),
  notes: z.array(z.string()).default([]),
});
export type BotDecision = z.infer<typeof BotDecisionSchema>;

export const BotRunSchema = z.object({
  at: z.string(),
  session: z.string(),
  bars: z.number(),
  symbols: z.number(),
  mode: z.string(),
  decisions: z.array(BotDecisionSchema).default([]),
  ms: z.number(),
});
export type BotRun = z.infer<typeof BotRunSchema>;

export const BotStatusSchema = z.object({
  status: z.string(),
  config: BotConfigSchema,
  kill: z.enum(['ARMED', 'HALTED', 'TRIPPED']).default('ARMED'),
  halted: z.boolean().default(false),
  live_gates: LiveGatesSchema,
  confirm_phrase: z.string().default(''),
  account: z.object({
    equity: z.number().nullish(),
    cash: z.number().nullish(),
    positions: z.number().default(0),
    realized_total: z.number().nullish(),
  }).nullish(),
  last_runs: z.array(BotRunSchema).default([]),
  auto_run: z.boolean().default(false),
  note: z.string().default(''),
});
export type BotStatus = z.infer<typeof BotStatusSchema>;

export const BotHistorySchema = z.object({
  status: z.string(),
  runs: z.array(BotRunSchema).default([]),
  events: z.array(z.object({
    kind: z.string().nullish(),
    status: z.string().nullish(),
    symbol: z.string().nullish(),
    detail: z.string().nullish(),
    at: z.string().nullish(),
    at_epoch: z.number().nullish(),
  }).passthrough()).default([]),
  account: z.record(z.string(), z.unknown()).default({}),
});
export type BotHistory = z.infer<typeof BotHistorySchema>;

export type RunVerdict = 'ok' | 'refused' | 'halted' | 'no_data' | 'error' | 'unknown';

/**
 * حکمِ یکِ اجرا — چهار حالتِ متمایز، نه «موفق/ناموفق».
 * `no_data` یعنی ربات درست کار کرد ولی داده نبود؛ `unknown` یعنی پاسخ را
 * نفهمیدیم (شبکه قطع) و هیچ ادعایی دربارهٔ نتیجه نمی‌کنیم.
 */
export function verdictOf(res: Record<string, unknown> | null | undefined): RunVerdict {
  const s = String(res?.status ?? '');
  if (s === 'ok' || s === 'refused' || s === 'halted' || s === 'no_data' || s === 'error') {
    return s as RunVerdict;
  }
  return 'unknown';
}

export function useBotStatus(enabled = true) {
  return useQuery({
    queryKey: ['bot-status'],
    queryFn: ({ signal }) => http<BotStatus>('/api/bot/status', { schema: BotStatusSchema, signal }),
    enabled,
    staleTime: 10_000,
    // ربات خودکار اجرا نمی‌شود؛ این polling فقط وضعیتِ دفتر را تازه نگه می‌دارد
    refetchInterval: enabled ? sessionPollMs(30_000) : false,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useBotHistory(enabled = true) {
  return useQuery({
    queryKey: ['bot-history'],
    queryFn: ({ signal }) => http<BotHistory>('/api/bot/history', { schema: BotHistorySchema, signal }),
    enabled,
    staleTime: 5_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function invalidateBot(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ['bot-status'] });
  qc.invalidateQueries({ queryKey: ['bot-history'] });
}

/**
 * هر نوشتنی درِ مسیرِ ربات ازِ همین پنج در می‌گذرد.
 * `retries: 0` مثلِ orderApi: پاسخ‌نرسیدن به معنی «دوباره بفرست» نیست —
 * برایِ /run یعنی اجرایِ دوبارهٔ همان نشست، و برایِ halt/resume یعنی
 * نوشتنِ دوباره رویِ قفلِ پایدار.
 */
const NO_RETRY = { retries: 0 } as const;

export const botApi = {
  putConfig: (body: Record<string, unknown>) =>
    http<Record<string, unknown>>('/api/bot/config', { method: 'PUT', body, ...NO_RETRY }),
  run: () => http<Record<string, unknown>>('/api/bot/run', { method: 'POST', body: {}, ...NO_RETRY }),
  halt: (reason: string) =>
    http<Record<string, unknown>>('/api/bot/halt', { method: 'POST', body: { reason }, ...NO_RETRY }),
  resume: () => http<Record<string, unknown>>('/api/bot/resume', { method: 'POST', body: {}, ...NO_RETRY }),
  resetAccount: () =>
    http<Record<string, unknown>>('/api/bot/account/reset', { method: 'POST', body: {}, ...NO_RETRY }),
};

export const KILL_LABEL: Record<string, string> = {
  ARMED: 'آماده',
  HALTED: 'متوقف‌شده با دستورِ شما',
  TRIPPED: 'قفلِ خودکارِ ریسک',
};

export const VERDICT_LABEL: Record<RunVerdict, string> = {
  ok: 'نشست اجرا شد',
  refused: 'اجازه داده نشد',
  halted: 'متوقف است',
  no_data: 'داده‌ای نبود',
  error: 'خطا',
  unknown: 'نامعلوم',
};
