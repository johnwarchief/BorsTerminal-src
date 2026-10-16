// features/portfolio/components/ExecutionPanel.tsx -- کنترلِ سرخطی، با وضعیتِ واقعی
//
// این پنل جایِ «اسلاتِ غیرفعال»ِ پیشین درِ WatchSummaryPanel است. قاعدۀِ حاکم:
// هیچ کنترلی بی‌پشتوانه روشن نمی‌شود. `capabilities` و `session` از پاسخِ
// `/api/execution/status` می‌آیند (features/portfolio/lib/orderClient.ts) — نه
// از متنِ ثابتِ رابط. بی‌نشست، برچسب «نشست بسته است» نوشته می‌شود نه «Connected».
//
// ارتفاعِ پنل درِ حالتِ بی‌کارکردن (~۳ سطر) می‌ماند: یک خطِ پاسخ، چیپ‌ها درِ یک
// ردیفِ جمع‌شونده، و جزئیات (پیش‌نمایشِ بدنه، تاریخچه، نشانیِ نشست) پشتِ یک
// بازشو. هیچ متنی که کاربر روزانه نمی‌خواند بیرونِ بازشو نیست.
//
// نشانیِ نشست: فیلدِ type=password، بی‌ autoComplete، و مقدارش هرگز درِ stateِ
// قابلِ لاگِ سرور/کوئری‑کی نمی‌نشیند؛ فقط به `POST /api/execution/session`
// می‌رود و دور ریخته می‌شود.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge } from '@shared/components/Badge';
import { HttpError } from '@shared/api/http';
import { fmtInt, parseNum, toEnDigits, toFaDigits } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';
import {
  CODE_LABEL, PHASE_LABEL, SESSION_LABEL, invalidateExecution, messageOf,
  orderApi, phaseFromResponse, phaseOf, useExecutionLedger, useExecutionStatus,
  type ActionState, type ExecutionRecord, type OrderPhase,
} from '../lib/orderClient';

const freshId = () => 'ui-' + Math.random().toString(36).slice(2, 10);

/** متنِ امنِ خطا — هیچ‌وقت بدنهٔ پاسخ یا هدرِ درخواست را نشان نمی‌دهیم */
function safeError(e: unknown): string {
  if (e instanceof HttpError) return `خطایِ ${e.status} درِ ${e.url.replace(/^https?:\/\/[^/]+/, '')}`;
  if (e instanceof Error) return e.message.slice(0, 140);
  return 'خطایِ نامعلوم';
}

const TONE: Record<ActionState, string> = {
  idle: 'text-text-secondary',
  busy: 'text-text-muted',
  ok: 'text-accent-green',
  warn: 'text-accent-yellow',
  unknown: 'text-accent-orange',
  error: 'text-accent-red',
};

type ExecAction = 'preflight' | 'preview' | 'dispatch' | 'refresh' | 'reconcile'
  | 'queue' | 'halt' | 'resume' | 'probe' | 'session';

/**
 * پاسخِ هر اقدام جدا معنا می‌شود، چون فازهایِ مسیرِ اجرا جداوند: «پیش‌فرود»
 * ارسال نیست، «توقف» وضعیتِ هیچ سفارشی را عوض نمی‌کند، و «نامعلوم» هرگز به
 * «ردشده» برگردانده نمی‌شود (بندِ ۴-ج مأموریت). عددِ پاسخ ازِ خودِ پاسخِ
 * سرویس می‌آید، نه ازِ متنِ ثابتِ رابط.
 */
function summarize(kind: ExecAction, res: Record<string, unknown>, wireHypothesis: boolean):
  { state: ActionState; phase: OrderPhase | null; text: string } {
  const err = messageOf(res);
  if (res.status === 'error' || res.status === 'refused') {
    const unknown = res.unknown_result === true
      || ['TIMEOUT', 'NETWORK_ERROR', 'UNKNOWN_RESULT'].includes(String(res.code));
    return { state: unknown ? 'unknown' : 'error',
      phase: unknown ? 'unknown' : 'errored',
      text: err || (unknown ? 'نتیجه نامعلوم — فقط رفعِ ابهام، نه ارسالِ دوباره' : 'رد شد') };
  }
  switch (kind) {
    case 'preflight': {
      const checks = (res.checks ?? {}) as Record<string, string>;
      const vals = Object.values(checks);
      const fail = vals.filter((v) => v === 'FAIL').length;
      const unk = vals.filter((v) => v === 'UNKNOWN').length;
      const reasons = (res.reasons ?? {}) as Record<string, string>;
      const why = Object.entries(checks).filter(([, v]) => v === 'FAIL')
        .map(([k]) => `${k}${reasons[k] ? ` (${reasons[k]})` : ''}`).join('، ');
      return { state: fail ? 'warn' : 'ok', phase: 'preflight',
        text: `پیش‌فرود: ${toFaDigits(vals.length - fail - unk)} سبز`
          + (fail ? `، ${toFaDigits(fail)} رد${why ? ` — ${why}` : ''}` : '')
          + (unk ? `، ${toFaDigits(unk)} نامعلوم` : '') };
    }
    case 'preview':
      return { state: 'ok', phase: 'preflight',
        text: 'پیش‌نمایشِ بدنۀ واقعی آماده شد'
          + (wireHypothesis ? ' — سیم هنوز علیه کارگزاری تأیید نشده' : '') };
    case 'dispatch': {
      const r = phaseFromResponse(res);
      if (r.phase === 'scheduled') {
        return { state: 'ok', phase: 'scheduled',
          text: 'زمان‌بندی شد — تا مهلت هیچ درخواستی نمی‌رود و «توقف» آن را لغو می‌کند' };
      }
      const rec = res.record as ExecutionRecord | undefined;
      return { state: r.state, phase: r.phase,
        text: r.phase === 'unknown'
          ? 'نتیجه نامعلوم — «رفعِ ابهام» از فهرستِ سفارش، نه ارسالِ دوباره'
          : `${PHASE_LABEL[r.phase]}${rec?.broker_order_id ? ` — ${rec.broker_order_id}` : ''}` };
    }
    case 'refresh':
    case 'reconcile': {
      const rec = res.record as ExecutionRecord | undefined;
      const ph = phaseOf(rec ?? null);
      return { state: ph === 'unknown' ? 'unknown' : 'ok', phase: ph,
        text: `${kind === 'reconcile' ? 'رفعِ ابهام' : 'بازخوانی'}: ${PHASE_LABEL[ph]}`
          + (rec?.broker_order_id ? ` — ${rec.broker_order_id}` : '') };
    }
    case 'queue': {
      if (res.supported === false) {
        return { state: 'warn', phase: null, text: String(res.reason ?? 'کارگزاری جایِ صف نمی‌دهد') };
      }
      const snap = res.snapshot as { position?: number | null; volume_ahead?: number | null } | null;
      if (!res.known || snap?.position == null) {
        return { state: 'warn', phase: null,
          text: String(res.reason ?? 'جایِ صف داده نشد — «نمی‌دانیم»، نه صفر') };
      }
      return { state: 'ok', phase: null,
        text: `جایِ صف: ${toFaDigits(snap.position)}`
          + (snap.volume_ahead != null
            ? ` (حجمِ جلوتر ${toFaDigits(snap.volume_ahead)} — واحدش تأیید نشده)` : '') };
    }
    case 'halt':
      return { state: 'warn', phase: null,
        text: 'توقف برقرار شد — رویِ دیسک می‌ماند'
          + (Number(res.aborted_schedules) > 0
            ? ` و ${toFaDigits(Number(res.aborted_schedules))} زمان‌بندی لغو شد` : '') };
    case 'resume':
      return { state: 'ok', phase: null,
        text: 'ادامه باز شد'
          + (Array.isArray(res.open_ids) && res.open_ids.length
            ? ` — ${toFaDigits(res.open_ids.length)} سفارشِ باز برایِ رفعِ ابهام` : '') };
    case 'probe':
      return res.ok
        ? { state: 'ok', phase: null,
          text: `اتصالِ فقط‌خواندنی تأیید شد (${toFaDigits(Math.round(Number(res.response_ms) || 0))} ms`
            + (res.orders_seen != null
              ? `، ${toFaDigits(Number(res.orders_seen))} سفارش دیده شد` : '') + ')' }
        : { state: 'warn', phase: null,
          text: String(res.detail ?? messageOf(res) ?? 'اتصال برقرار نشد') };
    case 'session':
      return res.status === 'success'
        ? { state: 'ok', phase: null,
          text: res.live ? 'نشست باز شد — اتصالِ زنده فعال است'
            : 'نشست در حافظه ماند (ترافیک هنوز خاموش است)' }
        : { state: 'warn', phase: null, text: messageOf(res) || 'نشست ذخیره نشد' };
  }
}

function Chip({ onClick, disabled, children, testId, tone = 'ghost', title }: {
  onClick: () => void; disabled?: boolean; children: React.ReactNode;
  testId: string; tone?: 'ghost' | 'danger' | 'primary'; title?: string;
}) {
  const skin = tone === 'danger'
    ? 'border-accent-red/40 text-accent-red hover:bg-accent-red/10'
    : tone === 'primary'
      ? 'border-accent-blue/40 text-accent-blue hover:bg-accent-blue/10'
      : 'border-border-c text-text-secondary hover:bg-bg-card';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled}
      title={title}
      data-testid={testId}
      className={`rounded-lg border px-2 py-0.5 text-3xs font-bold ${
        disabled ? 'cursor-not-allowed border-border-c/60 text-text-muted/60' : skin
      }`}
    >
      {children}
    </button>
  );
}

export function ExecutionPanel({ symbol, row }: { symbol: string; row: MarketRow | null }) {
  const { gate } = useExecutionStatus();
  const ledger = useExecutionLedger(gate.endpointPresent);
  const qc = useQueryClient();

  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [qty, setQty] = useState('');
  const [price, setPrice] = useState('');
  const [eid, setEid] = useState(freshId);
  const [confirmed, setConfirmed] = useState(false);
  const [phase, setPhase] = useState<OrderPhase>('idle');
  const [state, setState] = useState<ActionState>('idle');
  const [answer, setAnswer] = useState('');
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [last, setLast] = useState<ExecutionRecord | null>(null);
  const [queue, setQueue] = useState<string>('');
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState('');

  // هر تغییرِ فرم یکِ شناسۀِ تازه می‌سازد: «یک execution_id = یکِ تلاش» قاعدۀ
  // سرویس است (ردِّپایِ dispatch رویِ دیسک تکرار را می‌گیرد)، پس فرمِ ویرایش‌شده
  // نباید شناسۀِ سفارشِ قبلی را حمل کند.
  useEffect(() => { setEid(freshId()); setConfirmed(false); setPhase('idle'); },
    [symbol, side, price, qty]);

  const body = useCallback(() => ({
    execution_id: eid, symbol, side, mode: 'safe',
    price: parseNum(toEnDigits(price)),
    quantity: parseNum(toEnDigits(qty)),
    price_source: row?.p_last != null ? 'board.p_last' : 'unspecified',
    price_as_of: row?.row_h != null ? String(row.row_h) : null,
    confirmed,
  }), [eid, symbol, side, price, qty, row?.p_last, row?.row_h, confirmed]);

  const ask = useCallback(async (kind: ExecAction,
    fn: () => Promise<Record<string, unknown>>) => {
    setBusy(true);
    setState('busy');
    try {
      const res = await fn();
      const v = summarize(kind, res, gate.status?.wire_hypothesis === true);
      if (v.phase) setPhase(v.phase);
      setState(v.state);
      setAnswer(v.text);
      if (res.record) setLast(res.record as ExecutionRecord);
      if (res.snapshot || typeof res.position === 'number') {
        setQueue(String((res.snapshot as { position?: unknown })?.position
          ?? res.position ?? ''));
      }
      invalidateExecution(qc);
      return res;
    } catch (e) {
      setState('error');
      setAnswer(safeError(e));
      return null;
    } finally {
      setBusy(false);
    }
  }, [qc]);

  const records = useMemo(() => (ledger.data?.records ?? []).slice(-6).reverse(),
    [ledger.data]);
  const canSubmit = gate.canTrade && confirmed && !!parseNum(toEnDigits(qty))
    && !!parseNum(toEnDigits(price)) && !busy;
  const canPreview = gate.endpointPresent && !busy;
  // سبز بودنِ نشست فقط وقتی مجاز است که اتصالِ زنده واقعاً برقرار باشد — وگرنه
  // «نشستِ بدل» با رنگِ خنثی نشان داده می‌شود، تا هیچ‌وقت «Connected»ِ ظاهری
  // جایِ «به کارگزاری وصل نیستیم» را نگیرد (بندِ ۴-ب مأموریت).
  const sessionTone = gate.sessionState === 'connected'
    ? (gate.status?.live_enabled === true ? 'green' : 'gray')
    : gate.sessionState === 'unknown' ? 'gray' : 'red';
  const sessionText = gate.sessionState === 'connected' && gate.status?.live_enabled !== true
    ? 'نشستِ بدل باز است'
    : SESSION_LABEL[gate.sessionState];

  return (
    <div
      className="mt-auto rounded-xl border border-dashed border-border-c bg-bg-card/40 p-2"
      data-testid="watch-order-panel"
      data-can-trade={gate.canTrade ? 'true' : 'false'}
      data-adapter={gate.status?.adapter ?? 'none'}
      data-session={gate.sessionState}
    >
      <div className="mb-1 flex flex-wrap items-center justify-between gap-1">
        <h5 className="text-2xs font-black text-text-secondary">پنلِ معامله</h5>
        <div className="flex flex-wrap items-center gap-1">
          <Badge tone={gate.endpointPresent ? (gate.canTrade ? 'green' : 'yellow') : 'gray'}
            title={gate.status?.adapter === 'easytrader'
              ? 'سیمِ EasyTrader — هنوز هیچ ثابتش علیه کارگزاری تأیید نشده' : undefined}>
            {gate.endpointPresent
              ? `سرویسِ اجرا: ${gate.status?.adapter ?? '—'}${gate.dryRun ? ' · بدل' : ''}`
              : 'سرویسِ اجرا نیست'}
          </Badge>
          <Badge tone={sessionTone} title="وضعیتِ نشست از پاسخِ خودِ سرویس">
            {sessionText}
          </Badge>
        </div>
      </div>

      <div className="mb-1 grid grid-cols-2 gap-1.5">
        {(['buy', 'sell'] as const).map((s) => (
          <button
            key={s}
            type="button"
            disabled={!gate.endpointPresent}
            aria-disabled={!gate.endpointPresent}
            onClick={() => setSide(s)}
            data-testid={s === 'buy' ? 'watch-order-buy' : 'watch-order-sell'}
            aria-pressed={side === s}
            title={gate.endpointPresent
              ? (s === 'buy' ? 'جهتِ خرید' : 'جهتِ فروش')
              : gate.reason}
            className={`rounded-lg px-2 py-1.5 text-2xs font-black transition-colors ${
              side === s
                ? s === 'buy' ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
                : 'bg-accent-green/5 text-text-muted hover:bg-accent-green/10'
            } ${!gate.endpointPresent ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            {s === 'buy' ? 'خرید' : 'فروش'}
          </button>
        ))}
      </div>

      <div className="mb-1 grid grid-cols-2 gap-1.5">
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">
          قیمت (ریال)
          <input
            type="text" inputMode="numeric" value={price}
            onChange={(e) => setPrice(e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, ''))}
            data-testid="watch-order-price" placeholder={row?.p_last != null ? toFaDigits(String(row.p_last)) : '—'}
            className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary placeholder:text-text-muted"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">
          مقدار (سهم)
          <input
            type="text" inputMode="numeric" value={qty}
            onChange={(e) => setQty(e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, ''))}
            data-testid="watch-order-qty" placeholder="مثلاً ۱۰۰۰"
            className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary placeholder:text-text-muted"
          />
        </label>
      </div>

      {/* موجودی: هرگز صفرِ جعلی. نبودِ capability یعنی «نمی‌دانیم»، و عددِ
          تابلو هم جایِ «موجودِ نقدِ کارگزاری» را نمی‌گیرد. */}
      <div className="mb-1 flex flex-wrap items-baseline gap-1 text-3xs text-text-muted"
        data-testid="watch-order-balance-row">
        <span>موجودی:</span>
        <span className="num font-bold text-text-primary" data-testid="watch-order-balance">
          {gate.caps?.balances === true
            ? (row?.buy_power_i != null ? `${toFaDigits(row.buy_power_i.toFixed(2))}×` : '—')
            : 'بی‌داده'}
        </span>
        <span data-testid="watch-order-balance-note">
          {gate.caps?.balances === true
            ? 'از سرانۀ تابلو؛ موجودِ نقدِ کارگزاری نیست'
            : 'کارگزاری موجودی نمی‌دهد (capabilities.balances: false) — صفر جا نمی‌زند'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <div className="flex flex-wrap items-center gap-1" data-testid="watch-order-actions">
          <Chip testId="exec-preflight" disabled={!canPreview}
            title="پیش‌فرود: پیشِ هر ارسال، با هیچ سفارشی به کارگزاری نمی‌رود"
            onClick={() => void ask('preflight', () => orderApi.preflight(body()))}>پیش‌فرود</Chip>
          <Chip testId="exec-preview" disabled={!canPreview}
            title="بدنۀ واقعی که اگر اتصال وصل باشد می‌رود را نشان می‌دهد"
            onClick={() => void ask('preview', async () => {
              const res = await orderApi.prepare(body());
              setPreview(res);
              return res;
            })}>پیش‌نمایش</Chip>
          <label className="flex cursor-pointer items-center gap-1 text-3xs text-text-secondary"
            data-testid="exec-confirm-wrap">
            <input type="checkbox" checked={confirmed} disabled={!gate.canTrade}
              onChange={(e) => setConfirmed(e.target.checked)} data-testid="exec-confirm"
              className="size-3 accent-accent-blue" />
            تأییدِ نهایی
          </label>
          <button
            type="button"
            disabled={!canSubmit}
            aria-disabled={!canSubmit}
            onClick={() => void ask('dispatch', () => orderApi.dispatch(body()))}
            data-testid="exec-submit"
            title={canSubmit ? 'ارسالِ همین سفارش' : gate.reason || 'تأییدِ نهایی و مقدارِ معتبر لازم است'}
            className={`rounded-lg px-2.5 py-0.5 text-3xs font-black ${
              canSubmit ? 'bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30'
                : 'cursor-not-allowed bg-accent-blue/10 text-accent-blue/50'}`}
          >
            ارسال
          </button>
          <Chip testId="exec-probe" disabled={!gate.endpointPresent || busy}
            title="آزمونِ اتصالِ فقط‌خواندنی — هیچ سفارشی برایِ سنجشِ سرعت نمی‌رود"
            onClick={() => void ask('probe', () => orderApi.probe())}>آزمونِ اتصال</Chip>
          {gate.halted
            ? (
              <Chip testId="exec-resume" disabled={!gate.endpointPresent || busy} tone="primary"
                title="بازکردنِ قفلِ توقف — حالتِ خودکار بی‌تأییدِ صریح باز نمی‌شود"
                onClick={() => void ask('resume', () => orderApi.resume('ادامهٔ دستوری از رابط'))}>ادامه</Chip>
            )
            : null}
          <Chip testId="watch-kill-switch" disabled={!gate.endpointPresent}
            tone="danger"
            title={gate.endpointPresent
              ? 'توقفِ اضطراری: رویِ دیسک می‌نشیند و زمان‌بندی‌هایِ درِ انتظار را لغو می‌کند'
              : 'سرویسِ اجرا پاسخ نمی‌دهد'}
            onClick={() => void ask('halt', () => orderApi.halt('توقف از پنلِ معامله'))}>توقف</Chip>
        </div>
        <span className="ms-auto text-3xs text-text-muted" data-testid="watch-order-phase">
          وضعیتِ سفارش: {PHASE_LABEL[phase]}
        </span>
      </div>

      <p className={`mt-1 text-3xs leading-4 ${TONE[state]}`} data-testid="watch-order-reason">
        {answer || (gate.canTrade
          ? 'اتصالِ اجرا فعال است؛ پیش‌فرود و سقفها را خودِ سرویس تعیین می‌کند.'
          : `${gate.reason}. تا پیش از اتصالِ تأییدشده هیچ سفارشی از این صفحه ارسال نمی‌شود.`)}
      </p>

      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid="exec-detail-toggle"
          className="text-3xs font-bold text-accent-blue underline-offset-2 hover:underline"
        >
          {open ? 'بستنِ جزئیات' : 'جزئیات، پیش‌نمایش و تاریخچه'}
        </button>
        {last?.broker_order_id
          ? (
            <span className="num text-3xs text-text-secondary" data-testid="exec-order-id">
              شناسۀِ کارگزاری: {last.broker_order_id}
            </span>
          )
          : null}
        {last?.error_code
          ? (
            <span className="text-3xs text-accent-red" data-testid="exec-error-code"
              title={String(last.error_detail ?? '')}>
              {CODE_LABEL[last.error_code] ?? last.error_code}
            </span>
          )
          : null}
      </div>

      {open && (
        <div className="mt-1.5 flex flex-col gap-1.5 border-t border-border-c/50 pt-1.5"
          data-testid="exec-details">
          {gate.wireHypothesis
            ? (
              <p className="text-3xs leading-4 text-accent-yellow" data-testid="exec-hypothesis-note">
                سیمِ این اتصال از پنج منبعِ عمومی استخراج شده و هنوز علیه کارگزاری تأیید
                نشده است. پیش‌نمایشِ زیر «شکلِ انتظار» است، نه «شکلِ تأییدشده».
              </p>
            )
            : null}

          {preview
            ? (
              <div className="rounded-lg bg-bg-primary/60 p-1.5" data-testid="exec-preview-out">
                <span className="text-3xs font-bold text-text-secondary">پیش‌نمایشِ نهایی</span>
                <pre className="num mt-0.5 max-h-28 overflow-auto text-3xs leading-4 text-text-primary"
                  dir="ltr">
                  {JSON.stringify((preview as { wire_preview?: unknown }).wire_preview
                    ?? (preview as { payload_preview?: unknown }).payload_preview ?? preview, null, 1)}
                </pre>
                <pre className="num mt-1 max-h-20 overflow-auto text-3xs leading-4 text-text-muted" dir="ltr">
                  {JSON.stringify((preview as { checks?: unknown }).checks ?? {}, null, 1)}
                </pre>
              </div>
            )
            : null}

          <div className="flex flex-wrap items-end gap-1.5">
            <label className="flex min-w-0 flex-1 flex-col gap-0.5 text-3xs text-text-muted">
              نشانیِ نشست (اختیاری — فقط درِ حافظه)
              <input
                type="password" autoComplete="off" spellCheck={false} value={token}
                onChange={(e) => setToken(e.target.value)}
                data-testid="exec-token-input"
                className="rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-3xs text-text-primary"
              />
            </label>
            <Chip testId="exec-token-save" disabled={!token.trim() || busy}
              title="هیچ مسیری این را درِ فایل، دیتابیس یا لاگ نمی‌نویسد؛ با restart می‌میرد"
              onClick={() => void ask('session', async () => {
                const value = token;
                setToken('');
                return orderApi.putSession(value);
              })}>ذخیره</Chip>
            <Chip testId="exec-token-clear" disabled={busy}
              onClick={() => void ask('session', () => orderApi.delSession())}>پاک کردنِ نشست</Chip>
          </div>

          <div className="flex flex-col gap-0.5" data-testid="exec-history">
            <span className="text-3xs font-bold text-text-secondary">تاریخچه و پایش</span>
            {records.length === 0
              ? (
                <span className="text-3xs text-text-muted" data-testid="exec-history-empty">
                  {gate.status?.adapter === 'easytrader'
                    ? 'سفارشی درِ دفترِ اجرا نیست — فهرستِ کارگزاری تنها با «آزمونِ اتصال» خوانده می‌شود'
                    : 'سفارشی درِ دفترِ اجرا نیست'}
                </span>
              )
              : records.map((r) => (
                <div key={r.execution_id}
                  className="flex flex-wrap items-baseline gap-1.5 border-b border-border-c/30 py-0.5 last:border-0"
                  data-testid={`exec-history-${r.execution_id}`}>
                  <span className="num text-3xs font-bold text-text-primary">{r.symbol || '—'}</span>
                  <span className={`text-3xs font-bold ${
                    r.side === 'sell' ? 'text-accent-red' : 'text-accent-green'}`}>
                    {r.side === 'sell' ? 'فروش' : 'خرید'}
                  </span>
                  <span className="num text-3xs text-text-secondary">
                    {r.price != null ? fmtInt(r.price) : '—'} × {r.quantity != null ? fmtInt(r.quantity) : '—'}
                  </span>
                  <span className="text-3xs text-text-muted">{PHASE_LABEL[phaseOf(r)]}</span>
                  {r.broker_order_id
                    ? <span className="num text-3xs text-text-muted" title="شناسۀ کارگزاری">{r.broker_order_id}</span>
                    : null}
                  <Chip testId={`exec-refresh-${r.execution_id}`} disabled={busy}
                    title="نظرِ تازهٔ سرور دربارهٔ همین سفارش — هیچ سفارشِ تازه‌ای نمی‌سازد"
                    onClick={() => void ask('refresh', () => orderApi.refresh(r.execution_id))}>بازخوانی</Chip>
                  {r.status === 'unknown_result'
                    ? (
                      <Chip testId={`exec-reconcile-${r.execution_id}`} disabled={busy} tone="danger"
                        title="رفعِ ابهام از فهرستِ سفارش‌ها — نه ارسالِ دوباره"
                        onClick={() => void ask('reconcile', () => orderApi.reconcile(r.execution_id))}>رفعِ ابهام</Chip>
                    )
                    : null}
                  {gate.caps?.queue_position === true && r.broker_order_id
                    ? (
                      <Chip testId={`exec-queue-${r.execution_id}`} disabled={busy}
                        title="جایِ صف فقط با دادهٔ واقعی نشان داده می‌شود؛ نبودِ داده یعنی «نمی‌دانیم»"
                        onClick={() => void ask('queue', () => orderApi.queue(r.execution_id))}>صف</Chip>
                    )
                    : null}
                </div>
              ))}
            {queue
              ? (
                <span className="num text-3xs text-text-secondary" data-testid="exec-queue-out" dir="ltr">
                  {queue}
                </span>
              )
              : null}
          </div>

          {gate.status?.clock_limit
            ? (
              <p className="text-3xs leading-4 text-text-muted" data-testid="exec-clock-note">
                ساعت: {gate.status.clock_source} — {gate.status.clock_limit}
              </p>
            )
            : null}
        </div>
      )}
    </div>
  );
}
