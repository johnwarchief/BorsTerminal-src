// cockpit وضعیت/Preflight/Mock — یک پنل، نه دیوارِ کارت.
// دادهٔ واقعی از API؛ هر سناریوی Mock با برچسب MOCK و بی‌مسیرِ سفارش.
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import {
  cockpitApi, useCockpitRunDetail, useCockpitRuns, useCockpitStatus, useOfferings,
  type CockpitEvent, type CockpitGate, type CockpitRun, type LedgerView,
} from '../../lib/orderClient';
import { SarkhatiDurableScheduleCard } from './SarkhatiDurableScheduleCard';
import { SarkhatiOfferingsCard } from './SarkhatiOfferingsCard';
import { SarkhatiScheduleCard } from './SarkhatiScheduleCard';
import { Chip, GhostBtn, Line, Note, Section, Table, Td, Tr } from './parts';

const INPUT = 'min-w-0 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 '
  + 'text-xs text-text-primary outline-none focus:border-border-accent';
const GATE_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = {
  PASS: 'ok', FAIL: 'bad', BLOCKED: 'bad', UNVERIFIED: 'warn',
  NOT_RUN: 'idle', UNKNOWN: 'warn', UNKNOWN_HOLD: 'bad', INTERRUPTED: 'warn',
  SKIPPED_BUDGET: 'warn', IDEMPOTENT: 'ok', STOPPED: 'warn', RUNNING: 'warn',
};
const RUN_LABEL: Record<string, string> = {
  PASS: 'موفق', FAIL: 'ناموفق', BLOCKED: 'مسدود', UNKNOWN: 'نامعلوم',
  UNKNOWN_HOLD: 'نگه‌داشت UNKNOWN', INTERRUPTED: 'نیازمند بررسی',
  STOPPED: 'متوقف', RUNNING: 'در حال اجرا', IDEMPOTENT: 'تکراریِ امن',
};
const clock = (ms?: number | null) => {
  if (!ms) return '—';
  const v = ms > 1e12 ? ms : ms * 1000;
  return new Date(v).toLocaleTimeString('fa-IR', { hour12: false });
};
const fa = (v: unknown) => toFaDigits(String(v ?? 0));
const gateTone = (s: string) => GATE_TONE[s] ?? 'warn';
const runTone = (s: string) => GATE_TONE[s] ?? 'warn';

function GateRow({ gate }: { gate: CockpitGate }) {
  return (
    <Tr testId={`cockpit-gate-${gate.id}`}>
      <Td strong>{gate.label}<span className="ms-1 text-text-muted">({gate.id})</span></Td>
      <Td><Chip tone={gateTone(gate.status)}>{gate.status}</Chip></Td>
      <Td>
        <span className="text-text-secondary">{gate.reason}</span>
        <span className="block text-3xs text-text-muted">
          {gate.evidence}{gate.age_s != null ? ` · عمر ${fa(Math.round(gate.age_s))}s` : ''}
          {gate.source ? ` · منبع ${gate.source}` : ''}
        </span>
      </Td>
    </Tr>
  );
}

function EventsTable({ events, testId = 'cockpit-events' }: {
  events: CockpitEvent[]; testId?: string;
}) {
  if (!events.length) return <Line kind="muted" testId="cockpit-events-empty">رویدادی برای این اجرا ثبت نشده است.</Line>;
  return (
    <Table testId={testId} minWidth={760}
      head={['زمان', 'مرحله', 'نتیجه', 'مدت', 'جزئیات']}>
      {events.map((e) => (
        <Tr key={e.seq}>
          <Td num>{clock(e.at)}</Td>
          <Td strong>{e.phase}</Td>
          <Td><Chip tone={gateTone(e.status)}>{e.status}</Chip></Td>
          <Td num>{e.duration_ms == null ? '—' : `${fa(Math.round(e.duration_ms))}ms`}</Td>
          <Td>{e.detail}</Td>
        </Tr>
      ))}
    </Table>
  );
}

export function SarkhatiCockpitCard({ ledger }: { ledger: LedgerView | null | undefined }) {
  const qc = useQueryClient();
  const statusQ = useCockpitStatus();
  const runsQ = useCockpitRuns();
  const offersQ = useOfferings();
  const status = statusQ.data;
  const gates = status?.gates ?? [];
  const blocking = gates.filter((g) => g.status !== 'PASS');
  const offers = offersQ.data?.offerings ?? [];
  const [selOffer, setSelOffer] = useState('');
  const [price, setPrice] = useState('');
  const [qty, setQty] = useState('');
  const [pf, setPf] = useState<Record<string, unknown> | null>(null);
  const [scenario, setScenario] = useState('success');
  const [selectedRun, setSelectedRun] = useState('');
  const [lastRun, setLastRun] = useState<CockpitRun | null>(null);
  const [answer, setAnswer] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  const [busy, setBusy] = useState('');

  const verified = useMemo(() => offers.filter((o) => o.status === 'VERIFIED'), [offers]);
  useEffect(() => {
    if (!selOffer && verified.length) setSelOffer(verified[0].id);
  }, [selOffer, verified]);

  const runs = runsQ.data?.runs ?? [];
  const scenarios = runsQ.data?.scenarios ?? [];
  const latestRun = runs[0] as CockpitRun | undefined;
  const activeRun = runs.find((r) => r.id === selectedRun)
    ?? (lastRun && lastRun.id === selectedRun ? lastRun : latestRun);
  useEffect(() => {
    if (!selectedRun && latestRun) setSelectedRun(latestRun.id);
  }, [latestRun, selectedRun]);
  const detailQ = useCockpitRunDetail(selectedRun);
  useEffect(() => {
    const d = detailQ.data?.run;
    if (d && d.id === selectedRun) setLastRun(d);
  }, [detailQ.data?.run, selectedRun]);
  const events = (detailQ.data?.run?.events
    ?? activeRun?.events ?? runsQ.data?.events ?? []) as CockpitEvent[];
  const liveRun = activeRun?.status === 'RUNNING';

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-cockpit-status'] });
    void qc.invalidateQueries({ queryKey: ['execution-cockpit-runs'] });
    void qc.invalidateQueries({ queryKey: ['execution-cockpit-run'] });
    void qc.invalidateQueries({ queryKey: ['execution-offerings'] });
  };

  const runPreflight = async () => {
    setBusy('preflight'); setAnswer('');
    try {
      const res = await cockpitApi.preflight({
        offering_id: selOffer, price: price || null, quantity: qty || null,
        max_age_s: 3600,
      });
      const rep = (res.preflight ?? {}) as Record<string, unknown>;
      setPf(rep);
      if (res.status === 'success' && rep.ok === true) {
        setTone('ok'); setAnswer('Preflight این عرضه سبز است؛ هنوز ارسال زنده مجاز نیست.');
      } else {
        setTone('bad');
        setAnswer(String(rep.reason || rep.action || 'Preflight مسدود است؛ Gateهای قرمز را ببینید.'));
      }
      refresh();
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const runMock = async () => {
    setBusy('run'); setAnswer('');
    try {
      const res = await cockpitApi.run({ scenario, offering_id: selOffer || undefined,
        price: price || undefined, quantity: qty || undefined });
      const run = res.run as CockpitRun | undefined;
      if (res.status === 'success' && run) {
        setLastRun(run);
        setSelectedRun(run.id); setTone(run.status === 'PASS' ? 'ok' : 'warn');
        setAnswer(`آزمون ${run.id} · ${RUN_LABEL[run.status] ?? run.status} · MOCK`);
      } else {
        setTone('bad'); setAnswer(String(res.code ?? res.detail ?? 'آزمون اجرا نشد'));
      }
      refresh();
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const stopMock = async () => {
    if (!activeRun) return;
    setBusy('stop');
    try {
      const res = await cockpitApi.stop(activeRun.id);
      const rs = String(res.run_status ?? '');
      setTone('warn');
      setAnswer(String(res.status === 'success'
        ? (res.unchanged ? `اجرای ${activeRun.id} قبلاً ${rs} است؛ توقف لازم نیست`
          : `توقف ${activeRun.id} ثبت شد؛ وضعیت نهایی از Timeline خوانده می‌شود`)
        : (res.detail ?? 'توقف ممکن نشد')));
      refresh();
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const downloadReport = async () => {
    setBusy('report');
    try {
      const rep = await cockpitApi.report(activeRun?.id ?? '');
      const blob = new Blob([JSON.stringify(rep, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `sarkhati-cockpit-${Date.now()}.json`; a.click();
      URL.revokeObjectURL(url);
      setTone('ok'); setAnswer('گزارش JSON دریافت شد؛ token/cookie در آن نیست.');
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const pfChecks = (pf?.checks ?? []) as { name: string; state: string; detail: string;
    source?: string; observed_at?: number | null }[];

  return (
    <Section title="آمادگی و مانیتورینگ سرخطی"
      sub="یک وضعیت، Gateها، Preflight و آزمونِ Mock — live خاموش"
      testId="sarkhati-cockpit"
      tone={status?.live_ready ? 'default' : 'alarm'}
      right={<>
        <Chip tone={status?.live_ready ? 'ok' : 'bad'} testId="cockpit-live-state">
          {status?.live_ready ? 'Live آماده' : 'Live مسدود'}
        </Chip>
        <Chip tone="idle" testId="cockpit-mode">MOCK / بدون ارسال</Chip>
      </>}>
      {statusQ.isPending ? <Line kind="muted" testId="cockpit-loading">در حال خواندن وضعیت…</Line> : null}
      {statusQ.isError ? <Line kind="error" testId="cockpit-error">وضعیت cockpit خوانده نشد؛ هیچ Gateای سبز فرض نمی‌شود.</Line> : null}

      <div className="grid grid-cols-1 gap-1 rounded-lg border border-border-c/50 bg-bg-secondary/30 px-2 py-1.5 md:grid-cols-[auto_1fr]">
        <div className="flex flex-wrap items-center gap-1">
          <Chip tone="bad" testId="cockpit-overall">
            {status?.live_ready ? 'آماده' : `${fa(status?.failing_count ?? 0)} Gate باز`}
          </Chip>
          <span className="text-2xs text-text-muted">نسخهٔ {status?.app_version ?? '—'}</span>
        </div>
        <p className="min-w-0 text-2xs leading-5 text-text-secondary" data-testid="cockpit-next-action">
          <b className="text-text-primary">اقدام بعدی: </b>
          {status?.next_action || 'وضعیت را تازه کنید؛ Gateهای باز را بررسی کنید.'}
        </p>
      </div>

      <div className="mt-1.5 flex flex-wrap gap-1" data-testid="cockpit-components">
        <Chip tone={statusQ.isError ? 'bad' : 'ok'}>API: {statusQ.isError ? 'قطع' : 'پاسخ'}</Chip>
        <Chip tone="ok">DB: {fa(Object.values((status?.components?.db ?? {}) as Record<string, boolean>).filter(Boolean).length)}/4</Chip>
        <Chip tone={status?.components?.browser_host === 'healthy' ? 'ok' : 'warn'}>
          host: {String(status?.components?.browser_host ?? '—')}
        </Chip>
        <Chip tone={status?.components?.session === 'proven' ? 'ok' : 'warn'}>
          دسترسی: {String(status?.components?.session ?? '—')}
        </Chip>
        <Chip tone="idle">عرضه: {fa(offers.length)} / تأییدشده {fa(verified.length)}</Chip>
        <Chip tone={(status?.components?.unknown_holds as number || 0) > 0 ? 'bad' : 'idle'}>
          UNKNOWN_HOLD: {fa(status?.components?.unknown_holds ?? 0)}
        </Chip>
      </div>

      <div className="mt-1.5 flex flex-wrap gap-1" data-testid="cockpit-gates">
        {blocking.map((g) => (
          <span key={g.id} data-testid={`cockpit-gate-chip-${g.id}`}
            className="inline-flex items-center gap-1 rounded-md border border-border-c/50 bg-bg-secondary/30 px-1.5 py-[1px]">
            <Chip tone={gateTone(g.status)}>{g.status}</Chip>
            <span className="text-3xs text-text-secondary">{g.label}</span>
          </span>
        ))}
        {!blocking.length && gates.length ? <Chip tone="ok" testId="cockpit-gates-all-pass">همهٔ Gateها PASS</Chip> : null}
        {!gates.length ? <Line kind="muted" testId="cockpit-gates-empty">Gateها هنوز خوانده نشده‌اند.</Line> : null}
      </div>
      <details className="mt-1 rounded-lg border border-border-c/50 px-2 py-1" data-testid="cockpit-gates-details">
        <summary className="cursor-pointer text-3xs font-bold text-accent-blue">
          دلیل هر Gate · {fa(blocking.length)} باز از {fa(gates.length)}
        </summary>
        <div className="mt-1">
          <Table testId="cockpit-gates-all" minWidth={620} head={['Gate', 'وضعیت', 'دلیل/شاهد']}>
            {gates.map((g) => <GateRow key={g.id} gate={g} />)}
          </Table>
        </div>
      </details>

      <div className="mt-1.5 grid grid-cols-1 items-start gap-1.5 lg:grid-cols-2">
        <details className="rounded-lg border border-border-c/50 px-2 py-1.5" data-testid="cockpit-preflight-section">
          <summary className="flex cursor-pointer flex-wrap items-center gap-1 text-2xs font-black text-text-primary">
            مرکز Preflight
            {pf ? <Chip tone={pf.ok === true ? 'ok' : 'bad'} testId="cockpit-preflight-state">
              {pf.ok === true ? 'PASS' : String(pf.state ?? 'BLOCKED')}
            </Chip> : null}
            <span className="ms-auto text-3xs font-normal text-accent-blue">بازکردن</span>
          </summary>
          <div className="mt-1.5 grid grid-cols-2 gap-1 sm:grid-cols-4">
            <label className="col-span-2 flex flex-col gap-0.5 text-3xs text-text-muted">عرضه
              <select className={INPUT} value={selOffer} onChange={(e) => setSelOffer(e.target.value)}
                data-testid="cockpit-offer-select">
                <option value="">—</option>
                {offers.map((o) => <option key={o.id} value={o.id}>{o.symbol} · {o.status}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">قیمت
              <input className={INPUT} value={price} onChange={(e) => setPrice(e.target.value)}
                data-testid="cockpit-price" inputMode="decimal" />
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">تعداد
              <input className={INPUT} value={qty} onChange={(e) => setQty(e.target.value)}
                data-testid="cockpit-qty" inputMode="numeric" />
            </label>
            <div className="col-span-2 flex items-end gap-1 sm:col-span-4">
              <GhostBtn testId="cockpit-run-preflight" disabled={busy !== ''}
                onClick={() => void runPreflight()}>اجرای Preflight</GhostBtn>
            </div>
          </div>
          {pfChecks.length ? (
            <Table testId="cockpit-preflight-checks" minWidth={560}
              head={['بررسی', 'وضعیت', 'جزئیات', 'منبع']}>
              {pfChecks.map((c) => (
                <Tr key={c.name} testId={`cockpit-check-${c.name}`}>
                  <Td strong>{c.name}</Td>
                  <Td><Chip tone={gateTone(c.state)}>{c.state}</Chip></Td>
                  <Td>{c.detail}</Td>
                  <Td>{c.source || '—'}{c.observed_at ? ` · ${clock(c.observed_at)}` : ''}</Td>
                </Tr>
              ))}
            </Table>
          ) : pf ? <Line kind="muted" testId="cockpit-preflight-reason">{String(pf.reason ?? pf.action ?? 'Preflight نتیجه‌ای ندارد')}</Line> : null}
        </details>

        <details className="rounded-lg border border-border-c/50 px-2 py-1.5" data-testid="cockpit-mock-section">
          <summary className="flex cursor-pointer flex-wrap items-center gap-1 text-2xs font-black text-text-primary">
            اجرای Mock درون‌برنامه
            {activeRun ? <Chip tone={runTone(activeRun.status)} testId="cockpit-run-state">
              {activeRun.id} · {RUN_LABEL[activeRun.status] ?? activeRun.status}
            </Chip> : <Chip tone="idle" testId="cockpit-run-state">بدون اجرا</Chip>}
            <span className="ms-auto text-3xs font-normal text-accent-blue">بازکردن</span>
          </summary>
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <select className={INPUT} value={scenario} onChange={(e) => setScenario(e.target.value)}
              data-testid="cockpit-scenario">
              {scenarios.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <GhostBtn testId="cockpit-run-mock"
              disabled={busy !== '' || !scenarios.length || liveRun}
              onClick={() => void runMock()}>اجرای سناریو</GhostBtn>
            <GhostBtn testId="cockpit-stop-mock" disabled={!liveRun || busy !== ''}
              onClick={() => void stopMock()}>توقف آزمون</GhostBtn>
            <GhostBtn testId="cockpit-report" disabled={busy !== ''}
              onClick={() => void downloadReport()}>گزارش JSON</GhostBtn>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <Chip tone="idle">MOCK · بدون ارسال</Chip>
            {activeRun?.summary?.order_sent === false ? <Chip tone="ok">order_sent=false</Chip> : null}
            {activeRun?.summary?.retry_performed === false ? <Chip tone="ok">بدون retry</Chip> : null}
            <select className={`${INPUT} ms-auto`} value={selectedRun}
              onChange={(e) => setSelectedRun(e.target.value)} data-testid="cockpit-run-select">
              <option value="">آخرین اجرا</option>
              {runs.map((r) => <option key={r.id} value={r.id}>{clock(r.started_at)} · {r.scenario} · {r.status}</option>)}
            </select>
          </div>
          <EventsTable events={events} />
          <Note label="قاعدهٔ ایمنی Mock" testId="cockpit-mock-rule">
            این مسیر فقط رویدادهای Mock در `execution_cockpit.db` می‌نویسد؛ هیچ
            رزرو واقعی، هیچ API سفارش و هیچ fallback زنده‌ای در آن نیست. نتیجهٔ
            شبیه‌سازی با «نتیجهٔ کارگزاری» یکی نیست.
          </Note>
        </details>
      </div>

      {answer ? <Line kind={tone === 'bad' ? 'error' : tone === 'ok' ? 'ok' : tone === 'warn' ? 'warn' : 'muted'}
        testId="cockpit-answer">{answer}</Line> : null}

      <details className="mt-1.5 rounded-lg border border-border-c/50 px-2 py-1.5" data-testid="cockpit-offerings">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          مدیریت عرضه، بودجه و رزروها
        </summary>
        <div className="mt-1.5"><SarkhatiOfferingsCard /></div>
      </details>
      <details className="mt-1.5 rounded-lg border border-border-c/50 px-2 py-1.5" data-testid="cockpit-schedules">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          زمان‌بندی ماندگار و ابزارهای قدیمی
        </summary>
        <div className="mt-1.5 flex flex-col gap-2">
          <SarkhatiDurableScheduleCard />
          <SarkhatiScheduleCard ledger={ledger} />
        </div>
      </details>
    </Section>
  );
}
