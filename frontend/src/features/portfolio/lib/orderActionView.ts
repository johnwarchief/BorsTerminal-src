// features/portfolio/lib/orderActionView.ts — یگانه تعبیرِ «پاسخِ سرویس» برایِ رابط
//
// چرا این فایل جداست: پنلِ کوچکِ دیده‌بان و کارت‌هایِ تبِّ «سرخطی» هر دو پاسخِ
// همان `api/execution.py` را به کاربر نشان می‌دهند. اگر معنا درِ دو جا نوشته
// شود، یکِ اقدام دو خوانش پیدا می‌کند — همان بیماری‌ای که درِ «نبض بازار» دیدیم
// (یکِ شاخص، دو قاعدۀ شمارش). پس این‌جا تنها جایِ ترجمه است: kind + پاسخ ←
// (حالت، فاز، متنِ خطِ پاسخ).
//
// سه چیزی که این ترجمه هرگز نمی‌کند:
//  • «۲۰۰» را «پذیرشِ کارگزاری» نمی‌خواند (§۴-ج).
//  • نامعلوم را به ردشده یا فرستاده برنمی‌گرداند؛ `unknown` حالتِ سوم است.
//  • متنِ ثابتِ رابط جایِ عددِ پاسخ را نمی‌گیرد — شمارش‌ها ازِ خودِ پاسخ می‌آیند.
import { HttpError } from '@shared/api/http';
import { toFaDigits } from '@shared/lib/fmt';
import type { ExecutionRecord, OrderPhase } from './orderClient';
import { PHASE_LABEL, messageOf, phaseFromResponse, phaseOf } from './orderClient';

export type ActionState = 'idle' | 'busy' | 'ok' | 'warn' | 'unknown' | 'error';

export const TONE: Record<ActionState, string> = {
  idle: 'text-text-secondary',
  busy: 'text-text-muted',
  ok: 'text-accent-green',
  warn: 'text-accent-yellow',
  unknown: 'text-accent-susp',
  error: 'text-accent-red',
};

/** متنِ امنِ خطا — هیچ‌وقت بدنهٔ پاسخ یا هدرِ درخواست را نشان نمی‌دهیم */
export function safeError(e: unknown): string {
  if (e instanceof HttpError) return `خطایِ ${e.status} درِ ${e.url.replace(/^https?:\/\/[^/]+/, '')}`;
  if (e instanceof Error) return e.message.slice(0, 140);
  return 'خطایِ نامعلوم';
}

export type ExecAction = 'preflight' | 'preview' | 'dispatch' | 'refresh' | 'reconcile'
  | 'queue' | 'halt' | 'resume' | 'probe' | 'session' | 'cancel' | 'cancelSchedule';

export const freshId = () => 'ui-' + Math.random().toString(36).slice(2, 10);

/**
 * پاسخِ هر اقدام جدا معنا می‌شود، چون فازهایِ مسیرِ اجرا جداوند: «پیش‌فرود»
 * ارسال نیست، «توقف» وضعیتِ هیچ سفارشی را عوض نمی‌کند، و «نامعلوم» هرگز به
 * «ردشده» برگردانده نمی‌شود (بندِ ۴-ج مأموریت).
 */
export function summarize(kind: ExecAction, res: Record<string, unknown>, wireHypothesis: boolean):
  { state: ActionState; phase: OrderPhase | null; text: string } {
  const err = messageOf(res);
  if (res.status === 'error' || res.status === 'refused') {
    const unknown = res.unknown_result === true
      || ['TIMEOUT', 'NETWORK_ERROR', 'UNKNOWN_RESULT'].includes(String(res.code));
    return { state: unknown ? 'unknown' : 'error',
      phase: unknown ? 'unknown' : 'errored',
      text: err || (unknown ? 'نتیجه نامعلوم — فقط رفعِ ابهام، نه ارسالِ دوباره' : 'رد شد') };
  }
  switch (kind) {
    case 'preflight': {
      const checks = (res.checks ?? {}) as Record<string, string>;
      const vals = Object.values(checks);
      const fail = vals.filter((v) => v === 'FAIL').length;
      const unk = vals.filter((v) => v === 'UNKNOWN').length;
      const blocked = res.ok === false;
      const reasons = (res.reasons ?? {}) as Record<string, string>;
      const why = Object.entries(checks).filter(([, v]) => v === 'FAIL')
        .map(([k]) => `${k}${reasons[k] ? ` (${reasons[k]})` : ''}`).join('، ');
      return { state: fail || blocked ? 'warn' : 'ok', phase: 'preflight',
        text: `پیش‌فرود: ${fa(vals.length - fail - unk)} سبز`
          + (fail ? `، ${fa(fail)} رد${why ? ` — ${why}` : ''}` : '')
          + (unk ? `، ${fa(unk)} نامعلوم` : '')
          + (blocked ? ' — مسدود؛ تا دادهٔ تأییدشده نیاید هیچ ارسالی نیست' : '') };
    }
    case 'preview':
      return { state: 'ok', phase: 'preflight',
        text: 'پیش‌نمایشِ بدنۀ واقعی آماده شد'
          + (wireHypothesis ? ' — سیم هنوز علیه کارگزاری تأیید نشده' : '') };
    case 'dispatch': {
      const r = phaseFromResponse(res);
      if (r.phase === 'scheduled') {
        const wait = Number(res.wait_ms ?? 0);
        return { state: 'ok', phase: 'scheduled',
          text: 'زمان‌بندی شد — تا مهلت هیچ درخواستی نمی‌رود و «توقف» آن را لغو می‌کند'
            + (wait > 0 ? ` (مهلتِ ظاهری ${fa(Math.round(wait / 1000))} ثانیه)` : '') };
      }
      const rec = res.record as ExecutionRecord | undefined;
      return { state: r.state, phase: r.phase,
        text: r.phase === 'unknown'
          ? 'نتیجه نامعلوم — «رفعِ ابهام» از فهرستِ سفارش، نه ارسالِ دوباره'
          : `${PHASE_LABEL[r.phase]}${rec?.broker_order_id ? ` — ${rec.broker_order_id}` : ''}` };
    }
    case 'refresh':
    case 'reconcile': {
      const rec = res.record as ExecutionRecord | undefined;
      const ph = phaseOf(rec ?? null);
      return { state: ph === 'unknown' ? 'unknown' : 'ok', phase: ph,
        text: `${kind === 'reconcile' ? 'رفعِ ابهام' : 'بازخوانی'}: ${PHASE_LABEL[ph]}`
          + (rec?.broker_order_id ? ` — ${rec.broker_order_id}` : '') };
    }
    case 'cancel': {
      const rec = res.record as ExecutionRecord | undefined;
      const ph = phaseOf(rec ?? null);
      // سه رأیِ جدا: «لغو تأیید شد» فقط باِ بازخوانی؛ «پذیرفته شد» تنها ادعایِ
      // ادapte است؛ و رد/نامعلوم هیچ‌کدام «لغوشده» نمی‌شوند (§۴-د).
      if (res.cancelled_confirmed === true) {
        return { state: 'ok', phase: ph === 'cancelled' ? 'cancelled' : ph,
          text: 'لغو تأیید شد — بازخوانیِ وضعیت همان را نشان داد' };
      }
      return { state: 'warn', phase: ph,
        text: String(res.note ?? 'لغو پذیرفته شد ولی بازخوانی تأیید نکرد — «تأییدِ لغو» ادعا نمی‌شود') };
    }
    case 'cancelSchedule':
      return res.aborted === true
        ? { state: 'warn', phase: 'cancelled',
          text: String(res.note ?? 'پیشِ آتش لغو شد — هیچ درخواستی به کارگزاری نرفت') }
        : { state: 'warn', phase: null,
          text: String(res.note ?? 'زمان‌بندی درِ انتظار نبود؛ وضعیت ازِ دفترِ اجرا خوانده می‌شود') };
    case 'queue': {
      if (res.supported === false) {
        return { state: 'warn', phase: null, text: String(res.reason ?? 'کارگزاری جایِ صف نمی‌دهد') };
      }
      const snap = res.snapshot as { position?: number | null; volume_ahead?: number | null } | null;
      if (!res.known || snap?.position == null) {
        return { state: 'warn', phase: null,
          text: String(res.reason ?? 'جایِ صف داده نشد — «نمی‌دانیم»، نه صفر') };
      }
      return { state: 'ok', phase: null,
        text: `جایِ صف: ${fa(snap.position)}`
          + (snap.volume_ahead != null
            ? ` (حجمِ جلوتر ${fa(snap.volume_ahead)} — واحدش تأیید نشده)` : '') };
    }
    case 'halt':
      return { state: 'warn', phase: null,
        text: 'توقف برقرار شد — رویِ دیسک می‌ماند'
          + (Number(res.aborted_schedules) > 0
            ? ` و ${fa(Number(res.aborted_schedules))} زمان‌بندی لغو شد` : '') };
    case 'resume':
      return { state: 'ok', phase: null,
        text: 'ادامه باز شد'
          + (Array.isArray(res.open_ids) && res.open_ids.length
            ? ` — ${fa(res.open_ids.length)} سفارشِ باز برایِ رفعِ ابهام` : '') };
    case 'probe':
      return res.ok
        ? { state: 'ok', phase: null,
          text: `اتصالِ فقط‌خواندنی تأیید شد (${fa(Math.round(Number(res.response_ms) || 0))} ms`
            + (res.orders_seen != null
              ? `، ${fa(Number(res.orders_seen))} سفارش دیده شد` : '') + ')' }
        : { state: 'warn', phase: null,
          text: String(res.detail ?? messageOf(res) ?? 'اتصال برقرار نشد') };
    case 'session':
      return res.status === 'success'
        ? { state: 'ok', phase: null,
          text: res.live ? 'نشست باز شد — اتصالِ زنده فعال است'
            : 'نشست در حافظه ماند (ترافیک هنوز خاموش است)' }
        : { state: 'warn', phase: null, text: messageOf(res) || 'نشست ذخیره نشد' };
  }
}

/** ارقامِ فارسی، ازِ همان `toFaDigits`ِ مشترکِ برنامه */
function fa(n: number): string {
  return toFaDigits(String(n));
}
