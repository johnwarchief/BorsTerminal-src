// features/portfolio/lib/sarkhatiFlow.ts — «قدمِ شما» درِ تبِّ سرخطی
//
// این فایل تنها یک چیز می‌سازد: کدام پرسشِ کاربر **الان** بی‌پاسخ مانده است.
// هیچ داوریِ معاملاتی اینجا نیست — نه قیمت، نه مجازبودن، نه پذیرش. همه‌چیز از
// همان پاسخِ `/api/execution/status` و stateِ فرم می‌آید که `ExecutionPanel` هم
// از همان می‌خواند، و دروازۀ واقعیِ ارسال همان `gate.canTradeِ` خودِ سرویس است؛
// پس «قدمِ پیشنهادیِ رابط» و «دروازۀ ارسال» دو نسخهٔ یک قاعده نمی‌شوند
// (قاعدهٔ مخزن: یک داور).
//
// ترتیبِ پرسش‌ها ازِ مأموریتِ مالک (2026-10-18) است:
//   اتصال ← نماد ← سفارش ← نتیجه/پیگیری
//
// `go` بخشی است که دکمهٔ «برو به …» باز می‌کند و تنها یک‌جا از `step` جدا
// می‌شود: درِ توقفِ اضطراری قدمِ مسیر رویِ «سفارش» می‌ماند، ولی چیزی که قفل را
// باز می‌کند درِ «ریسک و ایمنی» است. پیشنهادی که مقصدِ کار ندارد، گم‌کردنِ کاربر
// است، نه راهنمایی.
import { DRY_RUN_LABEL } from './orderClient';
import type { SessionStateValue, TradingGate } from './orderClient';

export type SarkhatiStep = 'connect' | 'symbol' | 'order' | 'tracking';

/** بخش‌هایِ صفحه: چهار قدم + سه ابزارِ حرفه‌ای — یک واژگان برایِ قدم و مقصد. */
export type SarkhatiPanel = SarkhatiStep | 'schedule' | 'risk' | 'monitor';

/** ترتیبِ پرسش‌ها؛ همان ترتیبی که کاربر باید طی کند. */
export const STEP_ORDER: readonly SarkhatiStep[] = ['connect', 'symbol', 'order', 'tracking'];

export const STEP_LABEL: Record<SarkhatiStep, string> = {
  connect: 'اتصال',
  symbol: 'نماد',
  order: 'سفارش',
  tracking: 'نتیجه و پیگیری',
};

export const PRO_LABEL: Record<'schedule' | 'risk' | 'monitor', string> = {
  schedule: 'زمان‌بندی',
  risk: 'ریسک و ایمنی',
  monitor: 'پایش و سابقه',
};

/** شمارهٔ قدم برایِ نمایش (۱..۴) */
export function stepIndex(step: SarkhatiStep): number {
  return STEP_ORDER.indexOf(step) + 1;
}

/** نامِ نمایشیِ هر بخش، قدم یا حرفه‌ای — تا دکمه و عنوان یک واژگان داشته باشند. */
export function panelLabel(panel: SarkhatiPanel): string {
  return panel in STEP_LABEL ? STEP_LABEL[panel as SarkhatiStep] : PRO_LABEL[panel as
    'schedule' | 'risk' | 'monitor'];
}

export type StepDraft = {
  side?: string | null;
  price?: string | null;
  quantity?: string | null;
  targetLocal?: string | null;
};

export type StepSuggestion = { step: SarkhatiStep; why: string; go: SarkhatiPanel };

/** یک قدم + علتِ یک‌خطی‌اش + بخشی که باز می‌کند. `why` متنِ رابط است، نه دادهٔ
 *  سرویس؛ هر بندش باید به یک فیلدِ واقعیِ همان پاسخ برگردد (بی‌این، «قدم» حدس
 *  می‌شود). */
export function deriveStep(input: {
  gate: TradingGate;
  symbol: string | null;
  draft?: StepDraft | null;
  hasRecord?: boolean;
}): StepSuggestion {
  const { gate, symbol, draft, hasRecord } = input;
  const st = gate.status;

  if (!gate.endpointPresent) {
    return { step: 'connect', go: 'connect',
      why: 'سرویسِ اجرا پاسخ نمی‌دهد؛ تا رسیدنش هیچ قدمی ممکن نیست' };
  }
  if (gate.halted) {
    return { step: 'order', go: 'risk',
      why: `توقفِ اضطراری باز است${st?.kill_reason ? ` (${st.kill_reason})` : ''} — «ادامهٔ دستوری» درِ «ریسک و ایمنی» لازم است` };
  }
  // بی‌نشستِ راستی‌آزمایی‌شده، «سفارش نوشتن» هم ممکن نیست؛ اما بیلدِ mock که
  // خودِ سرویس نشستش را connected می‌دهد اینجا متوقف نمی‌شود (خواندۀ زندهٔ
  // /api/execution/status: state=connected، account_label=mock-acct-1).
  if (gate.sessionState !== 'connected') {
    return { step: 'connect', go: 'connect',
      why: 'نشستِ راستی‌آزمایی‌شده نداریم؛ «بررسی اتصال» لازم است' };
  }
  if (!symbol) {
    return { step: 'symbol', go: 'symbol', why: 'نمادی انتخاب نشده — «—» نماد نیست' };
  }
  const priceOk = (draft?.price ?? '').trim() !== '';
  const qtyOk = (draft?.quantity ?? '').trim() !== '';
  if (!priceOk || !qtyOk) {
    return { step: 'order', go: 'order', why: `قیمت یا حجمِ «${symbol}» هنوز نوشته نشده` };
  }
  // «ارسال شد» با «نتیجه‌اش روشن است» یکی نیست: تا وقتی رکوردی درِ دفترِ اجرا
  // نباشد، کاربر هنوز درِ همان قدمِ سفارش است.
  if (hasRecord) {
    return { step: 'tracking', go: 'tracking',
      why: `آخرین سفارشِ «${symbol}» درِ دفترِ اجراست؛ وضعیتش ازِ خودِ سرویس خوانده می‌شود` };
  }
  const mode = st?.dry_run === true || st?.adapter === 'mock'
    ? ' (حالتِ تمرین — هیچ سفارشی بیرون نمی‌رود)' : '';
  return { step: 'order', go: 'order', why: `آمادهٔ پیش‌فرود و بازبینی${mode}` };
}

/** واژگانِ نشست درِ یکِ خطِ اولِ صفحه. `SESSION_LABELِ` خودِ سرویس واژۀ فنی‌تر
 *  دارد («نشست بسته است»)؛ این‌جا همان حالت‌ها به زبانِ مأموریتِ مالک نوشته
 *  شده‌اند: متصل نیست / متصل / نشست منقضی شده / خطای اتصال. «در حال اتصال»
 *  وضعیتِ سرویس نیست، وضعیتِ میانهٔ خودِ فرمِ اتصال است و درِ `ConnectBrokerRow`
 *  خوانده می‌شود — پس درِ این فهرست نیست و جعل نمی‌شود. */
const SESSION_SHORT: Record<SessionStateValue, string> = {
  disconnected: 'متصل نیست',
  connected: '',
  expired: 'نشست منقضی شده',
  auth_failed: 'اجازۀ دسترسی داده نشد',
  error: 'خطای اتصال',
  unknown: 'وضعیتِ نشست روشن نیست',
};

/** یک خطِ وضعیتِ اولِ صفحه: چه‌چیزی حاکم است، و قدمِ بعدی کجاست. */
export function statusLine(gate: TradingGate): string {
  const st = gate.status;
  if (!gate.endpointPresent) return 'سرویسِ اجرا نمی‌رسد';
  if (gate.halted) return 'توقفِ اضطراری فعال است';
  const mode = st?.adapter === 'mock' ? 'بدلِ سرویس (mock)'
    // درِ فقط‌خواندنی یک GET ازِ ماشین بیرون می‌رود؛ «بی‌ترافیک» گفتنش همان
    // دروغِ وارونه است. `dry_run` فقط می‌گوید «سفارش ارسال نمی‌شود».
    : st?.read_only === true && st?.traffic_allowed === true
      ? 'فقط‌خواندنی: خواندن بله، ارسال نه'
      : st?.dry_run === true ? DRY_RUN_LABEL
        : st?.live_enabled === true ? 'اتصالِ زنده' : 'نشستِ بی‌ترافیک';
  return `${mode}${SESSION_SHORT[gate.sessionState] ? ` · ${SESSION_SHORT[gate.sessionState]}` : ''}`;
}
