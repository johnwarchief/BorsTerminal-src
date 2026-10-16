// features/portfolio/lib/orderClient.ts -- قراردادِ پنلِ معامله با رباتِ سرخطی
//
// چرا این فایل هست: مالک می‌خواهد پنلِ راستِ «دیده‌بان بازار» از امروز برایِ
// اتصالِ بعدی به ربات ساخته باشد، ولی هیچ سفارشِ واقعی نرود. پس رابطِ UI یک
// چیزِ تازه نمی‌سازد: همان چیزی را می‌خواند که `api/execution.py` از قبل
// اعلام می‌کند (`GET /api/execution/status`: adapter، dry_run، live_enabled،
// blocked_on و capabilitiesِ همان `execution_contract.Capabilities`).
// نتیجه: روزی که آداپتورِ کارگزاری بنشیند، همین slotها پر می‌شوند و UI
// بازنویسی نمی‌خواهد -- و تا آن روز، «غیرفعال» از ادعایِ رابط نیست، از
// پاسخِ خودِ سرویس خوانده می‌شود.
//
// dry_run درِ بک‌اند ثابتِ True است و تنها adapterِ ممکن mock است (D8/D1 بی‌پاسخ);
// این لایه هیچ‌جا آن را دور نمی‌زند و هیچ فراخوانِ place/cancel نمی‌سازد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';

const bool = z.boolean().nullish();

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

export const ExecutionStatusSchema = z.object({
  status: z.string(),
  adapter: z.string().nullish(),
  dry_run: bool,
  experimental: bool,
  live_enabled: bool,
  live_requested: bool,
  wire_hypothesis: bool,
  /** اعلامِ خودِ دروازہ: درِ اینِ آداپتور هیچِ چیزی ازِ دستگاه بیرون نمی‌رود */
  nothing_will_leave_the_machine: bool,
  blocked_on: z.array(z.string()).nullish(),
  capabilities: BrokerCapabilitiesSchema.nullish(),
  limits: z.unknown().nullish(),
  ledger_size: z.number().nullish(),
  session: z.unknown().nullish(),
});
export type ExecutionStatus = z.infer<typeof ExecutionStatusSchema>;

/** حالت‌های یک سفارش -- واژگانِ `execution_contract`، نه اختراعِ رابط */
export const ORDER_PHASES = [
  'idle', 'draft', 'preflight', 'sending', 'submitted',
  'accepted', 'rejected', 'cancelled', 'errored',
] as const;
export type OrderPhase = (typeof ORDER_PHASES)[number];

export const PHASE_LABEL: Record<OrderPhase, string> = {
  idle: 'بی‌سفارش',
  draft: 'پیش‌نویس',
  preflight: 'پیش‌فرود',
  sending: 'در حالِ ارسال',
  submitted: 'ارسال‌شده',
  accepted: 'تأییدشده',
  rejected: 'ردشده',
  cancelled: 'لغوشده',
  errored: 'خطا',
};

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
};

/**
 * داوریِ درِ رابط از capabilitiesِ اعلام‌شده؛ نبودِ پاسخ ⇒ غیرفعال، نه «صفرِ مجاز».
 * سه حالت جداست چون متنِ «سرویس نیست» و «هنوز نرسیده» دو چیزند:
 *   ok      پاسخِ معتبر آمده
 *   loading هنوز اولین پاسخ نیامده — درِ این حالت هم دکمه‌ها بسته‌اند
 *   absent  سرویس پاسخ نداد (۴۰/خطا): درِ این نسخه درِ اجرا وجود ندارد
 */
export type GateSource = 'ok' | 'loading' | 'absent';

export function deriveGate(status: ExecutionStatus | null | undefined, source: GateSource = 'ok'): TradingGate {
  if (source === 'loading') {
    return {
      canTrade: false,
      reason: 'در حالِ خواندنِ وضعیتِ سرویسِ اجرا — تا نیامدنِ پاسخ هیچ سفارشی باز نمی‌شود',
      dryRun: true,
      caps: null,
      status: null,
      endpointPresent: false,
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
    };
  }
  const caps = status.capabilities ?? null;
  if (status.live_enabled !== true) {
    const blocked = (status.blocked_on ?? []).join(' · ');
    return {
      canTrade: false,
      reason: blocked
        ? `اتصالِ کارگزاری فعال نیست — در انتظارِ رأی: ${blocked}`
        : 'اتصالِ کارگزاری فعال نیست (live_enabled: false)',
      dryRun: status.dry_run !== false,
      caps,
      status,
      endpointPresent: true,
    };
  }
  if (caps?.place !== true) {
    return {
      canTrade: false,
      reason: 'سازندۀ سفارش (place) در این adapter فعال اعلام نشده است',
      dryRun: status.dry_run !== false,
      caps,
      status,
      endpointPresent: true,
    };
  }
  return {
    canTrade: status.dry_run !== true,
    reason: status.dry_run === true
      ? 'حالتِ بدل (dry_run) فعال است — هیچ سفارشی به کارگزاری نمی‌رود'
      : '',
    dryRun: status.dry_run === true,
    caps,
    status,
    endpointPresent: true,
  };
}

/** وضعیتِ اتصالِ اجرا یک‌بار در هر نشستِ بازار کافی است؛ ثابت‌تر از آن نیست */
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
