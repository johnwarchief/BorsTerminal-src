// features/portfolio/components/sarkhati/SarkhatiTrackingCard.tsx — نتیجهٔ هرِ درخواست
//
// شش حالتِ جدا، همان‌طور که درِ قراردادِ اجرا تعریف شده‌اند (orderClient.PHASE_LABEL):
// «ساخته شد» / «ارسالِ درخواست تأیید شد» / «پذیرشِ کارگزاری تأیید شد» / «رد شد» /
// «لغو تأیید شد» / «نتیجه نامعلوم». هیچ‌کدام به دیگری برگردانده نمی‌شود:
// نامعلوم ≠ ردشده، و ۲۰۰ ≠ پذیرش (§۴-ج).
//
// کنش‌ها بی‌capability ساخته نمی‌شوند: «لغو» فقط وقتی هست که `capabilities.cancel`
// true باشد (درِ EasyTrader صریح false است، چون هیچ مرجعِ بازبینی‌شده‌ای آن را
// پیاده نکرده)؛ «صف» فقط وقتی که جایِ صف داده شود، و بی‌آن «نمی‌دانیم» نوشته
// می‌شود نه رتبۀِ ساختگی.
//
// «رکوردی نیست» و «پاسخی نرسید» دو خطِ جدا هستند: یکی صفرِ واقعی است، دیگری
// خرابیِ در. رنگِ سبز رویِ نبودِ پاسخ، همان صفرِ جعلی است که درِ نبض بازار دیدیم.
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import {
  CODE_LABEL, ORDER_PHASES, PHASE_LABEL, invalidateExecution, orderApi, phaseOf,
  type ExecutionRecord, type ExecutionStatus, type LedgerView,
} from '../../lib/orderClient';
import { TONE, safeError, summarize, type ActionState } from '../../lib/orderActionView';
import { Chip, DangerBtn, GhostBtn, Line, Note, Table, Td, Tr } from './parts';

const CHIP_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle' | 'live'> = {
  accepted: 'ok', filled: 'ok', partial: 'live', submitted: 'live',
  scheduled: 'warn', rejected: 'bad', errored: 'bad', cancelled: 'idle',
  unknown: 'warn', draft: 'idle', preflight: 'idle', idle: 'idle', sending: 'warn',
};

const time = (sec?: number | null) =>
  sec ? new Date(sec * 1000).toLocaleTimeString('fa-IR', { hour12: false }) : '—';

const INPUT = 'rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-2xs '
  + 'text-text-primary placeholder:text-text-muted';

export function SarkhatiTrackingCard({ ledger, caps, status, endpointPresent = true }: {
  ledger: LedgerView | null | undefined;
  caps: Record<string, boolean | null | undefined> | null;
  status: ExecutionStatus | null;
  /** «سرویس نیست» با «سفارشی نیست» دو چیزند — یکی‌کردنشان صفرِ سبزِ جعلی است */
  endpointPresent?: boolean;
}) {
  const qc = useQueryClient();
  const [fSym, setFSym] = useState('');
  const [fPhase, setFPhase] = useState('');
  const [fId, setFId] = useState('');
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [state, setState] = useState<ActionState>('idle');
  const [trail, setTrail] = useState<Record<string, unknown[]>>({});

  const rows = useMemo(() => {
    const needleSym = fSym.trim();
    const needleId = fId.trim();
    return (ledger?.records ?? [])
      .filter((r) => (!needleSym || String(r.symbol ?? '').includes(needleSym))
        && (!needleId || String(r.execution_id).includes(needleId))
        && (!fPhase || phaseOf(r) === fPhase))
      .slice()
      .reverse();
  }, [ledger?.records, fSym, fId, fPhase]);

  const ask = async (kind: 'refresh' | 'reconcile' | 'cancel' | 'queue', id: string) => {
    setBusy(kind + id); setAnswer('');
    try {
      const res = kind === 'refresh' ? await orderApi.refresh(id)
        : kind === 'reconcile' ? await orderApi.reconcile(id)
          : kind === 'queue' ? await orderApi.queue(id)
            : await orderApi.cancel(id);
      const v = summarize(kind, res, false);
      setState(v.state); setAnswer(v.text);
      invalidateExecution(qc);
    } catch (e) {
      setState('error'); setAnswer(safeError(e));
    } finally {
      setBusy('');
    }
  };

  const readTrail = async (id: string) => {
    setBusy('trail' + id);
    try {
      const res = await orderApi.audit(id);
      setTrail((t) => ({ ...t, [id]: Array.isArray(res.events) ? res.events : [] }));
    } catch (e) {
      setAnswer(safeError(e)); setState('error');
    } finally {
      setBusy('');
    }
  };

  const canCancel = caps?.cancel === true;
  const canQueue = caps?.queue_position === true;
  const total = (ledger?.records ?? []).length;

  return (
    <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
      data-testid="sarkhati-tracking-card">
      <header className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1.5">
        <h4 className="text-xs font-black leading-4 text-text-primary">نتیجۀِ درخواست‌ها</h4>
        <input value={fSym} onChange={(e) => setFSym(e.target.value)}
          placeholder="نماد" aria-label="فیلترِ نماد" data-testid="sarkhati-filter-symbol"
          className={`${INPUT} w-24`} />
        <select value={fPhase} onChange={(e) => setFPhase(e.target.value)}
          aria-label="فیلترِ وضعیت" data-testid="sarkhati-filter-phase" className={INPUT}>
          <option value="">همۀِ وضعیت‌ها</option>
          {ORDER_PHASES.map((p) => (<option key={p} value={p}>{PHASE_LABEL[p]}</option>))}
        </select>
        <input value={fId} onChange={(e) => setFId(e.target.value)}
          placeholder="شناسۀِ اجرا" aria-label="فیلترِ شناسۀِ اجرا"
          data-testid="sarkhati-filter-id" className={`${INPUT} num w-32`} />
        <span className="ms-auto text-2xs text-text-muted">
          <span className="num font-bold text-text-primary">{toFaDigits(String(rows.length))}</span>
          {' از '}
          <span className="num font-bold text-text-primary">{toFaDigits(String(total))}</span> رکورد
        </span>
      </header>

      {!endpointPresent ? (
        <Line kind="error" testId="sarkhati-track-noservice">
          دفترِ اجرا خوانده نشد — این «رکوردی نیست» نیست، «پاسخی نرسید» است.
          با «آزمونِ اتصال» درِ بخشِ سفارش دوباره بسنجید.
        </Line>
      ) : rows.length === 0 ? (
        <Line testId="sarkhati-track-empty">
          {total === 0
            ? 'رکوردی درِ دفترِ اجرا نیست — تا اینجا هیچ سفارشی ساخته نشده.'
            : 'ردیفی با این فیلترها نیست؛ فیلترها را بردارید.'}
        </Line>
      ) : (
        <Table testId="sarkhati-track-rows" minWidth={720}
          head={['شناسه', 'نماد', 'جهت', 'قیمت × حجم', 'پر شده', 'وضعیت',
            'شناسۀ کارگزاری', 'زمانِ پاسخ', 'کنش']}>
          {rows.map((r: ExecutionRecord) => {
            const ph = phaseOf(r);
            const tr = trail[r.execution_id] as Array<Record<string, unknown>> | undefined;
            return (
              <Tr key={r.execution_id} testId={`sarkhati-row-${r.execution_id}`}>
                <Td num strong>{r.execution_id}</Td>
                <Td num>{r.symbol || '—'}</Td>
                <Td tone={r.side === 'sell' ? 'bad' : 'ok'}>
                  {r.side === 'sell' ? 'فروش' : 'خرید'}
                </Td>
                <Td num>
                  {r.price != null ? fmtInt(r.price) : '—'} ×{' '}
                  {r.quantity != null ? fmtInt(r.quantity) : '—'}
                </Td>
                <Td num>{r.filled_quantity != null ? fmtInt(r.filled_quantity) : '—'}</Td>
                <Td>
                  <Chip tone={CHIP_TONE[ph] ?? 'idle'}
                    title={r.error_code ? String(r.error_detail ?? '') : undefined}>
                    {PHASE_LABEL[ph]}
                  </Chip>
                  {r.error_code ? (
                    <span className="ms-1 text-accent-red"
                      title={String(r.error_detail ?? '')}
                      data-testid={`sarkhati-row-code-${r.execution_id}`}>
                      {CODE_LABEL[String(r.error_code)] ?? String(r.error_code)}
                    </span>
                  ) : null}
                </Td>
                <Td num>{r.broker_order_id ?? '—'}</Td>
                <Td num>{time(r.response_at)}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    <GhostBtn testId={`sarkhati-refresh-${r.execution_id}`} disabled={busy !== ''}
                      title="نظرِ تازهٔ سرور دربارهٔ همین سفارش — هیچ سفارشِ تازه‌ای نمی‌سازد"
                      onClick={() => void ask('refresh', r.execution_id)}>بازخوانی</GhostBtn>
                    {r.status === 'unknown_result' ? (
                      <GhostBtn testId={`sarkhati-reconcile-${r.execution_id}`} disabled={busy !== ''}
                        title="رفعِ ابهام از فهرستِ سفارش‌ها — نه ارسالِ دوباره"
                        onClick={() => void ask('reconcile', r.execution_id)}>
                        <span className="text-accent-yellow">رفعِ ابهام</span>
                      </GhostBtn>
                    ) : null}
                    {canQueue && r.broker_order_id ? (
                      <GhostBtn testId={`sarkhati-queue-${r.execution_id}`} disabled={busy !== ''}
                        title="جایِ صف فقط با دادهٔ واقعی نشان داده می‌شود؛ نبودِ داده یعنی «نمی‌دانیم»"
                        onClick={() => void ask('queue', r.execution_id)}>صف</GhostBtn>
                    ) : null}
                    {canCancel && r.broker_order_id ? (
                      <DangerBtn testId={`sarkhati-cancel-${r.execution_id}`} disabled={busy !== ''}
                        title="لغو فقط با بازخوانیِ «تأیید شد» از کارگزاری قطعی می‌شود"
                        onClick={() => void ask('cancel', r.execution_id)}>لغوِ سفارش</DangerBtn>
                    ) : null}
                    <GhostBtn testId={`sarkhati-audit-${r.execution_id}`} disabled={busy !== ''}
                      title="ردِّپایِ ماندگارِ همین شناسه ازِ سرویس"
                      onClick={() => void readTrail(r.execution_id)}>ردِّپا</GhostBtn>
                  </div>
                  {tr ? (
                    <ul className="mt-1 flex max-w-[46ch] flex-col gap-0.5 rounded-lg bg-bg-primary/50 p-1 text-2xs text-text-muted"
                      data-testid={`sarkhati-trail-${r.execution_id}`}>
                      {tr.map((e, i) => (
                        <li key={i} className="flex flex-wrap gap-x-1.5">
                          <span className="num">{String(e.written_at ?? '')}</span>
                          <span className="font-bold text-text-secondary">{String(e.kind ?? '')}</span>
                          <span>{String(e.status ?? '')}{e.order_state ? `/${String(e.order_state)}` : ''}</span>
                          {e.detail ? <span className="min-w-0 break-words">{String(e.detail)}</span> : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </Td>
              </Tr>
            );
          })}
        </Table>
      )}

      {answer ? (
        <p className={`mt-1.5 text-2xs leading-4 ${TONE[state]}`} data-testid="sarkhati-track-answer">
          {answer}
        </p>
      ) : null}

      {!canCancel ? (
        <Line kind="warn" testId="sarkhati-cancel-unsupported">
          «لغوِ سفارش» درِ این اتصال پشتیبانی نمی‌شود (capabilities.cancel: false) —
          دکمه‌ای برایش ساخته نشده، چون کارگزاری آن را اعلام نکرده است.
        </Line>
      ) : null}

      {Array.isArray(ledger?.open_ids) && ledger.open_ids.length ? (
        <Line kind="warn" testId="sarkhati-open-ids">
          <span className="num font-black">
            {toFaDigits(String(ledger.open_ids.length))}</span>{' '}
          سفارشِ باز برایِ رفعِ ابهام باقی مانده است:{' '}
          <span className="num">{ledger.open_ids.slice(0, 6).join('، ')}</span>
        </Line>
      ) : null}

      <div className="mt-1">
        <Note label="هر کنش دقیقاً چه می‌کند" testId="sarkhati-track-caption">
          «بازخوانی» نظرِ تازهٔ سرور دربارهٔ همان سفارش است و سفارشِ تازه نمی‌سازد.
          «رفعِ ابهام» تنها مسیرِ مجازِ بعدِ timeout است و «نبودنِ ردیف در فهرست»
          ردشدن را ثابت نمی‌کند. «لغو» تنها باِ بازخوانی «تأیید شد» قطعی می‌شود.
          رتبۀِ صف: {String(status?.queue_rank?.why
            ?? 'رتبۀِ رسمی از کارگزاری نخوانده شده — پس زمانِ ارسال و پاسخ نشان داده می‌شود، نه جایِ تخمینی.')}
        </Note>
      </div>
    </section>
  );
}
