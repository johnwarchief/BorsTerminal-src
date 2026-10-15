// features/portfolio/components/BotPanel.tsx — ربات معاملاتی درِ برنامۀ دسکتاپ
//
// چرا این پنل هست: موتورِ ربات (`paper_trading.py`) از دورِ پیش آماده بود و
// ۵۴ سنجه می‌گذراند، ولی درِ برنامه هیچ دری نداشت — یعنی برایِ مالک وجود
// نداشت. این پنل همان در است: پیکربندی، اجرایِ **دستیِ** یکِ نشست، وضعیتِ
// واقعیِ قفل، تاریخچه، و توقف/ادامه.
//
// سه قولِ متنی که درِ کد هم نقض نمی‌شود:
//  • پیش‌فرض کاغذی است و با باز شدنِ برنامه هیچ اجرا نمی‌شود.
//  • «اجرایِ واقعی» سه قفل دارد؛ اگر یکی بسته باشد، رابط صریح می‌گوید کدام.
//  • هیچ‌جا وعدهٔ اولی بودن یا پرشدنِ قطعی داده نمی‌شود.
//
// چیدمان عمداً فشرده است: یکِ سطرِ وضعیت + سه دکمه، و بقیه پشتِ باز‌شو.
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import {
  botApi, invalidateBot, KILL_LABEL, useBotHistory, useBotStatus, VERDICT_LABEL,
  verdictOf, type RunVerdict,
} from '../lib/botClient';

type Tone = 'green' | 'red' | 'yellow' | 'gray' | 'blue';

const KILL_TONE: Record<string, Tone> = { ARMED: 'green', HALTED: 'yellow', TRIPPED: 'red' };

/** عددِ فارسی با جداکنندۀ هزارگان؛ null ⇒ «—» نه صفر */
function n(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  return toFaDigits(v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }));
}

export function BotPanel() {
  const qc = useQueryClient();
  const { data: status, isError } = useBotStatus();
  const { data: history } = useBotHistory(!!status);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<{ kind: RunVerdict; text: string } | null>(null);
  const [errs, setErrs] = useState<string[]>([]);
  const [liveConfirm, setLiveConfirm] = useState('');

  const cfg = status?.config ?? null;
  const gates = status?.live_gates ?? null;
  const last = (status?.last_runs ?? [])[0];

  const summary = useMemo(() => {
    if (!status) return 'در حال خواندنِ وضعیتِ ربات…';
    const mode = status.config?.mode === 'live' ? 'واقعی' : 'کاغذی';
    const eq = status.account?.equity;
    return `ربات ${status.config?.enabled ? 'روشن' : 'خاموش'} · ${mode} · ${KILL_LABEL[status.kill] ?? status.kill}`
      + ` · ${n(status.account?.positions ?? 0)} موقعیت · سرمایهٔ نمایشی ${n(eq)} ریال`;
  }, [status]);

  async function act(kind: string, fn: () => Promise<Record<string, unknown> | null | undefined>) {
    setBusy(kind); setErrs([]);
    try {
      const res = await fn();
      const v = verdictOf(res);
      const run = res?.run as { session?: string; decisions?: unknown[] } | undefined;
      const raw = String(res?.message ?? run?.session ?? '');
      const msg = /^\d{6,8}$/.test(raw) ? toFaDigits(raw) : raw;   // نشستِ عددی با رقمِ فارسی
      setVerdict({
        kind: v,
        text: kind === 'run'
          ? `${VERDICT_LABEL[v]}${msg ? ' — ' + msg : ''}${
            v === 'ok' ? ` · ${toFaDigits(run?.decisions?.length ?? 0)} تصمیم` : ''}`
          : `${VERDICT_LABEL[v]}${msg ? ' — ' + msg : ''}`,
      });
      invalidateBot(qc);
    } catch (e) {
      // حالتِ جدا: نمی‌دانیم چه شد. نه «اجرا شد» می‌گوییم نه «اجرا نشد» —
      // و درخواستِ دوباره هم خودکار نمی‌فرستیم (retries: 0 درِ botApi).
      setVerdict({ kind: 'unknown',
        text: `${VERDICT_LABEL.unknown} — پاسخ نرسید: `
          + (e instanceof Error ? e.message.slice(0, 80) : String(e).slice(0, 80)) });
    } finally {
      setBusy(null);
    }
  }

  async function saveConfig(patch: Record<string, unknown>) {
    await act('config', async () => {
      const res = await botApi.putConfig(patch);
      const list = Array.isArray(res?.errors) ? (res!.errors as unknown[]).map(String) : [];
      setErrs(list);
      return res;
    });
  }

  if (isError) {
    return (
      <section data-testid="bot-panel" className="rounded-lg border border-border-c bg-bg-card/40 p-3">
        <div className="text-xs font-bold text-text-primary">ربات معاملاتی</div>
        <p className="mt-1 text-2xs text-text-muted">
          دروازۀ ربات در این نسخه پاسخ نداد. ربات اجرا نشده است — این با «خاموش» یکی نیست.
        </p>
      </section>
    );
  }

  const tone: Tone = verdict ? (verdict.kind === 'ok' ? 'green' : verdict.kind === 'halted' ? 'yellow' : 'red') : 'gray';
  const liveBlockedReason = !gates ? 'وضعیتِ قفل‌ها نامعلوم است'
    : !gates.env_live ? 'متغیرِ محیطیِ BORS_EXECUTION_LIVE روشن نیست'
      : !gates.live_capable ? 'آداپتورِ فعال این قابلیت‌ها را اعلام نکرده (place + order_state + list_orders)'
        : gates.session !== 'connected' ? 'نشستِ کارگزاری راستی‌آزمایی‌نشده' : '';

  return (
    <section data-testid="bot-panel" className="rounded-lg border border-border-c bg-bg-card/40">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <button
          type="button"
          data-testid="bot-toggle-open"
          onClick={() => setOpen((v) => !v)}
          className="text-xs font-black text-text-primary"
          aria-expanded={open}
        >
          {open ? '▾' : '▸'} ربات معاملاتی
        </button>
        <Badge tone={status?.kill === 'ARMED' ? 'green' : KILL_TONE[status?.kill ?? ''] ?? 'gray'}>
          {KILL_LABEL[status?.kill ?? ''] ?? status?.kill ?? '—'}
        </Badge>
        <span className="text-2xs text-text-muted">{summary}</span>
        {last ? (
          <span className="num text-2xs text-text-muted">
            آخرین اجرا: نشست {toFaDigits(last.session)} · {n(last.bars)} ردیف ·{' '}
            {n(last.decisions?.reduce((a, d) => a + d.signals, 0) ?? 0)} سیگنال ·{' '}
            {n(last.decisions?.reduce((a, d) => a + d.dispatched, 0) ?? 0)} ارسال
          </span>
        ) : <span className="text-2xs text-text-muted">هنوز اجرایی ثبت نشده</span>}

        <div className="ms-auto flex items-center gap-1.5">
          <button
            type="button"
            data-testid="bot-run"
            disabled={!!busy}
            onClick={() => act('run', () => botApi.run())}
            className="rounded-md border border-accent-blue/60 bg-accent-blue/15 px-2.5 py-1 text-2xs font-bold text-accent-blue disabled:opacity-40"
          >
            {busy === 'run' ? 'در حال اجرا…' : 'اجرایِ نشست'}
          </button>
          {status?.halted ? (
            <button
              type="button" data-testid="bot-resume" disabled={!!busy}
              onClick={() => act('resume', () => botApi.resume())}
              className="rounded-md border border-border-c px-2.5 py-1 text-2xs font-bold text-text-secondary disabled:opacity-40"
            >ادامه</button>
          ) : (
            <button
              type="button" data-testid="bot-halt" disabled={!!busy}
              onClick={() => act('halt', () => botApi.halt('توقفِ دستی از پنل'))}
              className="rounded-md border border-accent-red/50 px-2.5 py-1 text-2xs font-bold text-accent-red disabled:opacity-40"
            >توقف</button>
          )}
        </div>
      </div>

      {verdict ? (
        <div className="px-3 pb-2" role="status" aria-live="polite">
          <Badge tone={tone}>{verdict.text}</Badge>
        </div>
      ) : null}

      {open ? (
        <div className="border-t border-border-c/60 px-3 py-2.5">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            <label className="flex items-center gap-1.5 text-2xs text-text-secondary">
              <input
                type="checkbox" data-testid="bot-enabled"
                checked={!!cfg?.enabled}
                onChange={(e) => void saveConfig({ enabled: e.target.checked })}
              />
              روشن
            </label>
            <Field label="پیش‌فاصلۀ اندازه" value={cfg?.sizing_fraction} scale={100}
              onCommit={(v) => void saveConfig({ sizing_fraction: v })} />
            <Field label="سقف سفارش در نشست" value={cfg?.max_orders}
              onCommit={(v) => void saveConfig({ max_orders: v })} />
            <Field label="سقف ارزش هر سفارش (ریال)" value={cfg?.max_order_value}
              onCommit={(v) => void saveConfig({ max_order_value: v })} />
            <Field label="سقف ضرر روز (ریال)" value={cfg?.max_daily_loss}
              onCommit={(v) => void saveConfig({ max_daily_loss: v })} />
            <Field label="سرمایهٔ شروع (ریال)" value={cfg?.start_cash}
              onCommit={(v) => void saveConfig({ start_cash: v })} />
            <label className="text-2xs text-text-secondary">
              <span className="block">حالتِ بنیادی</span>
              <select
                data-testid="bot-fund-mode" defaultValue={cfg?.fund_mode ?? 'standard'}
                onChange={(e) => void saveConfig({ fund_mode: e.target.value })}
                className="mt-0.5 w-full rounded-md border border-border-c bg-bg-primary px-1.5 py-1 text-2xs"
              >
                <option value="hard">سخت</option>
                <option value="standard">استاندارد</option>
                <option value="exception">با استثنا</option>
              </select>
            </label>
            <label className="text-2xs text-text-secondary">
              <span className="block">ترکیب چیپ‌ها</span>
              <select
                data-testid="bot-logic" defaultValue={cfg?.logic ?? 'and'}
                onChange={(e) => void saveConfig({ logic: e.target.value })}
                className="mt-0.5 w-full rounded-md border border-border-c bg-bg-primary px-1.5 py-1 text-2xs"
              >
                <option value="and">اشتراک</option>
                <option value="or">اجتماع</option>
              </select>
            </label>
          </div>

          {errs.length ? (
            <ul data-testid="bot-config-errors" className="mt-2 space-y-0.5 text-2xs text-accent-red">
              {errs.map((e) => <li key={e}>• {e}</li>)}
            </ul>
          ) : null}

          <div className="mt-3 rounded-md border border-border-c/70 p-2">
            <div className="text-2xs font-bold text-text-primary">مسیرِ اجرایِ واقعی</div>
            <ul className="mt-1 space-y-0.5 text-2xs text-text-muted">
              <li>{gates?.env_live ? '✓' : '✗'} متغیرِ محیطیِ اجرا (BORS_EXECUTION_LIVE)</li>
              <li>{gates?.live_capable ? '✓' : '✗'} آداپتورِ {toFaDigits(gates?.adapter ?? 'mock')} این
                قابلیت‌ها را دارد: place + order_state + list_orders</li>
              <li>{gates?.session === 'connected' ? '✓' : '✗'} نشستِ راستی‌آزمایی‌شدۀ کارگزاری
                ({toFaDigits(gates?.session ?? 'none')})</li>
            </ul>
            <div className="mt-1.5 text-2xs text-text-secondary">
              {liveBlockedReason
                ? `اجرایِ واقعی بسته است: ${liveBlockedReason}.`
                : 'سه قفل باز است؛ با نوشتنِ عبارتِ تأیید، حالتِ ربات بر «واقعی» می‌گذارد.'}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <input
                data-testid="bot-live-confirm" value={liveConfirm}
                disabled={!!liveBlockedReason}
                onChange={(e) => setLiveConfirm(e.target.value)}
                placeholder={status?.confirm_phrase}
                className="min-w-[14rem] flex-1 rounded-md border border-border-c bg-bg-primary px-1.5 py-1 text-2xs disabled:opacity-40"
              />
              <button
                type="button" data-testid="bot-live-arm"
                title={liveBlockedReason || 'سه قفل باز است'}
                disabled={!!liveBlockedReason || liveConfirm !== (status?.confirm_phrase || '')}
                onClick={() => void saveConfig({ mode: 'live', confirm: liveConfirm })}
                className="rounded-md border border-accent-red/60 px-2.5 py-1 text-2xs font-bold text-accent-red disabled:opacity-40"
              >انتقالِ ربات به اجرایِ واقعی</button>
            </div>
            {cfg?.mode === 'live' ? (
              <button
                type="button" data-testid="bot-to-paper"
                onClick={() => void saveConfig({ mode: 'paper' })}
                className="mt-1.5 rounded-md border border-border-c px-2.5 py-1 text-2xs text-text-secondary"
              >بازگشت به کاغذی</button>
            ) : null}
          </div>

          <div className="mt-3">
            <div className="text-2xs font-bold text-text-primary">تاریخچۀ اجرا</div>
            <div className="mt-1 overflow-x-auto">
              <table className="w-full text-2xs">
                <thead className="text-text-muted">
                  <tr>
                    <th className="text-start font-bold">نشست</th>
                    <th className="text-start font-bold">ردیف</th>
                    <th className="text-start font-bold">سیگنال</th>
                    <th className="text-start font-bold">ارسال‌شده</th>
                    <th className="text-start font-bold">ردشده</th>
                    <th className="text-start font-bold">سرمایه</th>
                  </tr>
                </thead>
                <tbody>
                  {(history?.runs ?? []).slice(-8).reverse().map((r, i) => {
                    const agg = (r.decisions ?? []).reduce(
                      (a, d) => ({ sig: a.sig + d.signals, dis: a.dis + d.dispatched, rej: a.rej + d.rejected }),
                      { sig: 0, dis: 0, rej: 0 });
                    return (
                      <tr key={`${r.at}-${i}`} data-testid={`bot-run-row-${r.session}`}
                          className="border-t border-border-c/40">
                        <td className="num py-0.5">{toFaDigits(r.session)}</td>
                        <td className="num py-0.5">{n(r.bars)}</td>
                        <td className="num py-0.5">{n(agg.sig)}</td>
                        <td className="num py-0.5">{n(agg.dis)}</td>
                        <td className="num py-0.5">{n(agg.rej)}</td>
                        <td className="num py-0.5">{n(r.decisions?.[r.decisions.length - 1]?.equity)}</td>
                      </tr>
                    );
                  })}
                  {(history?.runs ?? []).length === 0 ? (
                    <tr><td colSpan={6} className="py-1 text-text-muted">
                      اجرایی ثبت نشده. ربات تنها با دکمهٔ «اجرایِ نشست» کار می‌کند.
                    </td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2 text-2xs text-text-muted">
            <button
              type="button" data-testid="bot-reset"
              onClick={() => act('reset', () => botApi.resetAccount())}
              className="rounded-md border border-border-c px-2 py-0.5 text-text-secondary"
            >صفرِکردنِ حسابِ کاغذی</button>
            <span>دفترِ ردِّپا پاک نمی‌شود.</span>
            <span className="ms-auto">{status?.note}</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** رقم‌هایِ فارسی/عربیِ واردشده را با کدپونتی برمی‌گرداند، نه با فهرستِ دستیِ
 *  کاراکتر: یکِ رقمِ جاافتاده درِ چنین فهرستی، بی‌سروصدا عدد را عوض می‌کند
 *  (سابقۀ همین مخزن درِ متن‌هایِ فارسی). */
function parseFaNumber(s: string): number {
  const latin = s.replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[،٫]/g, '.');
  const n = Number(latin);
  return Number.isFinite(n) ? n : NaN;
}

/** ورودیِ عددیِ کوچک: رقمِ فارسی/لاتین را می‌پذیرد و درِ blur می‌فرستد.
 *  `scale` برایِ درصد است (0.05 ⇄ ۵): مقدارِ ذخیره‌شده همیشه واحدِ پایه است. */
function Field({ label, value, scale = 1, onCommit }: {
  label: string;
  value: number | null | undefined;
  scale?: number;
  onCommit: (v: number) => void;
}) {
  const shown = value === null || value === undefined ? '' : String(value * scale);
  const [raw, setRaw] = useState(shown);
  const [synced, setSynced] = useState(shown);
  if (shown !== synced) { setRaw(shown); setSynced(shown); }   // بی‌useEffect، فقط همگام‌سازیِ مقدارِ بیرونی
  return (
    <label className="text-2xs text-text-secondary">
      <span className="block">{label}{scale !== 1 ? ' (٪)' : ''}</span>
      <input
        inputMode="decimal"
        value={raw}
        onChange={(e) => setRaw(e.target.value.replace(/[^0-9۰-۹٠-٩.،٫]/g, ''))}
        onBlur={() => {
          const num = parseFaNumber(raw);
          if (Number.isFinite(num) && num > 0) onCommit(num / scale);
        }}
        className="num mt-0.5 w-full rounded-md border border-border-c bg-bg-primary px-1.5 py-1 text-2xs"
      />
    </label>
  );
}
