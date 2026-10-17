// features/portfolio/components/sarkhati/SarkhatiScheduleCard.tsx — زمان‌بندی،
// باِ تفکیکِ «برنامه‌ریزی / آماده‌سازی / ارسال / پذیرش»
//
// هیچ عددی اینجا ساخته نمی‌شود: زمان‌هایِ چهارگانه ازِ خودِ رکوردِ اجرا می‌آیند
// (`scheduled_at`، `actual_send_wall_ms`، `response_at`، `rtt_ms`) و durations از
// `/api/execution/timings` که monotonic است. زمانِ سرورِ کارگزاری «اثبات‌نشده»
// نوشته می‌شود، چون هیچ اندپوینتِ مستندی برایِ آن نداریم (§۵ مأموریت: فقط
// اندپوینت‌هایِ مستندشده؛ و «هرگز اولِ صف را تضمین نکن»).
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge } from '@shared/components/Badge';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { invalidateExecution, orderApi, useExecutionTimings, type LedgerView }
  from '../../lib/orderClient';
import { TONE, safeError, summarize, type ActionState } from '../../lib/orderActionView';

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
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-schedule-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">زمان‌بندیِ ارسال</h4>
        <Badge tone={pending.length ? 'blue' : 'gray'}>
          {toFaDigits(String(pending.length))} در انتظارِ مهلت
        </Badge>
      </div>

      {rows.length === 0 ? (
        <p className="text-3xs text-text-muted" data-testid="sarkhati-schedule-empty">
          هیچ زمان‌بندیِ ثبت‌شده‌ای نیست. «زمانِ هدف» را درِ فرمِ سفارش بگذارید؛ تا
          مهلت نرسیده هیچ درخواستی نمی‌رود و «توقف» همه را لغو می‌کند.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-3xs" data-testid="sarkhati-schedule-rows">
            <thead>
              <tr className="text-text-muted">
                <th className="text-start font-bold">شناسۀ اجرا</th>
                <th className="text-start font-bold">وضعیت</th>
                <th className="text-start font-bold">هدف</th>
                <th className="text-start font-bold">لحظۀ ارسال (پیش‌افت)</th>
                <th className="text-start font-bold">چرا لغو شد</th>
                <th className="text-start font-bold"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e, i) => (
                <tr key={e.execution_id ?? i}
                  data-testid={`sarkhati-sched-${e.execution_id ?? i}`}
                  className="border-t border-border-c/40">
                  <td className="num py-1 font-bold text-text-primary">{e.execution_id ?? '—'}</td>
                  <td>{STATE_LABEL[String(e.state)] ?? String(e.state ?? '—')}</td>
                  <td className="num">{clock(e.target_wall_ms)}</td>
                  <td className="num">
                    {clock(e.send_at_wall_ms)}
                    {e.target_wall_ms && e.send_at_wall_ms ? (
                      <span className="text-text-muted">
                        {' '}({toFaDigits(fmtInt(e.target_wall_ms - e.send_at_wall_ms))} ms زودتر)
                      </span>
                    ) : null}
                  </td>
                  <td className="text-text-secondary">{e.cancelled_by ?? '—'}</td>
                  <td className="text-start">
                    {['waiting', 'scheduled'].includes(String(e.state)) ? (
                      <button type="button"
                        onClick={() => void cancel(String(e.execution_id))}
                        disabled={busy !== ''}
                        data-testid={`sarkhati-sched-cancel-${e.execution_id}`}
                        className="rounded-lg border border-accent-red/40 px-2 py-0.5 text-3xs font-bold text-accent-red hover:bg-accent-red/10 disabled:opacity-40">
                        لغوِ زمان‌بندی
                      </button>
                    ) : <span className="text-text-muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {answer ? (
        <p className={`text-3xs leading-4 ${TONE[state]}`} data-testid="sarkhati-sched-answer">
          {answer}
        </p>
      ) : null}

      <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-schedule-rule">
        پیش ازِ رسیدنِ مهلت، لغو ممکن است. پس ازِ POST، «لغوِ زمان‌بندی» هیچ سفارشی
        را ازِ کارگزاری پس نمی‌گیرد؛ از آن به بعد فقط «لغوِ سفارش» معنی دارد، و آن هم
        فقط اگر کارگزاری `cancel` را درِ capabilities اعلام کرده باشد.
      </p>

      <div className="flex flex-col gap-0.5 text-3xs" data-testid="sarkhati-record-times">
        <span className="font-bold text-text-secondary">زمان‌هایِ چهارگانۀ آخرین رکوردها</span>
        {(ledger?.records ?? []).slice(-4).reverse().map((r) => (
          <div key={r.execution_id} className="flex flex-wrap items-baseline gap-1.5"
            data-testid={`sarkhati-times-${r.execution_id}`}>
            <span className="num font-bold text-text-primary">{r.execution_id}</span>
            <span>برنامه‌ریزی: {clock(r.scheduled_at ? r.scheduled_at * 1000 : null)}</span>
            <span>ارسال: {clock(r.actual_send_wall_ms)}</span>
            <span>پاسخ: {clock(r.response_at ? r.response_at * 1000 : null)}</span>
            <span>RTT: {r.rtt_ms != null ? `${toFaDigits(String(Math.round(r.rtt_ms)))} ms` : 'بی‌اندازه'}</span>
            <span>آفست ساعت: {r.clock_offset_ms != null
              ? `${toFaDigits(String(Math.round(r.clock_offset_ms)))} ms` : 'بی‌اندازه'}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-0.5 text-3xs" data-testid="sarkhati-timings">
        <span className="font-bold text-text-secondary">
          تأخیرهایِ اندازه‌گیری‌شدۀ همین نشست (monotonic)
        </span>
        {phaseNames.length === 0 ? (
          <span className="text-text-muted" data-testid="sarkhati-timings-empty">
            هنوز هیچ فازی درِ این نشست زمان‌سنجی نشده است — عددی برایِ «چقدر زودتر
            بفرستم» وجود ندارد، پس پیش‌افت را بی‌شاهد پر نکنید.
          </span>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-3xs">
              <thead>
                <tr className="text-text-muted">
                  <th className="text-start font-bold">فاز</th>
                  <th className="text-start font-bold">n</th>
                  <th className="text-start font-bold">p50</th>
                  <th className="text-start font-bold">p95</th>
                  <th className="text-start font-bold">p99</th>
                  <th className="text-start font-bold">min–max</th>
                </tr>
              </thead>
              <tbody>
                {phaseNames.map((name) => {
                  const t = phases[name] ?? {};
                  return (
                    <tr key={name} className="border-t border-border-c/40"
                      data-testid={`sarkhati-timing-${name}`}>
                      <td className="py-1 font-bold text-text-primary">{name}
                        {t.thin ? <span className="text-accent-yellow"> · نمونۀ کم</span> : null}
                      </td>
                      <td className="num">{toFaDigits(String(t.n ?? 0))}</td>
                      <td className="num">{t.p50 != null ? toFaDigits(String(t.p50)) : '—'}</td>
                      <td className="num">{t.p95 != null ? toFaDigits(String(t.p95)) : 'بی‌کافیِ نمونه'}</td>
                      <td className="num">{t.p99 != null ? toFaDigits(String(t.p99)) : 'بی‌کافیِ نمونه'}</td>
                      <td className="num">{t.min != null && t.max != null
                        ? `${toFaDigits(String(t.min))}–${toFaDigits(String(t.max))}` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <span className="text-text-muted" data-testid="sarkhati-server-clock-note">
          ساعتِ سرورِ کارگزاری: اثبات‌نشده (NOT_PROVEN) — هیچ اندپوینتِ مستندِ
          زمانِ سروری درِ قراردادِ فعلی نیست، پس «درستِ همان لحظه» وعده داده نمی‌شود.
        </span>
      </div>
    </div>
  );
}
