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
import { http } from '@shared/api/http';
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
});
export type SessionStatusView = z.infer<typeof SessionStatusSchema>;

/** شش مقدارِ `execution_contract.SessionState` -- یک واژگان، درِ همان لایۀ canonical */
export const SESSION_STATES = [
  'disconnected', 'connected', 'expired', 'auth_failed', 'error', 'unknown',
] as const;
export type SessionStateValue = (typeof SESSION_STATES)[number];

export const SESSION_LABEL: Record<SessionStateValue, string> = {
  disconnected: 'نشست بسته است',
  connected: 'نشست باز است',
  expired: 'نشست منقضی شده',
  auth_failed: 'اجازۀ دسترسی داده نشد',
  error: 'پاسخِ کارگزاری نامفهوم بود',
  unknown: 'وضعیتِ نشست روشن نیست',
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
  return {
    ...base,
    canTrade: status.dry_run !== true,
    dryRun: status.dry_run === true,
    reason: status.dry_run === true
      ? 'حالتِ بدل (dry_run) فعال است — هیچ سفارشی به کارگزاری نمی‌رود'
      : '',
  };
}

/** وضعیتِ اتصالِ اجرا یک‌بار در هر نشستِ بازار کافی است؛ ثابت‌تر از آن نیست */
export function useBrokerConnect() {
  return useQuery({
    queryKey: ['execution-connect'],
    queryFn: ({ signal }) => connectApi.status(signal),
    refetchInterval: 60_000,
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
    retry: false,
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
  audit: (id: string) => http<Record<string, unknown>>(`/api/execution/audit/${id}`),
  halt: (reason: string) => http<Record<string, unknown>>('/api/execution/halt',
    { method: 'POST', body: { reason }, ...NO_RETRY }),
  resume: (reason: string, confirm = false) => http<Record<string, unknown>>(
    '/api/execution/resume', { method: 'POST', body: { reason, confirm }, ...NO_RETRY }),
  probe: () => http<Record<string, unknown>>('/api/execution/probe', { method: 'POST', ...NO_RETRY }),
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
  SESSION_EXPIRED: 'نشست منقضی شد',
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
