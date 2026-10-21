// features/portfolio/routes/AutoClickerPage.tsx — تنظیمات و آمادگیِ AutoClicker
//
// این صفحه فقط پوستهٔ تصمیم است: قیمت/تعداد را کاربر در فرمِ خودِ کارگزاری
// وارد می‌کند، و AutoClicker فقط دکمهٔ ارسالِ همان فرمِ ازپیش‌آماده را در زمانِ
// هدف می‌زند. هیچ فیلد سفارشی از این صفحه به فرمِ کارگزاری تزریق نمی‌شود،
// هیچ مسیرِ Live از این صفحه صدا زده نمی‌شود، و «آزمون» فقط dry-run است.
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  browserHostApi, mofidApi, orderApi, useBrowserHost, useExecutionReadiness,
  useExecutionStatus, useMofidSession, useStrategies,
  type MofidProbeView, type StrategyRowView,
} from '../lib/orderClient';
import { Chip, Field, GhostBtn, Line, Note, Section } from '../components/sarkhati/parts';
import { toFaDigits } from '@shared/lib/fmt';

function newIntentKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `ac-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const INTENT_SLOT = 'bors.autoclicker.intent';
function intentSig(symbol: string, side: string, price: string, qty: string, target: string): string {
  return [symbol.trim(), side, price.trim(), qty.trim(), target.trim()].join('|');
}
/** کلیدِ قصد در localStorage مشترک است تا دو تب با همان فرم، یک قصد ببینند. */
function readSharedIntent(sig: string): string {
  try {
    const raw = globalThis.localStorage?.getItem(INTENT_SLOT);
    if (!raw) return '';
    const got = JSON.parse(raw) as { sig?: string; key?: string };
    return got?.sig === sig && typeof got.key === 'string' ? got.key : '';
  } catch {
    return '';
  }
}
function writeSharedIntent(sig: string, key: string): void {
  try {
    globalThis.localStorage?.setItem(INTENT_SLOT, JSON.stringify({ sig, key }));
  } catch {
    /* storage در دسترس نیست؛ همین تب با کلیدِ محلی ادامه می‌دهد */
  }
}

const DEFAULTS = {
  form_symbol_selector: "[data-cy='order-form-header-symbol-name']",
  open_form_selector: 'button.order-buy-btn',
  price_selector: '#price',
  quantity_selector: '#quantity',
  submit_selector: "button[aria-label='ارسال خرید']",
  action_timeout_ms: '1200',
  intercept_pattern: '**/core/api/v2/order*',
};
type OptKey = keyof typeof DEFAULTS;
const INPUT = 'min-w-0 rounded-lg border border-border-c bg-bg-primary px-2 py-1 '
  + 'text-2xs text-text-primary outline-none focus:border-border-accent';

const MOFID_STATE_LABEL: Record<string, string> = {
  NEEDS_LOGIN: 'نیازمند ورود',
  AUTHENTICATING: 'در حال بررسی',
  AUTHENTICATED_UNVERIFIED: 'نشست تأیید نشده',
  READ_ONLY_PROBE_OK: 'خواندن تأیید شد',
  SESSION_EXPIRED: 'نشست منقضی',
  READ_ONLY_PROBE_FAILED: 'بررسی ناموفق',
};

function optionText(row: StrategyRowView | undefined, key: string, fallback: string): string {
  const v = row?.settings?.options?.[key];
  return v == null ? fallback : String(v);
}

function optBool(row: StrategyRowView | undefined, key: string, fallback: boolean): boolean {
  const v = row?.settings?.options?.[key];
  return typeof v === 'boolean' ? v : fallback;
}

function numText(v: unknown): string {
  if (v == null || v === '') return '—';
  const n = Number(v);
  return Number.isFinite(n) ? toFaDigits(n.toLocaleString('en-US')) : '—';
}

export default function AutoClickerPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const strategies = useStrategies();
  const hostQ = useBrowserHost();
  const statusQ = useExecutionStatus();
  const [execPath, setExecPath] = useState<'browser' | 'api'>('browser');
  const strategyId = execPath === 'api' ? 'direct_api' : 'autoclicker';
  const row = (strategies.data?.strategies ?? []).find((s) => s.id === strategyId);
  const browserRow = (strategies.data?.strategies ?? []).find((s) => s.id === 'autoclicker');
  const host = (hostQ.data?.host ?? {}) as { healthy?: boolean; status?: string; cdp_url?: string };
  const [opts, setOpts] = useState<Record<OptKey, string>>(DEFAULTS);
  const [preclick, setPreclick] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [symbol, setSymbol] = useState('');
  const [isin, setIsin] = useState('');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [price, setPrice] = useState('');
  const [qty, setQty] = useState('');
  const [target, setTarget] = useState('');
  const [intentKey, setIntentKey] = useState(() => newIntentKey());
  const [dryAck, setDryAck] = useState(false);
  const [preparedId, setPreparedId] = useState('');
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const recovered = strategies.data?.recovered_intents ?? {};
  const recoveredTotal = Object.values(recovered).reduce((n, v) => n + (Number(v) || 0), 0);
  const readinessQ = useExecutionReadiness({
    symbol: symbol.trim() || undefined,
    side,
    price: Number(price) > 0 ? Number(price) : undefined,
    quantity: Number(qty) > 0 ? Number(qty) : undefined,
  }, symbol.trim().length > 0);
  const serverReady = readinessQ.data;
  const adapterKind = String(statusQ.data?.adapter ?? '');
  const isMofidApi = execPath === 'api' && adapterKind === 'mofid';
  const mofidSessionQ = useMofidSession(isMofidApi);
  const mofidSession = mofidSessionQ.data;
  const [mofidProbe, setMofidProbe] = useState<MofidProbeView | null>(null);
  const [mofidBusy, setMofidBusy] = useState('');
  const mofidState = mofidBusy === 'verify' ? 'AUTHENTICATING'
    : String(mofidProbe?.state ?? mofidSession?.state ?? 'NEEDS_LOGIN');
  const mofidProbeFailed = mofidProbe != null && mofidProbe.status !== 'success';
  const probeAccount = (mofidProbe?.account ?? null) as Record<string, unknown> | null;
  const probePositions = (probeAccount?.positions as Array<Record<string, unknown>> | undefined) ?? [];
  const probeOrders = (probeAccount?.orders as Array<Record<string, unknown>> | undefined) ?? [];
  const probePosition = probePositions.find((r) => {
    const rowIsin = String(r.isin ?? '').toUpperCase();
    const rowSymbol = String(r.symbol ?? '');
    return (isin.trim() && rowIsin === isin.trim().toUpperCase())
      || (!isin.trim() && symbol.trim() && rowSymbol === symbol.trim());
  });
  const probeVisible = mofidState === 'READ_ONLY_PROBE_OK' && probeAccount != null;
  const sellableState = probePosition?.sellable_state
    ?? probePositions[0]?.sellable_state ?? '—';
  const accountReadiness = (mofidProbe?.account_readiness
    ?? mofidSession?.account_readiness ?? null) as Record<string, unknown> | null;
  const readinessGates = (accountReadiness?.gates as Array<Record<string, unknown>> | undefined) ?? [];
  const readinessWarnings = (accountReadiness?.warnings as Array<Record<string, unknown>> | undefined) ?? [];
  const readOnlyAccountReady = accountReadiness?.read_only_account_ready === true;
  const probeOrderDetail = String(mofidProbe?.steps?.order_detail ?? '—');

  useEffect(() => {
    if (!browserRow || loaded) return;
    setOpts((old) => {
      const next = { ...old };
      (Object.keys(DEFAULTS) as OptKey[]).forEach((k) => {
        next[k] = optionText(browserRow, k, DEFAULTS[k]);
      });
      return next;
    });
    setPreclick(optBool(browserRow, 'preclick_check', true));
    setLoaded(true);
  }, [browserRow, loaded]);

  const configured = useMemo(() => {
    if (execPath === 'api') return true;
    const sel = browserRow?.settings?.options ?? {};
    return !!(sel.form_symbol_selector || sel.symbol_selector)
      && !!sel.price_selector && !!sel.quantity_selector && !!sel.submit_selector;
  }, [browserRow, execPath]);
  const hostOk = execPath === 'api' || host.healthy === true;
  const sessionOk = statusQ.data?.session?.proven === true
    || mofidSession?.session_proven === true
    || mofidState === 'READ_ONLY_PROBE_OK';
  const accountGateOk = mofidState === 'READ_ONLY_PROBE_OK';
  const liveAllowed = strategies.data?.live_allowed === true;
  const selectorsOk = execPath === 'api' || Object.values(opts).every((v, i) =>
    i >= Object.keys(DEFAULTS).length - 2 ? true : v.trim().length > 0);
  const targetSet = target.trim().length > 0;
  const readiness = [
    ['host', 'browser host', hostOk, execPath === 'api' ? 'برای API لازم نیست' : (hostOk ? 'سالم' : 'بسته/ناسالم')],
    ['session', 'نشست', sessionOk, sessionOk ? 'تأییدشده' : 'تأییدنشده'],
    ['strategy', 'Strategy', !!row?.available, row?.unavailable_reason || (row?.available ? 'در دسترس' : 'نامعلوم')],
    ['selectors', 'شناسه‌های فرم', configured && selectorsOk, execPath === 'api' ? 'قرارداد API' : (configured ? 'تنظیم‌شده' : 'ناقص')],
    ['prefill', 'فرم ازپیش‌پر', execPath === 'api' || (!optBool(browserRow, 'autofill', true) && optBool(browserRow, 'require_prefilled', true)),
      execPath === 'api' ? 'برای API لازم نیست' : 'autofill=false · require_prefilled=true'],
    ['target', 'زمان هدف', targetSet, targetSet ? 'تعیین شده' : 'تعیین نشده'],
    ['live', 'Live', !liveAllowed, liveAllowed ? 'فعال — ممنوع' : 'بسته'],
  ] as const;

  const save = async () => {
    setBusy('save'); setAnswer('');
    try {
      const body: Record<string, unknown> = {
        enabled: true, mode: 'shadow', options: {
          ...opts,
          action_timeout_ms: Number(opts.action_timeout_ms) || 1200,
          preclick_check: preclick,
          autofill: false, require_prefilled: true, headless: false,
        },
      };
      const res = await orderApi.strategySettings('autoclicker', body);
      setTone(res.status === 'success' ? 'ok' : 'bad');
      setAnswer(res.status === 'success'
        ? 'تنظیمات ذخیره شد (shadow؛ فیلدهای قیمت/تعداد در فرم کارگزاری دست شماست)'
        : String(res.detail ?? res.code ?? 'ذخیره نشد'));
      if (res.status === 'success') void qc.invalidateQueries({ queryKey: ['execution-strategies'] });
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const probeNow = async () => {
    setBusy('probe'); setAnswer(''); setProbe(null);
    try {
      const res = await orderApi.strategyProbe(strategyId);
      setProbe((res.probe ?? res) as Record<string, unknown>);
      setTone(res.status === 'success' ? 'ok' : 'warn');
      setAnswer(res.status === 'success'
        ? 'Probe فقط‌خواندنی اجرا شد؛ هیچ کلیک/سفارشی ساخته نشد.'
        : String(res.detail ?? res.code ?? 'probe پاسخ نداد'));
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const prepare = async () => {
    setBusy('prepare'); setAnswer(''); setPreparedId('');
    const sig = intentSig(symbol, side, price, qty, target);
    const shared = readSharedIntent(sig);
    const key = shared || newIntentKey();
    writeSharedIntent(sig, key);
    setIntentKey(key);
    try {
      const res = await orderApi.strategyPrepare({
        symbol: symbol.trim(), side, price: Number(price), quantity: Number(qty),
        strategy: strategyId,
        target_tehran: target.trim() || undefined,
        intent_key: key,
        execution_id: `ac-${Date.now()}`,
      });
      if (res.status === 'success') {
        setPreparedId(String(res.prepared_id ?? ''));
        setTone('ok');
        setAnswer('آماده‌سازی شد؛ هیچ ارسالی انجام نشد. برای آزمون dry-run تأیید کنید.');
      } else {
        setTone('bad'); setAnswer(String(res.detail ?? res.code ?? 'آماده نشد'));
      }
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const dryRun = async () => {
    if (!preparedId || !dryAck) return;
    setBusy('dry'); setAnswer('');
    try {
      const res = await orderApi.strategyTrigger({ prepared_id: preparedId });
      const st = String(res.status ?? '');
      setLastResult((res.result as Record<string, unknown> | undefined) ?? res);
      if (st === 'scheduled') {
        setTone('ok');
        setAnswer('زمان‌بندی شد؛ dry-run در زمان هدف (تهران) اجرا می‌شود و پیش از dispatch متوقف می‌شود.');
      } else if (st === 'success') {
        setTone('warn');
        setAnswer(execPath === 'api'
          ? 'dry-run API: payload ساخته شد ولی هیچ درخواستی به کارگزاری نرفت.'
          : 'dry-run: کلیک با intercept اجرا شد؛ درخواست پیش از dispatch aborted شد.');
      } else {
        setTone('bad');
        setAnswer(String(res.detail ?? res.code ?? 'dry-run ناموفق'));
      }
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const abort = async () => {
    const key = readSharedIntent(intentSig(symbol, side, price, qty, target)) || intentKey;
    if (!preparedId && !key) return;
    setBusy('abort');
    try {
      if (preparedId) await orderApi.strategyAbort(preparedId);
      await orderApi.strategyAbortIntent(key);
      setTone('warn'); setAnswer('توقف ثبت شد؛ هیچ سفارشی لغو یا ارسال نشد.');
    } catch (e) { setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(''); }
  };

  const refreshResult = async () => {
    if (!preparedId) return;
    setBusy('result');
    try {
      const res = await orderApi.strategyOrder(preparedId);
      setLastResult(res);
      setTone(res.status === 'success' ? 'ok' : 'warn');
      setAnswer('نتیجه به‌روزرسانی شد؛ صف فقط با شناسهٔ معتبرِ کارگزاری خوانده می‌شود.');
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const startHost = async () => {
    setBusy('host');
    try {
      const res = await browserHostApi.start();
      setTone(res.status === 'success' ? 'ok' : 'bad');
      setAnswer(res.status === 'success' ? 'پنجرهٔ host باز شد؛ خودتان در EasyTrader وارد شوید.'
        : String(res.detail ?? res.code ?? 'host باز نشد'));
      void hostQ.refetch();
    } catch (e) { setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(''); }
  };

  const openMofidLogin = async () => {
    setMofidBusy('open'); setAnswer(''); setMofidProbe(null);
    try {
      const res = await mofidApi.loginWindow();
      const ok = res.status === 'success';
      setTone(ok ? 'ok' : 'bad');
      setAnswer(ok
        ? 'پنجرهٔ رسمی مفید باز شد؛ خودتان وارد شوید. برنامه رمز/OTP/CAPTCHA نمی‌پرسد.'
        : String(res.detail ?? res.code ?? 'پنجرهٔ ورود باز نشد'));
      void mofidSessionQ.refetch();
    } catch (e) { setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e)); }
    finally { setMofidBusy(''); }
  };

  const verifyMofidSession = async () => {
    setMofidBusy('verify'); setAnswer('');
    // دادهٔ قبلی فوراً پاک می‌شود تا پاسخِ کهنه به‌عنوانِ نتیجهٔ فعلی نماند.
    setMofidProbe(null);
    try {
      const res = await mofidApi.verifySession();
      setMofidProbe(res);
      const ok = res.status === 'success' && res.state === 'READ_ONLY_PROBE_OK';
      setTone(ok ? 'ok' : 'bad');
      setAnswer(ok
        ? 'نشست تأیید شد و حساب فقط‌خواندنی خوانده شد؛ ارسالِ سفارش بسته است.'
        : String(res.detail ?? res.code ?? 'بررسیِ نشست ناموفق بود'));
      if (ok) {
        void qc.invalidateQueries({ queryKey: ['execution-portfolio'] });
        void qc.invalidateQueries({ queryKey: ['execution-buying-power'] });
      }
      void mofidSessionQ.refetch();
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setMofidBusy(''); }
  };

  const closeMofidLogin = async () => {
    setMofidBusy('close');
    try {
      const res = await mofidApi.stopWindow();
      setTone(res.status === 'success' ? 'warn' : 'bad');
      setAnswer(res.status === 'success'
        ? 'پنجرهٔ ورود بسته شد؛ نشستِ حافظه دست‌نخورده است.'
        : String(res.detail ?? res.code ?? 'پنجره بسته نشد'));
      void mofidSessionQ.refetch();
    } catch (e) { setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e)); }
    finally { setMofidBusy(''); }
  };

  return (
    <div className="flex flex-col gap-2 p-3" data-testid="autoclicker-page">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-black text-text-primary">AutoClicker — آمادگی و اجرا</h2>
        <span className="text-2xs text-text-muted">یک intent مشترک؛ مسیر مرورگر یا API؛ بدون retry و بدون ارسال در این صفحه</span>
        <GhostBtn testId="autoclicker-back" onClick={() => navigate('/sarkhati')}>بازگشت به سرخطی</GhostBtn>
        <GhostBtn testId="autoclicker-path-browser" onClick={() => setExecPath('browser')}>مرورگر</GhostBtn>
        <GhostBtn testId="autoclicker-path-api" onClick={() => setExecPath('api')}>API</GhostBtn>
        <GhostBtn testId="autoclicker-open-host" onClick={() => void startHost()} disabled={busy !== '' || hostOk}>
          {execPath === 'api' ? 'host لازم نیست' : (hostOk ? 'host سالم' : 'بازکردن host')}
        </GhostBtn>
      </header>

      <Section title="آمادگی" sub="هر شرط از پاسخِ خودِ سرویس؛ خالی PASS نیست" testId="autoclicker-readiness">
        <div className="flex flex-wrap gap-1">
          {readiness.map(([id, label, ok, detail]) => (
            <Chip key={id} tone={ok ? 'ok' : 'warn'} testId={`autoclicker-gate-${id}`} title={detail}>
              {label}: {ok ? 'سبز' : 'باز'}
            </Chip>
          ))}
          {isMofidApi ? (
            <Chip tone={accountGateOk ? 'ok' : 'warn'} testId="autoclicker-gate-account"
              title={String(mofidProbe?.detail ?? mofidState)}>
              حساب مفید: {accountGateOk ? 'خوانده شد' : (MOFID_STATE_LABEL[mofidState] ?? 'باز')}
            </Chip>
          ) : null}
          <span className="text-3xs text-text-muted num" data-testid="autoclicker-strategy-state">
            {row?.settings?.mode ?? '—'} · {row?.configured ? 'configured' : 'default'}
          </span>
        </div>
        <Line kind={hostOk && sessionOk ? 'ok' : 'warn'} testId="autoclicker-readiness-line">
          {execPath === 'api'
            ? 'مسیر API: قرارداد و preflight مشترک؛ host لازم نیست و ارسال زنده بسته است.'
            : (hostOk && sessionOk
              ? 'host و نشست آماده‌اند؛ Probe را بزنید تا شناسه‌ها/فرم دیده شوند.'
              : 'برای Probe، host را باز و در EasyTrader وارد شوید.')}
        </Line>
        {execPath === 'api' && adapterKind !== 'mofid' ? (
          <Line kind="warn" testId="autoclicker-mofid-not-active">
            آداپتورِ فعال مفید نیست (adapter={adapterKind || '—'})؛ در «تنظیم اتصال»
            مفید آنلاین + فقط‌خواندنی را انتخاب و برنامه را restart کنید.
          </Line>
        ) : null}
        {serverReady ? (
          <Line kind={serverReady.live_ready ? 'ok' : 'warn'}
            testId="autoclicker-server-readiness">
            آمادگی سرور: live_ready={serverReady.live_ready ? 'بله' : 'خیر'} ·
            {' '}{serverReady.blocking_count ?? '?'} مانع ·
            اقدام: {serverReady.next_action || '—'}
          </Line>
        ) : null}
        {recoveredTotal > 0 ? (
          <Line kind="warn" testId="autoclicker-recovered">
            پس از restart، {Object.entries(recovered)
              .filter(([, v]) => Number(v) > 0)
              .map(([k, v]) => `${k}: ${v}`)
              .join(' · ')} — پیش از هر تلاش دوباره بررسی کنید.
          </Line>
        ) : null}
      </Section>

      {execPath === 'api' ? (
        <Section title="حساب مفید (ورود دستی، فقط‌خواندنی)"
          sub="ورود را خودتان در پنجرهٔ رسمی انجام دهید؛ سپس نشست و حساب فقط خوانده می‌شوند"
          testId="autoclicker-mofid-account">
          <div className="flex flex-wrap items-center gap-1">
            <Chip tone={mofidState === 'READ_ONLY_PROBE_OK' ? 'ok' : 'warn'}
              testId="autoclicker-mofid-state">
              {MOFID_STATE_LABEL[mofidState] ?? mofidState}
            </Chip>
            <GhostBtn testId="autoclicker-mofid-login" onClick={() => void openMofidLogin()}
              disabled={busy !== '' || mofidBusy !== ''}>ورود به حساب مفید</GhostBtn>
            <GhostBtn testId="autoclicker-mofid-verify" onClick={() => void verifyMofidSession()}
              disabled={busy !== '' || mofidBusy !== ''}>ورود انجام شد؛ بررسی اتصال</GhostBtn>
            <GhostBtn testId="autoclicker-mofid-close" onClick={() => void closeMofidLogin()}
              disabled={busy !== '' || mofidBusy !== ''}>بستن پنجرهٔ ورود</GhostBtn>
          </div>
          <Line kind="muted" testId="autoclicker-mofid-login-note">
            رمز/OTP/CAPTCHA را خودتان در پنجرهٔ رسمی وارد کنید؛ برنامه آن را نمی‌پرسد و ذخیره نمی‌کند.
          </Line>
          {!isMofidApi || mofidSession?.adapter_ready === false ? (
            <Line kind="warn" testId="autoclicker-mofid-prereq">
              آداپتورِ فعال Mofid + فقط‌خواندنی نیست
              ({String(mofidSession?.adapter_reason ?? (isMofidApi ? '—' : 'ADAPTER_NOT_MOFID'))})؛
              در «تنظیم اتصال» انتخاب و برنامه را restart کنید.
            </Line>
          ) : null}
          {mofidState === 'AUTHENTICATING' ? (
            <Line kind="warn" testId="autoclicker-mofid-progress">
              در حال خواندن و تأییدِ فقط‌خواندنی…
            </Line>
          ) : null}
          {mofidState === 'AUTHENTICATED_UNVERIFIED' ? (
            <Line kind="warn" testId="autoclicker-mofid-unverified">
              نشست در حافظه است ولی خواندن هنوز تأیید نشده؛ «بررسی اتصال» را بزنید.
            </Line>
          ) : null}
          {mofidProbeFailed ? (
            <Line kind="error" testId="autoclicker-mofid-error">
              {String(mofidProbe?.detail ?? mofidProbe?.code ?? 'بررسی ناموفق')}
            </Line>
          ) : null}
          {probeVisible ? (
            <>
              <div className="flex flex-wrap gap-1">
                <Line kind="ok" testId="autoclicker-mofid-bp">
                  قدرت خرید: {numText(probeAccount?.buying_power)}
                  {' '}{String(probeAccount?.unit ?? '')} ·
                  واحد: {String(probeAccount?.unit_state ?? '—')} ·
                  دقت: {numText(probeAccount?.precision)}
                </Line>
                <Line kind="ok" testId="autoclicker-mofid-portfolio">
                  دارایی: {numText(probePositions.length)} ردیف ·
                  سفارش باز: {numText(probeOrders.length)} ·
                  سفارش امروز: {numText(mofidProbe?.counts?.today_orders)} ·
                  جزئیات: {numText(mofidProbe?.counts?.order_details)}
                </Line>
              </div>
              {probePosition ? (
                <Line kind="muted" testId="autoclicker-mofid-row">
                  {String(probePosition.symbol ?? probePosition.isin ?? '—')} ·
                  دارایی: {numText(probePosition.current_asset)} ·
                  قابل‌فروش (برآورد): {numText(probePosition.sellable)} ·
                  سفارشِ باز فروش: {numText(probePosition.open_sell)}
                </Line>
              ) : null}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-3xs text-text-muted" data-testid="autoclicker-mofid-sellable-state">
                  sellable: {String(sellableState)}
                </span>
                <span className="text-3xs text-text-muted">
                  {String(probeAccount?.source ?? '')}
                </span>
              </div>
              <div className="text-3xs text-text-muted" data-testid="autoclicker-mofid-steps">
                گام‌ها: {Object.entries(mofidProbe?.steps ?? {})
                  .map(([k, v]) => `${k}:${v}`).join(' · ') || '—'}
              </div>
              {accountReadiness ? (
                <Line kind={readOnlyAccountReady ? 'ok' : 'warn'}
                  testId="autoclicker-mofid-account-readiness">
                  آمادگی حساب: {readOnlyAccountReady ? 'کامل' : 'ناقص'} ·
                  گیت‌های باز: {readinessWarnings
                    .map((w) => `${String(w.id)}:${String(w.status)}`)
                    .join(' · ') || '—'}
                </Line>
              ) : null}
              <Line kind="muted" testId="autoclicker-mofid-freshness">
                تازگی: {String(probeAccount?.freshness ?? '—')} ·
                دریافت: {String(probeAccount?.fetched_at ?? '—')} ·
                read-back: {probeOrderDetail === 'SKIPPED_NO_ORDERS'
                  ? 'اندازه‌گیری‌نشده (سفارشی نیست)' : probeOrderDetail}
              </Line>
              <details className="mt-1">
                <summary className="cursor-pointer text-3xs text-text-muted">
                  ردیف‌های حساب و سفارش‌ها
                </summary>
                <pre className="mt-1 max-h-40 overflow-auto text-3xs text-text-muted" dir="ltr">
                  {JSON.stringify({
                    positions: probePositions.slice(0, 20),
                    orders: probeOrders.slice(0, 20),
                    details: mofidProbe?.account?.order_details ?? [],
                    readiness_gates: readinessGates,
                    position_fields: probeAccount?.position_fields,
                    order_contract: mofidProbe?.order_contract,
                  }, null, 1)}
                </pre>
              </details>
            </>
          ) : null}
          <Line kind="muted" testId="autoclicker-mofid-live-closed">
            ارسال سفارش بسته است: live_enabled=false · live_ready=false
          </Line>
        </Section>
      ) : null}

      <div className="grid gap-2 lg:grid-cols-2">
        <Section title="تنظیمات مسیر مرورگر" sub="در مسیر API این شناسه‌ها استفاده نمی‌شوند؛ تغییر فقط در همین دستگاه" testId="autoclicker-settings">
          <div className="grid gap-1 sm:grid-cols-2">
            {(Object.keys(DEFAULTS) as OptKey[]).map((k) => (
              <label key={k} className="flex flex-col gap-0.5 text-3xs text-text-muted">
                {k}
                <input value={opts[k]} onChange={(e) => setOpts({ ...opts, [k]: e.target.value })}
                  data-testid={`autoclicker-opt-${k}`} className={INPUT} dir="ltr" />
              </label>
            ))}
          </div>
          <label className="mt-1 flex items-center gap-1 text-2xs text-text-secondary">
            <input type="checkbox" checked={preclick} onChange={(e) => setPreclick(e.target.checked)}
              data-testid="autoclicker-preclick" className="size-3 accent-accent-blue" />
            قبل از کلیک، وجود و فعال‌بودن دکمه دوباره بررسی شود
          </label>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <GhostBtn testId="autoclicker-save" onClick={() => void save()} disabled={busy !== ''}>ذخیرهٔ تنظیمات</GhostBtn>
            <GhostBtn testId="autoclicker-probe" onClick={() => void probeNow()} disabled={busy !== ''}>Probe فقط‌خواندنی</GhostBtn>
          </div>
          <Line kind="muted" testId="autoclicker-click-policy">
            سیاست کلیک: یک کلیک در هر اجرا؛ هیچ retry یا ارسالِ دوباره‌ای در این مسیر نیست.
          </Line>
        </Section>

        <Section title="قصد سفارش و آزمون" sub={execPath === 'api'
          ? 'قیمت/تعداد را وارد کنید؛ payload API ساخته می‌شود ولی ارسال زنده بسته است'
          : 'قیمت/تعداد را در فرم کارگزاری وارد کنید؛ اینجا فقط انتظار را تأیید می‌کنیم'} testId="autoclicker-order">
          <div className="grid gap-1 sm:grid-cols-2">
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">نماد
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)}
                data-testid="autoclicker-symbol" className={INPUT} />
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">ISIN (اختیاری)
              <input value={isin} onChange={(e) => setIsin(e.target.value)}
                data-testid="autoclicker-isin" className={INPUT} dir="ltr" />
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">سمت
              <select value={side} onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}
                data-testid="autoclicker-side" className={INPUT}>
                <option value="buy">خرید</option><option value="sell">فروش</option>
              </select>
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">قیمت انتظاری
              <input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal"
                data-testid="autoclicker-price" className={INPUT} />
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">تعداد انتظاری
              <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal"
                data-testid="autoclicker-qty" className={INPUT} />
            </label>
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">زمان هدف (به وقت تهران)
              <input type="datetime-local" value={target} onChange={(e) => setTarget(e.target.value)}
                data-testid="autoclicker-target" className={INPUT} />
            </label>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <GhostBtn testId="autoclicker-prepare" onClick={() => void prepare()}
              disabled={busy !== '' || !symbol.trim() || !price || !qty}>آماده‌سازی (بدون ارسال)</GhostBtn>
            <GhostBtn testId="autoclicker-abort" onClick={() => void abort()} disabled={busy !== ''}>توقف از هر تب</GhostBtn>
            <GhostBtn testId="autoclicker-new-intent" onClick={() => {
              const key = newIntentKey();
              setIntentKey(key);
              writeSharedIntent(intentSig(symbol, side, price, qty, target), key);
              setPreparedId('');
              setDryAck(false);
              setTone('idle');
              setAnswer('قصد تازه ساخته شد؛ هیچ کلیک/سفارشی ساخته نشد.');
            }} disabled={busy !== ''}>قصد تازه</GhostBtn>
          </div>
          {preparedId ? (
            <div className="mt-1 rounded-lg border border-border-c/40 bg-bg-primary/30 px-2 py-1">
              <Field label="prepared_id" value={<span className="num" dir="ltr">{preparedId}</span>} />
              <label className="mt-1 flex items-center gap-1 text-2xs text-text-secondary">
                <input type="checkbox" checked={dryAck} onChange={(e) => setDryAck(e.target.checked)}
                  data-testid="autoclicker-dry-ack" className="size-3 accent-accent-blue" />
                می‌دانم این dry-run است و درخواست پیش از dispatch abort می‌شود؛ کلیکِ نهایی را تأیید می‌کنم.
              </label>
              <GhostBtn testId="autoclicker-dry-run" onClick={() => void dryRun()}
                disabled={!dryAck || busy !== ''}>آزمون dry-run با intercept</GhostBtn>
            </div>
          ) : null}
        </Section>
      </div>

      <Section title="نتیجه و پایش سفارش" sub="order-id و صف فقط اگر منبعِ معتبر بدهد؛ مقدارِ ناموجود صفر نشان داده نمی‌شود" testId="autoclicker-monitor">
        {lastResult ? (
          <>
            <Line kind={lastResult.unknown ? 'warn' : 'ok'} testId="autoclicker-result">
              وضعیت: {String(lastResult.status ?? '—')} ·
              order-id: {String(lastResult.broker_order_id ?? '—')} ·
              صف: {lastResult.queue_position == null
                ? 'در دسترس نیست' : String(lastResult.queue_position)} ·
              UNKNOWN: {lastResult.unknown ? 'بله' : 'خیر'}
            </Line>
            <details className="mt-1">
              <summary className="cursor-pointer text-3xs text-text-muted">جزئیاتِ نتیجه</summary>
              <pre className="mt-1 max-h-40 overflow-auto text-3xs text-text-muted" dir="ltr">
                {JSON.stringify(lastResult, null, 1)}
              </pre>
            </details>
          </>
        ) : (
          <Line kind="muted" testId="autoclicker-result-empty">هنوز اجرایی در این نشست ثبت نشده است.</Line>
        )}
        <GhostBtn testId="autoclicker-result-refresh" onClick={() => void refreshResult()}
          disabled={!preparedId || busy !== ''}>به‌روزرسانی نتیجه</GhostBtn>
      </Section>

      {answer ? <Line kind={tone === 'ok' ? 'ok' : tone === 'bad' ? 'error' : 'warn'} testId="autoclicker-answer">{answer}</Line> : null}
      {probe ? (
        <details className="rounded-lg border border-border-c/40 px-2 py-1" data-testid="autoclicker-probe-result">
          <summary className="cursor-pointer text-3xs font-bold text-text-secondary">نتیجهٔ Probe (بدونِ مقدار فرم)</summary>
          <pre className="mt-1 max-h-48 overflow-auto text-3xs text-text-muted" dir="ltr">
            {JSON.stringify({ login: probe.login, origin_ok: probe.origin_ok,
              selectors: probe.selectors,
              structure: {
                buttons: ((probe.structure as { buttons?: unknown[] } | undefined)?.buttons ?? []).slice(0, 10),
                inputs: ((probe.structure as { inputs?: unknown[] } | undefined)?.inputs ?? []).slice(0, 10),
              },
              browser: probe.browser,
              network: probe.network }, null, 1)}
          </pre>
        </details>
      ) : null}
      <Note label="این صفحه چه چیزی نیست" testId="autoclicker-nots">
        <ul className="flex flex-col gap-0.5">
          <li>مسیر مرورگر فرمِ کارگزاری را پر نمی‌کند؛ قیمت/تعداد را خودتان در EasyTrader وارد می‌کنید.</li>
          <li>مسیر API از آداپتورِ فعالِ سرور پیروی می‌کند: EasyTrader (Orbis) یا Mofid (Titan)؛ انتخابِ آداپتور در «تنظیم اتصال» است.</li>
          <li>حساب مفید فقط خوانده می‌شود؛ «قابل‌فروش» برآوردِ محافظه‌کارانه از پرتفوی است و نوشتن/پاسخِ ثبت تأیید نشده.</li>
          <li>پنجرهٔ ورود مفید فقط برای ورود دستیِ خودتان است؛ برنامه رمز/OTP/CAPTCHA نمی‌پرسد و نشست را فقط در حافظه نگه می‌دارد.</li>
          <li>هیچ ارسالِ Live از این صفحه انجام نمی‌شود؛ `live_allowed` باید false بماند.</li>
          <li>dry-run مرورگر یک کلیک با intercept است و dry-run API هیچ ترابری صدا نمی‌زند؛ هیچ‌کدام پذیرش سفارش نیست.</li>
        </ul>
      </Note>
    </div>
  );
}
