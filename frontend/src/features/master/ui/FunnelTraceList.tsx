// features/master/ui/FunnelTraceList.tsx — ردپایِ فیلتر‌به‌فیلترِ یک نماد
//
// درِ صفحۀ «جزئیات بازار»ِ پنلِ نماد می‌نشیند. هیچ وضعیتی اینجا ساخته نمی‌شود:
// هر سطر یا از `timeline`ِ خودِ موتور است، یا «رسیدنِ پاسخ نرسیده» را صادق
// می‌گوید. واژگانِ وضعیت از همان `STATUS_LABEL`ِ غربالگری خوانده می‌شود تا
// سایدبار و جدولِ غربالگری دو نامِ مختلف برایِ یک حالت نداشته باشند.
import { toFaDigits } from '@shared/lib/fmt';
import { STATUS_LABEL } from '../lib/ftsFunnel';
import type { TraceStep } from '../api/useFunnelTrace';

const STAGE_TITLE: Record<string, string> = {
  universe: 'جامعۀ غربالگری',
  tape: 'تابلوخوانی',
  technical: 'تکنیکال',
  fundamental: 'بنیادی',
  handover: 'تحویل',
};

const stepTitle = (s: TraceStep): string => {
  const [head, detail] = s.stage.split(':');
  const label = STAGE_TITLE[head] ?? s.stage;
  return detail ? `${label} · ${detail}` : label;
};

const TONE: Record<string, string> = {
  pass: 'bg-accent-green',
  reject: 'bg-accent-red',
  pending: 'bg-accent-yellow',
  unavailable: 'bg-border-c',
  not_required: 'bg-border-c/40',
  not_in_universe: 'bg-bg-secondary ring-1 ring-border-c',
};

export function FunnelTraceList({ steps, rulesetVersion, asOf }: {
  steps: readonly TraceStep[];
  rulesetVersion?: string | null;
  asOf?: number | null;
}) {
  if (steps.length === 0) {
    return (
      <p className="text-[10px] text-text-muted" data-testid="funnel-trace-empty">
        ردپایی برایِ این نماد ثبت نشده
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-1" data-testid="funnel-trace">
      {steps.map((s, i) => (
        <li key={`${s.stage}-${s.seq ?? i}`} data-testid={`funnel-trace-step-${i}`}
            className="flex items-start gap-1.5">
          <span aria-hidden
                className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${TONE[s.status] ?? 'bg-border-c'}`} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[10px] font-bold text-text-primary"
                  title={stepTitle(s)}>
              {stepTitle(s)}
              {typeof s.input_count === 'number' && typeof s.output_count === 'number' ? (
                <span className="num ms-1 text-[9px] font-normal text-text-muted">
                  {` (ورودی ${toFaDigits(s.input_count)} → خروجی ${toFaDigits(s.output_count)})`}
                </span>
              ) : null}
            </span>
            <span className="block truncate text-[9.5px] text-text-secondary"
                  title={`${s.human_reason ?? ''}${s.reason_code ? ` · ${s.reason_code}` : ''}${s.source ? ` · منبع: ${s.source}` : ''}`}>
              {STATUS_LABEL[s.status as keyof typeof STATUS_LABEL] ?? s.status}
              {s.human_reason ? ` — ${s.human_reason}` : ''}
            </span>
          </span>
        </li>
      ))}
      {/* explainability (#12): هر داوری باید نسخهٔ قاعده و زمانش را نشان دهد */}
      <li className="num text-[8.5px] text-text-muted" data-testid="funnel-trace-meta">
        نسخهٔ قواعد: {rulesetVersion ?? '—'}
        {asOf ? ` · داده: ${new Date(asOf * 1000).toLocaleTimeString('fa-IR')}` : ''}
      </li>
    </ol>
  );
}
