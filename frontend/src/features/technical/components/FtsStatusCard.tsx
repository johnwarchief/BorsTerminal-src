// features/technical/components/FtsStatusCard.tsx -- بج وضعیت استراتژی FTS
//
// متنِ وضعیت از `payload.status` می‌آید — همان `_fts_status_block` درِ موتور.
// کامپوننت هیچ وضعیتی را از «ستاپ‌ها» حدس نمی‌زند: پیش از این همین کارت هر
// حالتی را با رشتهٔ ثابتِ «در انتظار شکست خط آبی» توضیح می‌داد، حتی وقتی موتور
// «حدِ ضرر» یا «تریگرِ جت» گفته بود، و با وتوی هفتگی هم‌زمان «پرواز فعال»
// نشان می‌داد (باگِ دورِ J). اولویتِ رأی درِ خودِ موتور حساب شده است:
// حدِ ضرر ← خروجِ تأییدشده ← وتوی هفتگی ← تریگرِ امروز ← هشدار ← زمینه ←
// بی‌سیگنال ← بی‌داده. تنها چیزی که بالاتر از موتور می‌ایستد گیتِ ریسکِ بنیادی
// است، چون از دامنهٔ تکنیکال بیرون است.
import type { AgentSignal } from '@contracts/signal';
import type { TechnicalPayload } from '@contracts/technical';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';

type Tone = 'red' | 'green' | 'yellow' | 'blue' | 'gray';

/** لحنِ رنگ از کدِ موتور؛ متن را خودِ موتور نوشته است */
const TONE_BY_CODE: Record<string, Tone> = {
  hard_stop: 'red',
  confirmed_exit: 'red',
  weekly_veto: 'yellow',
  entry_trigger: 'green',
  warning: 'yellow',
  context_only: 'blue',
  no_signal: 'gray',
  insufficient: 'gray',
  gate_rejected: 'red',
};

export type FtsStatusView = { code: string; text: string; tone: Tone };

/** تنها نگاشتِ مجاز: payload → وضعیتِ نمایش. بی‌رأیِ موتور، رأیی ساخته نمی‌شود. */
export function resolveFtsStatusView(
  signal: AgentSignal<TechnicalPayload> | null,
  gateBlocked: boolean,
): FtsStatusView {
  if (gateBlocked) {
    return { code: 'gate_rejected', text: 'مردود در گیت ریسک', tone: 'red' };
  }
  const st = signal?.payload.status;
  if (!st) {
    return {
      code: 'insufficient',
      text: 'موتور FTS هنوز وضعیتِ عمومی را منتشر نکرده',
      tone: 'gray',
    };
  }
  return { code: st.code, text: st.text, tone: TONE_BY_CODE[st.code] ?? 'gray' };
}

export function FtsStatusCard({
  signal,
  gateBlocked,
  jetPrice,
  jetReason,
  trigger,
}: {
  signal: AgentSignal<TechnicalPayload> | null;
  gateBlocked: boolean;
  jetPrice: number | null;
  /** «چرا جت نیست» از خودِ موتور — بی‌این فقط «محاسبه نشد» خوانده می‌شد */
  jetReason?: string | null;
  /** تریگرِ فعلی از موتور: kind + price + date (رسم/markِ رویِ کندلِ تریگر) */
  trigger?: { kind: string; label?: string | null; price?: number | null; date?: string | null } | null;
}) {
  const view = resolveFtsStatusView(signal, gateBlocked);
  return (
    <div className="glass-panel panel-in p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">وضعیت FTS</h3>
        <Badge tone={view.tone}>{view.text}</Badge>
      </div>
      <div className="mt-2 flex flex-col gap-1 text-xs text-text-secondary">
        {trigger?.price != null ? (
          <span>
            تریگرِ امروز{trigger.label ? ` (${trigger.label})` : ''}:{' '}
            <span className="num font-bold text-neon-cyan">{toFaDigits(trigger.price.toFixed(0))}</span>
            {trigger.date ? <span className="num"> · {trigger.date}</span> : null}
          </span>
        ) : jetPrice != null ? (
          <span>
            مقاومتِ جت (خط آبی):{' '}
            <span className="num font-bold text-neon-cyan">{toFaDigits(jetPrice.toFixed(0))}</span>
          </span>
        ) : (
          <span data-testid="fts-jet-reason">{jetReason || 'موتور سطحی برایِ امروز نگفت'}</span>
        )}
        {signal?.score != null ? (
          <span>
            امتیاز همگرایی:{' '}
            <span className="num font-bold text-text-primary">{toFaDigits(signal.score)}</span>
          </span>
        ) : null}
        {signal ? <span>{signal.rationale}</span> : <span>در انتظار داده...</span>}
      </div>
    </div>
  );
}
