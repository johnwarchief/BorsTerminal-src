/**
 * frontend-v2/src/features/technical/ui/workspace/ActiveEventCard.tsx
 *
 * کارت رویداد فعالِ ریل بازرس (منتقل‌شده از ScannerFeed در B3، بدون تغییر رفتار):
 * - آخرین الگوی در حال تشکیل با درصد تشکیلِ تاریخیِ همین نماد (فقط وقتی نمونه کافی است)
 * - کیفیت ساختار، هدف/حد ضرر، بازده‌های ۱/۳/۵ کندلی و برچسب ردهٔ ۲ («کم‌بسامد»)
 * - تأکید بر اینکه کندلِ در حال تشکیل ≠ تأییدشده و درصد پیش‌بینی نیست
 */

import { toFaDigits } from '@shared/lib/fa';
import { PATTERN_CONFIG } from '../../model/patterns/config';
import { DIRECTION_FA, KIND_FA, showPercent } from '../../model/patterns/labels';
import { faNum, faPct } from '../../model/patterns/format';
import type { ChartPattern } from '../../model/patterns/types';

const STATUS_FA: Record<string, string> = { forming: 'در حال تشکیل', confirmed: 'تأییدشده', invalidated: 'باطل‌شده' };

export interface ActiveEventCardProps {
  /** آخرین الگوی در حال تشکیل؛ نبودش حالت خالی کارت را نشان می‌دهد. */
  pattern?: ChartPattern;
}

export function ActiveEventCard({ pattern }: ActiveEventCardProps) {
  const estimate = pattern?.formation;
  const gated = showPercent(estimate, PATTERN_CONFIG.formationMinResolved);

  return (
    <section data-testid="pattern-card" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
      {pattern ? (
        <>
          <div className="flex items-baseline justify-between gap-2">
            <span className="flex items-baseline gap-1">
              <b className="text-[13px]">{KIND_FA[pattern.kind] ?? pattern.kind}</b>
              <span className="text-[12px] text-[var(--text-2)]">{DIRECTION_FA[pattern.direction]}</span>
              {pattern.tier === 2 ? (
                <span
                  data-testid="pattern-tier-2"
                  className="rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-600"
                >
                  کم‌بسامد
                </span>
              ) : null}
            </span>
            <span className="text-[12px] text-[var(--text-3)]">{STATUS_FA[pattern.status]}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-[12px] text-[var(--text-3)]">
            <span data-testid="pattern-quality">کیفیت ساختار {toFaDigits(Math.round(pattern.quality))}</span>
            <span className="tabular-nums">هدف {faNum(pattern.target, 0)} · حد ضرر {faNum(pattern.stopLoss, 0)}</span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {gated != null && estimate ? (
              <>
                <b className="text-[20px] tabular-nums">{faPct(gated)}</b>
                <span className="text-[12px] text-[var(--text-3)]">
                  {toFaDigits(estimate.successes)} از {toFaDigits(estimate.resolved)} نمونه
                  {estimate.intervalLow != null && estimate.intervalHigh != null
                    ? ` · بازهٔ ${faPct(estimate.intervalLow)}–${faPct(estimate.intervalHigh)}`
                    : ''}
                </span>
              </>
            ) : (
              <span className="text-[12px] text-[var(--text-3)]">نمونهٔ کافی نیست</span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-[12px] text-[var(--text-3)]">
            <span>کندل ۱: {faNum(pattern.returns?.h1)}٪</span>
            <span>کندل ۳: {faNum(pattern.returns?.h3)}٪</span>
            <span>کندل ۵: {faNum(pattern.returns?.h5)}٪</span>
          </div>
          <p className="mt-2 text-[12px] text-[var(--text-3)]">
            کندلِ در حال تشکیل ≠ تأییدشده؛ درصد از تاریخچهٔ همین نماد است، نه پیش‌بینی.
          </p>
        </>
      ) : (
        <p className="text-[12px] text-[var(--text-3)]">الگوی در حال تشکیل نیست</p>
      )}
    </section>
  );
}
