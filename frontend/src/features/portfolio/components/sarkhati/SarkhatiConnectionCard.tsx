// اتصال: یک وضعیت، شش قدمِ قابل‌فهم، و جزئیاتِ فنیِ پنهان.
// «پنجره باز شد»، «وارد شدم» و «API تأیید شد» سه چیزند و اینجا سه سطر جدا دارند.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import {
  browserHostApi, connectionApi, PORTFOLIO_LABEL, PORTFOLIO_STATES,
  TRAFFIC_LABEL, TRAFFIC_MODES, useBrokerConnect, useBrowserHost,
  useConnectionDiagnosis, useExecutionPortfolio,
  type ConnectionStep, type PortfolioState, type TrafficMode,
} from '../../lib/orderClient';
import { ConnectBrokerRow } from '../ConnectBrokerRow';
import { SarkhatiConnectionSettings } from './SarkhatiConnectionSettings';
import { SarkhatiSessionForm } from './SarkhatiSessionForm';
import { Chip, Field, GhostBtn, Line, Note, Section } from './parts';

const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'idle'> = {
  PASS: 'ok', FAIL: 'bad', BLOCKED: 'bad', UNVERIFIED: 'warn', NOT_RUN: 'idle',
};
const PRIMARY = ['backend', 'host', 'cdp', 'page', 'login', 'session'];
const STEP_NUM: Record<string, number> = {
  backend: 1, host: 2, cdp: 3, page: 4, login: 5, session: 6,
};

function StepRow({ step }: { step: ConnectionStep }) {
  const n = STEP_NUM[step.key] ?? 7;
  return (
    <li data-testid={`connection-step-${step.key}`}
      className="flex min-w-0 items-start gap-2 border-b border-border-c/25 py-1 last:border-0">
      <span className="num mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-md
        border border-border-c bg-bg-primary text-3xs font-black text-text-muted">
        {toFaDigits(n)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-2xs font-black text-text-primary">{step.title}</span>
          <Chip tone={TONE[step.status] ?? 'warn'}>{step.status}</Chip>
          {step.duration_ms != null ? (
            <span className="num text-3xs text-text-muted">{toFaDigits(Math.round(step.duration_ms))}ms</span>
          ) : null}
        </div>
        <p className="text-3xs leading-4 text-text-secondary" data-testid={`connection-reason-${step.key}`}>
          {step.reason}
        </p>
        {step.evidence ? (
          <p className="text-3xs leading-4 text-text-muted" dir="ltr" title={step.evidence}>
            {step.evidence}
          </p>
        ) : null}
        {step.action ? (
          <p className="text-3xs leading-4 text-accent-yellow">اقدام: {step.action}</p>
        ) : null}
      </div>
    </li>
  );
}

export function SarkhatiConnectionCard() {
  const qc = useQueryClient();
  const q = useConnectionDiagnosis();
  const hostQ = useBrowserHost();
  const c = useBrokerConnect().data;
  const pf = useExecutionPortfolio().data;
  const traffic = (TRAFFIC_MODES as readonly string[]).includes(String(c?.traffic_mode))
    ? String(c?.traffic_mode) as TrafficMode : 'blocked';
  const pfState = (PORTFOLIO_STATES as readonly string[]).includes(String(pf?.status))
    ? String(pf?.status) as PortfolioState : null;
  const pfRows = Array.isArray(pf?.rows) ? (pf?.rows?.length ?? null) : null;
  const pfAsOf = pf?.as_of ?? pf?.cached_at ?? null;
  const pfError = pf?.error ?? null;
  const d = q.data;
  const steps = d?.steps ?? [];
  const primary = steps.filter((s) => PRIMARY.includes(s.key));
  const extra = steps.filter((s) => !PRIMARY.includes(s.key));
  const hostState = (hostQ.data?.host ?? {}) as Record<string, unknown>;
  const hostHealthy = hostState.healthy === true;
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-connection-diagnosis'] });
    void qc.invalidateQueries({ queryKey: ['execution-browser-host'] });
    void qc.invalidateQueries({ queryKey: ['execution-connect'] });
  };

  const startHost = async () => {
    setBusy('host'); setNote('');
    try {
      const r = await browserHostApi.start();
      setTone(r.status === 'success' ? 'ok' : 'bad');
      setNote(r.status === 'success'
        ? 'پنجرهٔ اتصال باز شد؛ حالا خودتان در همان پنجره وارد EasyTrader شوید.'
        : String(r.detail ?? r.code ?? 'host باز نشد'));
      refresh();
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const check = async () => {
    setBusy('check'); setNote('');
    try {
      const r = await connectionApi.verify();
      setTone(r.status === 'success' ? 'warn' : 'bad');
      setNote(r.state_label || 'وضعیت تازه شد');
      refresh();
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const stopHost = async () => {
    setBusy('stop'); setNote('');
    try {
      const r = await browserHostApi.stop();
      setTone(r.status === 'success' ? 'warn' : 'bad');
      setNote(r.status === 'success' ? 'host بسته شد' : String(r.detail ?? 'بستن ممکن نشد'));
      refresh();
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const download = async () => {
    setBusy('report');
    try {
      const rep = await connectionApi.report();
      const blob = new Blob([JSON.stringify(rep, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `sarkhati-connection-${Date.now()}.json`; a.click();
      URL.revokeObjectURL(url);
      setTone('ok'); setNote('گزارش تشخیصی دریافت شد؛ token/cookie در آن نیست.');
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const stateTone = d?.state === 'CONNECTED' ? 'ok'
    : d?.state === 'HOST_DOWN' || d?.state === 'CDP_DOWN' || d?.state === 'PAGE_MISSING' ? 'bad'
      : 'warn';

  return (
    <Section title="اتصال کارگزاری" testId="sarkhati-connection-card"
      sub="Backend ← host ← CDP ← صفحه ← نشست ← API"
      tone={d?.state === 'CONNECTED' ? 'quiet' : 'default'}
      right={<Chip tone={stateTone} testId="sarkhati-connection-state">
        {d?.state_label ?? 'وضعیت اتصال خوانده نشد'}
      </Chip>}>
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border-c/50
        bg-bg-secondary/30 px-2 py-1.5">
        <Chip tone={hostHealthy ? 'ok' : 'warn'} testId="sarkhati-host-state">
          host: {hostHealthy ? 'آماده' : 'بسته'}
        </Chip>
        <Chip tone={d?.adapter === 'easytrader' ? 'ok' : 'warn'} testId="sarkhati-adapter-state">
          آداپتور: {d?.adapter ?? '—'}
        </Chip>
        <span className="text-2xs text-text-muted" data-testid="sarkhati-connection-next">
          اقدام بعدی: {d?.next_action || 'وضعیت را بررسی کنید'}
        </span>
        <div className="ms-auto flex flex-wrap items-center gap-1">
          <GhostBtn testId="connection-open-host" disabled={busy !== '' || hostHealthy}
            onClick={() => void startHost()}>باز کردن پنجرهٔ اتصال</GhostBtn>
          <GhostBtn testId="connection-check" disabled={busy !== ''}
            onClick={() => void check()}>بررسی وضعیت</GhostBtn>
          <GhostBtn testId="connection-stop-host" disabled={busy !== '' || !hostHealthy}
            onClick={() => void stopHost()}>بستن host</GhostBtn>
          <GhostBtn testId="connection-report" disabled={busy !== ''}
            onClick={() => void download()}>گزارش تشخیصی</GhostBtn>
        </div>
      </div>

      {q.isPending ? <Line kind="muted" testId="connection-loading">در حال خواندن مراحل اتصال…</Line> : null}
      {q.isError ? <Line kind="error" testId="connection-error">
        تشخیص اتصال خوانده نشد؛ هیچ مرحله‌ای سبز فرض نمی‌شود.
      </Line> : null}
      {!q.isPending && !q.isError && !steps.length ? (
        <Line kind="warn" testId="connection-no-diagnosis">
          تشخیصِ مرحله‌ای در دسترس نیست؛ «بررسی وضعیت» را بزنید.
        </Line>
      ) : null}

      {primary.length ? (
        <ol className="mt-1.5 rounded-lg border border-border-c/50 px-2 py-1"
          data-testid="connection-steps">
          {primary.map((s) => <StepRow key={s.key} step={s} />)}
        </ol>
      ) : null}

      {d?.state === 'BROWSER_READY_API_UNVERIFIED' ? (
        <Line kind="warn" testId="connection-browser-ready-api-unverified">
          مرورگر آماده است؛ اتصال API کارگزاری هنوز تأیید نشده است. بازبودن صفحه یا
          ورود شما به‌تنهایی «اتصال API» نیست.
        </Line>
      ) : null}

      {d?.state === 'LOGIN_REQUIRED' ? (
        <Line kind="warn" testId="connection-login-needed">
          در پنجرهٔ host وارد EasyTrader شوید؛ پس از ورود «بررسی وضعیت» را بزنید.
          این برنامه رمز/CAPTCHA/MFA را نمی‌پرسد و دور نمی‌زند.
        </Line>
      ) : null}

      {note ? <Line kind={tone === 'bad' ? 'error' : tone === 'ok' ? 'ok' : 'warn'}
        testId="connection-note">{note}</Line> : null}

      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1"
        data-testid="sarkhati-traffic-and-proof">
        <Field label="ترافیک" value={(
          <Chip tone={TRAFFIC_LABEL[traffic].tone} testId="sarkhati-traffic-mode">
            {TRAFFIC_LABEL[traffic].text}
          </Chip>)} />
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1"
        data-testid="sarkhati-portfolio-line">
        <Field label="پرتفویِ فقط‌خواندنی" value={(
          <span className="text-2xs text-text-secondary" data-testid="sarkhati-portfolio-status">
            {pfState ? PORTFOLIO_LABEL[pfState] : 'پاسخی نیامده'}
            {pfRows != null ? ` · ${toFaDigits(pfRows)} ردیف` : ''}
          </span>)} />
        {pfAsOf ? <span className="num text-3xs text-text-muted" data-testid="sarkhati-portfolio-asof"
          dir="ltr">{String(pfAsOf)}</span> : null}
        {pfError ? <span className="text-3xs text-accent-yellow"
          data-testid="sarkhati-portfolio-error">{String(pfError)}</span> : null}
      </div>

      <details className="mt-1.5 rounded-lg border border-border-c/50 px-2 py-1"
        data-testid="connection-api-details">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          مراحلِ API و حساب (۷ تا ۱۰)
        </summary>
        {extra.length ? <ol>{extra.map((s) => <StepRow key={s.key} step={s} />)}</ol>
          : <Line kind="muted">این مراحل هنوز خوانده نشده‌اند.</Line>}
      </details>

      <details className="mt-1.5 rounded-lg border border-border-c/50 px-2 py-1"
        data-testid="sarkhati-connection-technical">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          جزئیات فنی، تنظیم آداپتور و ورود دستیِ پیشرفته
        </summary>
        <div className="mt-1.5 flex flex-col gap-2">
          <ConnectBrokerRow />
          <SarkhatiConnectionSettings />
          <SarkhatiSessionForm />
          <Note label="چرا ورود دستی؟" testId="connection-manual-rule">
            ورود با خودِ مالک در پنجرهٔ host انجام می‌شود؛ برنامه رمز/CAPTCHA/MFA را
            نمی‌پرسد و هیچ token/cookie را در فایل، log یا گزارش نمی‌نویسد. فیلد
            نشستِ پایین فقط برایِ مسیرِ فنی/سازگاری است و مسیر اصلی نیست.
          </Note>
        </div>
      </details>
    </Section>
  );
}
