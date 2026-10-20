// زمان‌بندیِ ماندگار: ذخیرهٔ اتمیک، بازیابی پس از restart به NEEDS_REVIEW، و
// اجرای dry-run. مسیر زنده از readiness خوانده می‌شود و در این نسخه قفل است.
// هیچ قیمت/حجمی پیش‌فرض ندارد؛ مقدارها فقط از ورودیِ خودِ مالک می‌آیند.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import { orderApi, scheduleApi, useDurableSchedules, type DurableSchedule }
  from '../../lib/orderClient';
import { Chip, GhostBtn, Line, Note, Section, Table, Td, Tr } from './parts';

const STATE: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'idle' | 'live' }> = {
  PREPARED: { label: 'آماده (مسلح نشده)', tone: 'idle' },
  ARMED: { label: 'مسلح', tone: 'warn' },
  RUNNING: { label: 'در حال اجرا', tone: 'live' },
  SUBMITTING: { label: 'در حال ارسال', tone: 'warn' },
  DRY_RUN: { label: 'dry-run اجرا شد', tone: 'ok' },
  ACKNOWLEDGED: { label: 'پذیرفته', tone: 'ok' },
  REJECTED: { label: 'رد شد', tone: 'bad' },
  UNKNOWN: { label: 'نامعلوم — بازبینی', tone: 'bad' },
  CANCELLED: { label: 'لغو شد', tone: 'idle' },
  EXPIRED: { label: 'منقضی', tone: 'idle' },
  SKIPPED: { label: 'رد شد (روز/نماد)', tone: 'idle' },
  MISSED_TARGET: { label: 'هدف از دست رفت', tone: 'bad' },
  NEEDS_REVIEW: { label: 'نیازمند بازبینی', tone: 'bad' },
};

const clock = (ms?: number | null) =>
  ms ? new Date(ms).toLocaleString('fa-IR', { hour12: false }) : '—';

const RESULT: Record<string, { label: string; tone: 'ok' | 'warn' | 'bad' | 'idle' }> = {
  NOT_SENT: { label: 'ارسال نشده', tone: 'idle' },
  REJECTED: { label: 'رد شد', tone: 'bad' },
  ACCEPTED: { label: 'پذیرفته', tone: 'ok' },
  UNKNOWN: { label: 'نامعلوم', tone: 'bad' },
  FILLED: { label: 'پر شد', tone: 'ok' },
  CANCELLED: { label: 'لغو', tone: 'idle' },
};
const toneOf = (s: string) => STATE[s]?.tone ?? 'idle';
const labelOf = (s: string) => STATE[s]?.label ?? s;
const INPUT = 'min-w-0 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 '
  + 'text-xs text-text-primary outline-none focus:border-border-accent';
const STRATEGY_LABEL: Record<string, string> = {
  direct_api: 'Direct API', autoclicker: 'AutoClicker', playwright_dom: 'Playwright/DOM',
  javascript: 'JavaScript', keyboard: 'Keyboard', selenium: 'Selenium',
};
type PfRow = Record<string, unknown>;
type PfView = { strategies?: PfRow[]; ready?: string[]; recommended_dry_run?: string | null;
  live_send?: boolean };

function canArm(s: string) { return s === 'PREPARED'; }
function canCancel(s: string) { return s === 'PREPARED' || s === 'ARMED'; }
function canReset(s: string) { return s === 'NEEDS_REVIEW'; }

export function SarkhatiDurableScheduleCard() {
  const q = useDurableSchedules();
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState('');
  const [isin, setIsin] = useState('');
  const [fullName, setFullName] = useState('');
  const [side, setSide] = useState('buy');
  const [price, setPrice] = useState('');
  const [qty, setQty] = useState('');
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  const [pf, setPf] = useState<PfView | null>(null);
  const [pfBusy, setPfBusy] = useState(false);

  const rows = q.data?.schedules ?? [];
  const readiness = q.data?.readiness;
  const liveReady = readiness?.live_ready === true;

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-durable-schedules'] });
  };

  const fail = (e: unknown) => {
    setTone('bad');
    setAnswer(e instanceof Error ? e.message : String(e));
  };

  const lookup = async () => {
    if (!symbol.trim()) { setTone('warn'); setAnswer('نماد را وارد کنید'); return; }
    setBusy('lookup'); setAnswer('');
    try {
      const res = await scheduleApi.instrument(symbol.trim());
      const inst = (res.instrument ?? {}) as Record<string, unknown>;
      if (res.status === 'success' && inst.isin) {
        setIsin(String(inst.isin));
        setFullName(String(inst.full_name ?? ''));
        setTone('ok');
        setAnswer('هویت محلی پیدا شد؛ ISIN از دادهٔ محلی پر شد');
      } else {
        setTone('bad'); setAnswer(String(res.detail ?? 'هویت پیدا نشد'));
      }
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const create = async () => {
    if (!symbol.trim() || !isin.trim() || !price || !qty || !target) {
      setTone('warn');
      setAnswer('نماد، ISIN، قیمت، تعداد و زمان هدف را کامل کنید');
      return;
    }
    setBusy('create'); setAnswer('');
    try {
      const res = await scheduleApi.create({
        symbol: symbol.trim(), isin: isin.trim(), side,
        price: Number(price), quantity: Number(qty),
        target_local: target, mode: 'dry_run',
        order_type: 'normal', validity: 'day', strategy: 'playwright_dom',
      });
      if (res.status === 'success') {
        setTone('ok');
        setAnswer('ذخیره شد؛ برای اجرای dry-run باید «مسلح» شود');
        refresh();
      } else {
        setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'ذخیره نشد'));
      }
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const arm = async (r: DurableSchedule) => {
    setBusy(r.id); setAnswer('');
    try {
      const res = await scheduleApi.arm(r.id);
      if (res.status === 'success') { setTone('ok'); setAnswer('مسلح شد (dry-run)'); }
      else { setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'مسلح نشد')); }
      refresh();
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const cancel = async (r: DurableSchedule) => {
    setBusy(r.id); setAnswer('');
    try {
      const res = await scheduleApi.cancel(r.id);
      if (res.status === 'success') { setTone('ok'); setAnswer('لغو شد؛ هیچ درخواستی ساخته نشد'); }
      else { setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'لغو نشد')); }
      refresh();
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const reset = async (r: DurableSchedule) => {
    setBusy(r.id); setAnswer('');
    try {
      const res = await scheduleApi.reset(r.id);
      if (res.status === 'success') { setTone('ok'); setAnswer('به PREPARED بازگشت؛ دوباره بازبینی کنید'); }
      else { setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'بازنشانی نشد')); }
      refresh();
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const runPreflight = async () => {
    setPfBusy(true); setAnswer('');
    try {
      const res = await orderApi.strategyPreflightAll();
      const pre = (res.preflight ?? {}) as PfView;
      setPf(pre);
      if (res.status === 'success') {
        setTone('ok');
        setAnswer(`پیش‌فرود موازی: ${toFaDigits(String(pre.ready?.length ?? 0))} روشِ آماده (فقط‌خواندنی؛ هیچ ارسالی نشد)`);
      } else {
        setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'پیش‌فرود ناموفق'));
      }
    } catch (e) { fail(e); } finally { setPfBusy(false); }
  };

  return (
    <Section title="زمان‌بندیِ ماندگار (dry-run)"
      sub="ذخیرهٔ اتمیک؛ پس از restart هیچ سفارشی خودکار اجرا نمی‌شود"
      testId="sarkhati-durable-schedule"
      right={<>
        <Chip tone={liveReady ? 'ok' : 'bad'} title="ارسال زنده تا تأیید قرارداد/نشست قفل است">
          {liveReady ? 'زنده: باز' : 'زنده: قفل'}
        </Chip>
        <Chip tone="live">dry-run</Chip>
      </>}>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          نماد
          <input data-testid="sched-symbol" value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="داروند" className={INPUT} />
        </label>
        <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          ISIN
          <input data-testid="sched-isin" value={isin}
            onChange={(e) => setIsin(e.target.value)}
            placeholder="IRO1…" className={INPUT} />
        </label>
        <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          سمت
          <select data-testid="sched-side" value={side}
            onChange={(e) => setSide(e.target.value)} className={INPUT}>
            <option value="buy">خرید</option>
            <option value="sell">فروش</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          قیمت (ریال)
          <input data-testid="sched-price" value={price} inputMode="decimal"
            onChange={(e) => setPrice(e.target.value)} className={INPUT} />
        </label>
        <label className="flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          تعداد (سهم)
          <input data-testid="sched-qty" value={qty} inputMode="numeric"
            onChange={(e) => setQty(e.target.value)} className={INPUT} />
        </label>
        <label className="col-span-2 flex min-w-0 flex-col gap-0.5 text-3xs text-text-muted">
          زمان هدف (Asia/Tehran)
          <input data-testid="sched-target" type="datetime-local" value={target}
            onChange={(e) => setTarget(e.target.value)} className={INPUT} />
        </label>
        <div className="flex items-end gap-1">
          <GhostBtn testId="sched-lookup" disabled={busy !== ''} onClick={() => void lookup()}>
            استعلام هویت
          </GhostBtn>
          <GhostBtn testId="sched-create" disabled={busy !== ''} onClick={() => void create()}>
            ذخیره
          </GhostBtn>
          <GhostBtn testId="sched-parallel-preflight" disabled={busy !== '' || pfBusy}
            title="Probeِ موازیِ همهٔ روش‌ها؛ فقط‌خواندنی، بدون prepare/trigger"
            onClick={() => void runPreflight()}>
            پیش‌فرود موازی
          </GhostBtn>
        </div>
      </div>
      {fullName ? <Line kind="muted">هویت محلی: {fullName}</Line> : null}

      {readiness?.blockers?.length ? (
        <Line kind="warn" testId="sched-blockers">
          <span className="font-black">ارسال زنده مسدود:</span>{' '}
          {readiness.blockers.slice(0, 3).map((b) => b.detail).join(' · ')}
        </Line>
      ) : null}

      {pf?.strategies?.length ? (
        <details open className="mt-1.5" data-testid="sched-preflight-details">
          <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
            نتیجهٔ پیش‌فرودِ موازی — {toFaDigits(String(pf.ready?.length ?? 0))} آماده
            {pf.recommended_dry_run ? ` · پیشنهادِ dry-run: ${STRATEGY_LABEL[pf.recommended_dry_run] ?? pf.recommended_dry_run}` : ''}
          </summary>
          <Table testId="sched-preflight-rows" minWidth={420} head={['روش', 'وضعیت', 'زمان (ms)']}>
            {(pf.strategies ?? []).map((x) => {
              const sid = String(x.strategy ?? '');
              const ok = x.status === 'success' && x.available !== false;
              return (
                <Tr key={sid} testId={`sched-pf-${sid}`}>
                  <Td strong>{STRATEGY_LABEL[sid] ?? sid}</Td>
                  <Td>
                    <Chip tone={ok ? 'ok' : x.status === 'timeout' ? 'warn' : 'bad'}
                      title={String(x.detail ?? x.code ?? '')}>
                      {ok ? 'آماده' : String(x.status ?? '—')}
                    </Chip>
                  </Td>
                  <Td num>{x.elapsed_ms != null ? toFaDigits(String(x.elapsed_ms)) : '—'}</Td>
                </Tr>
              );
            })}
          </Table>
          <Line kind="muted">فقط Probe؛ هیچ سفارشی آماده یا ارسال نشد.</Line>
        </details>
      ) : null}

      {q.isError ? (
        <Line kind="warn" testId="sched-load-error">
          خواندنِ زمان‌بندی‌ها ناموفق بود؛ هیچ عددی ساخته نمی‌شود.
        </Line>
      ) : rows.length === 0 ? (
        <Line testId="sched-empty">هیچ زمان‌بندیِ ماندگاری ثبت نشده است.</Line>
      ) : (
        <Table testId="sched-rows" minWidth={720}
          head={['شناسه', 'نماد', 'سمت', 'قیمت×تعداد', 'هدف', 'وضعیت', 'نتیجه', 'کنش']}>
          {rows.map((r) => (
            <Tr key={r.id} testId={`sched-row-${r.id}`}>
              <Td num strong>{r.execution_id}</Td>
              <Td strong>{r.symbol}</Td>
              <Td>{r.side === 'sell' ? 'فروش' : 'خرید'}</Td>
              <Td num>{toFaDigits(String(r.price))}×{toFaDigits(String(r.quantity))}</Td>
              <Td num>{clock(r.target_ms)}</Td>
              <Td>
                <Chip tone={toneOf(r.state)} title={r.last_error ?? undefined}>
                  {labelOf(r.state)}
                </Chip>
              </Td>
              <Td>
                {r.result_state ? (
                  <Chip tone={RESULT[r.result_state]?.tone ?? 'idle'}>
                    {RESULT[r.result_state]?.label ?? r.result_state}
                  </Chip>
                ) : '—'}
              </Td>
              <Td>
                <div className="flex flex-wrap items-center gap-1">
                  {canArm(r.state) ? (
                    <GhostBtn testId={`sched-arm-${r.id}`} disabled={busy !== ''}
                      onClick={() => void arm(r)}>مسلح‌کردن</GhostBtn>
                  ) : null}
                  {canCancel(r.state) ? (
                    <GhostBtn testId={`sched-cancel-${r.id}`} disabled={busy !== ''}
                      onClick={() => void cancel(r)}>لغو</GhostBtn>
                  ) : null}
                  {canReset(r.state) ? (
                    <GhostBtn testId={`sched-reset-${r.id}`} disabled={busy !== ''}
                      onClick={() => void reset(r)}>بازبینی</GhostBtn>
                  ) : null}
                </div>
              </Td>
            </Tr>
          ))}
        </Table>
      )}

      {answer ? (
        <p data-testid="sched-answer"
          className={`mt-1.5 text-2xs leading-4 ${
            tone === 'ok' ? 'text-accent-green' : tone === 'bad' ? 'text-accent-red'
              : tone === 'warn' ? 'text-accent-yellow' : 'text-text-secondary'}`}>
          {answer}
        </p>
      ) : null}

      <Note label="قاعدهٔ اجرا" testId="sched-rule">
        فقط «مسلح» اجرا می‌شود. در restart، هر سفارشِ فعال به «نیازمند بازبینی» می‌رود و
        خودکار ارسال نمی‌شود. هدفِ ازدست‌رفته «MISSED_TARGET» می‌شود، نه ارسالِ فوری.
        این نسخه فقط dry-run اجرا می‌کند.
      </Note>
    </Section>
  );
}
