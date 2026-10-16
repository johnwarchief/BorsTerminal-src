// features/execution/api/orderLineApi.ts -- قراردادِ دروازۀِ اجرایِ سرخطی
//
// چرا این فایل هست (بندِ ۱.۱ وِ ۱.۲ مأموریتِ System 2): دروازۀِ `/api/execution/*`
// رویِ همینِ شاخه ثبت نبود -- سنجشِ زنده نشان داد status/session/bot هر سه ۲۰۰
// باِ `text/html` (fallbackِ SPA) برمی‌گشتند، یعنی «موفق» بی‌هیچِ قراردادی. پسِ
// اینِ لایه دقیقاً همانِ چیزی را که `api/execution.py` اعلام می‌کند تایپ می‌کند،
// نه چیزی که رابط دوست دارد:
//  • واژگانِ وضعیت ازِ `ExecutionStatus` خودِ قرارداد است (draft…reconciled)،
//    نه ازِ یکِ فهرستِ تازهٔ UI.
//  • `checks` دیکشنریِ نام→PASS/FAIL/UNKNOWN است؛ `UNKNOWN` با `FAIL` یکی نیست
//    و هیچ‌کدام با «بی‌عدد» یکی نمی‌شوند.
//  • `retries: 0` برایِ هرِ نوشتار: `shared/api/http.ts` پیش‌فرض دوِ بارِ دوباره
//    می‌فرستد وِ اینِ رویِ POST یعنی «یکِ کلیک، دوِ سفارش». ضدِ تکراریِ اصلی
//    درِ بک‌اند است (`duplicate` درِ preflight، باِ ردِّپایِ ماندگار) وِ رابط آن را
//    دور نمی‌زند.
//  • `execution_id` را رابط می‌سازد وِ ثابت نگه می‌دارد: همانِ شناسه کلیدِ
//    idempotency درِ سرویس است، پسِ retry یاِ refresh سفارشِ تازه نمی‌سازد.
import { z } from 'zod';
import { http } from '@shared/api/http';
import { ExecutionStatusSchema } from '@features/portfolio/lib/orderClient';

export { ExecutionStatusSchema };
export type { ExecutionStatus } from '@features/portfolio/lib/orderClient';

const str = z.string().nullish();
const num = z.number().nullish();
const bool = z.boolean().nullish();

/** `execution_contract.ExecutionStatus` -- ده مقدار، بی‌اختراعِ رابط */
export const EXECUTION_PHASES = [
  'draft', 'validated', 'prepared', 'scheduled', 'dispatched',
  'acknowledged', 'unknown_result', 'reconciled', 'failed',
] as const;
export type ExecutionPhase = (typeof EXECUTION_PHASES)[number];

export const PHASE_FA: Record<ExecutionPhase, string> = {
  draft: 'پیش‌نویس',
  validated: 'اعتبارسنجی‌شده',
  prepared: 'آمادهٔ ارسال',
  scheduled: 'زمان‌بندی‌شده',
  dispatched: 'ارسال‌شده',
  acknowledged: 'پذیرفته‌شده',
  unknown_result: 'نتیجهٔ نامعلوم',
  reconciled: 'مطابقت‌یافته',
  failed: 'رد/خطا',
};

/** `execution_service.py:40` -- PASS/FAIL/UNKNOWN؛ UNKNOWN یعنی «نگاه نکردم» */
export const VERDICT_FA: Record<string, string> = {
  PASS: 'قبول', FAIL: 'رد', UNKNOWN: 'نامعلوم',
};

export const ChecksSchema = z.record(z.string(), z.string());
export const ReasonsSchema = z.record(z.string(), z.string());

/** بدنهٔ مشترکِ preflight/prepare/dispatch (`_draft_from` درِ api/execution.py) */
export type OrderDraftBody = {
  execution_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  mode: 'safe' | 'fast' | 'ultra';
  price: number | null;
  quantity: number | null;
  price_source?: string;
  price_as_of?: string | null;
  /** تأییدِ صریحِ کاربرِ همانِ لحظه -- `require_confirmation` درِ limits */
  confirmed?: boolean;
  /** فقطِ برایِ دیدنِ کلِ مسیر رویِ بدل؛ نگاشتِ کارگزاری نمی‌سازد */
  mock_instrument?: boolean;
  target_wall_ms?: number | null;
  one_way_ms?: number;
  margin_ms?: number;
};

export const PreflightSchema = z.object({
  status: z.string(),
  adapter: str,
  dry_run: bool,
  live: bool,
  execution_id: z.string(),
  ok: z.boolean(),
  checks: ChecksSchema.default({}),
  reasons: ReasonsSchema.default({}),
  unknown: z.array(z.string()).default([]),
  instrument: z.record(z.string(), z.unknown()).nullish(),
});
export type PreflightResult = z.infer<typeof PreflightSchema>;

export const PrepareSchema = z.object({
  status: z.string(),
  execution_id: z.string(),
  mode: str,
  dry_run: bool,
  sendable: bool,
  checks: ChecksSchema.default({}),
  detail: str,
  code: str,
  payload_preview: z.record(z.string(), z.unknown()).nullish(),
  wire_preview: z.record(z.string(), z.unknown()).nullish(),
  wire_hypothesis: bool,
  plan: z.record(z.string(), z.unknown()).nullish(),
  timings: z.record(z.string(), z.unknown()).nullish(),
});
export type PrepareResult = z.infer<typeof PrepareSchema>;

/** `_record_dict(ExecutionRecord)` -- ردِّپا؛ فیلدهایِ نامعلوم null می‌مانند */
export const RecordSchema = z.object({
  execution_id: z.string(),
  symbol: str,
  side: str,
  price: num,
  quantity: num,
  mode: str,
  status: z.string(),
  order_state: str,
  broker_order_id: str,
  filled_quantity: num,
  rtt_ms: num,
  drift_us: num,
  actual_send_wall_ms: num,
  response_at: num,
  error_code: str,
  detail: str,
  events: z.array(z.unknown()).nullish(),
}).passthrough();
export type ExecutionRecordView = z.infer<typeof RecordSchema>;

/**
 * `POST /dispatch` -- سهshapeِ واقعی که `tools/ui_execution_contract_capture.py`
 * ازِ خودِ دروازہ ضبط کرده: موفق (`record` + `kill_switch: "ARMED"` رشته)،
 * خطایِ داوری (`code`/`detail`/`checks` بی‌`live`) وِ زمان‌بندی‌شده
 * (`send_at_wall_ms`/`wait_ms`). `execution_id` درِ پاسخِ موفق هیچ‌گاه نبود؛
 * ادعایِ وجودش schema را می‌شکست وِ رابط «مطابقت نرسید» می‌گفت، نه نتیجهٔ سفارش.
 */
export const DispatchSchema = z.object({
  status: z.string(),
  adapter: str,
  dry_run: bool,
  live: bool,
  execution_id: str,
  record: RecordSchema.nullish(),
  send_at_wall_ms: num,
  wait_ms: num,
  unknown_result: bool,
  code: str,
  detail: str,
  /** خودِ دروازہ حالتِ کلیدِ توقف را رشته می‌دهد (ARMED / HALTED) */
  kill_switch: z.union([z.string(), z.record(z.string(), z.unknown())]).nullish(),
  timings: z.record(z.string(), z.unknown()).nullish(),
  checks: ChecksSchema.nullish(),
  payload_preview: z.record(z.string(), z.unknown()).nullish(),
}).passthrough();
export type DispatchResult = z.infer<typeof DispatchSchema>;

export const LimitsSchema = z.object({
  status: z.string(),
  limits: z.object({
    max_orders: num,
    max_total_value: num,
    max_order_value: num,
    max_total_quantity: num,
    max_symbol_exposure: num,
    require_confirmation: bool,
    max_orders_per_window: num,
  }).passthrough().nullish(),
}).passthrough();
export type LimitsView = z.infer<typeof LimitsSchema>;

const WRITE = { retries: 0 } as const;

export function fetchExecutionStatus(signal?: AbortSignal) {
  return http<z.infer<typeof ExecutionStatusSchema>>('/api/execution/status', {
    schema: ExecutionStatusSchema,
    signal,
    // خواندنی است وِ بی‌خطر؛ باِ اینِ حال retries کم، چون «سرویس نیست» باید زود
    // وِ صادق بهِ رابط برسد، نه بعد ازِ سه تلاشِ بی‌فایده رویِ 200-HTML.
    retries: 1,
  });
}

export function runPreflight(body: OrderDraftBody, signal?: AbortSignal) {
  return http<PreflightResult>('/api/execution/preflight', {
    method: 'POST', body, schema: PreflightSchema, signal, ...WRITE,
  });
}

export function prepareOrder(body: OrderDraftBody, signal?: AbortSignal) {
  return http<PrepareResult>('/api/execution/prepare', {
    method: 'POST', body, schema: PrepareSchema, signal, ...WRITE,
  });
}

export function dispatchOrder(body: OrderDraftBody, signal?: AbortSignal) {
  return http<DispatchResult>('/api/execution/dispatch', {
    method: 'POST', body, schema: DispatchSchema, signal, ...WRITE,
  });
}

export function reconcileOrder(executionId: string, signal?: AbortSignal) {
  return http<DispatchResult>(`/api/execution/reconcile/${encodeURIComponent(executionId)}`, {
    method: 'POST', body: {}, schema: DispatchSchema, signal, ...WRITE,
  });
}

export function fetchLimits(signal?: AbortSignal) {
  return http<LimitsView>('/api/execution/limits', { schema: LimitsSchema, signal, retries: 1 });
}

/** قفلِ سراسریِ توقف -- اثرش رویِ همهٔ تب‌هاست، پس درِ هرِ تب روشن نشان داده می‌شود */
export function setHalt(halt: boolean, reason: string, signal?: AbortSignal) {
  return http<Record<string, unknown>>(halt ? '/api/execution/halt' : '/api/execution/resume', {
    method: 'POST',
    body: halt ? { reason } : { reason },
    schema: z.record(z.string(), z.unknown()),
    signal,
    ...WRITE,
  });
}
