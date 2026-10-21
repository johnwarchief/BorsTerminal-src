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
  browserHostApi, orderApi, useBrowserHost, useExecutionStatus, useStrategies,
  type StrategyRowView,
} from '../lib/orderClient';
import { targetWallMs } from '../stores/sarkhatiFormStore';
import { Chip, Field, GhostBtn, Line, Note, Section } from '../components/sarkhati/parts';

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

function optionText(row: StrategyRowView | undefined, key: string, fallback: string): string {
  const v = row?.settings?.options?.[key];
  return v == null ? fallback : String(v);
}

function optBool(row: StrategyRowView | undefined, key: string, fallback: boolean): boolean {
  const v = row?.settings?.options?.[key];
  return typeof v === 'boolean' ? v : fallback;
}

export default function AutoClickerPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const strategies = useStrategies();
  const hostQ = useBrowserHost();
  const statusQ = useExecutionStatus();
  const row = (strategies.data?.strategies ?? []).find((s) => s.id === 'autoclicker');
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
  const [dryAck, setDryAck] = useState(false);
  const [preparedId, setPreparedId] = useState('');
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!row || loaded) return;
    setOpts((old) => {
      const next = { ...old };
      (Object.keys(DEFAULTS) as OptKey[]).forEach((k) => {
        next[k] = optionText(row, k, DEFAULTS[k]);
      });
      return next;
    });
    setPreclick(optBool(row, 'preclick_check', true));
    setLoaded(true);
  }, [row, loaded]);

  const configured = useMemo(() => {
    const sel = row?.settings?.options ?? {};
    return !!(sel.form_symbol_selector || sel.symbol_selector)
      && !!sel.price_selector && !!sel.quantity_selector && !!sel.submit_selector;
  }, [row]);
  const hostOk = host.healthy === true;
  const sessionOk = statusQ.data?.session?.proven === true;
  const liveAllowed = strategies.data?.live_allowed === true;
  const selectorsOk = Object.values(opts).every((v, i) =>
    i >= Object.keys(DEFAULTS).length - 2 ? true : v.trim().length > 0);
  const targetMs = targetWallMs(target);
  const readiness = [
    ['host', 'browser host', hostOk, hostOk ? 'سالم' : 'بسته/ناسالم'],
    ['session', 'نشست', sessionOk, sessionOk ? 'تأییدشده' : 'تأییدنشده'],
    ['strategy', 'Strategy', !!row?.available, row?.unavailable_reason || (row?.available ? 'در دسترس' : 'نامعلوم')],
    ['selectors', 'شناسه‌های فرم', configured && selectorsOk, configured ? 'تنظیم‌شده' : 'ناقص'],
    ['prefill', 'فرم ازپیش‌پر', !optBool(row, 'autofill', true) && optBool(row, 'require_prefilled', true),
      'autofill=false · require_prefilled=true'],
    ['target', 'زمان هدف', targetMs != null, targetMs == null ? 'تعیین نشده' : 'تعیین شده'],
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
      const res = await orderApi.strategyProbe('autoclicker');
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
    try {
      const res = await orderApi.strategyPrepare({
        symbol: symbol.trim(), side, price: Number(price), quantity: Number(qty),
        strategy: 'autoclicker',
        target_wall_ms: targetMs ?? undefined,
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
      setTone(res.status === 'success' ? 'warn' : 'bad');
      setAnswer(res.status === 'success'
        ? 'dry-run: کلیک با intercept اجرا شد؛ درخواست پیش از dispatch aborted شد.'
        : String(res.detail ?? res.code ?? 'dry-run ناموفق'));
    } catch (e) {
      setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const abort = async () => {
    if (!preparedId) return;
    setBusy('abort');
    try {
      await orderApi.strategyAbort(preparedId);
      setTone('warn'); setAnswer('توقف ثبت شد؛ هیچ سفارشی لغو یا ارسال نشد.');
    } catch (e) { setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(''); }
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

  return (
    <div className="flex flex-col gap-2 p-3" data-testid="autoclicker-page">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-black text-text-primary">AutoClicker — تنظیمات و آمادگی</h2>
        <span className="text-2xs text-text-muted">فقط یک کلیک در زمان هدف؛ فرم را خودتان در کارگزاری پر کنید</span>
        <GhostBtn testId="autoclicker-back" onClick={() => navigate('/sarkhati')}>بازگشت به سرخطی</GhostBtn>
        <GhostBtn testId="autoclicker-open-host" onClick={() => void startHost()} disabled={busy !== '' || hostOk}>
          {hostOk ? 'host سالم' : 'بازکردن host'}
        </GhostBtn>
      </header>

      <Section title="آمادگی" sub="هر شرط از پاسخِ خودِ سرویس؛ خالی PASS نیست" testId="autoclicker-readiness">
        <div className="flex flex-wrap gap-1">
          {readiness.map(([id, label, ok, detail]) => (
            <Chip key={id} tone={ok ? 'ok' : 'warn'} testId={`autoclicker-gate-${id}`} title={detail}>
              {label}: {ok ? 'سبز' : 'باز'}
            </Chip>
          ))}
          <span className="text-3xs text-text-muted num" data-testid="autoclicker-strategy-state">
            {row?.settings?.mode ?? '—'} · {row?.configured ? 'configured' : 'default'}
          </span>
        </div>
        <Line kind={hostOk && sessionOk ? 'ok' : 'warn'} testId="autoclicker-readiness-line">
          {hostOk && sessionOk
            ? 'host و نشست آماده‌اند؛ Probe را بزنید تا شناسه‌ها/فرم دیده شوند.'
            : 'برای Probe، host را باز و در EasyTrader وارد شوید.'}
        </Line>
      </Section>

      <div className="grid gap-2 lg:grid-cols-2">
        <Section title="تنظیمات شناسه‌ها" sub="مقادیر پیش‌فرض از UI دیده‌شده‌اند؛ تغییر فقط در همین دستگاه" testId="autoclicker-settings">
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

        <Section title="سفارشِ ازپیش‌پر و آزمون" sub="قیمت/تعداد را در فرم کارگزاری وارد کنید؛ اینجا فقط انتظار را تأیید می‌کنیم" testId="autoclicker-order">
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
            <label className="flex flex-col gap-0.5 text-3xs text-text-muted">زمان هدف
              <input type="datetime-local" value={target} onChange={(e) => setTarget(e.target.value)}
                data-testid="autoclicker-target" className={INPUT} />
            </label>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            <GhostBtn testId="autoclicker-prepare" onClick={() => void prepare()}
              disabled={busy !== '' || !symbol.trim() || !price || !qty}>آماده‌سازی (بدون ارسال)</GhostBtn>
            <GhostBtn testId="autoclicker-abort" onClick={() => void abort()} disabled={!preparedId || busy !== ''}>توقف</GhostBtn>
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

      {answer ? <Line kind={tone === 'ok' ? 'ok' : tone === 'bad' ? 'error' : 'warn'} testId="autoclicker-answer">{answer}</Line> : null}
      {probe ? (
        <details className="rounded-lg border border-border-c/40 px-2 py-1" data-testid="autoclicker-probe-result">
          <summary className="cursor-pointer text-3xs font-bold text-text-secondary">نتیجهٔ Probe (بدونِ مقدار فرم)</summary>
          <pre className="mt-1 max-h-48 overflow-auto text-3xs text-text-muted" dir="ltr">
            {JSON.stringify({ login: probe.login, origin_ok: probe.origin_ok,
              selectors: probe.selectors, browser: probe.browser,
              network: probe.network }, null, 1)}
          </pre>
        </details>
      ) : null}
      <Note label="این صفحه چه چیزی نیست" testId="autoclicker-nots">
        <ul className="flex flex-col gap-0.5">
          <li>این صفحه فرمِ کارگزاری را پر نمی‌کند؛ قیمت/تعداد را خودتان در EasyTrader وارد می‌کنید.</li>
          <li>هیچ ارسالِ Live از این صفحه انجام نمی‌شود؛ `live_allowed` باید false بماند.</li>
          <li>dry-run یعنی یک کلیک با intercept و abort پیش از dispatch؛ نتیجهٔ سفارش ادعا نمی‌شود.</li>
        </ul>
      </Note>
    </div>
  );
}
