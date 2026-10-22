// features/portfolio/lib/orderClient.ts -- قراردادِ پنلِ معامله با موتورِ اجرای سرخطی
//
// چرا این فایل هست: هیچ عددی درِ رابطِ کاربر از خودِ رابط نمی‌آید. هر چیزی که
// این لایه می‌گوید از پاسخِ `api/execution.py` خوانده می‌شود -- adapter،
// dry_run، live_enabled، session، capabilities و `wire_hypothesis` (نتیجۀِ
// مأموریتِ ۱۴۰۵-۰۷-۲۴: سیمِ EasyTrader درِ کد پیاده شده ولی هیچ ثابتش علیه
// کارگزاری تأیید نشده، پس رابط هم نباید آن را «تأییدشده» نشان دهد).
//
// قاعدۀِ «غیرفعال»: یک کنترل وقتی روشن می‌شود که capabilityِ همان کار درِ
// پاسخِ بک‌اند true باشد. نبودِ پاسخ ⇒ غیرفعال، نه «صفر مجاز»؛ و بی‌نشست،
// «Connected» نمایش داده نمی‌شود چون `_SERVICE` همان را دروغ می‌دانَد.
//
// token هیچ‌جا درِ این لایه نمی‌نشیند: فقط `POST /api/execution/session` و
// پاسخِ آن «هست/نیست» را برمی‌گرداند. هیچ لاگ/کوئری‑کی/متنِ دکمه‌ای او را
// نمی‌بینَد.
import { useQuery, type QueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { http, HttpError } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';

const bool = z.boolean().nullish();
const num = z.number().nullish();
const txt = z.string().nullish();

export const BrokerCapabilitiesSchema = z.object({
  place: bool,
  list_orders: bool,
  order_state: bool,
  queue_position: bool,
  cancel: bool,
  best_bid_ask: bool,
  balances: bool,
});
export type BrokerCapabilities = z.infer<typeof BrokerCapabilitiesSchema>;

export const SessionStatusSchema = z.object({
  state: txt,
  account_label: txt,
  checked_at: txt,
  // مأموریتِ 2026-10-18: «هست» و «اثبات‌شده» دو چیزند. `origin` می‌گوید آداپتورِ
  // جاری کدام است (mock هیچ‌وقت به کارگزاری وصل نمی‌شود) و `proven` فقط وقتی true
  // است که یکِ پرسشِ *واقعاً* پاسخِ ۲xx داده باشد. بی‌این دو، رابط «متصل» را ازِ
  // حضورِ رشته‌ای درِ حافظه می‌ساخت.
  origin: txt,
  proven: bool,
  verified_by: z.record(z.string(), z.unknown()).nullish(),
});
export type SessionStatusView = z.infer<typeof SessionStatusSchema>;

/** شش مقدارِ `execution_contract.SessionState` -- یک واژگان، درِ همان لایۀ canonical */
export const SESSION_STATES = [
  'disconnected', 'connected', 'expired', 'auth_failed', 'error', 'unknown',
] as const;
export type SessionStateValue = (typeof SESSION_STATES)[number];

export const SESSION_LABEL: Record<SessionStateValue, string> = {
  disconnected: 'دسترسی به حساب بسته است',
  connected: 'دسترسی به حساب تأیید شده است',
  expired: 'دسترسی به حساب منقضی شده است',
  auth_failed: 'اجازۀ دسترسی داده نشد',
  error: 'پاسخِ کارگزاری نامفهوم بود',
  unknown: 'وضعیت دسترسی روشن نیست',
};

/** `traffic_mode` ازِ `execution_connect.status_dict` — سه راهِ جدا، نه یکِ بُولین */
export const TRAFFIC_MODES = ['writes', 'read_only', 'blocked'] as const;
export type TrafficMode = (typeof TRAFFIC_MODES)[number];

/** یکِ واژه برایِ یکِ حالت، درِ دو جایِ صفحه (هدر و نوارِ وضعیت): «dry_run» یعنی
 *  سفارش ارسال نمی‌شود — نه اینکه هیچ درخواستی بیرون نمی‌رود. */
export const DRY_RUN_LABEL = 'بی‌ارسالِ سفارش (dry_run)';

export const TRAFFIC_LABEL: Record<TrafficMode, { text: string; tone: 'ok' | 'warn' | 'idle' }> = {
  writes: { text: 'خواندن و ارسال آزاد', tone: 'warn' },
  read_only: { text: 'فقط‌خواندنی: خواندن بله، ارسال نه', tone: 'ok' },
  blocked: { text: 'هیچ ترافیکی مجاز نیست', tone: 'idle' },
};

/** Strategyهای چندروشی: متریک‌ها فقط از نمونهٔ واقعیِ همان پروسه می‌آیند؛
 *  p95/p99 با نمونهٔ کم null است، نه صفر. */
export type StrategyPhaseMetrics = {
  count: number; ok: number; failed: number;
  p50: number | null; p95: number | null; p99: number | null;
  last_ms: number | null; last_error: string; last_at: number | null; thin: boolean;
};
export type StrategyRowView = {
  id: string; label: string; kind: string; description: string;
  requires_browser: boolean; available: boolean; configured: boolean;
  unavailable_reason: string; live_ready: boolean;
  settings: { strategy: string; enabled: boolean; mode: string; priority: number;
    options: Record<string, unknown>; updated_at: number };
  metrics: Record<string, StrategyPhaseMetrics>;
  outcomes: Record<string, number>;
  last_result: Record<string, unknown> | null;
};
export type StrategySelectionRow = {
  strategy: string; count: number;
  p50: number | null; p95: number | null; p99: number | null;
  accepted: number; unknown: number;
  usable_dry: boolean; usable_live: boolean;
  reason_dry: string; reason_live: string;
};
export type StrategiesView = {
  status: string; strategies: StrategyRowView[]; selection: StrategySelectionRow[];
  rate_limiter: Record<string, unknown>; orders: Record<string, unknown>[];
  live_allowed: boolean; dry_run: boolean; adapter: string;
  recovered_intents?: Record<string, number>;
};

/** `status` ازِ `/api/execution/portfolio` — «بی‌منبع» و «خالی» دو چیزند */
export const PORTFOLIO_STATES = ['success', 'cached', 'no_source', 'unverified_session',
  'blocked', 'error'] as const;
export type PortfolioState = (typeof PORTFOLIO_STATES)[number];

export const PORTFOLIO_LABEL: Record<PortfolioState, string> = {
  success: 'ازِ کارگزاری خوانده شد',
  cached: 'نسخۀِ انبارِ همین نشست',
  no_source: 'منبعِ مستندِ خواندنی برایِ پرتفوی نداریم',
  unverified_session: 'دسترسی تأیید نشده — پرسشی زده نشد',
  blocked: 'ترافیک مجاز نیست',
  error: 'پرسش انجام شد و پاسخِ معنادار نداد',
};

export const ExecutionStatusSchema = z.object({
  status: z.string(),
  adapter: txt,
  dry_run: bool,
  experimental: bool,
  live_enabled: bool,
  live: bool,
  live_requested: bool,
  nothing_will_leave_the_machine: bool,
  wire_hypothesis: bool,
  blocked_on: z.array(z.string()).nullish(),
  confirm_gate: z.record(z.string(), z.unknown()).nullish(),
  capabilities: BrokerCapabilitiesSchema.nullish(),
  session: SessionStatusSchema.nullish(),
  limits: z.unknown().nullish(),
  ledger_size: num,
  kill_switch: txt,
  halted: bool,
  kill_reason: txt,
  durable_events: num,
  recovered_after_restart: num,
  clock_source: txt,
  clock_limit: txt,
  scheduled_pending: num,
  // ── سه چیزی که پنل‌هایِ تبِّ «سرخطی» مستقیم می‌خوانند (§۴ و §۵ مأموریت) ──
  // `mode_matrix` منشأش کدِ پایتون است، نه ادعایِ رابط؛ `queue_rank` صریح
  // می‌گوید جایِ صف ادعا نشده؛ و `confirm_epoch` به رابط می‌گوید تأییدِ رویِ
  // صفحه به دورۀِ جاری تعلق دارد یا کهنه شده است.
  confirm_epoch: num,
  mode_matrix: z.record(z.string(), z.object({
    implemented: bool, active: bool, door: txt, proves: txt,
    can_reach_broker: bool,
  }).nullish()).nullish(),
  queue_rank: z.object({
    claims_first: bool, official_rank_source: z.string().nullish(), why: txt,
  }).nullish(),
  wire_provenance: z.unknown().nullish(),
  // ── سه گیتِ جدا (مأموریتِ 2026-10-18) ──
  // `live_enabled` = «ارسالِ سفارش آزاد است»، `read_only` = «این برنامه فقط می‌خواند»،
  // `traffic_allowed` = «ترافیک ازِ این پروسه بیرون می‌رود (حتی GET)». پیش ازِ این
  // تنها اولی بود، پس «تأییدِ نشست» هم ناگزیر به گیتِ نوشتن گره می‌خورد و هرگز
  // ممکن نمی‌شد. `connection_config` هم «ذخیره شد» را از «اعمال شد» جدا می‌گوید.
  read_only: bool,
  session_live: bool,
  traffic_allowed: bool,
  connection_config: z.record(z.string(), z.unknown()).nullish(),
});
export type ExecutionStatus = z.infer<typeof ExecutionStatusSchema>;

/** رکوردِ اجرا -- همان `ExecutionRecord`ِ سرویس، با واژگانِ خودش */
export const ExecutionRecordSchema = z.object({
  execution_id: z.string(),
  broker: txt,
  symbol: txt,
  isin: txt,
  side: txt,
  price: num,
  quantity: num,
  mode: txt,
  status: txt,
  order_state: txt,
  broker_order_id: txt,
  filled_quantity: num,
  queue_position: num,
  // چهار زمانِ جداگانهٔ مسیر (بندِ C مأموریت) — همه ازِ خودِ رکورد، هیچ‌کدام
  // محاسبهٔ رابط نیست. `null` یعنی آن مرحله رخ نداده، نه صفر.
  scheduled_at: num,
  actual_send_at: num,
  clock_offset_ms: num,
  drift_us: num,
  volume_ahead: num,
  queue_as_of: txt,
  error_code: txt,
  error_detail: txt,
  attempts: num,
  rtt_ms: num,
  response_at: num,
  actual_send_wall_ms: num,
  events: z.array(z.string()).nullish(),
});
export type ExecutionRecord = z.infer<typeof ExecutionRecordSchema>;

export const LedgerSchema = z.object({
  status: z.string(),
  adapter: txt,
  dry_run: bool,
  live: bool,
  kill_switch: txt,
  open_ids: z.array(z.string()).nullish(),
  scheduled: z.array(z.record(z.string(), z.unknown())).nullish(),
  records: z.array(ExecutionRecordSchema).nullish(),
});
export type LedgerView = z.infer<typeof LedgerSchema>;

/** حالت‌های یک سفارش -- واژگانِ `execution_contract`، نه اختراعِ رابط */
export const ORDER_PHASES = [
  'idle', 'draft', 'preflight', 'scheduled', 'sending', 'submitted',
  'accepted', 'partial', 'filled', 'rejected', 'cancelled', 'unknown', 'errored',
] as const;
export type OrderPhase = (typeof ORDER_PHASES)[number];

export const PHASE_LABEL: Record<OrderPhase, string> = {
  idle: 'بی‌سفارش',
  draft: 'پیش‌نویس',
  preflight: 'پیش‌فرود',
  scheduled: 'زمان‌بندی‌شده',
  sending: 'در حالِ ارسال',
  submitted: 'ارسال‌شده',
  accepted: 'تأییدشده',
  partial: 'بعضی پر شد',
  filled: 'کامل پر شد',
  rejected: 'ردشده',
  cancelled: 'لغوشده',
  unknown: 'نتیجه نامعلوم',
  errored: 'خطا',
};

/**
 * رکوردِ سرویس ← فازِ رابط. دو واژگانِ جداست (`ExecutionStatus` برایِ «ما چه
 * کردیم»، `OrderState` برایِ «سرور با سفارش چه می‌کند») و رابط هر دو را می‌خواند:
 * نامعلوم بودنِ نتیجه *هرگز* «ردشده» نمی‌شود، چون آن دو درِ رفتارِ بعدی فرق
 * دارند -- ردشده قابلِ تکرارِ آگاهانه است، نامعلوم فقط قابلِ reconcile.
 */
export function phaseOf(rec: ExecutionRecord | null | undefined): OrderPhase {
  if (!rec) return 'idle';
  const st = rec.status ?? '';
  const os = rec.order_state ?? 'unknown';
  if (st === 'unknown_result' || os === 'unknown') {
    return st === 'failed' ? 'errored' : 'unknown';
  }
  if (os === 'rejected') return 'rejected';
  if (os === 'cancelled') return 'cancelled';
  if (os === 'filled') return 'filled';
  if (os === 'partial') return 'partial';
  switch (st) {
    case 'draft': return 'draft';
    case 'validated': return 'preflight';
    case 'prepared': return 'preflight';
    case 'scheduled': return 'scheduled';
    case 'dispatched': return 'submitted';
    case 'acknowledged': return 'accepted';
    case 'reconciled': return os === 'open' || os === 'pending' ? 'submitted' : 'accepted';
    case 'failed': return 'rejected';
    default: return 'errored';
  }
}

export type TradingGate = {
  canTrade: boolean;
  /** چرا نمی‌شود -- از پاسخِ سرویس، نه از متنِ ثابتِ رابط */
  reason: string;
  /** یادآوریِ همیشۀ «این بدل است، نه صرافی» */
  dryRun: boolean;
  caps: BrokerCapabilities | null;
  status: ExecutionStatus | null;
  /** درِ UI: آیا اصلاً سرویسِ اجرا در این نسخه هست؟ */
  endpointPresent: boolean;
  /** وضعیتِ نشست -- برایِ «Connectedِ ظاهری» نبودن */
  sessionState: SessionStateValue;
  /** سیمِ پروتکل هنوز فرضیه است؟ (پیش‌نمایشِ بدنه «تأییدشده» برچسب نمی‌گیرد) */
  wireHypothesis: boolean;
  /** توقفِ اضطراری بسته است؟ (رنگِ دکمه از اینجا می‌آید، نه از حدس) */
  halted: boolean;
};

function sessionOf(status: ExecutionStatus | null): SessionStateValue {
  const s = status?.session?.state;
  return (SESSION_STATES as readonly string[]).includes(s ?? '')
    ? (s as SessionStateValue)
    : 'unknown';
}

/**
 * داوریِ درِ رابط از capabilitiesِ اعلام‌شده؛ نبودِ پاسخ ⇒ غیرفعال، نه «صفرِ مجاز».
 * سه حالت جداست چون متنِ «سرویس نیست» و «هنوز نرسیده» دو چیزند:
 *   ok      پاسخِ معتبر آمده
 *   loading هنوز اولین پاسخ نیامده — درِ این حالت هم دکمه‌ها بسته‌اند
 *   absent  سرویس پاسخ نداد (۴۰۴/خطا): درِ این نسخه درِ اجرا وجود ندارد
 */
export function deriveGate(status: ExecutionStatus | null | undefined, source: GateSource = 'ok'): TradingGate {
  if (source === 'loading') {
    return {
      canTrade: false,
      reason: 'در حالِ خواندنِ وضعیتِ سرویسِ اجرا — تا نیامدنِ پاسخ هیچ سفارشی باز نمی‌شود',
      dryRun: true,
      caps: null,
      status: null,
      endpointPresent: false,
      sessionState: 'unknown',
      wireHypothesis: false,
      halted: false,
    };
  }
  if (source === 'absent' || !status) {
    return {
      canTrade: false,
      reason: 'سرویسِ اجرای سفارش در این نسخه پاسخ نمی‌دهد — اتصالِ کارگزاری وجود ندارد',
      dryRun: true,
      caps: null,
      status: null,
      endpointPresent: false,
      sessionState: 'unknown',
      wireHypothesis: false,
      halted: false,
    };
  }
  const caps = status.capabilities ?? null;
  const sessionState = sessionOf(status);
  const halted = status.halted === true;
  const base = { caps, status, endpointPresent: true, sessionState, halted,
    wireHypothesis: status.wire_hypothesis === true };
  if (halted) {
    return { ...base, canTrade: false, dryRun: status.dry_run !== false,
      reason: `توقفِ اضطراری باز است${status.kill_reason ? ` (${status.kill_reason})` : ''} — «ادامهٔ دستوری» لازم است` };
  }
  if (status.live_enabled !== true) {
    const blocked = (status.blocked_on ?? []).join(' · ');
    const sess = sessionState !== 'connected' ? ` — ${SESSION_LABEL[sessionState]}` : '';
    // حالتِ فقط‌خواندنی «اتصالِ فعال نیست» نیست: خواندن وصل است و نشست هم می‌تواند
    // ثابت‌شده باشد؛ چیزی که بسته است درِ *ارسال* است. متنِ «فعال نیست» کاربر را
    // به سراغِ تنظیمِ اتصال می‌فرستد وقتی تنظیم درست بوده.
    if (status.read_only === true && status.traffic_allowed === true) {
      const proof = status.session?.proven === true ? 'دسترسی تأیید شده' : 'دسترسی تأیید نشده';
      return {
        ...base, canTrade: false, dryRun: true,
        reason: `حالتِ فقط‌خواندنی: خواندن بله، ارسال نه — ${proof}. `
          + 'برایِ ارسال، BORS_EXECUTION_LIVE=1 لازم است (گیتِ جدا، درِ این برنامه روشن نمی‌شود)',
      };
    }
    return {
      ...base,
      canTrade: false,
      dryRun: status.dry_run !== false,
      reason: blocked
        ? `اتصالِ کارگزاری فعال نیست${sess} — در انتظارِ: ${blocked}`
        : `اتصالِ کارگزاری فعال نیست${sess} (live_enabled: false)`,
    };
  }
  if (caps?.place !== true) {
    return { ...base, canTrade: false, dryRun: status.dry_run !== false,
      reason: 'سازندۀ سفارش (place) در این adapter فعال اعلام نشده است' };
  }
  if (status.dry_run === true) {
    return { ...base, canTrade: false, dryRun: true,
      reason: 'حالتِ بدل (dry_run) فعال است — هیچ سفارشی به کارگزاری نمی‌رود' };
  }
  // «توکن هست» مجوزِ ارسال نیست. بک‌اند هم POST را باِ همین قفل می‌بندد
  // (`_verified_token is not _token`)؛ رابط نباید دروازه‌ای بازتر از خودِ سرویس
  // نشان دهد، وگرنه کاربر «آمادهٔ ارسال» می‌بیند و ارسال بی‌پاسخ می‌ماند.
  if (sessionState !== 'connected') {
    return { ...base, canTrade: false, dryRun: false,
      reason: SESSION_LABEL[sessionState]
        + ' — «بررسی وضعیت» لازم است؛ حضور دسترسی به‌تنهایی نشانهٔ تأیید نیست' };
  }
  return { ...base, canTrade: true, dryRun: false, reason: '' };
}

/** وضعیتِ اتصالِ اجرا یک‌بار در هر نشستِ بازار کافی است؛ ثابت‌تر از آن نیست */
export function useBrokerConnect() {
  return useQuery({
    queryKey: ['execution-connect'],
    queryFn: ({ signal }) => connectApi.status(signal),
    refetchInterval: 60_000,
  });
}


export function useStrategies(enabled = true) {
  return useQuery({
    queryKey: ['execution-strategies'],
    queryFn: () => orderApi.strategies(),
    enabled,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useExecutionStatus() {
  const q = useQuery({
    queryKey: ['execution-status'],
    queryFn: ({ signal }) =>
      http<ExecutionStatus>('/api/execution/status', { schema: ExecutionStatusSchema, signal }),
    staleTime: 120_000,
    gcTime: 10 * 60_000,
    refetchInterval: () => sessionPollMs(120_000),
    refetchOnWindowFocus: false,
    // نبودِ در (نسخۀ بی‌Sarkhati / بیلدِ کهنه) خطایِ صفحه نیست: «غیرفعال» است.
    retry: (count, error) => count < 2 && !(error instanceof HttpError && error.status === 404),
  });
  const source: GateSource = q.isError ? 'absent' : (!q.data && q.isPending ? 'loading' : 'ok');
  return { ...q, gate: deriveGate(q.data ?? null, source) };
}

/** دفترِ اجرا + زمان‌بندی‌هایِ باز. پس ازِ هر اقدامِ تازه invalidate می‌شود. */
export function useExecutionLedger(enabled = true) {
  return useQuery({
    queryKey: ['execution-ledger'],
    queryFn: ({ signal }) =>
      http<LedgerView>('/api/execution/ledger', { schema: LedgerSchema, signal }),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? sessionPollMs(20_000) : false,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function invalidateExecution(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ['execution-status'] });
  qc.invalidateQueries({ queryKey: ['execution-ledger'] });
  qc.invalidateQueries({ queryKey: ['execution-strategies'] });
  qc.invalidateQueries({ queryKey: ['execution-durable-schedules'] });
}

export function useExecutionStrategies(enabled: boolean) {
  return useQuery({
    queryKey: ['execution-strategies'],
    queryFn: ({ signal }) =>
      http<StrategiesView>('/api/execution/strategies', { signal }),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? sessionPollMs(15_000) : false,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/**
 * هر نوشتنی درِ مسیرِ اجرا از همین چهار در می‌گذرد — بی‌fetchِ موازی درِ UI.
 *
 * `retries: 0` رویِ همهٔ نوشتن‌ها عمدی و امنیتی است: `http()` پیش‌فرض دو بار
 * با backoff تلاش می‌کند و رویِ «خطایِ شبکه» هم این کار را می‌کند. برایِ GET
 * درست است؛ برایِ POSTِ ارسالِ سفارش یعنی «پاسخ نرسید ⇒ دوباره بفرست»، و
 * پاسخ‌نرسیدن بعد ازِ رسیدنِ درخواست = سفارشِ تکراری درِ کارگزاری. مأموریتِ
 * ۱۴۰-۰۷-۲۴ (§۴-ب) صریحاً همین را ممنوع کرده؛ ابهام را حالتِ `unknown` درِ
 * همان دروازه حل می‌کند، نه retry.
 */
const NO_RETRY = { retries: 0 } as const;

export const orderApi = {
  strategies: () => http<StrategiesView>('/api/execution/strategies'),
  strategySettings: (id: string, body: Record<string, unknown>) =>
    http<Record<string, unknown>>(
      `/api/execution/strategies/${encodeURIComponent(id)}/settings`,
      { method: 'POST', body, ...NO_RETRY }),
  strategyPrepare: (body: unknown) =>
    http<Record<string, unknown>>('/api/execution/strategies/prepare',
      { method: 'POST', body, ...NO_RETRY }),
  strategyTrigger: (body: Record<string, unknown>) =>
    http<Record<string, unknown>>('/api/execution/strategies/trigger',
      { method: 'POST', body, ...NO_RETRY }),
  /** مسیرِ زندهٔ Strategy — فقط با env، نشست و عبارتِ تأیید. رابط فعلاً از آن
   *  استفاده نمی‌کند؛ تا مجوزِ صریح، فقط `/trigger`ِ dry-run صدا زده می‌شود. */
  strategyDispatch: (body: Record<string, unknown>) =>
    http<Record<string, unknown>>('/api/execution/strategies/dispatch',
      { method: 'POST', body, ...NO_RETRY }),
  strategyAbort: (id: string) =>
    http<Record<string, unknown>>('/api/execution/strategies/abort',
      { method: 'POST', body: { prepared_id: id }, ...NO_RETRY }),
  strategyIntent: (key: string) =>
    http<Record<string, unknown>>(
      `/api/execution/strategies/intents/${encodeURIComponent(key)}`),
  strategyAbortIntent: (key: string) =>
    http<Record<string, unknown>>(
      `/api/execution/strategies/intents/${encodeURIComponent(key)}/abort`,
      { method: 'POST', ...NO_RETRY }),
  strategyReconcile: (id: string) =>
    http<Record<string, unknown>>('/api/execution/strategies/reconcile',
      { method: 'POST', body: { prepared_id: id }, ...NO_RETRY }),
  strategyOrder: (id: string) =>
    http<Record<string, unknown>>(
      `/api/execution/strategies/order/${encodeURIComponent(id)}`),
  strategyProbe: (id: string) =>
    http<Record<string, unknown>>(
      `/api/execution/strategies/${encodeURIComponent(id)}/probe`,
      { method: 'POST', ...NO_RETRY }),
  strategyPreflightAll: (strategies?: string[]) =>
    http<Record<string, unknown>>('/api/execution/strategies/preflight',
      { method: 'POST', body: strategies ? { strategies } : {}, ...NO_RETRY }),
  preflight: (body: unknown) => http<Record<string, unknown>>('/api/execution/preflight',
    { method: 'POST', body, ...NO_RETRY }),
  prepare: (body: unknown) => http<Record<string, unknown>>('/api/execution/prepare',
    { method: 'POST', body, ...NO_RETRY }),
  dispatch: (body: unknown) => http<Record<string, unknown>>('/api/execution/dispatch',
    { method: 'POST', body, ...NO_RETRY }),
  reconcile: (id: string) => http<Record<string, unknown>>(`/api/execution/reconcile/${id}`,
    { method: 'POST', ...NO_RETRY }),
  refresh: (id: string) => http<Record<string, unknown>>(`/api/execution/refresh/${id}`,
    { method: 'POST', ...NO_RETRY }),
  queue: (id: string) => http<Record<string, unknown>>(`/api/execution/queue/${id}`),
  audit: (id: string) => http<Record<string, unknown>>(`/api/execution/audit/${encodeURIComponent(id)}`),
  events: (filters: EventFilters, signal?: AbortSignal) =>
    http<EventsView>(`/api/execution/events${eventQuery(filters)}`,
      { schema: EventsSchema, signal }),
  halt: (reason: string) => http<Record<string, unknown>>('/api/execution/halt',
    { method: 'POST', body: { reason }, ...NO_RETRY }),
  resume: (reason: string, confirm = false) => http<Record<string, unknown>>(
    '/api/execution/resume', { method: 'POST', body: { reason, confirm }, ...NO_RETRY }),
  probe: () => http<Record<string, unknown>>('/api/execution/probe', { method: 'POST', ...NO_RETRY }),
  /**
   * لغوِ سفارشی که به کارگزاری رفته. `confirm: true` درِ بک‌اند الزامی است —
   * «دکمه زده شد» مجوزِ عملِ حساس نیست (همان قاعدۀ `/resume`). بی‌این، درِ
   * بک‌اند هیچ فراخوانی به آداپتور نمی‌فرستد و همان را برمی‌گرداند.
   */
  cancel: (id: string, reason = 'لغو از رابط') => http<Record<string, unknown>>(
    `/api/execution/cancel/${encodeURIComponent(id)}`,
    { method: 'POST', body: { confirm: true, reason }, ...NO_RETRY }),
  /** لغوِ زمان‌بندیِ *نجوشیده* — باِ لغوِ سفارشِ فرستاده‌شده دو کارِ جدا‌اند */
  cancelSchedule: (id: string) => http<Record<string, unknown>>(
    `/api/execution/schedule/${encodeURIComponent(id)}`, { method: 'DELETE', ...NO_RETRY }),
  schedule: (id: string) => http<Record<string, unknown>>(
    `/api/execution/schedule/${encodeURIComponent(id)}`),
  /** نشانی را فقط درِ حافظۀِ پروسۀِ بک‌اند می‌گذارد؛ پاسخ هیچ مقدارِ باز نمی‌گرداند */
  putSession: (token: string) => http<Record<string, unknown>>('/api/execution/session',
    { method: 'POST', body: { token }, ...NO_RETRY }),
  delSession: () => http<Record<string, unknown>>('/api/execution/session',
    { method: 'DELETE', ...NO_RETRY }),
};

/** وضعیتِ صریحِ نشستِ کارگزاری — همان چهار حالتِ `execution_connect.py`.
 *  «CONNECTED» فقط از پرسشِ واقعی می‌آید؛ HTMLِ صفحۀ ورود هرگز دلیلِ اتصال نیست. */
export type ConnectState = 'CONNECTED' | 'DISCONNECTED' | 'EXPIRED' | 'UNKNOWN';

export const CONNECT_LABEL: Record<ConnectState, string> = {
  CONNECTED: 'متصل',
  DISCONNECTED: 'قطع',
  EXPIRED: 'منقضی',
  UNKNOWN: 'نامعلوم',
};

const BrowserSchema = z.object({
  open: z.boolean().nullish(),
  pid: z.number().nullish(),
  url: z.string().nullish(),
  profile_kept: z.boolean().nullish(),
  opened_seconds_ago: z.number().nullish(),
}).nullish();

const VerifySchema = z.object({
  state: z.string().nullish(),
  reason: z.string().nullish(),
  blocked_reason: z.string().nullish(),
  checked_at: z.string().nullish(),
  live: z.boolean().nullish(),
  token_present: z.boolean().nullish(),
  adapter: z.string().nullish(),
  // تازگیِ ادعا درِ بک‌اند ساخته می‌شود (`effective_verify`)؛ این چهار کلید باید
  // درِ parse زنده بمانند، وگرنه «متصلِ کهنه» درِ رابط بی‌علت خاموش می‌شود.
  age_s: z.number().nullish(),
  verify_max_age_s: z.number().nullish(),
  stale: z.boolean().nullish(),
  verified_state: z.string().nullish(),
  // «چه چیزی این اتصال را ثابت کرد» و «درِ کدام حالتیم» — هر دو ازِ بک‌اند.
  // `proof.path` می‌گوید پاسخ ازِ مسیرِ دیدہ‌شدہ آمد یا ازِ مسیرِ فرضی، پس رابط
  // می‌تواند «تأییدِ نشست (فرضِ مسیر)» را از «تأییدِ نشست» جدا بنویسد.
  proof: z.record(z.string(), z.unknown()).nullish(),
  read_only: z.boolean().nullish(),
}).nullish();

export const ConnectSchema = z.object({
  status: z.string(),
  states_supported: z.array(z.string()).nullish(),
  browser: BrowserSchema,
  allowed_hosts: z.array(z.string()).nullish(),
  login_hosts_configured: z.array(z.string()).nullish(),
  login_host_blocked_reason: z.string().nullish(),
  last_verify: VerifySchema,
  secrets_stored: z.boolean().nullish(),
  detail: z.string().nullish(),
  // `traffic_mode` سه مقدارِ جدا دارد: writes | read_only | blocked. «blocked»
  // یعنی حتی GET هم نمی‌رود — پس «پنجره را باز کردم» هرگز اتصال نیست.
  traffic_mode: z.string().nullish(),
  session_proven: z.boolean().nullish(),
  // پاسخ‌هایِ خطا (NO_LOGIN_HOST / BROWSER_REFUSED) کلیدهایِ دیگری هم دارند؛
  // بی‌catchall کلِ پاسخ درِ parse می‌افتاد و رابط «نرسید» می‌گفت.
}).catchall(z.unknown());

export type BrokerConnect = z.infer<typeof ConnectSchema>;

export const connectApi = {
  status: (signal?: AbortSignal) => http<BrokerConnect>('/api/execution/connect',
    { schema: ConnectSchema, signal }),
  openBrowser: (url?: string) => http<Record<string, unknown>>('/api/execution/connect/browser',
    { method: 'POST', body: url ? { url } : {}, ...NO_RETRY }),
  closeBrowser: () => http<Record<string, unknown>>('/api/execution/connect/browser',
    { method: 'DELETE', ...NO_RETRY }),
  verify: () => http<Record<string, unknown>>('/api/execution/connect/verify',
    { method: 'POST', ...NO_RETRY }),
  disconnect: () => http<Record<string, unknown>>('/api/execution/connect',
    { method: 'DELETE', ...NO_RETRY }),
};

/**
 * تنظیمِ اتصال — دو کلید، هیچ‌کدام محرمانه نیست (`adapter`, `read_only`).
 * نشانی/رمز ازِ این مسیر *نمی‌گذرد*: بک‌اند کلیدِ ناشناخته را رد می‌کند و درِ
 * `execution_settings` تنها همین دو را می‌پذیرد. چون آداپتور درِ `import` ساخته
 * می‌شود، `applies_on_restart` یعنی «ذخیره شد ≠ اعمال شد» — رابط همین را می‌گوید.
 */
export const BrokerConfigSchema = z.object({
  status: z.string(),
  stored: z.object({
    adapter: z.string().nullish(),
    read_only: z.boolean().nullish(),
    source: z.string().nullish(),
    updated_at: z.number().nullish(),
  }).nullish(),
  effective: z.object({
    adapter: z.string().nullish(),
    traffic_allowed: z.boolean().nullish(),
    read_only: z.boolean().nullish(),
    live_requested: z.boolean().nullish(),
    session_live: z.boolean().nullish(),
    writes_gate: z.string().nullish(),
  }).nullish(),
  applies_on_restart: z.boolean().nullish(),
  secrets_stored: z.boolean().nullish(),
  detail: z.string().nullish(),
  code: z.string().nullish(),
}).catchall(z.unknown());
export type BrokerConfig = z.infer<typeof BrokerConfigSchema>;

/** پرتفویِ فقط‌خواندنی. `rows: null` باِ `rows: []` یکی نیست — «بی‌منبع» ≠ «خالی». */
export const PortfolioSchema = z.object({
  status: z.string(),
  adapter: z.string().nullish(),
  live: z.boolean().nullish(),
  session_proven: z.boolean().nullish(),
  state: z.string().nullish(),
  as_of: z.string().nullish(),
  source: z.string().nullish(),
  rows: z.array(z.record(z.string(), z.unknown())).nullish(),
  positions: z.array(z.record(z.string(), z.unknown())).nullish(),
  fetched_at: z.string().nullish(),
  raw_count: z.number().nullish(),
  resolved_count: z.number().nullish(),
  unresolved_count: z.number().nullish(),
  duplicate_count: z.number().nullish(),
  missing_fields: z.array(z.string()).nullish(),
  unresolved: z.array(z.record(z.string(), z.unknown())).nullish(),
  buying_power: z.record(z.string(), z.unknown()).nullish(),
  cached_at: z.string().nullish(),
  error: z.string().nullish(),
  detail: z.string().nullish(),
  code: z.string().nullish(),
}).catchall(z.unknown());
export type PortfolioView = z.infer<typeof PortfolioSchema>;

export const WatchlistSchema = z.object({
  status: z.string(),
  state: z.string().nullish(),
  source: z.string().nullish(),
  fetched_at: z.string().nullish(),
  categories: z.array(z.record(z.string(), z.unknown())).nullish(),
  rows: z.array(z.record(z.string(), z.unknown())).nullish(),
  raw_count: z.number().nullish(),
  resolved_count: z.number().nullish(),
  unresolved_count: z.number().nullish(),
  duplicate_count: z.number().nullish(),
  unresolved: z.array(z.record(z.string(), z.unknown())).nullish(),
  empty: z.boolean().nullish(),
  error: z.string().nullish(),
}).catchall(z.unknown());
export type WatchlistView = z.infer<typeof WatchlistSchema>;

export const BuyingPowerSchema = z.object({
  status: z.string(),
  state: z.string().nullish(),
  source: z.string().nullish(),
  unit: z.string().nullish(),
  value: z.number().nullish(),
  raw: z.record(z.string(), z.unknown()).nullish(),
  formula: z.string().nullish(),
  fetched_at: z.string().nullish(),
  order_write_state: z.string().nullish(),
  error: z.string().nullish(),
}).catchall(z.unknown());
export type BuyingPowerView = z.infer<typeof BuyingPowerSchema>;

export const configApi = {
  get: (signal?: AbortSignal) =>
    http<BrokerConfig>('/api/execution/config', { schema: BrokerConfigSchema, signal }),
  put: (body: { adapter?: string; read_only?: boolean }) =>
    http<BrokerConfig>('/api/execution/config',
      { method: 'POST', schema: BrokerConfigSchema, body, ...NO_RETRY }),
};

export const portfolioApi = {
  get: (signal?: AbortSignal) =>
    http<PortfolioView>('/api/execution/portfolio', { schema: PortfolioSchema, signal }),
};

export const accountSourcesApi = {
  watchlist: (signal?: AbortSignal) =>
    http<WatchlistView>('/api/execution/watchlist',
      { schema: WatchlistSchema, signal }),
  buyingPower: (signal?: AbortSignal) =>
    http<BuyingPowerView>('/api/execution/buying-power',
      { schema: BuyingPowerSchema, signal }),
};

const ReadinessGateSchema = z.object({
  id: z.string(),
  label: z.string(),
  status: z.string(),
  detail: txt,
  action: txt,
  source: txt,
}).catchall(z.unknown());
export type ReadinessGate = z.infer<typeof ReadinessGateSchema>;

export const ReadinessSchema = z.object({
  status: z.string(),
  data_risk_ready: z.boolean().nullish(),
  live_ready: z.boolean().nullish(),
  live_enabled: z.boolean().nullish(),
  contract_state: txt,
  blocking_count: num,
  next_action: txt,
  gates: z.array(ReadinessGateSchema).nullish(),
  contract: z.record(z.string(), z.unknown()).nullish(),
  adapter: txt,
  symbol: txt,
  side: txt,
}).catchall(z.unknown());
export type ReadinessView = z.infer<typeof ReadinessSchema>;

export const readinessApi = {
  get: (args: { symbol?: string; side?: string; price?: number; quantity?: number } = {},
       signal?: AbortSignal) => {
    const q = new URLSearchParams();
    if (args.symbol) q.set('symbol', args.symbol);
    if (args.side) q.set('side', args.side);
    if (args.price != null) q.set('price', String(args.price));
    if (args.quantity != null) q.set('quantity', String(args.quantity));
    return http<ReadinessView>(`/api/execution/readiness?${q.toString()}`,
      { schema: ReadinessSchema, signal });
  },
};

export function useExecutionReadiness(args: {
  symbol?: string; side?: string; price?: number; quantity?: number;
} = {}, enabled = true) {
  return useQuery({
    queryKey: ['execution-readiness', args.symbol ?? '', args.side ?? '',
      args.price ?? '', args.quantity ?? ''],
    queryFn: ({ signal }) => readinessApi.get(args, signal),
    enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/** یک‌بار در هر نشست کافی است؛ تنظیمِ دیسک بی‌restart عوض نمی‌شود. */
export function useBrokerConfig() {
  return useQuery({
    queryKey: ['execution-config'],
    queryFn: ({ signal }) => configApi.get(signal),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: (count, error) => count < 2 && !(error instanceof HttpError && error.status === 404),
  });
}

/** پرتفوی فقط وقتی خوانده می‌شود که درِ فقط‌خواندنی یا نوشتن باز باشد. */
export function useExecutionPortfolio(enabled = true) {
  return useQuery({
    queryKey: ['execution-portfolio'],
    queryFn: ({ signal }) => portfolioApi.get(signal),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: (count, error) => count < 2 && !(error instanceof HttpError && error.status === 404),
  });
}

/** دیده‌بانِ شخصی EasyTrader — منبعی جدا از دیده‌بانِ محلی و پرتفوی. */
export function useEasyTraderWatchlist(enabled = true) {
  return useQuery({
    queryKey: ['execution-watchlist'],
    queryFn: ({ signal }) => accountSourcesApi.watchlist(signal),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/** قدرت خریدِ خواندنی — منبعی جدا از نقدینگی و ارزش پرتفوی. */
export function useBuyingPower(enabled = true) {
  return useQuery({
    queryKey: ['execution-buying-power'],
    queryFn: ({ signal }) => accountSourcesApi.buyingPower(signal),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

/**
 * حالت‌های یک اقدامِ UI. «unknown» صراحتاً یک حالتِ جداست: اگر نتیجهٔ ارسال
 * نامعلوم شد، رابط نه «فرستاد» می‌گوید نه «نفرستاد» — دکمهٔ «رفعِ ابهام» هم
 * همین‌جا ظاهر می‌شود، نه «تلاشِ دوباره».
 */
export type ActionState = 'idle' | 'busy' | 'ok' | 'warn' | 'unknown' | 'error';

export type GateSource = 'ok' | 'loading' | 'absent';

export function messageOf(res: Record<string, unknown> | null | undefined): string {
  const code = res?.code;
  const detail = res?.detail;
  const rec = res?.record as ExecutionRecord | undefined;
  if (typeof code === 'string') {
    return `${CODE_LABEL[code] ?? code}${detail ? ` — ${String(detail)}` : ''}`;
  }
  if (rec?.error_code) {
    const c = String(rec.error_code);
    return `${CODE_LABEL[c] ?? c}${rec.error_detail ? ` — ${String(rec.error_detail)}` : ''}`;
  }
  return '';
}

/** کدِ خطایِ سرویس ← پیامِ خوانا، بدونِ حذفِ کدِ خام (درِ tooltip می‌ماند) */
export const CODE_LABEL: Record<string, string> = {
  AUTH_FAILED: 'اجازۀ دسترسی رد شد',
  SESSION_EXPIRED: 'دسترسی منقضی شد',
  NETWORK_ERROR: 'خطای شبکه — نتیجه نامعلوم',
  TIMEOUT: 'پاسخی نیامد — نتیجه نامعلوم',
  BROKER_REJECTED: 'کارگزاری سفارش را رد کرد',
  INVALID_PRICE: 'قیمت نامعتبر',
  INVALID_QUANTITY: 'حجم نامعتبر',
  MARKET_CLOSED: 'بازار بسته است',
  DUPLICATE_GUARD: 'این سفارش پیش‌تر ارسال شده',
  UNKNOWN_RESULT: 'نتیجه نامعلوم',
  QUEUE_UNAVAILABLE: 'جای صف داده نمی‌شود',
  RATE_LIMITED: 'محدودیتِ نرخ',
  NOT_ORDERABLE: 'این نماد قابل سفارش نیست',
  UNSUPPORTED: 'این کار در اتصالِ فعال پشتیبانی نمی‌شود',
  HALTED: 'توقفِ اضطراری باز است',
  RISK_LIMIT: 'سقفِ ریسک',
  STALE_DATA: 'داده کهنه است',
  INVALID_EXECUTION_ID: 'شناسۀ سفارش نامعتبر است',
  MISSING_TOKEN: 'نشانی داده نشد',
};

/**
 * پاسخِ سرویس ← فازِ رابط. سه رأیِ جداست و هیچ‌کدام به دیگری تبدیل نمی‌شود:
 * success (با رکورد)، scheduled (درِ انتظارِ مهلت)، و unknown/خطا. «نامعلوم»
 * هرگز «ردشده» خوانده نمی‌شود: ردشده قابلِ تکرارِ آگاهانه است و نامعلوم فقط
 * قابلِ رفعِ ابهام از فهرستِ سفارش‌ها.
 */
export function phaseFromResponse(res: Record<string, unknown> | null): {
  phase: OrderPhase; state: ActionState;
} {
  if (!res) return { phase: 'idle', state: 'idle' };
  const status = String(res.status ?? '');
  if (status === 'scheduled') return { phase: 'scheduled', state: 'ok' };
  if (res.unknown_result === true) return { phase: 'unknown', state: 'unknown' };
  if (status === 'success') {
    const rec = res.record as ExecutionRecord | undefined;
    if (!rec) return { phase: 'submitted', state: 'ok' };
    const p = phaseOf(rec);
    return { phase: p, state: p === 'unknown' ? 'unknown' : 'ok' };
  }
  const code = String(res.code ?? '');
  if (code === 'TIMEOUT' || code === 'NETWORK_ERROR' || code === 'UNKNOWN_RESULT') {
    return { phase: 'unknown', state: 'unknown' };
  }
  return { phase: 'errored', state: 'error' };
}

// ─────────────────────────── زمان، سقف‌ها و سابقه ───────────────────────────
/** `GET /api/execution/timings` — مدتِ هر فاز رویِ monotonic باِ p50/p95/p99ِ
 *  نمونه‌هایِ واقعی. `thin: true` یعنی نمونۀِ کم؛ رابط ازِ آن «تضمینِ زمان»
 *  نمی‌سازد (§۵-۶: «هرگز اولِ صف را تضمین نکن»). */
export const PhaseTimingSchema = z.object({
  n: num, p50: num, p95: num, p99: num, min: num, max: num, thin: bool,
});
export type PhaseTiming = z.infer<typeof PhaseTimingSchema>;

export const TimingsSchema = z.object({
  status: z.string(),
  dry_run: bool,
  adapter: txt,
  samples: num,
  clock: txt,
  phases: z.record(z.string(), PhaseTimingSchema.nullish()).nullish(),
});
export type TimingsView = z.infer<typeof TimingsSchema>;

export function useExecutionTimings(enabled = true) {
  return useQuery({
    queryKey: ['execution-timings'],
    queryFn: ({ signal }) =>
      http<TimingsView>('/api/execution/timings', { schema: TimingsSchema, signal }),
    enabled,
    staleTime: 30_000,
    refetchInterval: sessionPollMs(60_000),
    retry: false,
  });
}

/** `GET /api/execution/limits` — سقف‌هایِ تنظیم‌شده، باِ تفکیکِ «تعریف‌نشده» از
 *  «صفر». اگر سقفی None باشد یعنی آن گیت خاموش است، نه اینکه مجازِ صفر است. */
export const LimitsSchema = z.object({
  status: z.string(),
  limits: z.object({
    max_orders: num,
    max_total_value: num,
    max_total_quantity: num,
    require_confirmation: bool,
    max_order_value: num,
    max_symbol_exposure: num,
    max_total_exposure: num,
    max_daily_loss: num,
    max_orders_per_window: num,
    max_total_orders_per_window: num,
    window_seconds: num,
    max_data_age_s: num,
  }).nullish(),
  codes: z.array(z.string()).nullish(),
});
export type LimitsView = z.infer<typeof LimitsSchema>;

export function useExecutionLimits() {
  return useQuery({
    queryKey: ['execution-limits'],
    queryFn: ({ signal }) =>
      http<LimitsView>('/api/execution/limits', { schema: LimitsSchema, signal }),
    staleTime: 120_000,
    retry: false,
  });
}

/** `GET /api/execution/events` — سابقۀِ ماندگارِ خودِ برنامه، باِ فیلتر.
 *  بی‌`payload` و باِ `detail`ِ ردact‌شده (سنجیده درِ dev/sarkhati_tab_v1122.py). */
export const EventSchema = z.object({
  id: z.number(),
  execution_id: z.string(),
  written_at: txt,
  at_epoch: num,
  kind: txt,
  status: txt,
  order_state: txt,
  error_code: txt,
  detail: txt,
  broker: txt,
  symbol: txt,
  side: txt,
  price: num,
  quantity: num,
  filled: num,
  mode: txt,
});
export type ExecutionEvent = z.infer<typeof EventSchema>;

export const EventsSchema = z.object({
  status: z.string(),
  adapter: txt,
  dry_run: bool,
  count: num,
  events: z.array(EventSchema).nullish(),
  note: txt,
  code: txt,
  detail: txt,
});
export type EventsView = z.infer<typeof EventsSchema>;

export type EventFilters = {
  executionId?: string;
  symbol?: string;
  status?: string;
  orderState?: string;
  kinds?: string;
  /** `YYYY-MM-DD` — بک‌اند خودش به epoch می‌شکند؛ ساعتِ منطقه‌ای درِ فیلتر نقشی ندارد */
  since?: string;
  until?: string;
  limit?: number;
};

export function eventQuery(f: EventFilters): string {
  const q = new URLSearchParams();
  if (f.executionId?.trim()) q.set('execution_id', f.executionId.trim());
  if (f.symbol?.trim()) q.set('symbol', f.symbol.trim());
  if (f.status?.trim()) q.set('status', f.status.trim());
  if (f.orderState?.trim()) q.set('order_state', f.orderState.trim());
  if (f.kinds?.trim()) q.set('kind', f.kinds.trim());
  if (f.since?.trim()) q.set('since', f.since.trim());
  if (f.until?.trim()) q.set('until', f.until.trim());
  if (f.limit) q.set('limit', String(f.limit));
  const s = q.toString();
  return s ? `?${s}` : '';
}

export function useExecutionEvents(filters: EventFilters, enabled = true) {
  return useQuery({
    queryKey: ['execution-events', filters.executionId ?? '', filters.symbol ?? '',
      filters.status ?? '', filters.orderState ?? '', filters.kinds ?? '',
      filters.since ?? '', filters.until ?? '', filters.limit ?? 200],
    queryFn: ({ signal }) => http<EventsView>(
      `/api/execution/events${eventQuery(filters)}`, { schema: EventsSchema, signal }),
    enabled,
    staleTime: 10_000,
    refetchInterval: enabled ? sessionPollMs(60_000) : false,
    retry: false,
  });
}

// ── زمان‌بندیِ ماندگار (execution_schedule.py) ─────────────────────────────
// این لایه فقط نمایش می‌دهد؛ داوریِ اعتبارسنجی/وضعیت در بک‌اند است. مبلغ/حجم
// پیش‌فرض ندارد و live درِ پاسخِ readiness باید false باشد تا دکمهٔ زنده نیاید.
export type DurableSchedule = {
  id: string; execution_id: string; symbol: string; isin: string;
  full_name?: string | null; side: string; price: number; quantity: number;
  order_type: string; validity: string; mode: string; state: string;
  target_ms: number; target_local: string; tz: string; attempts: number;
  validation_ok?: boolean | null; last_validation?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null; result_state?: string | null; last_error?: string | null;
};
export type ScheduleBlocker = { code: string; detail: string };
export type ScheduleReadiness = {
  live_ready: boolean; dry_run_scheduling: boolean; executor: string;
  blockers: ScheduleBlocker[];
};
export type DurableSchedulesView = {
  status: string; schedules: DurableSchedule[]; readiness: ScheduleReadiness;
};

export const scheduleApi = {
  list: () => http<DurableSchedulesView>('/api/execution/schedules'),
  readiness: () => http<Record<string, unknown>>('/api/execution/schedules/readiness'),
  instrument: (symbol: string) => http<Record<string, unknown>>(
    `/api/execution/schedules/instrument?symbol=${encodeURIComponent(symbol)}`),
  create: (body: Record<string, unknown>) => http<Record<string, unknown>>(
    '/api/execution/schedules', { method: 'POST', body, ...NO_RETRY }),
  arm: (id: string) => http<Record<string, unknown>>(
    `/api/execution/schedules/${encodeURIComponent(id)}/arm`,
    { method: 'POST', ...NO_RETRY }),
  cancel: (id: string) => http<Record<string, unknown>>(
    `/api/execution/schedules/${encodeURIComponent(id)}/cancel`,
    { method: 'POST', body: { reason: 'user' }, ...NO_RETRY }),
  reset: (id: string) => http<Record<string, unknown>>(
    `/api/execution/schedules/${encodeURIComponent(id)}/reset`,
    { method: 'POST', ...NO_RETRY }),
};

export function useDurableSchedules(enabled = true) {
  return useQuery({
    queryKey: ['execution-durable-schedules'],
    queryFn: () => scheduleApi.list(),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? 10_000 : false,
    retry: false,
  });
}


// ── browser session host (CDP محلی؛ ورود دستی مالک) ─────────────────────────
export type BrowserHostView = {
  status?: string; healthy?: boolean; cdp_url?: string; port?: number;
  pid?: number; profile?: string; url?: string; started_at?: number;
};
export const browserHostApi = {
  get: () => http<Record<string, unknown>>('/api/execution/browser-host'),
  start: () => http<Record<string, unknown>>('/api/execution/browser-host',
    { method: 'POST', ...NO_RETRY }),
  stop: () => http<Record<string, unknown>>('/api/execution/browser-host',
    { method: 'DELETE', ...NO_RETRY }),
};
export function useBrowserHost() {
  return useQuery({
    queryKey: ['execution-browser-host'],
    queryFn: () => browserHostApi.get(),
    staleTime: 5_000,
    refetchInterval: 10_000,
    retry: false,
  });
}

// ── ورودِ دستیِ Mofid و Probeِ فقط‌خواندنی ──────────────────────────────────
export const MOFID_SESSION_STATES = ['NEEDS_LOGIN', 'AUTHENTICATING',
  'AUTHENTICATED_UNVERIFIED', 'READ_ONLY_PROBE_OK', 'SESSION_EXPIRED',
  'READ_ONLY_PROBE_FAILED'] as const;
export type MofidSessionState = (typeof MOFID_SESSION_STATES)[number];

export const MofidSessionSchema = z.object({
  status: z.string(),
  state: z.string().nullish(),
  reason: txt,
  adapter_ready: z.boolean().nullish(),
  adapter_reason: txt,
  host_open: z.boolean().nullish(),
  host_status: txt,
  token_present: z.boolean().nullish(),
  session_proven: z.boolean().nullish(),
  checked_at: txt,
  steps: z.record(z.string(), z.string()).nullish(),
  counts: z.record(z.string(), z.unknown()).nullish(),
  account_readiness: z.record(z.string(), z.unknown()).nullish(),
  login_url: txt,
  read_only: z.boolean().nullish(),
  live_enabled: z.boolean().nullish(),
  live_ready: z.boolean().nullish(),
}).catchall(z.unknown());
export type MofidSessionView = z.infer<typeof MofidSessionSchema>;

export const MofidProbeSchema = z.object({
  status: z.string(),
  code: txt,
  state: z.string().nullish(),
  detail: txt,
  account: z.record(z.string(), z.unknown()).nullish(),
  steps: z.record(z.string(), z.string()).nullish(),
  counts: z.record(z.string(), z.unknown()).nullish(),
  session: z.record(z.string(), z.unknown()).nullish(),
  session_state: z.record(z.string(), z.unknown()).nullish(),
  account_readiness: z.record(z.string(), z.unknown()).nullish(),
  position_fields: z.record(z.string(), z.string()).nullish(),
  order_contract: z.record(z.string(), z.unknown()).nullish(),
  checked_at: txt,
  read_only: z.boolean().nullish(),
  live_enabled: z.boolean().nullish(),
  live_ready: z.boolean().nullish(),
}).catchall(z.unknown());
export type MofidProbeView = z.infer<typeof MofidProbeSchema>;

export const mofidApi = {
  session: (signal?: AbortSignal) =>
    http<MofidSessionView>('/api/execution/mofid/session',
      { schema: MofidSessionSchema, signal }),
  loginWindow: () =>
    http<Record<string, unknown>>('/api/execution/mofid/login-window',
      { method: 'POST', ...NO_RETRY }),
  stopWindow: () =>
    http<Record<string, unknown>>('/api/execution/mofid/login-window',
      { method: 'DELETE', ...NO_RETRY }),
  verifySession: () =>
    http<MofidProbeView>('/api/execution/mofid/verify-session',
      { method: 'POST', schema: MofidProbeSchema, ...NO_RETRY }),
};

export function useMofidSession(enabled = true) {
  return useQuery({
    queryKey: ['mofid-session'],
    queryFn: ({ signal }) => mofidApi.session(signal),
    enabled,
    staleTime: 5_000,
    refetchInterval: 10_000,
    retry: false,
  });
}

// ── پایشِ جایگاهِ سفارش (Round 19) ─────────────────────────────────────────
// رتبه فقط وقتی KNOWN است که خودِ آداپتور مقدار داده باشد؛ نبودِ مقدار صفر
// نمی‌شود و ۰ هم «رتبهٔ اول» تفسیر نمی‌شود. Mofid در حالت فقط‌خواندنی
// UNSUPPORTED_READ_ONLY است چون قراردادش POST است.
const measure = z.union([z.number(), z.string()]).nullish();
export const QueueMonitorRowSchema = z.object({
  order_id: txt,
  symbol: txt,
  isin: txt,
  side: txt,
  price: measure,
  quantity: measure,
  filled_quantity: measure,
  execution_status: txt,
  order_state: txt,
  queue_status: z.string(),
  queue_position: measure,
  volume_ahead: measure,
  queue_source: txt,
  queue_as_of: txt,
  queue_freshness: txt,
  position_semantics: txt,
  volume_ahead_unit: txt,
  queue_reason: txt,
  queue_series: z.array(z.record(z.string(), z.unknown())).nullish(),
  read_back: txt,
  events: z.array(z.unknown()).nullish(),
}).catchall(z.unknown());
export type QueueMonitorRowView = z.infer<typeof QueueMonitorRowSchema>;

export const QueueMonitorSchema = z.object({
  status: z.string(),
  supported: bool,
  queue_supported: bool,
  rows: z.array(QueueMonitorRowSchema).default([]),
  reason: txt,
  contract: z.record(z.string(), z.unknown()).nullish(),
  claims_first_rank: bool,
  queue_source_verified: bool,
  queue_result_known: bool,
  observed_at: txt,
  poll_interval_ms: num,
  source: txt,
}).catchall(z.unknown());
export type QueueMonitorView = z.infer<typeof QueueMonitorSchema>;

/** گاردِ نمایش: رتبه فقط با KNOWN معنا دارد. */
export function queueRankText(row: QueueMonitorRowView): string {
  if (row.queue_status !== 'KNOWN' || row.queue_position == null) return '—';
  return String(row.queue_position);
}

export const queueMonitorApi = {
  get: (signal?: AbortSignal) =>
    http<QueueMonitorView>('/api/execution/queue-monitor',
      { schema: QueueMonitorSchema, signal }),
};

export function useQueueMonitor(enabled = true) {
  return useQuery({
    queryKey: ['execution-queue-monitor'],
    queryFn: ({ signal }) => queueMonitorApi.get(signal),
    enabled,
    staleTime: 5_000,
    refetchInterval: 10_000,
    retry: false,
  });
}

// ── چند عرضهٔ اولیه: داده، بودجه، Preflight و Timing ───────────────────────
export type OfferingView = {
  id: string; symbol: string; isin: string; market: string; method: string;
  start_ms?: number | null; end_ms?: number | null;
  price_min?: number | null; price_max?: number | null; price_step?: number | null;
  min_qty?: number | null; max_qty?: number | null;
  per_code_quota?: number | null; fee_rate?: number | null;
  source?: string; source_url?: string; verified_at_ms?: number | null;
  data_as_of_ms?: number | null; status: string;
  timing_relevance: string; timing_note: string;
};
export type OfferingsView = {
  status: string; offerings: OfferingView[];
  capital: { total_cap?: number | null; cash_reserve?: number | null;
    max_per_offering?: number | null; priorities?: Record<string, unknown>;
    version?: number };
  reserved_total: number; available?: number | null;
  reservations: Record<string, unknown>[];
};
export const offeringsApi = {
  list: () => http<OfferingsView>('/api/execution/offerings'),
  create: (body: Record<string, unknown>) => http<Record<string, unknown>>(
    '/api/execution/offerings', { method: 'POST', body, ...NO_RETRY }),
  budget: () => http<Record<string, unknown>>('/api/execution/offerings/budget'),
  setBudget: (body: Record<string, unknown>) => http<Record<string, unknown>>(
    '/api/execution/offerings/budget', { method: 'POST', body, ...NO_RETRY }),
  plan: (body: Record<string, unknown>) => http<Record<string, unknown>>(
    '/api/execution/offerings/plan', { method: 'POST', body, ...NO_RETRY }),
  preflight: (id: string, body: Record<string, unknown>) =>
    http<Record<string, unknown>>(
      `/api/execution/offerings/${encodeURIComponent(id)}/preflight`,
      { method: 'POST', body, ...NO_RETRY }),
  timing: (adapter: string, method: string, target_ms: number, network = '',
           margin_ms = 0) => http<Record<string, unknown>>(
    `/api/execution/offerings/timing?adapter=${encodeURIComponent(adapter)}`
    + `&method=${encodeURIComponent(method)}&target_ms=${target_ms}`
    + `&network=${encodeURIComponent(network)}&margin_ms=${margin_ms}`),
};
export function useOfferings() {
  return useQuery({
    queryKey: ['execution-offerings'],
    queryFn: () => offeringsApi.list(),
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: false,
  });
}

// ── cockpit: وضعیت، Preflight، Mock و گزارش ─────────────────────────────────
export type CockpitGate = {
  id: string; label: string; status: string; evidence: string; reason: string;
  action: string; source: string; observed_at?: number | null; age_s?: number | null;
};
export type CockpitStatusView = {
  status: string; live_ready: boolean; live_send: boolean; mode: string;
  app_version?: string; observed_at?: number; observed_iso?: string;
  gates: CockpitGate[]; next_action?: string; failing_count?: number;
  components?: Record<string, unknown>;
  readiness?: { live_ready?: boolean; blockers?: { code: string; detail: string }[] };
};
export type CockpitEvent = {
  seq: number; at: number; phase: string; status: string; detail: string;
  duration_ms?: number | null;
};
export type CockpitRun = {
  id: string; scenario: string; mode: string; status: string;
  started_at: number; finished_at?: number | null; event_count?: number;
  summary?: Record<string, unknown>; events?: CockpitEvent[];
};
export type CockpitRunsView = {
  status: string; mode: string; runs: CockpitRun[]; selected_run: string;
  events: CockpitEvent[]; scenarios: { id: string; label: string; detail: string }[];
};
export type CockpitPreflightView = {
  status: string; preflight?: {
    ok?: boolean; state?: string; checks?: { name: string; state: string;
      detail: string; source?: string; observed_at?: number | null }[];
    blockers?: string[]; amount?: number | null; fee?: number | null;
    reason?: string; action?: string; source?: string; observed_at?: number | null;
  };
};
export const cockpitApi = {
  status: () => http<CockpitStatusView>('/api/execution/cockpit/status'),
  runs: (limit = 30, runId = '') => http<CockpitRunsView>(
    `/api/execution/cockpit/runs?limit=${limit}`
    + (runId ? `&run_id=${encodeURIComponent(runId)}` : '')),
  run: (body: Record<string, unknown>) => http<Record<string, unknown>>(
    '/api/execution/cockpit/runs', { method: 'POST', body, ...NO_RETRY }),
  detail: (runId: string) => http<{ status: string; run: CockpitRun }>(
    `/api/execution/cockpit/runs/${encodeURIComponent(runId)}`),
  stop: (runId: string) => http<Record<string, unknown>>(
    `/api/execution/cockpit/runs/${encodeURIComponent(runId)}/stop`,
    { method: 'POST', ...NO_RETRY }),
  preflight: (body: Record<string, unknown>) => http<CockpitPreflightView>(
    '/api/execution/cockpit/preflight', { method: 'POST', body, ...NO_RETRY }),
  report: (runId = '') => http<Record<string, unknown>>(
    `/api/execution/cockpit/report`
    + (runId ? `?run_id=${encodeURIComponent(runId)}` : '')),
};
export function useCockpitStatus() {
  return useQuery({
    queryKey: ['execution-cockpit-status'],
    queryFn: () => cockpitApi.status(),
    staleTime: 5_000,
    refetchInterval: 15_000,
    retry: false,
  });
}
export function useCockpitRuns(enabled = true) {
  return useQuery({
    queryKey: ['execution-cockpit-runs'],
    queryFn: () => cockpitApi.runs(),
    enabled,
    staleTime: 2_000,
    refetchInterval: (query) => {
      const data = query.state.data as CockpitRunsView | undefined;
      return data?.runs?.some((r) => r.status === 'RUNNING') ? 1_500 : false;
    },
    retry: false,
  });
}
export function useCockpitRunDetail(runId: string) {
  return useQuery({
    queryKey: ['execution-cockpit-run', runId],
    queryFn: () => cockpitApi.detail(runId),
    enabled: !!runId,
    staleTime: 1_000,
    refetchInterval: (query) => {
      const data = query.state.data as { run?: CockpitRun } | undefined;
      return data?.run?.status === 'RUNNING' ? 1_200 : false;
    },
    retry: false,
  });
}

// ── تشخیصِ اتصال: ده مرحلهٔ مستقل از Mock ────────────────────────────────
export type ConnectionStep = {
  key: string; title: string; status: string; evidence: string; reason: string;
  action: string; observed_at: string; duration_ms?: number | null;
};
export type ConnectionDiagnosis = {
  status: string; app_version?: string; adapter?: string;
  state: string; state_label: string; steps: ConnectionStep[];
  next_action?: string; secrets_stored?: boolean; observed_at?: string;
  diagnose_ms?: number;
};
export type SessionCapture = {
  status?: string; code?: string; detail?: string; token_present?: boolean;
  page_host?: string; token_type?: string; expires_at?: number | null;
  scope?: string; has_refresh_token?: boolean; secrets_returned?: boolean;
  secrets_stored?: boolean;
};
export const connectionApi = {
  diagnose: () => http<ConnectionDiagnosis>('/api/execution/connection/diagnose'),
  verify: () => http<ConnectionDiagnosis>('/api/execution/connection/verify',
    { method: 'POST', ...NO_RETRY }),
  captureSession: () => http<SessionCapture>('/api/execution/connection/capture-session',
    { method: 'POST', ...NO_RETRY }),
  report: () => http<Record<string, unknown>>('/api/execution/connection/report'),
};
export function useConnectionDiagnosis() {
  return useQuery({
    queryKey: ['execution-connection-diagnosis'],
    queryFn: () => connectionApi.diagnose(),
    staleTime: 5_000,
    refetchInterval: 20_000,
    retry: false,
  });
}
