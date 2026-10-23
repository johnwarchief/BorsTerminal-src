// features/portfolio/components/sarkhati/Round22AutoClickerCard.tsx — اجرایِ واقعیِ سرخطی
//
// این کارت آینهٔ فشردهٔ نردبانِ ده‌فکتی و فرمان‌هایِ اجراست؛ سطحِ کاملِ کنترل
// در تبِ پنل (همان پنجره/پروفایلِ EasyTrader) باز می‌شود. هیچ فیلدی از اینجا
// به فرمِ کارگزاری نمی‌رود: قیمت/تعداد را کاربر خودش در فرم وارد می‌کند و
// برنامه فقط می‌خواند و مقایسه می‌کند.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import {
  autoclickerApi, type ApiReply, type AutoClickerStateView, type RunView,
} from '../../lib/autoclickerClient';
import { Chip, DangerBtn, GhostBtn, Section } from './parts';

const SHORT: Record<string, string> = {
  browser_open: 'پنجره',
  page_loaded: 'صفحه',
  login_verified: 'ورود',
  panel_connected: 'پنل',
  form_usable: 'فرم',
  symbol_side_detected: 'نماد/سمت',
  price_quantity_match: 'قیمت/تعداد',
  submit_button_ready: 'دکمه',
  constraints_checked: 'محدودیت‌ها',
  schedule_state: 'زمان‌بندی',
};

const STATE_LABEL: Record<string, string> = {
  DRAFT: 'پیش‌نویس',
  ARMED: 'مسلح',
  WARMING: 'گرم‌کردن',
  RUNNING: 'در حال اجرا',
  COMPLETED: 'تمام',
  STOPPED: 'متوقف',
  CANCELLED: 'لغو‌شده',
  BLOCKED: 'مسدود',
  NEEDS_REVIEW: 'نیازمند بازبینی',
  MISSED_TARGET: 'هدف از دست رفت',
  EXPIRED: 'منقضی',
};

const INPUT = 'min-w-0 rounded-md border border-border-c bg-bg-primary px-1.5 py-1 '
  + 'text-2xs text-text-primary outline-none focus:border-border-accent';

function toneOf(status: string): 'ok' | 'warn' | 'bad' | 'idle' {
  if (status === 'PASS') return 'ok';
  if (status === 'FAIL') return 'bad';
  if (status === 'WARN' || status === 'UNKNOWN') return 'warn';
  return 'idle';
}

function word(status: string): string {
  if (status === 'PASS') return 'سبز';
  if (status === 'FAIL') return 'قرمز';
  if (status === 'WARN') return 'هشدار';
  if (status === 'UNKNOWN') return 'نامعلوم';
  return status || '—';
}

function fa(n: unknown): string {
  const v = Number(n);
  return Number.isFinite(v) ? toFaDigits(v.toLocaleString('en-US')) : '—';
}

/** «الان» به وقتِ تهران برایِ مقدارِ پیش‌فرضِ ورودیِ datetime-local. */
function tehranNowLocal(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tehran', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date());
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}

export default function Round22AutoClickerCard() {
  const q = useQuery({
    queryKey: ['autoclicker-round22-state'],
    queryFn: () => autoclickerApi.state(),
    refetchInterval: 1500,
  });
  const st = q.data as AutoClickerStateView | undefined;
  const run: RunView | null = st?.run ?? null;
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad'>('warn');
  const [form, setForm] = useState({
    symbol: '', side: 'buy' as 'buy' | 'sell', price: '', qty: '',
    target: '', mode: 'single' as 'single' | 'repeat', count: '1', interval: '1000',
  });

  const facts = useMemo(
    () => (st?.fact_order ?? []).map((k) => [k, st?.facts?.[k]] as const),
    [st],
  );
  const ready = facts.every(([, f]) => f?.status === 'PASS');
  const preview = run?.preview;
  const running = ['ARMED', 'WARMING', 'RUNNING'].includes(String(run?.state ?? ''));

  const act = async (name: string, fn: () => Promise<ApiReply>, okText: string) => {
    setBusy(name); setMsg('');
    try {
      const res = await fn();
      const ok = res.status === 'success';
      setTone(ok ? 'ok' : 'warn');
      setMsg(ok ? okText : String(res.detail ?? res.code ?? 'انجام نشد'));
      await q.refetch();
    } catch (e) {
      setTone('bad');
      setMsg(e instanceof Error ? e.message : String(e));
    } finally { setBusy(''); }
  };

  const plan = () => {
    const price = Number(form.price);
    const qty = Number(form.qty);
    return autoclickerApi.createRun({
      symbol: form.symbol.trim(),
      side: form.side,
      expected_price: price,
      expected_quantity: qty,
      target_at: form.target || tehranNowLocal(),
      mode: form.mode,
      total_actions: form.mode === 'single' ? 1 : Number(form.count || 1),
      interval_ms: form.mode === 'single' ? 0 : Number(form.interval || 0),
      //: این کارت فقط تمرین می‌سازد؛ اجرایِ زنده فقط از پنل با عبارتِ تأیید.
      dry_run: true,
    });
  };

  return (
    <Section
      title="اجرایِ واقعیِ سرخطی"
      sub={`Round 22 · نسخهٔ ${st?.app_version ?? '—'} · وقتِ تهران ${st?.timezone?.now_local ?? '—'}`}
      testId="autoclicker-round22"
      right={<Chip tone={ready ? 'ok' : 'warn'} testId="autoclicker-round22-ready">
        {ready ? 'همهٔ شرط‌ها سبز' : 'آماده نیست'}
      </Chip>}
    >
      <div className="flex flex-wrap gap-1" data-testid="autoclicker-round22-ladder">
        {facts.map(([key, f]) => (
          <Chip key={key} tone={toneOf(String(f?.status ?? 'UNKNOWN'))}
            testId={`autoclicker-fact-${key}`}
            title={f?.detail || 'شاهد ثبت نشده'}>
            {SHORT[key] ?? key}: {word(String(f?.status ?? 'UNKNOWN'))}
          </Chip>
        ))}
      </div>

      <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          نماد
          <input className={`${INPUT} flex-1`} value={form.symbol} data-testid="ac22-symbol"
            onChange={(e) => setForm({ ...form, symbol: e.target.value })} />
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          سمت
          <select className={`${INPUT} flex-1`} value={form.side} data-testid="ac22-side"
            onChange={(e) => setForm({ ...form, side: e.target.value as 'buy' | 'sell' })}>
            <option value="buy">خرید</option>
            <option value="sell">فروش</option>
          </select>
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          قیمت
          <input className={`${INPUT} flex-1`} inputMode="numeric" value={form.price}
            data-testid="ac22-price"
            onChange={(e) => setForm({ ...form, price: e.target.value })} />
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          تعداد
          <input className={`${INPUT} flex-1`} inputMode="numeric" value={form.qty}
            data-testid="ac22-qty"
            onChange={(e) => setForm({ ...form, qty: e.target.value })} />
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          زمان (تهران)
          <input className={`${INPUT} flex-1`} type="datetime-local" value={form.target}
            data-testid="ac22-target"
            onChange={(e) => setForm({ ...form, target: e.target.value })} />
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          حالت
          <select className={`${INPUT} flex-1`} value={form.mode} data-testid="ac22-mode"
            onChange={(e) => setForm({ ...form, mode: e.target.value as 'single' | 'repeat' })}>
            <option value="single">تک‌اقدام</option>
            <option value="repeat">تکرارِ محدود</option>
          </select>
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          تعداد اقدام
          <input className={`${INPUT} flex-1`} inputMode="numeric" value={form.count}
            disabled={form.mode === 'single'} data-testid="ac22-count"
            onChange={(e) => setForm({ ...form, count: e.target.value })} />
        </label>
        <label className="flex items-center gap-1 text-3xs text-text-muted">
          فاصله (ms)
          <input className={`${INPUT} flex-1`} inputMode="numeric" value={form.interval}
            disabled={form.mode === 'single'} data-testid="ac22-interval"
            onChange={(e) => setForm({ ...form, interval: e.target.value })} />
        </label>
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <Chip tone="idle" testId="ac22-mode-chip">تمرین (dry-run)</Chip>
        <GhostBtn testId="ac22-save" disabled={busy !== ''}
          onClick={() => void act('save', plan, 'اجرا ساخته شد؛ پیش‌نمایش را ببینید.')}>
          ذخیره و پیش‌نمایش
        </GhostBtn>
        <GhostBtn testId="ac22-check" disabled={busy !== ''}
          onClick={() => void act('check', autoclickerApi.check,
            'فرم و محدودیت‌ها خوانده شد.')}>
          بررسی آمادگی
        </GhostBtn>
        <GhostBtn testId="ac22-arm" disabled={busy !== '' || !run}
          onClick={() => void act('arm', autoclickerApi.arm,
            'اجرا مسلح شد؛ هنوز کلیکی انجام نمی‌شود.')}>
          مسلح‌کردن
        </GhostBtn>
        <GhostBtn testId="ac22-start" disabled={busy !== '' || run?.state !== 'ARMED'}
          onClick={() => void act('start', autoclickerApi.start,
            'زمان‌بندی شروع شد.')}>
          شروع
        </GhostBtn>
        <DangerBtn testId="ac22-stop" disabled={busy !== ''}
          onClick={() => void act('stop', autoclickerApi.stop,
            'اجرا متوقف شد؛ ردیف‌هایِ مانده لغو شدند.')}>
          توقف اضطراری
        </DangerBtn>
        <GhostBtn testId="ac22-panel" disabled={busy !== ''}
          onClick={() => void act('panel', autoclickerApi.openPanel,
            'تبِ پنل در همان پنجره باز شد.')}>
          بازکردن پنل در پنجرهٔ EasyTrader
        </GhostBtn>
      </div>

      {preview ? (
        <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-2xs text-text-secondary"
          data-testid="ac22-preview">
          <span>اجرا {STATE_LABEL[String(run?.state ?? '')] ?? run?.state ?? '—'}</span>
          <span>حداکثر سفارش <b className="num">{fa(preview.max_orders_possible)}</b></span>
          <span>حداکثر سهم <b className="num">{fa(preview.total_shares_possible)}</b></span>
          <span>حداکثر ارزش <b className="num">{fa(preview.max_gross_value_rial)}</b> ریال</span>
          <span>انجام‌شده <b className="num">{fa(run?.fired_actions)}</b> از{' '}
            <b className="num">{fa(preview.total_actions)}</b></span>
          <span>{preview.dry_run ? 'تمرین' : 'زنده'} · {preview.target_at_local ?? '—'}</span>
        </div>
      ) : null}

      <p className="mt-1 text-3xs text-text-muted" data-testid="ac22-warning">
        هر کلیکِ موفق رویِ دکمهٔ ثبت می‌تواند یک سفارشِ مستقل بسازد. قیمت و تعداد را
        خودتان در فرمِ EasyTrader وارد کنید؛ برنامه آن‌ها را فقط می‌خواند و مقایسه می‌کند.
        سقف {fa(st?.ceiling?.max_actions)} اقدام و کفِ فاصله {fa(st?.ceiling?.min_interval_ms)}ms
        سقفِ داخلیِ BorsTerminal است، نه عددِ اعلام‌شدهٔ کارگزاری.
      </p>

      {msg ? (
        <p className={`mt-1 text-2xs ${tone === 'ok' ? 'text-accent-green'
          : tone === 'bad' ? 'text-accent-red' : 'text-accent-yellow'}`}
        data-testid="ac22-msg">
          {msg}{' '}({running ? 'اجرای فعال' : 'بی‌اجرا'})
        </p>
      ) : null}

      <details className="mt-1.5 text-2xs text-text-secondary">
        <summary className="cursor-pointer text-3xs text-text-muted">شاهدِ هر خانه</summary>
        <ul className="mt-1 space-y-0.5">
          {facts.map(([key, f]) => (
            <li key={key} data-testid={`ac22-detail-${key}`}>
              <b>{f?.label ?? SHORT[key] ?? key}</b>: {f?.status ?? 'UNKNOWN'} — {f?.detail || '—'}
              {f?.source ? <span className="text-text-muted"> ({f.source})</span> : null}
            </li>
          ))}
        </ul>
      </details>
    </Section>
  );
}
