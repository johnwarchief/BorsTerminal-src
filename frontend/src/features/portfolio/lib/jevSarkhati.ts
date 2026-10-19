// features/portfolio/lib/jevSarkhati.ts — resolverِ خودیِ قطعی برایِ لایۀ jev-ui
//
// چرا این فایل هست و چرا «مدل» نیست:
//  • رابطِ BorsTerminal یک دسکتاپِ آفلاین است: هیچ سرویسِ بیرونی‌ای درِ محصول
//    صدا زده نمی‌شود (قیدِ مخزن: «هیچ داده‌ای از ماشینِ کاربر بیرون نمی‌رود») و
//    کلیدِ API هرگز درِ bundle مرورگر نمی‌نشیند. پس ترانسپورتِ `live` خودِ
//    jev-ui درِ مسیرِ واقعیِ این محصول جایی برای دویدن ندارد — نه به‌خاطرِ
//    سلیقه، به‌خاطرِ این‌که باندلِ منتشرشده Node ندارد (PyInstaller + Tauri) و
//    `@typesafe-ai/sdk` با `process.env` کار می‌کند.
//  • چیزی که از jev-ui واقعاً به کار می‌آید لایۀِ *ارائه* است: provider،
//    batcher، ماشینِ وضعیت (pending / ready / error)، fallbackهایِ policy،
//    telemetryِ bandedِ `useTimeOnScreen`، و Inspector که دقیقاً همان payload را
//    نشان می‌دهد که اگر روزی مدل خواست برود. آن لایه با تابعِ `resolve` تزریق
//    می‌شود — همان درزی که مستنداتِ رسمی برایِ «route handler یا هر میزبانِ
//    غیر Next» توصیف می‌کند.
//  • پاسخ‌ها اینجا از یک جدولِ قاعدهٔ *خوانا* می‌آیند، نه از مدل. پس:
//      – `meta.transport` نامِ صریحِ `bors-rules-offline` را دارد و هیچ
//        `model`، `usage` یا `costUsd` نمی‌سازد؛
//      – `confidence` همیشه ۱ است، چون خروجیِ قطعی است؛ عددِ ۱ را «اطمینانِ
//        مدل» خواندن دروغ است؛
//      – هیچ قاعده‌ای دربارهٔ اعتبارِ سفارش، قیمت، حجم، مجازبودنِ ارسال،
//        انتخابِ حساب یا ارسالِ دوباره تصمیم نمی‌گیرد. ورودی‌ها فقط پرچم‌هایِ
//        غیرحساسِ همان پاسخِ `/api/execution/status` است.
//
// سانسورِ داده درِ همین فایل انجام می‌شود: `appStateForJev` صدها فیلدِ پاسخِ
// سرویس را به پنج بوِل و سه برچسبِ حالت تبدیل می‌کند. نماد، قیمت، حجم، برچسبِ
// حساب و هر جزئیاتِ سفارشی واردِ `app` نمی‌شود؛ تستِ
// `jev-sarkhati.spec.tsx` همین را می‌بندد، نه فقط ادعا.
import { buildPayload } from 'jev-ui';
import type { Answer, BaseState, Decision, ResolveFn } from 'jev-ui';

/** نامِ ترانسپورت درِ meta؛ هیچ‌جا نباید «live» یا نامِ مدل بیاید. */
export const JEV_TRANSPORT = 'bors-rules-offline';

/** پنل‌هایِ ثانویه (ابزارهایِ حرفه‌ای) — همان سه id که درِ `sarkhatiFlow` هست. */
export const PRO_IDS = ['schedule', 'risk', 'monitor'] as const;
export type ProId = (typeof PRO_IDS)[number];

/** دایرۀِ تصمیمِ رابط. هر کلیدِ این شیء باید بدونِ هیچ جزئیاتِ سفارش باشد. */
export type JevAppState = {
  /** دروازۀِ اجرا باز است؟ (همان `gate.canTrade`، نه داوریِ دوباره) */
  canTrade: boolean;
  /** توقفِ اضطراری فعال است؟ */
  halted: boolean;
  /** حالتِ نشست از پاسخِ سرویس: connected / expired / … */
  session: string;
  /** حالتِ ارسال: بدل، فقط‌خواندنی، یا زنده (بدونِ نامِ کارگزاری) */
  mode: 'mock' | 'dry_run' | 'read_only' | 'live' | 'unknown';
  /** سفارشِ زمان‌بندی‌شده درِ دفتر هست؟ (بوِل، بدونِ نماد) */
  hasScheduled: boolean;
  /** نتیجهٔ نامعلوم یا ردشده درِ دفتر هست؟ (بوِل، بدونِ شناسۀ سفارش) */
  hasUnclear: boolean;
  /** پنلِ فعلیِ صفحه — برایِ تشخیصِ « گیر کردن» باِ کلیکِ تکراری */
  panel: string;
};

/** یک بارِ باندِ آشنایی، ساخته‌شده از شمارشِ بازدیدِ خودِ رابط (بدونِ دادهٔ بیرونی). */
export type JevFamiliarity = 'first visit' | 'returning' | 'returns often';

/** تنها سازندۀِ `app`. ورودی‌اش را ازِ `gate` و دفترِ اجرا می‌گیریم و *انتخابِ*
 *  فیلدها اینجا هست، پس افزودنِ تصادفیِ یک فیلدِ حساس ممکن نیست. */
export function appStateForJev(input: {
  canTrade: boolean;
  halted: boolean;
  session: string;
  status: {
    adapter?: string | null; dry_run?: boolean | null; read_only?: boolean | null;
    live_enabled?: boolean | null; traffic_allowed?: boolean | null;
  } | null;
  hasScheduled: boolean;
  hasUnclear: boolean;
  panel: string;
}): JevAppState {
  const st = input.status;
  const mode: JevAppState['mode'] = st?.live_enabled === true ? 'live'
    : st?.adapter === 'mock' ? 'mock'
      : st?.read_only === true ? 'read_only'
        : st?.dry_run === true ? 'dry_run' : 'unknown';
  return {
    canTrade: input.canTrade,
    halted: input.halted,
    session: input.session,
    mode,
    hasScheduled: input.hasScheduled,
    hasUnclear: input.hasUnclear,
    panel: input.panel,
  };
}

/** سطح‌هایِ `useScore`: راهنما چقدر پر باشد. سه سطحِ متناظر با سه بریدهٔ متن. */
export const HELP_LEVELS = ['خلاصه', 'یک بندِ کمکی', 'با جزئیات'] as const;

/** آرایشِ پیش‌فرضِ ابزارهایِ حرفه‌ای؛ همان ترتیبی که امروز درِ DOM هست.
 *  قاعده بی‌شرطی همین بردار را می‌دهد، پس «بدونِ داوری» یعنی «هیچ تغییری». */
const DEFAULT_ORDER: readonly ProId[] = PRO_IDS;

function orderVector(order: readonly ProId[]): Record<string, number> {
  const n = order.length;
  const out: Record<string, number> = {};
  order.forEach((id, i) => { out[id] = (n - i) / (n * (n + 1) / 2); });
  return out;
}

/** تکرارِ یک مقصد درِ چهار کنشِ آخر ⇒ کاربر جایِ خودش دور می‌چرخد. */
function repeatedPanel(actions: readonly string[]): boolean {
  const last = actions.slice(-4);
  return last.length >= 3 && last.every((a) => a === last[last.length - 1]);
}

/** داوری‌ها: هر idِ تصمیم → پاسخِ قاعده‌محور. هیچ‌کدام تصمیمِ معاملاتی نیست. */
export function jevRuleAnswer(d: Decision, base: BaseState): Answer {
  const app = (base.app ?? {}) as Partial<JevAppState>;
  const actions = base.recent_actions ?? [];
  const dwell = base.time_spent ?? 'very short';

  if (d.id === 'sarkhati_pro_rank') {
    // اولویتِ پنل‌هایِ ثانویه از فکت‌هایِ خودِ سرویس می‌آید، نه از حدس:
    // توقفِ اضطراری ← ریسک و ایمنی؛ نتیجهٔ نامعلوم ← پایش و سابقه؛
    // سفارشِ زمان‌بندی‌شده ← زمان‌بندی. بی‌این‌ها همان ترتیبِ امروز.
    const order: readonly ProId[] = app.halted ? ['risk', 'schedule', 'monitor']
      : app.hasUnclear ? ['monitor', 'risk', 'schedule']
        : app.hasScheduled ? ['schedule', 'monitor', 'risk']
          : DEFAULT_ORDER;
    return { type: 'choice', choice: order[0], probabilities: orderVector(order), confidence: 1 };
  }

  if (d.id === 'sarkhati_hint') {
    // راهنما فقط وقتی لازم است که دروازه بسته باشد و کاربر هم نشانهٔ ماندن بدهد.
    // «بسته» یعنی «راهنما را نبین»، نه «مخفی کن»: هیچ کنترلِ ضروری این‌جا نیست.
    const stuck = repeatedPanel(actions) || dwell === 'long' || dwell === 'very long';
    const need = app.canTrade === false || app.session === 'expired' || app.session === 'auth_failed';
    return { type: 'noul', noul: need && stuck ? 0.9 : 0.05 };
  }

  if (d.id === 'sarkhati_hint_level') {
    // چگالیِ همان راهنما: تازه‌وارد دو بند می‌خواند، همیشگی یک بند.
    const level = app.mode === 'mock' && repeatedPanel(actions) ? 2
      : dwell === 'long' || dwell === 'very long' ? 1 : 0;
    return { type: 'score', score: level, probabilities: {}, confidence: 1 };
  }

  // تصمیمِ ناشناخته: پاسخِ تهی نمی‌دهیم تا batcher خطا نکند؛ چرخشِ بی‌ضرر.
  if (d.question.type === 'choice') return { type: 'choice', choice: '__none__', probabilities: {}, confidence: 0 };
  if (d.question.type === 'score') return { type: 'score', score: 0, probabilities: {}, confidence: 0 };
  return { type: 'noul', noul: 0 };
}

/** تابعی که به `JevProvider` تزریق می‌شود. هیچ fetch، هیچ کلید، هیچ شبکه. */
export const resolveJevRules: ResolveFn = async (decisions, base) => {
  const answers: Record<string, Answer> = {};
  for (const d of decisions) answers[d.id] = jevRuleAnswer(d, base);
  return {
    answers,
    meta: { transport: JEV_TRANSPORT, requests: 0, decisions: decisions.length, ms: 0 },
    // `sent` همان بدنه‌ای است که اگر روزی ترانسپورتِ زنده فعال شود بیرون می‌رود؛
    // Inspectorِ خودِ jev-ui همین را بی‌واسطه نشان می‌دهد، پس سانسور قابلِ دیدن است.
    sent: buildPayload(decisions, base),
  };
};
