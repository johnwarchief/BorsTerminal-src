// components/TechnicalStructureSummary.tsx -- خلاصهٔ جمع‌وجورِ تحلیل ساختاری در تبِ لایه‌ها
// فقط نمایشِ payloadِ `/api/fts` است: هیچ روندی از کندلِ محلی حساب نمی‌شود و هیچ
// حکمی از نو صادر نمی‌شود. حالت‌های در انتظار/خطا/خالی/آماده صریح‌اند، `null`
// معادلِ false یا اجازه نیست، و وتوی هفتگی هرگز «چراغ سبز» نمایش داده نمی‌شود.
import { Badge } from '@shared/components/Badge';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import { TREND_FA, trendTone } from './FtsBadgeStrip';
import { matrixDecisionFa, matrixSetupFa } from '../lib/ftsMatrixLabels';

export type SummaryState = 'loading' | 'error' | 'empty' | 'ready';

const TREND_LABEL: Record<'D' | 'W' | 'M', string> = { D: 'روزانه', W: 'هفتگی', M: 'ماهانه' };

function decisionTone(d: string | null | undefined): 'green' | 'red' | 'gray' {
  if (d === 'PERMITTED') return 'green';
  if (d === 'REJECT') return 'red';
  return 'gray';
}

export function TechnicalStructureSummary({
  fts,
  status,
  message,
  isLoading,
  isError,
}: {
  fts: FtsAnalysisData | null | undefined;
  status?: string | null;
  message?: string | null;
  isLoading: boolean;
  isError: boolean;
}) {
  let state: SummaryState;
  if (fts) state = 'ready';
  else if (isLoading) state = 'loading';
  else if (isError || status === 'error') state = 'error';
  else state = 'empty';

  const t = fts?.trend;
  const decision = t?.matrix?.decision;
  const setup = matrixSetupFa(t?.matrix?.setup);
  // وتو فقط با REJECT فعال است. «وتو ندارد» خاکستری می‌ماند؛ سبز، در این
  // ردیف، به‌معنای «خرید مجاز» خوانده می‌شد و حکمِ ماتریس جای دیگری است.
  const veto =
    decision === 'REJECT'
      ? { text: 'فعال (هفتگی)', tone: 'red' as const }
      : decision === 'PERMITTED'
        ? { text: 'ندارد', tone: 'gray' as const }
        : { text: 'نامشخص', tone: 'gray' as const };
  const setupText =
    decision === 'PERMITTED'
      ? (setup ?? 'گزارش نشده')
      : decision === 'REJECT'
        ? '— (وتوشده)'
        : '— (بدون حکم)';

  return (
    <section
      className="glass-panel flex flex-col gap-1.5 p-2"
      data-testid="technical-structure-summary"
      data-state={state}
      dir="rtl"
      aria-label="خلاصهٔ تحلیل ساختاری FTS"
    >
      <div className="flex items-baseline justify-between gap-1">
        <h3 className="text-xs font-black text-text-primary">تحلیل ساختاری FTS</h3>
        <span className="text-3xs text-text-muted">خلاصه</span>
      </div>

      <p className="text-3xs text-text-secondary" data-testid="tech-summary-state" data-state={state}>
        {state === 'loading' ? 'در حال دریافت تحلیل ساختاری…' : null}
        {state === 'error' ? `تحلیل ساختاری از سرور نیامد${message ? ` — ${message}` : ''}` : null}
        {state === 'empty' ? 'موتور FTS برای این نماد تحلیلی نفرستاد (بدون داده — نه تأیید)' : null}
        {state === 'ready' ? 'رأی‌ها همان خروجیِ موتورِ سرور است، نه محاسبهٔ دوباره.' : null}
      </p>

      {state === 'ready' ? (
        <>
          <div className="grid grid-cols-3 gap-1" data-testid="tech-summary-trends">
            {(['D', 'W', 'M'] as const).map((k) => {
              const tr = t?.[k]?.trend;
              return (
                <div
                  key={k}
                  className="flex flex-col items-center gap-0.5 rounded border border-border-c bg-bg-card/40 px-1 py-1"
                  data-testid={`tech-summary-trend-${k}`}
                >
                  <span className="text-3xs text-text-muted">{TREND_LABEL[k]}</span>
                  <Badge tone={trendTone(tr)}>{TREND_FA[tr ?? 'na'] ?? TREND_FA.na}</Badge>
                </div>
              );
            })}
          </div>

          <div className="flex flex-col gap-0.5 text-3xs" data-testid="tech-summary-matrix">
            <div className="flex items-center justify-between gap-2">
              <span className="text-text-secondary">حکمِ ماتریس FTS</span>
              <span title={t?.matrix?.desc ?? undefined}>
                <Badge tone={decisionTone(decision)}>{matrixDecisionFa(decision)}</Badge>
              </span>
            </div>
            <div className="flex items-center justify-between gap-2" data-testid="tech-summary-veto">
              <span className="text-text-secondary">وتوی هفتگی</span>
              <Badge tone={veto.tone}>{veto.text}</Badge>
            </div>
            <div className="flex items-center justify-between gap-2" data-testid="tech-summary-setup">
              <span className="text-text-secondary">ستاپِ گزارش‌شده</span>
              <span className="min-w-0 truncate text-text-primary" title={setupText}>
                {setupText}
              </span>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
