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
import { ConnectBrokerRow } from './ConnectBrokerRow';
import { fmtInt, parseNum, toEnDigits, toFaDigits } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';
import {
  CODE_LABEL, PHASE_LABEL, SESSION_LABEL, invalidateExecution,
  orderApi, phaseOf, useExecutionLedger, useExecutionStatus, useExecutionTimings,
  type ExecutionRecord, type OrderPhase,
} from '../lib/orderClient';
import {
  TONE, freshId, safeError, summarize, type ActionState, type ExecAction,
} from '../lib/orderActionView';
import {
  EMPTY_FIELDS, leadMs, targetWallMs,
  useSarkhatiFormStore, type OrderFields, type SarkhatiSide,
} from '../stores/sarkhatiFormStore';

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

export function ExecutionPanel({ symbol, row, schedule = false }: {
  symbol: string; row: MarketRow | null;
  /** تبِّ «سرخطی»: زمانِ هدف و پیش‌افت را هم نشان می‌دهد. دیده‌بان بدونِ آن
   *  دست‌نخورده می‌ماند (ارتفاعِ فشرده‌اش حفظ می‌شود). */
  schedule?: boolean;
}) {
  const { gate } = useExecutionStatus();
  const ledger = useExecutionLedger(gate.endpointPresent);
  const qc = useQueryClient();

  // قیمت/مقدار/جهت درِ storeِ نماد‌به‌نماد می‌مانند (رفتن از این تب و برگشتن
  // فرم را بی‌دلیل خالی نمی‌کند)؛ تأیید، عبارتِ تأیید و execution_id هرگز
  // آنجا نمی‌نشینند — یک‌مصرف‌اند و ماندنشان یعنی عبورِ رأیِ کهنه ازِ گیتِ تازه.
  const fields = useSarkhatiFormStore((st) => st.bySymbol[symbol] ?? EMPTY_FIELDS);
  const patch = useSarkhatiFormStore((st) => st.set);
  const side = fields.side;
  const qty = fields.quantity;
  const price = fields.price;
  const setField = (p: Partial<OrderFields>) => patch(symbol, p);
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
  const [phrase, setPhrase] = useState('');

  // هر تغییرِ فرم یکِ شناسۀِ تازه می‌سازد: «یک execution_id = یکِ تلاش» قاعدۀ
  // سرویس است (ردِّپایِ dispatch رویِ دیسک تکرار را می‌گیرد)، پس فرمِ ویرایش‌شده
  // نباید شناسۀِ سفارشِ قبلی را حمل کند.
  useEffect(() => { setEid(freshId()); setConfirmed(false); setPhrase(''); setPhase('idle'); },
    [symbol, side, price, qty]);

  const body = useCallback(() => ({
    execution_id: eid, symbol, side, mode: 'safe',
    price: parseNum(toEnDigits(price)),
    quantity: parseNum(toEnDigits(qty)),
    price_source: row?.p_last != null ? 'board.p_last' : 'unspecified',
    price_as_of: row?.row_h != null ? String(row.row_h) : null,
    confirmed,
    // درِ اجرایِ زنده بک‌اند این عبارت را می‌خواهد، نه فقطِ یکِ true
    confirm_phrase: phrase,
    // زمانِ هدف فقط وقتی کاربر خودش آن را نوشته اضافه می‌شود؛ رشتهٔ خالی
    // «بی‌هدف» است نه «صفر»، پس کلید هم نمی‌نشیند.
    ...(schedule && targetWallMs(fields.targetLocal) != null
      ? {
          target_wall_ms: targetWallMs(fields.targetLocal),
          ...(leadMs(fields.oneWayMs) != null ? { one_way_ms: leadMs(fields.oneWayMs) } : {}),
          ...(leadMs(fields.marginMs) != null ? { margin_ms: leadMs(fields.marginMs) } : {}),
        }
      : {}),
  }), [eid, symbol, side, price, qty, row?.p_last, row?.row_h,
      confirmed, phrase, schedule, fields.targetLocal, fields.oneWayMs, fields.marginMs]);

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
  // گیتِ عبارتِ تأیید (§۲-۲): بک‌اند آن را الزامی می‌کند و همین‌جا هم تا
  // برابرنکردنِ چیزی که رویِ صفحه نوشته، کلیدِ ارسال خاموش می‌ماند.
  const cgate = (gate.status?.confirm_gate ?? {}) as
    { required?: boolean; phrase?: string };
  const phraseOk = !cgate.required || phrase.trim() === String(cgate.phrase ?? '');
  const canSubmit = gate.canTrade && confirmed && phraseOk
    && !!parseNum(toEnDigits(qty))
    && !!parseNum(toEnDigits(price)) && !busy;
  const canPreview = gate.endpointPresent && !busy;

  // یادآوریِ زمان‌بندی فقط ازِ `/api/execution/timings` می‌آید (خودِ اندازه‌گیریِ
  // همین نشست). بی‌نمونه صریح «اندازه‌گیری نشده» می‌نویسیم تا کاربر پیش‌افتِ
  // ساختگی پر نکند (§۵: هیچ عددِ بدلِ کم‌نمونه‌ای منتشر نمی‌شود).
  const tphase = (useExecutionTimings(schedule).data?.phases ?? {}) as
    Record<string, { n?: number | null; p50?: number | null; thin?: boolean | null }>;
  const tdisp = tphase['dispatch_ms'] ?? null;
  const timingNote = tdisp && tdisp.n
    ? `اندازۀ همین نشست: dispatch p50 ${toFaDigits(String(tdisp.p50 ?? 0))} ms`
      + ` (n=${toFaDigits(String(tdisp.n))})${tdisp.thin ? ' — نمونۀ کم' : ''}`
    : 'هیچ durationی در این نشست اندازه‌گیری نشده — پیش‌افت را بی‌شاهد پر نکنید';

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
      className={schedule
        // درِ تبِّ «سرخطی» خودِ بخش قاب دارد؛ قابِ دوم زیرِ آن کارت‌در‌کارت می‌شود
        ? 'rounded-lg bg-bg-primary/30 p-1.5'
        : 'mt-auto rounded-xl border border-dashed border-border-c bg-bg-card/40 p-2'}
      data-testid="watch-order-panel"
      data-can-trade={gate.canTrade ? 'true' : 'false'}
      data-adapter={gate.status?.adapter ?? 'none'}
      data-session={gate.sessionState}
    >
      <ConnectBrokerRow />
      <div className="mb-1 flex flex-wrap items-center gap-1">
        {schedule ? null : (
          <h5 className="text-2xs font-black text-text-secondary">پنلِ معامله</h5>
        )}
        <div className="flex flex-wrap items-center gap-1">
          {/* درِ تبِّ «سرخطی» همین برچسب را خطِ وضعیتِ بالا می‌گوید — دو خوانش از
              یکِ پاسخ رویِ یکِ صفحه، همان چیزی که نباید بسازیم. */}
          {schedule ? null : (
            <Badge tone={gate.endpointPresent ? (gate.canTrade ? 'green' : 'yellow') : 'gray'}
              title={gate.status?.adapter === 'easytrader'
                ? 'سیمِ EasyTrader — هنوز هیچ ثابتش علیه کارگزاری تأیید نشده' : undefined}>
              {gate.endpointPresent
                ? `سرویسِ اجرا: ${gate.status?.adapter ?? '—'}${gate.dryRun ? ' · بدل' : ''}`
                : 'سرویسِ اجرا نیست'}
            </Badge>
          )}
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
            onClick={() => setField({ side: s as SarkhatiSide })}
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
            onChange={(e) => setField({ price: e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, '') })}
            data-testid="watch-order-price" placeholder={row?.p_last != null ? toFaDigits(String(row.p_last)) : '—'}
            className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary placeholder:text-text-muted"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">
          مقدار (سهم)
          <input
            type="text" inputMode="numeric" value={qty}
            onChange={(e) => setField({ quantity: e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, '') })}
            data-testid="watch-order-qty" placeholder="مثلاً ۱۰۰۰"
            className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary placeholder:text-text-muted"
          />
        </label>
      </div>

      {schedule ? (
        <div className="mb-1 rounded-lg border border-border-c/60 bg-bg-card/40 p-1.5"
          data-testid="exec-schedule">
          <div className="flex flex-wrap items-end gap-1.5">
            <label className="flex min-w-0 flex-1 flex-col gap-0.5 text-3xs text-text-muted">
              زمانِ هدفِ ارسال — خالی یعنی همین حالا
              <input type="datetime-local" dir="ltr" value={fields.targetLocal}
                disabled={!canPreview}
                onChange={(e) => setField({ targetLocal: e.target.value })}
                data-testid="exec-target-time"
                className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary" />
            </label>
            <label className="flex w-[86px] flex-col gap-0.5 text-3xs text-text-muted">
              پیش‌افت (ms)
              <input inputMode="numeric" dir="ltr" value={fields.oneWayMs}
                placeholder="بی‌عدد"
                onChange={(e) => setField({ oneWayMs: e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, '') })}
                data-testid="exec-one-way"
                className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary" />
            </label>
            <label className="flex w-[86px] flex-col gap-0.5 text-3xs text-text-muted">
              حاشیه (ms)
              <input inputMode="numeric" dir="ltr" value={fields.marginMs}
                placeholder="بی‌عدد"
                onChange={(e) => setField({ marginMs: e.target.value.replace(/[^0-9۰-۹٠-٩٬]/g, '') })}
                data-testid="exec-margin"
                className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs font-bold text-text-primary" />
            </label>
          </div>
          <p className="mt-1 text-2xs leading-4 text-text-muted" data-testid="exec-clock-facts">
            ساعتِ این دستگاه: {toFaDigits(String(gate.status?.clock_source ?? '—'))} ·{' '}
            {String(gate.status?.clock_limit ?? 'بی‌اعلانِ محدودیت')}
          </p>
          <p className="text-2xs leading-4 text-text-muted" data-testid="exec-server-clock">
            زمانِ سرورِ کارگزاری:{' '}
            <span className="font-black text-accent-yellow">اثبات‌نشده (NOT_PROVEN)</span>{' '}
            — هیچ وعده‌ای برایِ «درستِ همان لحظه» ساخته نمی‌شود
          </p>
          <p className="text-2xs leading-4 text-text-secondary" data-testid="exec-timings-line">
            {timingNote}
          </p>
        </div>
      ) : null}

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
          {cgate.required ? (
            <label className="flex flex-wrap items-center gap-1 text-2xs text-text-secondary"
              data-testid="exec-confirm-phrase-wrap">
              <span>عبارتِ «{String(cgate.phrase ?? '')}» را بنویسید تا اجرایِ زنده باز شود:</span>
              <input value={phrase} onChange={(e) => setPhrase(e.target.value)}
                placeholder={String(cgate.phrase ?? '')} aria-label="عبارتِ تأییدِ اجرایِ زنده"
                data-testid="exec-confirm-phrase"
                className="min-w-0 flex-1 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-2xs font-bold text-text-primary placeholder:text-text-muted" />
              <span className={phraseOk ? 'text-accent-green' : 'text-text-muted'}>
                {phraseOk ? 'مطابق است' : 'مطابق نیست'}</span>
            </label>
          ) : null}
          <button
            type="button"
            disabled={!canSubmit}
            aria-disabled={!canSubmit}
            onClick={() => void ask('dispatch', () => orderApi.dispatch(body()))}
            data-testid="exec-submit"
            title={canSubmit ? 'ارسالِ همین سفارش' : gate.reason || 'تأییدِ نهایی و مقدارِ معتبر لازم است'}
            className={`inline-flex min-h-[28px] items-center rounded-lg px-2.5 text-2xs font-black ${
              canSubmit ? 'bg-accent-blue/25 text-accent-blue hover:bg-accent-blue/35'
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
