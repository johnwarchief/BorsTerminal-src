import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../../api/useFtsCard';
import { statusFa, type AxisStatus } from '../../lib/axisMeta';

const SUB_STATE: Record<string, AxisStatus> = {
  pass: 'pass',
  fail: 'fail',
  na: 'na',
  unknown: 'unknown',
};

const DIGITS = ['۱', '۲', '۳', '۴', '۵'] as const;

/** R103: ارقام، جداکنندهٔ هزارگان و اعشارِ شواهد در سطحِ فارسی. */
function faText(value: string | null | undefined): string {
  if (value == null || value === '') return '—';
  return toFaDigits(value).replace(/,/g, '٬').replace(/\./g, '٫');
}

/** شواهدِ تفصیلی؛ کلیدِ ردیف‌ها `${digit}-${sub.key}` است چون key زیرچک‌ها بین محورها تکرار می‌شود. */
export function EvidencePanel({ card }: { card: FtsCard }) {
  const rows = DIGITS.flatMap((digit) =>
    (card.details?.[digit]?.subchecks ?? []).map((sub) => ({ digit, sub })),
  );
  return (
    <section data-testid="panel-evidence" className="rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2.5">
      <h3 className="mb-1 text-[11.5px] font-medium text-[var(--fd-text)]">شواهد و پاسخ «چرا»</h3>
      {rows.length === 0 ? (
        <p className="text-[9.5px] leading-relaxed text-[var(--fd-text-3)]">
          زیرشواهدی برای این نماد در کارت ثبت نشده است؛ نتیجه بدونِ شاهدِ تفصیلی است.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 max-[700px]:grid-cols-1">
          {rows.map(({ digit, sub }) => {
            const state = SUB_STATE[sub.state ?? ''] ?? null;
            return (
              <div
                key={`${digit}-${sub.key ?? ''}`}
                data-testid={`evidence-${digit}-${sub.key ?? ''}`}
                className="flex items-center gap-1.5 border-b border-[var(--fd-line)] py-0.5 text-[9.5px] text-[var(--fd-text-3)]"
              >
                <span className="grid h-4 w-4 flex-none place-items-center rounded border border-[var(--fd-line)] text-[8.5px]">{digit}</span>
                <span className="min-w-0 truncate" title={sub.detail ? faText(sub.detail) : undefined}>{sub.label ?? '—'}</span>
                <span className="ms-auto text-[var(--fd-text)]">{faText(sub.value)}</span>
                {sub.threshold ? <span title={sub.threshold}>{sub.threshold}</span> : null}
                {state ? <span className={`flex-none fd-status--${state}`}>{statusFa(state)}</span> : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
