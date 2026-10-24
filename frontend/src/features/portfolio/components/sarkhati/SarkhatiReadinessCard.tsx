// features/portfolio/components/sarkhati/SarkhatiReadinessCard.tsx — دروازهٔ اجرا
//
// یک خطِ وضعیت برایِ «داده/ریسک»، «نوشتن» و «مجوزِ مالک»؛ جزئیاتِ دوازده
// دروازه و قراردادِ بازسازی‌شده پشتِ یک expander می‌ماند. هیچ عدد/وضعیتی از
// این فایل ساخته نمی‌شود؛ همه از `/api/execution/readiness` می‌آید.
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useExecutionReadiness, type ReadinessGate } from '../../lib/orderClient';
import { Chip, GhostBtn, Line, Section } from './parts';

const LABEL: Record<string, string> = {
  PASS: 'سبز', BLOCKED: 'مسدود', UNVERIFIED: 'تأییدنشده',
  NOT_RUN: 'اجرا نشده', REQUIRED: 'لازم',
};
const TONE: Record<string, 'ok' | 'bad' | 'warn' | 'idle'> = {
  PASS: 'ok', BLOCKED: 'bad', UNVERIFIED: 'warn',
  NOT_RUN: 'idle', REQUIRED: 'warn',
};

function gate(gates: ReadinessGate[] | null | undefined, id: string) {
  return (gates ?? []).find((g) => g.id === id);
}

export function SarkhatiReadinessCard() {
  const qc = useQueryClient();
  const symbol = useSymbolStore((s) => s.symbol);
  const q = useExecutionReadiness({ symbol: symbol || undefined, side: 'buy' });
  const d = q.data;
  const gates = d?.gates ?? [];
  const dataGate = gate(gates, 'data_risk');
  const writeGate = gate(gates, 'write_contract');
  const ownerGate = gate(gates, 'owner_approval');
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-readiness'] });
  };
  const live = d?.live_ready === true;
  return (
    <Section title="آمادگیِ اجرا" sub="داده و ریسک از نوشتن جدا"
      testId="sarkhati-readiness-card"
      right={
        <>
          <Chip tone={live ? 'ok' : 'warn'} testId="readiness-live"
            title="live_ready فقط با قراردادِ عملیاتی، گیتِ کامل و مجوزِ مالک true می‌شود">
            Live: {live ? 'آماده' : 'بسته'}
          </Chip>
          <GhostBtn testId="readiness-refresh" onClick={refresh}>تازه‌سازی</GhostBtn>
          <GhostBtn testId="open-autoclicker" onClick={() => { window.location.hash = '#/autoclicker'; }}>AutoClicker</GhostBtn>
        </>
      }>
      {q.isPending ? <Line kind="muted" testId="readiness-loading">در حال خواندنِ دروازه‌ها…</Line> : null}
      {q.isError ? (
        <Line kind="error" testId="readiness-error">
          دروازهٔ آمادگی خوانده نشد: {q.error instanceof Error ? q.error.message : 'پاسخی نیامد'}
        </Line>
      ) : null}
      {d ? (
        <>
          <div className="flex flex-wrap items-center gap-1" data-testid="readiness-summary">
            <Chip tone={TONE[dataGate?.status ?? 'NOT_RUN'] ?? 'idle'} testId="readiness-data"
              title={dataGate?.detail ?? undefined}>
              داده/ریسک: {LABEL[dataGate?.status ?? 'NOT_RUN'] ?? dataGate?.status}
            </Chip>
            <Chip tone={TONE[writeGate?.status ?? 'UNVERIFIED'] ?? 'warn'} testId="readiness-write"
              title={writeGate?.detail ?? undefined}>
              نوشتن: {LABEL[writeGate?.status ?? 'UNVERIFIED'] ?? writeGate?.status}
            </Chip>
            <Chip tone={TONE[ownerGate?.status ?? 'REQUIRED'] ?? 'warn'} testId="readiness-owner"
              title={ownerGate?.detail ?? undefined}>
              مجوز مالک: {LABEL[ownerGate?.status ?? 'REQUIRED'] ?? ownerGate?.status}
            </Chip>
            <span className="text-3xs text-text-muted num" data-testid="readiness-blocking">
              {toFaDigits(String(d.blocking_count ?? 0))} باز
            </span>
          </div>
          <Line kind={live ? 'ok' : 'warn'} testId="readiness-next">
            اقدام بعدی: {d.next_action || '—'}
          </Line>
          <details className="mt-1 rounded-lg border border-border-c/40 px-2 py-1"
            data-testid="readiness-details">
            <summary className="cursor-pointer text-3xs font-bold text-text-secondary">
              دوازده دروازه و قراردادِ نوشتن
            </summary>
            <div className="mt-1 flex flex-wrap gap-1" data-testid="readiness-gates">
              {gates.map((g) => (
                <Chip key={g.id} tone={TONE[g.status] ?? 'idle'}
                  testId={`readiness-gate-${g.id}`}
                  title={`${g.detail ?? ''}${g.source ? ` · منبع: ${g.source}` : ''}`}>
                  {g.label}: {LABEL[g.status] ?? g.status}
                </Chip>
              ))}
            </div>
            <div className="mt-1 grid gap-x-3 gap-y-0.5 text-3xs sm:grid-cols-2"
              data-testid="readiness-contract">
              <span><span className="text-text-muted">روش: </span>
                <b className="num" dir="ltr">{String((d.contract as Record<string, unknown> | null)?.method ?? '—')}</b></span>
              <span dir="ltr" className="num break-all">
                {String((d.contract as Record<string, unknown> | null)?.endpoint ?? '—')}</span>
              <span><span className="text-text-muted">وضعیت: </span>
                <b>{String(d.contract_state ?? '—')}</b></span>
              <span><span className="text-text-muted">تأیید عملیاتی: </span>
                <b>{(d.contract as Record<string, unknown> | null)?.operationally_verified === true
                  ? 'بله' : 'نه'}</b></span>
            </div>
            <p className="mt-1 text-3xs leading-4 text-text-muted">
              {String((d.contract as Record<string, unknown> | null)?.provenance ?? '')}
            </p>
          </details>
        </>
      ) : null}
    </Section>
  );
}
