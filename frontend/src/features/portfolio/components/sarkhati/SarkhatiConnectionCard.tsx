// اتصال: یک وضعیت، شش قدمِ قابل‌فهم، و جزئیاتِ فنیِ پنهان.
// «پنجره باز شد»، «وارد شدم» و «API تأیید شد» سه چیزند و اینجا سه سطر جدا دارند.
import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CheckIcon, HelpIcon, XIcon } from '@shared/components/Icons';
import { toFaDigits } from '@shared/lib/fmt';
import {
  browserHostApi, connectApi, connectionApi, PORTFOLIO_LABEL, PORTFOLIO_STATES,
  TRAFFIC_LABEL, TRAFFIC_MODES, useBrokerConnect, useBrowserHost,
  useConnectionDiagnosis, useExecutionPortfolio,
  type ConnectionStep, type PortfolioState, type TrafficMode,
} from '../../lib/orderClient';
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
const SHORT: Record<string, string> = {
  backend: 'برنامه', host: 'مرورگر', cdp: 'ارتباط', page: 'صفحه', login: 'ورود', session: 'حساب',
};
const AUTO_CAPTURE_KEY = 'sarkhati-auto-capture';

function StepDot({ status }: { status: string }) {
  const tone = TONE[status] ?? 'warn';
  const cls = tone === 'ok' ? 'text-accent-green'
    : tone === 'bad' ? 'text-accent-red'
      : tone === 'warn' ? 'text-accent-yellow' : 'text-text-muted';
  return (
    <span className={`inline-grid h-3.5 w-3.5 place-items-center ${cls}`} aria-hidden="true">
      {status === 'PASS' ? <CheckIcon size={11} />
        : status === 'FAIL' || status === 'BLOCKED' ? <XIcon size={11} />
          : status === 'UNVERIFIED' ? <HelpIcon size={11} />
            : <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />}
    </span>
  );
}

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
  const sessionStep = primary.find((s) => s.key === 'session');
  const captureAllowed = d?.state === 'BROWSER_READY_API_UNVERIFIED'
    && d?.adapter === 'easytrader' && hostHealthy && sessionStep?.status === 'BLOCKED';
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  // پیش‌فرض روشن (خواستِ مالک، ۲۰۲۶-۱۰-۲۱): پس از ورود، نشست یک‌بار خودکار
  // خوانده می‌شود؛ کلید خاموش‌کردن در جزئیات فنی است و فقط یک ترجیحِ UI است.
  const [autoCapture, setAutoCapture] = useState<boolean>(() => {
    try { return localStorage.getItem(AUTO_CAPTURE_KEY) !== '0'; } catch { return true; }
  });
  const autoTried = useRef(false);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-connection-diagnosis'] });
    void qc.invalidateQueries({ queryKey: ['execution-browser-host'] });
    void qc.invalidateQueries({ queryKey: ['execution-connect'] });
    // منابعِ حساب بعد از تأییدِ نشست باید تازه خوانده شوند؛ دادهٔ blockedِ
    // پیش از تأیید نباید تا پایانِ staleTime بماند.
    void qc.invalidateQueries({ queryKey: ['execution-portfolio'] });
    void qc.invalidateQueries({ queryKey: ['execution-watchlist'] });
    void qc.invalidateQueries({ queryKey: ['execution-buying-power'] });
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
      // این در، پرسشِ واقعیِ read-only را می‌زند (`/connect/verify`)؛
      // `/connection/verify` فقط تشخیصِ محلی است و نشست را تأیید نمی‌کند.
      const r = await connectApi.verify();
      const v = (r.verify ?? {}) as Record<string, unknown>;
      const state = String(v.state ?? '');
      const ok = state === 'CONNECTED';
      setTone(ok ? 'ok' : state === 'UNKNOWN' ? 'warn' : 'bad');
      setNote(ok
        ? 'ارتباط با کارگزاری تأیید شد؛ اطلاعات خواندنی از حساب شما دریافت شد.'
        : String(v.reason ?? v.blocked_reason ?? 'ارتباط با کارگزاری تأیید نشد'));
      refresh();
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const capture = async (auto = false) => {
    setBusy('capture'); setNote('');
    try {
      const r = await connectionApi.captureSession();
      const ok = r.status === 'success';
      setTone(ok ? 'ok' : 'bad');
      setNote(ok
        ? (auto
          ? 'دسترسی به حساب به‌طور خودکار از مرورگر دریافت شد و فقط در حافظه ماند؛ حالا «بررسی وضعیت» را بزنید.'
          : 'دسترسی به حساب از مرورگر دریافت شد و فقط در حافظه ماند؛ حالا «بررسی وضعیت» را بزنید.')
        : String(r.detail ?? r.code ?? 'دریافت دسترسی از مرورگر ممکن نشد'));
      refresh();
    } catch (e) {
      setTone('bad'); setNote(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const toggleAuto = () => {
    setAutoCapture((v) => {
      const next = !v;
      try { localStorage.setItem(AUTO_CAPTURE_KEY, next ? '1' : '0'); } catch { /* preference only */ }
      return next;
    });
  };

  useEffect(() => {
    if (d?.state !== 'BROWSER_READY_API_UNVERIFIED') autoTried.current = false;
  }, [d?.state]);

  useEffect(() => {
    if (!autoCapture || !captureAllowed || busy !== '' || autoTried.current) return;
    autoTried.current = true;
    void capture(true);
  }, [autoCapture, captureAllowed, busy, capture]);

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
      sub="یک قدم در هر لحظه؛ جزئیات پشتِ یک بازشو"
      tone={d?.state === 'CONNECTED' ? 'quiet' : 'default'}
      right={<Chip tone={stateTone} testId="sarkhati-connection-state">
        {d?.state_label ?? 'وضعیت اتصال خوانده نشد'}
      </Chip>}>
      <div className="flex flex-wrap items-center gap-1.5">
        <p className="min-w-0 flex-1 text-2xs font-bold text-text-primary"
          data-testid="sarkhati-connection-next">
          {captureAllowed
            ? (autoCapture
              ? 'پس از ورود شما، دسترسی به حساب خودکار دریافت می‌شود؛ سپس «بررسی وضعیت» را بزنید'
              : 'دسترسی به حساب را از مرورگر دریافت کنید؛ سپس «بررسی وضعیت» را بزنید')
            : d?.next_action || 'وضعیت را بررسی کنید'}
        </p>
        {!hostHealthy ? (
          <button type="button" data-testid="connection-open-host" disabled={busy !== ''}
            onClick={() => void startHost()}
            className="inline-flex min-h-[30px] items-center justify-center rounded-md border
              border-accent-blue/60 bg-accent-blue/15 px-2.5 text-2xs font-black text-accent-blue
              transition-colors disabled:cursor-not-allowed disabled:opacity-40">
            باز کردن پنجرهٔ اتصال
          </button>
        ) : null}
        {captureAllowed ? (
          <button type="button" data-testid="connection-capture-session" disabled={busy !== ''}
            onClick={() => void capture()}
            className="inline-flex min-h-[30px] items-center justify-center rounded-md border
              border-accent-blue/60 bg-accent-blue/15 px-2.5 text-2xs font-black text-accent-blue
              transition-colors disabled:cursor-not-allowed disabled:opacity-40">
            {autoCapture ? 'دریافت دستی دسترسی' : 'دریافت دسترسی از مرورگر'}
          </button>
        ) : null}
        <button type="button" data-testid="connection-check" disabled={busy !== ''}
          onClick={() => void check()}
          className={`inline-flex min-h-[30px] items-center justify-center rounded-md border px-2.5
            text-2xs font-black transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
            hostHealthy && !captureAllowed
              ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue'
              : 'border-border-c bg-bg-primary/40 text-text-secondary hover:border-border-accent hover:text-accent-blue'
          }`}>
          بررسی وضعیت
        </button>
      </div>

      {primary.length ? (
        <ol className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="connection-summary">
          {primary.map((s) => (
            <li key={s.key} data-testid={`connection-summary-${s.key}`} data-status={s.status}
              title={`${s.title}: ${s.status}${s.reason ? ` — ${s.reason}` : ''}`}
              aria-label={`${SHORT[s.key] ?? s.title}: ${s.status}`}
              className="inline-flex items-center gap-0.5 text-2xs text-text-secondary">
              <StepDot status={s.status} />
              <span>{SHORT[s.key] ?? s.title}</span>
            </li>
          ))}
        </ol>
      ) : null}

      {q.isPending ? <Line kind="muted" testId="connection-loading">در حال خواندن مراحل اتصال…</Line> : null}
      {q.isError ? <Line kind="error" testId="connection-error">
        تشخیص اتصال خوانده نشد؛ هیچ مرحله‌ای سبز فرض نمی‌شود.
      </Line> : null}
      {!q.isPending && !q.isError && !steps.length ? (
        <Line kind="warn" testId="connection-no-diagnosis">
          تشخیصِ مرحله‌ای در دسترس نیست؛ «بررسی وضعیت» را بزنید.
        </Line>
      ) : null}

      {d?.state === 'BROWSER_READY_API_UNVERIFIED' ? (
        <Line kind="warn" testId="connection-browser-ready-api-unverified">
          مرورگر آماده است؛ هنوز مطمئن نیستیم به حساب کارگزاری دسترسی داریم.
          بازبودن صفحه یا واردشدن شما به‌تنهایی کافی نیست.
        </Line>
      ) : null}

      {d?.state === 'LOGIN_REQUIRED' ? (
        <Line kind="warn" testId="connection-login-needed">
          لطفاً در همین پنجره وارد کارگزاری شوید؛ سپس «بررسی وضعیت» را بزنید.
          برنامه رمز/CAPTCHA/MFA را نمی‌پرسد و دور نمی‌زند.
        </Line>
      ) : null}

      {note ? <Line kind={tone === 'bad' ? 'error' : tone === 'ok' ? 'ok' : 'warn'}
        testId="connection-note">{note}</Line> : null}

      <details className="mt-1 rounded-lg border border-border-c/50 px-2 py-1"
        data-testid="sarkhati-connection-technical">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          جزئیات فنی و تنظیم اتصال
        </summary>
        <div className="mt-1.5 flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone={hostHealthy ? 'ok' : 'warn'} testId="sarkhati-host-state">
              مرورگر: {hostHealthy ? 'آماده' : 'بسته'}
            </Chip>
            <Chip tone={d?.adapter === 'easytrader' ? 'ok' : 'warn'} testId="sarkhati-adapter-state">
              روش اتصال: {d?.adapter ?? '—'}
            </Chip>
            <GhostBtn testId="connection-auto-capture" onClick={toggleAuto}
              title="روشن: پس از ورود شما در پنجرهٔ مرورگر، دسترسی به حساب یک‌بار دریافت و فقط در حافظه نگه داشته می‌شود.">
              اتصال خودکار به حساب: {autoCapture ? 'روشن' : 'خاموش'}
            </GhostBtn>
            <div className="ms-auto flex flex-wrap items-center gap-1">
              <GhostBtn testId="connection-stop-host" disabled={busy !== '' || !hostHealthy}
                onClick={() => void stopHost()}>بستن host</GhostBtn>
              <GhostBtn testId="connection-report" disabled={busy !== ''}
                onClick={() => void download()}>گزارش تشخیصی</GhostBtn>
            </div>
          </div>

          {primary.length ? (
            <ol className="rounded-lg border border-border-c/50 px-2 py-1"
              data-testid="connection-steps">
              {primary.map((s) => <StepRow key={s.key} step={s} />)}
            </ol>
          ) : null}

          <details className="rounded-lg border border-border-c/50 px-2 py-1"
            data-testid="connection-api-details">
            <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
              مراحلِ API و حساب (۷ تا ۱۰)
            </summary>
            {extra.length ? <ol>{extra.map((s) => <StepRow key={s.key} step={s} />)}</ol>
              : <Line kind="muted">این مراحل هنوز خوانده نشده‌اند.</Line>}
          </details>

          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1"
            data-testid="sarkhati-traffic-and-proof">
            <Field label="ارتباط با کارگزاری" value={(
              <Chip tone={TRAFFIC_LABEL[traffic].tone} testId="sarkhati-traffic-mode">
                {TRAFFIC_LABEL[traffic].text}
              </Chip>)} />
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1"
            data-testid="sarkhati-portfolio-line">
            <Field label="اطلاعات حساب (فقط خواندن)" value={(
              <span className="text-2xs text-text-secondary" data-testid="sarkhati-portfolio-status">
                {pfState ? PORTFOLIO_LABEL[pfState] : 'پاسخی نیامده'}
                {pfRows != null ? ` · ${toFaDigits(pfRows)} ردیف` : ''}
              </span>)} />
            {pfAsOf ? <span className="num text-3xs text-text-muted" data-testid="sarkhati-portfolio-asof"
              dir="ltr">{String(pfAsOf)}</span> : null}
            {pfError ? <span className="text-3xs text-accent-yellow"
              data-testid="sarkhati-portfolio-error">{String(pfError)}</span> : null}
          </div>

          <SarkhatiConnectionSettings />
          <SarkhatiSessionForm />
          <Note label="ورود را خودتان انجام می‌دهید" testId="connection-manual-rule">
            ورود در پنجرهٔ مرورگر و به‌دست خودتان انجام می‌شود؛ برنامه رمز/CAPTCHA/MFA
            را نمی‌پرسد و هیچ token/cookie را در فایل، log یا گزارش نمی‌نویسد. فیلد
            دسترسیِ پایین فقط برای مسیر فنی/سازگاری است و مسیر اصلی نیست.
          </Note>
        </div>
      </details>
    </Section>
  );
}
