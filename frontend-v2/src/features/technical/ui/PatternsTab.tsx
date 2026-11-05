/**
 * frontend-v2/src/features/technical/ui/PatternsTab.tsx
 *
 * تب «الگوها» در میزکار عریض:
 * - کارت آخرین الگوی در حال تشکیل با درصد تشکیلِ تاریخیِ همین نماد (فقط وقتی نمونه کافی است)
 * - فهرست الگوهای اخیر با فیلتر خانواده؛ کلیک روی هر ردیف = فوکوس روی چارت (spec §7.3)
 * - کتاب قواعد؛ همهٔ اعداد از PATTERN_CONFIG خوانده می‌شوند تا با موتور یکی بمانند
 */
import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { PATTERN_CONFIG } from '../model/patterns/config';
import { DIRECTION_FA, KIND_FA } from '../model/patterns/labels';
import { useTechnicalStore } from '../model/technicalStore';
import type { ChartPattern, PatternFamily } from '../model/patterns/types';

const STATUS_FA: Record<string, string> = { forming: 'در حال تشکیل', confirmed: 'تأییدشده', invalidated: 'باطل‌شده' };
const FAMILY_FA: Record<PatternFamily, string> = { continuation: 'ادامه‌دهنده', reversal: 'بازگشتی' };
// R-PAT-24: FormationEstimate احتمال را به‌صورت نسبت ۰..۱ می‌دهد؛ درصد یعنی ×۱۰۰.
// بازهٔ ویلسون هم همان نسبت است، پس سرصفحه و بازه یک واحد دارند.
const faPct = (rate: number) => `${toFaDigits(Math.round(rate * 100))}٪`;
const faNum = (value: number | null | undefined, digits = 1) => {
  if (value == null || !Number.isFinite(value)) return '—';
  // Number(...) صفرهای انتهایی را حذف می‌کند تا «۰٫۵» به‌جای «۰٫۵۰» نمایش داده شود.
  return toFaDigits(Number(value.toFixed(digits))).replace('.', '٫');
};

export function PatternsTab({ patterns }: { patterns: readonly ChartPattern[] }) {
  const [family, setFamily] = useState<'all' | PatternFamily>('all');
  const setFocusPatternId = useTechnicalStore((s) => s.setFocusPatternId);
  const lastForming = [...patterns]
    .filter((p) => p.status === 'forming')
    .sort((a, b) => b.anchor.index - a.anchor.index)[0];
  const visible = [...patterns]
    .filter((p) => family === 'all' || p.family === family)
    .sort((a, b) => b.anchor.index - a.anchor.index)
    .slice(0, 20);
  const estimate = lastForming?.formation;

  return (
    <div className="flex flex-col gap-3 p-3 text-[var(--text)]">
      <section data-testid="pattern-card" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
        {lastForming ? (
          <>
            <div className="flex items-baseline justify-between gap-2">
              <span className="flex items-baseline gap-1">
                <b className="text-[13px]">{KIND_FA[lastForming.kind] ?? lastForming.kind}</b>
                <span className="text-[12px] text-[var(--text-2)]">{DIRECTION_FA[lastForming.direction]}</span>
              </span>
              <span className="text-[12px] text-[var(--text-3)]">{STATUS_FA[lastForming.status]}</span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              {estimate?.probability != null ? (
                <>
                  <b className="text-[20px] tabular-nums">{faPct(estimate.probability)}</b>
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
              <span>کندل ۱: {faNum(lastForming.returns?.h1)}٪</span>
              <span>کندل ۳: {faNum(lastForming.returns?.h3)}٪</span>
              <span>کندل ۵: {faNum(lastForming.returns?.h5)}٪</span>
            </div>
            <p className="mt-2 text-[12px] text-[var(--text-3)]">
              کندلِ در حال تشکیل ≠ تأییدشده؛ درصد از تاریخچهٔ همین نماد است، نه پیش‌بینی.
            </p>
          </>
        ) : (
          <p className="text-[12px] text-[var(--text-3)]">الگوی در حال تشکیل نیست</p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
          فیلتر خانواده
          <select
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-2 py-1 text-[12px]"
            value={family}
            onChange={(event) => setFamily(event.target.value as 'all' | PatternFamily)}
          >
            <option value="all">همه</option>
            <option value="continuation">ادامه‌دهنده</option>
            <option value="reversal">بازگشتی</option>
          </select>
        </label>
        <ul data-testid="pattern-list" className="flex flex-col">
          {visible.map((pattern) => (
            <li key={pattern.id}>
              {/* spec §7.3: کلیک روی ردیف = فوکوس روی چارت (استور، مصرف: KLineChartWrapper). */}
              <button
                type="button"
                data-testid={`pattern-row-${pattern.id}`}
                onClick={() => setFocusPatternId(pattern.id)}
                title="نمایش روی چارت"
                className="flex w-full items-baseline justify-between gap-2 border-b border-[var(--line)] bg-transparent py-2 text-start text-[12px]"
              >
                <span>{KIND_FA[pattern.kind] ?? pattern.kind}</span>
                <span className="text-[var(--text-3)]">{FAMILY_FA[pattern.family]} · {STATUS_FA[pattern.status]}</span>
                <span className="tabular-nums text-[var(--text-2)]">
                  {pattern.formation?.probability != null ? faPct(pattern.formation.probability) : '—'}
                </span>
              </button>
            </li>
          ))}
          {visible.length === 0 ? <li className="py-2 text-[12px] text-[var(--text-3)]">الگویی در این فیلتر نیست</li> : null}
        </ul>
      </section>

      <section data-testid="pattern-rules" className="rounded-xl border border-[var(--line)] p-3 text-[12px] text-[var(--text-3)]">
        <b className="mb-2 block text-[13px] text-[var(--text)]">قواعد</b>
        <p className="leading-6">
          پرچم: لگ ≥ {faNum(PATTERN_CONFIG.flag.impulseLegAtrMin)}×ATR · حداقل لگ {faNum(PATTERN_CONFIG.flag.minLegBars, 0)} کندل · عرض کانال ≤ {faNum(PATTERN_CONFIG.flag.channelMaxWidthPct, 0)}٪ لگ
        </p>
        <p className="leading-6">
          پنانت: لگ ≥ {faNum(PATTERN_CONFIG.pennant.impulseLegAtrMin)}×ATR · همگرایی ≥ {faNum(PATTERN_CONFIG.pennant.convergenceMin * 100, 0)}٪
        </p>
        <p className="leading-6">
          مثلث: تحمل تخت‌بودن {faNum(PATTERN_CONFIG.triangle.flatToleranceAtr, 2)}×ATR · همگرایی ≥ {faNum(PATTERN_CONFIG.triangle.convergenceMin * 100, 0)}٪ · حداقل طول {faNum(PATTERN_CONFIG.triangle.minSpan, 0)} کندل
        </p>
        <p className="leading-6">
          مستطیل: تحمل {faNum(PATTERN_CONFIG.rectangle.flatToleranceAtr, 2)}×ATR · گُوه: همگرایی ≥ {faNum(PATTERN_CONFIG.wedge.convergenceMin * 100, 0)}٪
        </p>
        <p className="leading-6">
          سر و شانه: سر ≥ {faNum(PATTERN_CONFIG.hs.headAboveShouldersAtr, 2)}×ATR بالاتر · شانه‌ها ±{faNum(PATTERN_CONFIG.hs.shouldersToleranceAtr, 2)}×ATR · سه‌قلو: تحمل سطح {faNum(PATTERN_CONFIG.triple.levelToleranceAtr, 2)}×ATR
        </p>
        <p className="leading-6">
          حداقل لمس هر خط {faNum(PATTERN_CONFIG.minTouchesPerLine, 0)} · پیوت {faNum(PATTERN_CONFIG.pivLeft, 0)} چپ / {faNum(PATTERN_CONFIG.pivRight, 0)} راست · دورهٔ ATR {faNum(PATTERN_CONFIG.atrPeriod, 0)}
        </p>
        <p className="leading-6">
          تحمل لمس {faNum(PATTERN_CONFIG.touchToleranceAtr, 2)}×ATR · بافر ابطال {faNum(PATTERN_CONFIG.invalidationBufferAtr, 2)}×ATR · افق سنجش {faNum(PATTERN_CONFIG.outcomeHorizon, 0)} کندل · حداقل نمونه {faNum(PATTERN_CONFIG.formationMinResolved, 0)}
        </p>
        <p className="leading-6">
          مهلت تمدید {faNum(PATTERN_CONFIG.expiryGraceBars, 0)} کندل · حداقل نقاط تمدید {faNum(PATTERN_CONFIG.expiryMinPoints, 0)} · حداقل هدف خنثی {faNum(PATTERN_CONFIG.neutralMinTargetAtr, 2)}×ATR
        </p>
        <p className="leading-6">
          حداقل طول بازگشتی {faNum(PATTERN_CONFIG.reversal.minSpanBars, 0)} کندل · حداقل نمونهٔ بازده {faNum(PATTERN_CONFIG.returnsMinSamples, 0)} · پنجرهٔ هم‌پوشانی {faNum(PATTERN_CONFIG.overlapWindowBars, 0)} کندل
        </p>
        <p className="leading-6">
          سقف کندل هر خانواده: پرچم {faNum(PATTERN_CONFIG.flag.maxBars, 0)} · پنانت {faNum(PATTERN_CONFIG.pennant.maxBars, 0)} · مثلث {faNum(PATTERN_CONFIG.triangle.maxBars, 0)} · مستطیل {faNum(PATTERN_CONFIG.rectangle.maxBars, 0)} · گُوه {faNum(PATTERN_CONFIG.wedge.maxBars, 0)} · سر و شانه {faNum(PATTERN_CONFIG.hs.maxBars, 0)} · سه‌قلو {faNum(PATTERN_CONFIG.triple.maxBars, 0)}
        </p>
      </section>
    </div>
  );
}
