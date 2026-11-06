/**
 * frontend-v2/src/features/technical/ui/ScannerFeed.tsx
 *
 * فیدِ واحدِ اسکنر (ادغامِ تبِ «الگوها» در «اسکنر الگوها»):
 * - فهرست الگوهای اخیر با فیلتر خانواده؛ کلیک روی هر ردیف = فوکوس روی چارت (spec §7.3)
 * - ردیف‌های پولبک/CHoCH که overlayهای موجود در استور می‌نویسند (کندل، جهت، تاریخ)
 * - کتاب قواعد؛ همهٔ اعداد از PATTERN_CONFIG خوانده می‌شوند تا با موتور یکی بمانند
 * - ردهٔ ۲ (کم‌بسامد) با برچسب نمایش داده می‌شود، نه پنهان.
 *
 * کارت رویداد فعال در B3 به ریل بازرس منتقل شد (ActiveEventCard)؛ این فید
 * فقط فهرست و رویدادها و قواعد را نگه می‌دارد تا pattern-card یکتا بماند.
 */
import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { PATTERN_CONFIG } from '../model/patterns/config';
import { KIND_FA, showPercent } from '../model/patterns/labels';
import { faDate, faNum, faPct } from '../model/patterns/format';
import { useTechnicalStore } from '../model/technicalStore';
import type { ChartPattern, PatternFamily } from '../model/patterns/types';
import type { CHoCHSignal, PullbackSignal } from '../model/types';

const STATUS_FA: Record<string, string> = { forming: 'در حال تشکیل', confirmed: 'تأییدشده', invalidated: 'باطل‌شده' };
const FAMILY_FA: Record<PatternFamily, string> = { continuation: 'ادامه‌دهنده', reversal: 'بازگشتی' };

export interface ScannerFeedProps {
  patterns: readonly ChartPattern[];
  pullbacks: readonly PullbackSignal[];
  chochs: readonly CHoCHSignal[];
}

export function ScannerFeed({ patterns, pullbacks, chochs }: ScannerFeedProps) {
  const [family, setFamily] = useState<'all' | PatternFamily>('all');
  const setFocusPatternId = useTechnicalStore((s) => s.setFocusPatternId);
  const visible = [...patterns]
    .filter((p) => family === 'all' || p.family === family)
    .sort((a, b) => b.anchor.index - a.anchor.index)
    .slice(0, 20);
  // R-PA-16: رویدادهای اسکنر هم مثل الگوها کران دارند و از تازه به قدیم مرتب‌اند.
  const scannerEvents = [
    ...pullbacks.map((s) => ({ key: `pb-${s.id}`, testid: s.id, kind: 'پولبک', bullish: s.type === 'BULLISH', index: s.index, timestamp: s.timestamp })),
    ...chochs.map((s) => ({ key: `ch-${s.id}`, testid: s.id, kind: s.type, bullish: s.isBullish, index: s.index, timestamp: s.timestamp })),
  ].sort((a, b) => b.index - a.index).slice(0, 20);

  return (
    <div className="flex flex-col gap-3 p-3 text-[var(--text)]">
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
          {visible.map((pattern) => {
            const rowProbability = showPercent(pattern.formation, PATTERN_CONFIG.formationMinResolved);
            return (
              <li key={pattern.id}>
                {/* spec §7.3: کلیک روی ردیف = فوکوس روی چارت (استور، مصرف: KLineChartWrapper). */}
                <button
                  type="button"
                  data-testid={`pattern-row-${pattern.id}`}
                  onClick={() => setFocusPatternId(pattern.id)}
                  title="نمایش روی چارت"
                  className="flex w-full items-baseline justify-between gap-2 border-b border-[var(--line)] bg-transparent py-2 text-start text-[12px]"
                >
                  <span className="flex items-baseline gap-1">
                    {KIND_FA[pattern.kind] ?? pattern.kind}
                    {pattern.tier === 2 ? (
                      <span className="rounded-full border border-amber-500/30 px-1 text-[11px] text-amber-600">
                        کم‌بسامد
                      </span>
                    ) : null}
                  </span>
                  <span className="text-[var(--text-3)]">{FAMILY_FA[pattern.family]} · {STATUS_FA[pattern.status]}</span>
                  <span className="tabular-nums text-[var(--text-3)]">کیفیت {toFaDigits(Math.round(pattern.quality))}</span>
                  <span className="tabular-nums text-[var(--text-2)]">
                    {rowProbability != null ? faPct(rowProbability) : '—'}
                  </span>
                </button>
              </li>
            );
          })}
          {visible.length === 0 ? <li className="py-2 text-[12px] text-[var(--text-3)]">الگویی در این فیلتر نیست</li> : null}
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between">
          <b className="text-[13px] text-[var(--text)]">رویدادهای پولبک و ساختار</b>
          <span className="text-[12px] text-[var(--text-3)]">
            {toFaDigits(pullbacks.length + chochs.length)} مورد
          </span>
        </div>
        <ul data-testid="scanner-events" className="flex flex-col">
          {scannerEvents.map((event) => (
            <li
              key={event.key}
              data-testid={`scanner-event-${event.testid}`}
              className="flex items-baseline justify-between gap-2 border-b border-[var(--line)] py-2 text-[12px]"
            >
              <span>{event.kind}</span>
              <span className={event.bullish ? 'text-emerald-500' : 'text-rose-500'}>
                {event.bullish ? 'صعودی' : 'نزولی'}
              </span>
              <span className="tabular-nums text-[var(--text-3)]">کندل {toFaDigits(event.index)}</span>
              <span className="tabular-nums text-[var(--text-3)]">{faDate(event.timestamp)}</span>
            </li>
          ))}
          {pullbacks.length + chochs.length === 0 ? (
            <li className="py-2 text-[12px] text-[var(--text-3)]">رویداد پولبک یا CHoCH ثبت نشده است</li>
          ) : null}
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
