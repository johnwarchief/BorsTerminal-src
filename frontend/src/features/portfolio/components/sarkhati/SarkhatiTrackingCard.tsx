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
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge } from '@shared/components/Badge';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import {
  CODE_LABEL, ORDER_PHASES, PHASE_LABEL, invalidateExecution, orderApi, phaseOf,
  type ExecutionRecord, type ExecutionStatus, type LedgerView,
} from '../../lib/orderClient';
import { TONE, safeError, summarize, type ActionState } from '../../lib/orderActionView';

const TONE_BY_PHASE: Record<string, 'green' | 'red' | 'yellow' | 'gray' | 'orange' | 'blue'> = {
  accepted: 'green', filled: 'green', partial: 'blue', submitted: 'blue',
  scheduled: 'yellow', rejected: 'red', errored: 'red', cancelled: 'gray',
  unknown: 'orange', draft: 'gray', preflight: 'gray', idle: 'gray', sending: 'yellow',
};

const time = (sec?: number | null) =>
  sec ? new Date(sec * 1000).toLocaleTimeString('fa-IR', { hour12: false }) : '—';

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

  return (
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-tracking-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">نتیجۀِ درخواست‌ها</h4>
        <input value={fSym} onChange={(e) => setFSym(e.target.value)}
          placeholder="فیلترِ نماد" aria-label="فیلترِ نماد"
          data-testid="sarkhati-filter-symbol"
          className="w-24 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-3xs" />
        <select value={fPhase} onChange={(e) => setFPhase(e.target.value)}
          aria-label="فیلترِ وضعیت" data-testid="sarkhati-filter-phase"
          className="rounded-lg border border-border-c bg-bg-primary px-1 py-0.5 text-3xs">
          <option value="">همۀِ وضعیت‌ها</option>
          {ORDER_PHASES.map((p) => (<option key={p} value={p}>{PHASE_LABEL[p]}</option>))}
        </select>
        <input value={fId} onChange={(e) => setFId(e.target.value)}
          placeholder="شناسۀِ اجرا" aria-label="فیلترِ شناسۀِ اجرا"
          data-testid="sarkhati-filter-id"
          className="w-32 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-3xs" />
        <span className="ms-auto text-3xs text-text-muted">
          {toFaDigits(String(rows.length))} از {toFaDigits(String((ledger?.records ?? []).length))} رکورد
        </span>
      </div>

      {!endpointPresent ? (
        <p className="text-3xs text-accent-red" data-testid="sarkhati-track-noservice">
          دفترِ اجرا خوانده نشد — این «رکوردی نیست» نیست، «پاسخی نرسید» است.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-3xs text-text-muted" data-testid="sarkhati-track-empty">
          رکوردی درِ دفترِ اجرا نیست (یا با این فیلترها نمی‌خواند).
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-3xs" data-testid="sarkhati-track-rows">
            <thead>
              <tr className="text-text-muted">
                <th className="text-start font-bold">شناسه</th>
                <th className="text-start font-bold">نماد</th>
                <th className="text-start font-bold">جهت</th>
                <th className="text-start font-bold">قیمت × حجم</th>
                <th className="text-start font-bold">پر شده</th>
                <th className="text-start font-bold">وضعیت</th>
                <th className="text-start font-bold">شناسۀ کارگزاری</th>
                <th className="text-start font-bold">زمانِ پاسخ</th>
                <th className="text-start font-bold">کنش</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: ExecutionRecord) => {
                const ph = phaseOf(r);
                return (
                  <tr key={r.execution_id} className="border-t border-border-c/40 align-top"
                    data-testid={`sarkhati-row-${r.execution_id}`}>
                    <td className="num py-1 font-bold text-text-primary">{r.execution_id}</td>
                    <td className="num">{r.symbol || '—'}</td>
                    <td className={r.side === 'sell' ? 'text-accent-red' : 'text-accent-green'}>
                      {r.side === 'sell' ? 'فروش' : 'خرید'}
                    </td>
                    <td className="num">
                      {r.price != null ? fmtInt(r.price) : '—'} ×{' '}
                      {r.quantity != null ? fmtInt(r.quantity) : '—'}
                    </td>
                    <td className="num">{r.filled_quantity != null ? fmtInt(r.filled_quantity) : '—'}</td>
                    <td>
                      <Badge tone={TONE_BY_PHASE[ph] ?? 'gray'}
                        title={r.error_code ? String(r.error_detail ?? '') : undefined}>
                        {PHASE_LABEL[ph]}
                      </Badge>
                      {r.error_code ? (
                        <span className="ms-1 text-accent-red"
                          title={String(r.error_detail ?? '')}
                          data-testid={`sarkhati-row-code-${r.execution_id}`}>
                          {CODE_LABEL[String(r.error_code)] ?? String(r.error_code)}
                        </span>
                      ) : null}
                    </td>
                    <td className="num">{r.broker_order_id ?? '—'}</td>
                    <td className="num">{time(r.response_at)}</td>
                    <td className="text-start">
                      <div className="flex flex-wrap gap-1">
                        <button type="button" disabled={busy !== ''}
                          onClick={() => void ask('refresh', r.execution_id)}
                          data-testid={`sarkhati-refresh-${r.execution_id}`}
                          className="rounded-lg border border-border-c px-1.5 py-0.5 font-bold text-text-secondary hover:bg-bg-card">
                          بازخوانی
                        </button>
                        {r.status === 'unknown_result' ? (
                          <button type="button" disabled={busy !== ''}
                            onClick={() => void ask('reconcile', r.execution_id)}
                            data-testid={`sarkhati-reconcile-${r.execution_id}`}
                            className="rounded-lg border border-accent-orange/40 px-1.5 py-0.5 font-bold text-accent-orange hover:bg-accent-susp-bg">
                            رفعِ ابهام
                          </button>
                        ) : null}
                        {canQueue && r.broker_order_id ? (
                          <button type="button" disabled={busy !== ''}
                            onClick={() => void ask('queue', r.execution_id)}
                            data-testid={`sarkhati-queue-${r.execution_id}`}
                            className="rounded-lg border border-border-c px-1.5 py-0.5 font-bold text-text-secondary hover:bg-bg-card">
                            صف
                          </button>
                        ) : null}
                        {canCancel && r.broker_order_id ? (
                          <button type="button" disabled={busy !== ''}
                            onClick={() => void ask('cancel', r.execution_id)}
                            data-testid={`sarkhati-cancel-${r.execution_id}`}
                            className="rounded-lg border border-accent-red/40 px-1.5 py-0.5 font-bold text-accent-red hover:bg-accent-red/10">
                            لغوِ سفارش
                          </button>
                        ) : null}
                        <button type="button" disabled={busy !== ''}
                          onClick={() => void readTrail(r.execution_id)}
                          data-testid={`sarkhati-audit-${r.execution_id}`}
                          className="rounded-lg border border-border-c px-1.5 py-0.5 font-bold text-text-secondary hover:bg-bg-card">
                          ردِّپا
                        </button>
                      </div>
                      {trail[r.execution_id] ? (
                        <ul className="mt-1 flex flex-col gap-0.5 text-3xs text-text-muted"
                          data-testid={`sarkhati-trail-${r.execution_id}`}>
                          {(trail[r.execution_id] as Array<Record<string, unknown>>).map((e, i) => (
                            <li key={i} className="flex flex-wrap gap-1.5">
                              <span>{String(e.written_at ?? '')}</span>
                              <span className="font-bold">{String(e.kind ?? '')}</span>
                              <span>{String(e.status ?? '')}{e.order_state ? `/${String(e.order_state)}` : ''}</span>
                              {e.detail ? <span>{String(e.detail)}</span> : null}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {answer ? (
        <p className={`text-3xs leading-4 ${TONE[state]}`} data-testid="sarkhati-track-answer">
          {answer}
        </p>
      ) : null}

      <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-track-caption">
        «بازخوانی» نظرِ تازهٔ سرور دربارهٔ همان سفارش است و سفارشِ تازه نمی‌سازد.
        «رفعِ ابهام» تنها مسیرِ مجازِ بعدِ timeout است. «لغو» تنها باِ بازخوانی
        «تأیید شد» می‌گیرد. و رتبۀِ صف: {String(status?.queue_rank?.why
          ?? 'رتبۀِ رسمی از کارگزاری نخوانده شده — پس زمانِ ارسال و پاسخ نشان داده می‌شود، نه جایِ تخمینی.')}.
      </p>
      {!canCancel ? (
        <p className="text-3xs leading-4 text-accent-yellow" data-testid="sarkhati-cancel-unsupported">
          «لغوِ سفارش» درِ این اتصال پشتیبانی نمی‌شود (capabilities.cancel: false) —
          دکمه‌ای برایش ساخته نشده، چون کارگزاری آن را اعلام نکرده است.
        </p>
      ) : null}
      {Array.isArray(ledger?.open_ids) && ledger.open_ids.length ? (
        <p className="text-3xs text-accent-orange" data-testid="sarkhati-open-ids">
          {toFaDigits(String(ledger.open_ids.length))} سفارشِ باز برایِ رفعِ ابهام باقی
          مانده است: {ledger.open_ids.slice(0, 6).join('، ')}
        </p>
      ) : null}
    </div>
  );
}
