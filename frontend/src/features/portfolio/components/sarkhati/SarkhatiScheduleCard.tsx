// features/portfolio/components/sarkhati/SarkhatiScheduleCard.tsx — زمان‌بندی،
// باِ تفکیکِ «برنامه‌ریزی / آماده‌سازی / ارسال / پذیرش»
//
// هیچ عددی اینجا ساخته نمی‌شود: زمان‌هایِ چهارگانه ازِ خودِ رکوردِ اجرا می‌آیند
// (`scheduled_at`، `actual_send_wall_ms`، `response_at`، `rtt_ms`) و durations از
// `/api/execution/timings` که monotonic است. زمانِ سرورِ کارگزاری «اثبات‌نشده»
// نوشته می‌شود، چون هیچ اندپوینتِ مستندی برایِ آن نداریم (§۵ مأموریت: فقط
// اندپوینت‌هایِ مستندشده؛ و «هرگز اولِ صف را تضمین نکن»).
//
// چرا دو جدول جدا: «برنامه‌هایِ زمان‌بندی» آینده‌اند و کنشِ لغو دارند؛ «زمان‌هایِ
// رکوردها» گذشته‌اند و فقط خوانده می‌شوند. ترکیب‌کردنشان یک جدولِ نیمه‌خالی می‌سازد.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { invalidateExecution, orderApi, useExecutionTimings, type LedgerView }
  from '../../lib/orderClient';
import { TONE, safeError, summarize, type ActionState } from '../../lib/orderActionView';
import { Chip, GhostBtn, Line, Note, Table, Td, Tr } from './parts';

type SchedEntry = {
  execution_id?: string;
  state?: string;
  target_wall_ms?: number | null;
  send_at_wall_ms?: number | null;
  confirm_epoch?: number | null;
  cancelled_by?: string | null;
};

const STATE_LABEL: Record<string, string> = {
  waiting: 'منتظرِ مهلت',
  scheduled: 'زمان‌بندی‌شده',
  fired: 'در مهلت فرستاد',
  aborted: 'لغو شد',
  sent: 'ارسال شد',
  failed: 'ناموفق',
};

const clock = (ms?: number | null) =>
  ms ? new Date(ms).toLocaleTimeString('fa-IR', { hour12: false }) : '—';

export function SarkhatiScheduleCard({ ledger }: { ledger: LedgerView | null | undefined }) {
  const timings = useExecutionTimings();
  const qc = useQueryClient();
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [state, setState] = useState<ActionState>('idle');
  const pending = (ledger?.scheduled ?? []).filter(
    (e) => ['waiting', 'scheduled'].includes(String((e as SchedEntry).state)));
  const rows = (ledger?.scheduled ?? []) as SchedEntry[];
  const times = (ledger?.records ?? []).slice(-4).reverse();

  const cancel = async (id: string) => {
    setBusy(id); setAnswer('');
    try {
      const res = await orderApi.cancelSchedule(id);
      const v = summarize('cancelSchedule', res, false);
      setState(v.state); setAnswer(v.text);
      invalidateExecution(qc);
    } catch (e) {
      setState('error'); setAnswer(safeError(e));
    } finally {
      setBusy('');
    }
  };

  const phases = (timings.data?.phases ?? {}) as Record<string,
    { n?: number | null; p50?: number | null; p95?: number | null;
      p99?: number | null; min?: number | null; max?: number | null; thin?: boolean | null }>;
  const phaseNames = Object.keys(phases);

  return (
    <div className="flex flex-col gap-2" data-testid="sarkhati-schedule-card">
      <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5">
        <header className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <h4 className="text-xs font-black leading-4 text-text-primary">زمان‌بندیِ ارسال</h4>
          <Chip tone={pending.length ? 'live' : 'idle'}>
            {toFaDigits(String(pending.length))} در انتظارِ مهلت
          </Chip>
          <span className="ms-auto text-2xs text-text-muted">
            {toFaDigits(String(rows.length))} برنامه درِ دفتر
          </span>
        </header>

        {rows.length === 0 ? (
          <Line testId="sarkhati-schedule-empty">
            هیچ زمان‌بندیِ ثبت‌شده‌ای نیست. «زمانِ هدف» را درِ بخشِ سفارش بگذارید؛ تا
            مهلت نرسیده هیچ درخواستی نمی‌رود و «توقف» همه را لغو می‌کند.
          </Line>
        ) : (
          <Table testId="sarkhati-schedule-rows" minWidth={620}
            head={['شناسۀ اجرا', 'وضعیت', 'هدف', 'لحظۀ ارسال (پیش‌افت)', 'چرا لغو شد', 'کنش']}>
              {rows.map((e, i) => (
                <Tr key={e.execution_id ?? i} testId={`sarkhati-sched-${e.execution_id ?? i}`}>
                  <Td num strong>{e.execution_id ?? '—'}</Td>
                  <Td>{STATE_LABEL[String(e.state)] ?? String(e.state ?? '—')}</Td>
                  <Td num>{clock(e.target_wall_ms)}</Td>
                  <Td num>
                    {clock(e.send_at_wall_ms)}
                    {e.target_wall_ms && e.send_at_wall_ms ? (
                      <span className="text-text-muted">
                        {' '}({toFaDigits(fmtInt(e.target_wall_ms - e.send_at_wall_ms))} ms زودتر)
                      </span>
                    ) : null}
                  </Td>
                  <Td tone={e.cancelled_by ? 'muted' : undefined}>
                    {e.cancelled_by ?? '—'}
                  </Td>
                  <Td>
                    {['waiting', 'scheduled'].includes(String(e.state)) ? (
                      <GhostBtn testId={`sarkhati-sched-cancel-${e.execution_id}`}
                        disabled={busy !== ''}
                        title="پیشِ مهلت: زمان‌بندی لغو می‌شود و هیچ درخواستی به کارگزاری نمی‌رود"
                        onClick={() => void cancel(String(e.execution_id))}>
                        لغوِ زمان‌بندی
                      </GhostBtn>
                    ) : <span className="text-text-muted">—</span>}
                  </Td>
                </Tr>
              ))}
          </Table>
        )}

        {answer ? (
          <p className={`mt-1.5 text-2xs leading-4 ${TONE[state]}`} data-testid="sarkhati-sched-answer">
            {answer}
          </p>
        ) : null}

        <div className="mt-1.5">
          <Note label="قواعدِ لغوِ زمان‌بندی" testId="sarkhati-schedule-rule">
            پیش ازِ رسیدنِ مهلت، لغو ممکن است. پس ازِ POST، «لغوِ زمان‌بندی» هیچ سفارشی
            را ازِ کارگزاری پس نمی‌گیرد؛ از آن به بعد فقط «لغوِ سفارش» معنی دارد، و آن هم
            فقط اگر کارگزاری `cancel` را درِ capabilities اعلام کرده باشد.
          </Note>
        </div>
      </section>

      {times.length ? (
        <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
          data-testid="sarkhati-record-times">
          <header className="mb-2 flex flex-wrap items-baseline gap-x-2">
            <h4 className="text-xs font-black leading-4 text-text-primary">
              زمان‌هایِ چهارگانۀ آخرین رکوردها
            </h4>
            <span className="text-2xs text-text-muted">ازِ خودِ رکورد، بی‌محاسبۀِ رابط</span>
          </header>
          <Table testId="sarkhati-times-rows" minWidth={660}
            head={['شناسۀ اجرا', 'برنامه‌ریزی', 'ارسال', 'پاسخ', 'RTT', 'آفست ساعت']}>
              {times.map((r) => (
                <Tr key={r.execution_id} testId={`sarkhati-times-${r.execution_id}`}>
                  <Td num strong>{r.execution_id}</Td>
                  <Td num>{clock(r.scheduled_at ? r.scheduled_at * 1000 : null)}</Td>
                  <Td num>{clock(r.actual_send_wall_ms)}</Td>
                  <Td num>{clock(r.response_at ? r.response_at * 1000 : null)}</Td>
                  <Td num>{r.rtt_ms != null ? `${toFaDigits(String(Math.round(r.rtt_ms)))} ms` : 'بی‌اندازه'}</Td>
                  <Td num>{r.clock_offset_ms != null
                    ? `${toFaDigits(String(Math.round(r.clock_offset_ms)))} ms` : 'بی‌اندازه'}</Td>
                </Tr>
              ))}
          </Table>
        </section>
      ) : null}

      <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
        data-testid="sarkhati-timings">
        <header className="mb-2 flex flex-wrap items-baseline gap-x-2">
          <h4 className="text-xs font-black leading-4 text-text-primary">
            تأخیرهایِ اندازه‌گیری‌شدۀ همین نشست
          </h4>
          <span className="text-2xs text-text-muted">monotonic — با پرشِ ساعتِ دیواری جابه‌جا نمی‌شود</span>
        </header>
        {phaseNames.length === 0 ? (
          <Line testId="sarkhati-timings-empty">
            هنوز هیچ فازی درِ این نشست زمان‌سنجی نشده است — عددی برایِ «چقدر زودتر
            بفرستم» وجود ندارد، پس پیش‌افت را بی‌شاهد پر نکنید.
          </Line>
        ) : (
          <Table testId="sarkhati-timings-rows" minWidth={560}
            head={['فاز', 'n', 'p50 (ms)', 'p95 (ms)', 'p99 (ms)', 'min–max (ms)']}>
              {phaseNames.map((name) => {
                const t = phases[name] ?? {};
                return (
                  <Tr key={name} testId={`sarkhati-timing-${name}`}>
                    <Td strong>
                      {name}
                      {t.thin ? <span className="text-accent-yellow"> · نمونۀ کم</span> : null}
                    </Td>
                    <Td num>{toFaDigits(String(t.n ?? 0))}</Td>
                    <Td num>{t.p50 != null ? toFaDigits(String(t.p50)) : '—'}</Td>
                    <Td num tone={t.p95 == null ? 'muted' : undefined}>
                      {t.p95 != null ? toFaDigits(String(t.p95)) : 'بی‌کافیِ نمونه'}
                    </Td>
                    <Td num tone={t.p99 == null ? 'muted' : undefined}>
                      {t.p99 != null ? toFaDigits(String(t.p99)) : 'بی‌کافیِ نمونه'}
                    </Td>
                    <Td num>{t.min != null && t.max != null
                      ? `${toFaDigits(String(t.min))}–${toFaDigits(String(t.max))}` : '—'}</Td>
                  </Tr>
                );
              })}
          </Table>
        )}
        <Line kind="warn" testId="sarkhati-server-clock-note">
          <span className="font-black">ساعتِ سرورِ کارگزاری: اثبات‌نشده (NOT_PROVEN)</span>
          {' '}— هیچ اندپوینتِ مستندِ زمانِ سروری درِ قراردادِ فعلی نیست، پس «درستِ همان
          لحظه» وعده داده نمی‌شود.
        </Line>
      </section>
    </div>
  );
}
