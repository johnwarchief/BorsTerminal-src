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
import type { BrokerConfig, ExecutionStatus, SessionStateValue, TradingGate } from './orderClient';

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
  schedule: 'آمادگی و پایش',
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
      why: 'هنوز مطمئن نیستیم به حساب کارگزاری دسترسی داریم؛ «بررسی وضعیت» لازم است' };
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
  disconnected: 'دسترسی نداریم',
  connected: '',
  expired: 'دسترسی منقضی شده',
  auth_failed: 'اجازۀ دسترسی داده نشد',
  error: 'خطای ارتباط',
  unknown: 'وضعیت دسترسی روشن نیست',
};

/** یک خطِ وضعیتِ اولِ صفحه: چه‌چیزی حاکم است، و قدمِ بعدی کجاست. */
export function statusLine(gate: TradingGate): string {
  const st = gate.status;
  if (!gate.endpointPresent) return 'سرویسِ اجرا نمی‌رسد';
  if (gate.halted) return 'توقفِ اضطراری فعال است';
  const mode = st?.adapter === 'mock' ? 'حالت آزمایشی'
    // درِ فقط‌خواندنی یک GET ازِ ماشین بیرون می‌رود؛ «بی‌ترافیک» گفتنش همان
    // دروغِ وارونه است. `dry_run` فقط می‌گوید «سفارش ارسال نمی‌شود».
    : st?.read_only === true && st?.traffic_allowed === true
      ? 'فقط‌خواندنی: خواندن بله، ارسال نه'
      : st?.dry_run === true ? DRY_RUN_LABEL
        : st?.live_enabled === true ? 'ارتباط زنده' : 'ارتباط برقرار نیست';
  return `${mode}${SESSION_SHORT[gate.sessionState] ? ` · ${SESSION_SHORT[gate.sessionState]}` : ''}`;
}

// ── چهار وضعیتِ جداِ اتصال ────────────────────────────────────────────────
// مأموریتِ مالک (2026-10-18) این چهار را از هم می‌خواهد: «تنظیمات ذخیره شد»،
// «نشست وارد شد»، «نشست با پاسخِ واقعی تأیید شد»، «ارسال سفارش مجاز است».
// رابطِ قبلی دومی و سومی را یکی می‌خواند (هر «نشستی» که درِ حافظه بود متصل
// به‌نظر می‌رسید) و «ذخیره شد» را گاهی به‌جایِ «تأیید شد» می‌گذاشت. هر چهار سطر
// این تابع از *یک* فیلدِ متفاوتِ پاسخ‌هایِ موجود می‌آید و هیچ‌کدام از دیگری
// مشتق نمی‌شود؛ پس روشن‌شدنِ یکی، دیگری را روشن نمی‌کند. هیچ عدد و متنی اینجا
// ساخته نمی‌شود: نبودِ پاسخ، خودش یک حالتِ خواناست («پاسخی نیامده»).
export type GateKey = 'config' | 'entered' | 'proven' | 'writes';
export type GateTone = 'ok' | 'warn' | 'bad' | 'idle';

export type GateRow = {
  key: GateKey; label: string; text: string; tone: GateTone; title: string;
};

const NO_REPLY = 'پاسخی نیامده';

/** حالتِ نشستِ بک‌اند به زبانِ مأموریت. `connected` باِ `proven` یکی نیست:
 *  نشانیِ واردشده «هست» است و پرسشِ موفقِ کارگزاری «اثبات». */
function enteredText(state: string, proven: boolean):
  { text: string; tone: GateTone; title: string } {
  if (state === 'expired') {
    return { text: 'دسترسی منقضی شده', tone: 'warn',
      title: 'کارگزاری گفت منقضی شده؛ دسترسی تازه لازم است، نه پرسش دوباره' };
  }
  if (state === 'auth_failed') {
    return { text: 'اجازۀ دسترسی داده نشد', tone: 'bad',
      title: 'اجازهٔ دسترسی رد شد — دسترسیِ داده‌شده به این حساب تعلق ندارد' };
  }
  if (state === 'error') {
    return { text: 'پاسخِ کارگزاری نامفهوم بود', tone: 'bad',
      title: 'پاسخ خوانا نبود؛ نتیجه نامعلوم می‌مانَد و هیچ چیز تأیید نمی‌شود' };
  }
  if (state === 'disconnected') {
    return { text: 'دسترسی نداریم', tone: 'idle',
      title: 'دسترسی به حساب در حافظهٔ همین برنامه نیست — بدون آن هیچ پرسشی به کارگزاری نمی‌رود' };
  }
  // `set_token` حالت را unknown می‌گذارد (نه connected): نشانی هست، پرسشی زده
  // نشده. «روشن نیست» گفتنش همان پرسش‌نزدن را پنهان می‌کرد.
  if (state === 'unknown' || state === 'connected') {
    return proven
      ? { text: 'دسترسی به حساب تأیید شد', tone: 'ok',
          title: 'دسترسی در حافظه است و یک پرسش فقط‌خواندنی پاسخ گرفته — با بستن برنامه پاک می‌شود' }
      : { text: 'دسترسی دریافت شد — بی‌تأیید', tone: 'warn',
          title: 'دسترسی فقط در حافظهٔ همین برنامه می‌ماند و هیچ‌جا نوشته نمی‌شود؛ '
            + 'تأیید تنها با «بررسی وضعیت» و پاسخ واقعی کارگزاری است' };
  }
  return { text: 'وضعیت دسترسی روشن نیست', tone: 'idle',
    title: 'سرویس حالت دسترسی را نفرستاده — از نبود پاسخ نتیجه ساخته نمی‌شود' };
}

export function connectionLadder(input: {
  cfg?: BrokerConfig | null;
  st?: ExecutionStatus | null;
}): GateRow[] {
  const cfg = input.cfg ?? null;
  const st = input.st ?? null;
  const sess = st?.session ?? null;
  const origin = String(sess?.origin ?? st?.adapter ?? '');
  const isMock = origin === 'mock' || st?.adapter === 'mock';
  const by = (sess?.verified_by ?? null) as Record<string, unknown> | null;
  // بدل هیچ‌وقت «تأییدِ کارگزاری» ندارد، حتی اگر پاسخی `proven` بفرستد.
  const proven = sess?.proven === true && !isMock;
  const path = by?.path ? ` · ${String(by.path)}` : '';

  const stored = cfg?.stored ?? null;
  const eff = cfg?.effective ?? null;
  const src = String(stored?.source ?? 'default');
  const savedAdapter = stored?.adapter ? String(stored.adapter) : '';
  const effAdapter = eff?.adapter ? String(eff.adapter) : '';

  let config: GateRow;
  if (!cfg) {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: NO_REPLY, tone: 'idle',
      title: 'درِ تنظیمِ اتصال پاسخی نبود — ادعایی از آن ساخته نمی‌شود' };
  } else if (src === 'env') {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: 'ازِ متغیرِ محیطی — مؤثر',
      tone: 'ok', title: 'متغیرِ محیطی برِ تنظیمِ دیسک مقدم است' };
  } else if (src === 'unavailable') {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: 'تنظیمِ دیسک خوانده نشد',
      tone: 'bad', title: 'خواندنِ تنظیمِ ذخیره‌شده شکست خورد؛ وضعیت از «بدونِ تنظیم» معتبرتر نیست' };
  } else if (src === 'default' || !savedAdapter) {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: 'تنظیمی ذخیره نشده',
      tone: 'idle', title: `پیش‌فرضِ همین پروسه: ${effAdapter || 'بدونِ آداپتور'}` };
  } else if (savedAdapter === effAdapter) {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: 'ذخیره شد و مؤثر است',
      tone: 'ok', title: 'ذخیره‌شدنِ تنظیمِ دیسک فقط دو کلیدِ غیرمحرمانه را می‌شناسد؛ رمز، کوکی و نشانی هیچ‌جا نوشته نمی‌شود' };
  } else {
    config = { key: 'config', label: 'تنظیمِ کارگزاری', text: 'ذخیره شد، مؤثر نشد',
      tone: 'warn', title: `ذخیره ≠ اعمال: ${savedAdapter} ذخیره شده، ${effAdapter || '—'} مؤثر است — آداپتور درِ راه‌اندازی خوانده می‌شود` };
  }

  const entered = isMock
    ? { text: 'حالت آزمایشی — دسترسی به حساب در کار نیست', tone: 'idle' as GateTone,
        title: 'حالت آزمایشی هیچ ارتباطی با کارگزاری ندارد، پس دسترسی به حساب معنا ندارد' }
    : !st || !sess
      ? { text: NO_REPLY, tone: 'idle' as GateTone, title: 'پاسخ دسترسی از سرویس نیامده' }
      : enteredText(String(sess.state ?? 'unknown'), proven);

  let provenRow: GateRow;
  if (isMock) {
    provenRow = { key: 'proven', label: 'تأییدِ واقعی', text: 'حالت آزمایشی — تأیید کارگزاری ندارد',
      tone: 'idle', title: 'هیچ پرسشی به کارگزاری نرفته، پس هیچ اثباتی هم نیست' };
  } else if (!sess) {
    provenRow = { key: 'proven', label: 'تأییدِ واقعی', text: NO_REPLY, tone: 'idle',
      title: 'بدون پاسخ دسترسی، تأیید گفته نمی‌شود' };
  } else if (!proven) {
    provenRow = { key: 'proven', label: 'تأییدِ واقعی', text: 'تأیید نشده', tone: 'idle',
      title: '«بررسی وضعیت» باید پاسخ موفقی از کارگزاری بگیرد؛ ثبت دسترسی به‌تنهایی تأیید نیست' };
  } else if (by?.hypothesis === true) {
    provenRow = { key: 'proven', label: 'تأییدِ واقعی', text: 'تأییدِ مسیرِ فرضی', tone: 'warn',
      title: 'پاسخِ واقعی ازِ مسیری آمد که درِ سندِ رسمیِ کارگزاری نیست' + path };
  } else {
    provenRow = { key: 'proven', label: 'تأییدِ واقعی', text: 'تأیید شد', tone: 'ok',
      title: 'ازِ یکِ پرسشِ فقط‌خواندنیِ دیدہ‌شدہ' + path };
  }

  const canPlace = st?.capabilities?.place === true;
  let writes: GateRow;
  if (!st) {
    writes = { key: 'writes', label: 'ارسالِ سفارش', text: NO_REPLY, tone: 'idle',
      title: 'سرویسِ اجرا پاسخ نداده؛ مجاز بودن از نبودِ پاسخ ساخته نمی‌شود' };
  } else if (st.live_enabled === true && canPlace) {
    writes = { key: 'writes', label: 'ارسالِ سفارش', text: 'مجاز', tone: 'warn',
      title: 'گیتِ نوشتن باِ متغیرِ محیطیِ پروسه باز شده است — پولِ واقعی' };
  } else if (st.live_enabled === true) {
    writes = { key: 'writes', label: 'ارسالِ سفارش', text: 'گیت باز، آداپتور ارسال را نمی‌پذیرد',
      tone: 'warn', title: 'ارسال درِ capabilityهایِ همین اتصال بسته است' };
  } else {
    writes = { key: 'writes', label: 'ارسالِ سفارش', text: 'خاموش', tone: 'idle',
      title: 'هیچ دکمه‌ای درِ این صفحه گیتِ نوشتن را باز نمی‌کند؛ ذخیرۀ «فقط‌خواندنی» '
        + 'هم روشنش نمی‌کند. تنها متغیرِ محیطیِ BORS_EXECUTION_LIVE=1 درِ خودِ پروسه '
        + 'تصمیمِ جداِ شماست' };
  }

  return [config,
    { key: 'entered', label: 'دسترسی به حساب', ...entered },
    provenRow, writes];
}
