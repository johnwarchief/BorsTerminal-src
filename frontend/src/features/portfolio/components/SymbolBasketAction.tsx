// features/portfolio/components/SymbolBasketAction.tsx -- دکمهٔ خودکفا «تصمیم سبد»
// وضعیت فعلی نماد را از /api/selection/portfolio می‌خواند (خودش با react-query؛
// در هر تب قابل نصب) و با کلیک، دیالوگ کوچک ثبت/ویرایش/حذف تصمیم باز می‌کند:
// وضعیت (خرید/نگهداری · زیر نظر · حذف · انصراف) + وزن + حد ضرر + یادداشت.
// اصل Circuit Breaker: خطا ⇒ «بدون داده» صادقانه؛ هرگز عدد ساختگی برای پوشاندن باگ بک‌اند.
import { useEffect, useState } from 'react';
import { Modal } from '@shared/components/Modal';
import {
  useRemoveBasketDecision,
  useSaveBasketDecision,
  useSymbolBasket,
  type BasketState,
  type BasketStatus,
} from '../api/useSymbolBasket';

export const BASKET_STATE_LABEL: Record<BasketState, string> = {
  accept: 'در سبد',
  monitor: 'زیر نظر',
  reject: 'حذف‌شده',
  none: 'خارج از سبد',
};

const STATE_TONE: Record<BasketState, string> = {
  accept: 'text-accent-green',
  monitor: 'text-accent-yellow',
  reject: 'text-accent-red',
  none: 'text-text-secondary',
};

const STATE_MARK: Record<BasketState, string> = {
  accept: '✓ در سبد',
  monitor: '👁 زیر نظر',
  reject: '✕ حذف‌شده',
  none: '+ افزودن به سبد',
};

/** گزینه‌های وضعیت تصمیم — pending یعنی انصراف و پاک شدن رکورد در بک‌اند */
const STATUS_OPTIONS: [BasketStatus, string][] = [
  ['accept', 'خرید / نگهداری (در سبد)'],
  ['monitor', 'زیر نظر (بدون وزن)'],
  ['reject', 'حذف / رد شده'],
  ['pending', 'انصراف — بازگشت به بررسی‌نشده'],
];

export function SymbolBasketAction({
  symbol,
  compact = false,
}: {
  symbol: string;
  compact?: boolean;
}) {
  const { state, decision, isLoading, isError } = useSymbolBasket(symbol);
  const save = useSaveBasketDecision();
  const remove = useRemoveBasketDecision();

  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<BasketStatus>('accept');
  const [weight, setWeight] = useState('');
  const [stop, setStop] = useState('');
  const [note, setNote] = useState('');
  const [formErr, setFormErr] = useState<string | null>(null);

  // هر بار دیالوگ باز می‌شود، فرم از دادهٔ ثبت‌شده پر می‌شود
  useEffect(() => {
    if (!open) return;
    setFormErr(null);
    setStatus(
      state === 'accept' || state === 'monitor' || state === 'reject' ? state : 'accept',
    );
    const w = decision?.weight_pct ?? decision?.weight_eff_pct;
    setWeight(w != null && Number.isFinite(w) && w > 0 ? String(w) : '');
    const sl = decision?.stop_loss;
    setStop(sl != null && String(sl).trim() !== '' ? String(sl) : '');
    setNote(decision?.note ?? '');
  }, [open, state, decision]);

  if (!symbol) return null;

  const busy = save.isPending || remove.isPending;
  const currentLabel = isLoading ? '...' : isError ? 'بدون داده' : BASKET_STATE_LABEL[state];

  const mutationErr = (e: unknown, fallback: string): string =>
    e instanceof Error && e.message ? e.message : fallback;
  const errText =
    formErr ??
    (save.error ? mutationErr(save.error, 'ثبت تصمیم ناموفق بود.') : null) ??
    (remove.error ? mutationErr(remove.error, 'حذف تصمیم ناموفق بود.') : null);

  const submit = async () => {
    const wTrim = weight.trim();
    let wNum: number | null = null;
    if (wTrim !== '') {
      wNum = Number(wTrim);
      if (!Number.isFinite(wNum) || wNum < 0 || wNum > 100) {
        setFormErr('وزن باید عددی بین ۰ تا ۱۰۰ باشد.');
        return;
      }
    }
    const sTrim = stop.trim();
    let sNum: number | null = null;
    if (sTrim !== '') {
      sNum = Number(sTrim);
      if (!Number.isFinite(sNum) || sNum <= 0) {
        setFormErr('حد ضرر باید عددی مثبت باشد.');
        return;
      }
    }
    setFormErr(null);
    try {
      await save.mutateAsync({ symbol, status, weightPct: wNum, stopLoss: sNum, note });
      setOpen(false);
    } catch {
      // خطای mutation در errText نمایش داده می‌شود
    }
  };

  const doRemove = async () => {
    setFormErr(null);
    try {
      await remove.mutateAsync(symbol);
      setOpen(false);
    } catch {
      // خطای mutation در errText نمایش داده می‌شود
    }
  };

  const trigger = compact ? (
    <button
      type="button"
      onClick={() => setOpen(true)}
      title={`تصمیم سبد: ${currentLabel}`}
      className={`num rounded-full border bg-bg-card/60 px-2.5 py-1 text-[11px] font-bold transition-opacity duration-200 hover:opacity-85 ${
        isError ? 'border-border-c text-text-muted' : `border-border-c ${STATE_TONE[state]}`
      }`}
    >
      {isLoading ? '…' : isError ? 'بدون داده' : STATE_MARK[state]}
    </button>
  ) : (
    <button
      type="button"
      onClick={() => setOpen(true)}
      title="ثبت یا ویرایش تصمیم این نماد در سبد"
      className="num inline-flex items-center gap-1.5 rounded-full border border-border-c bg-bg-card px-3 py-1.5 text-xs font-bold text-text-secondary transition-colors duration-200 hover:border-border-accent hover:text-text-primary"
    >
      <span>تصمیم سبد:</span>
      <span className={isError ? 'text-text-muted' : STATE_TONE[state]}>
        {isLoading ? '...' : isError ? 'بدون داده' : STATE_MARK[state]}
      </span>
    </button>
  );

  return (
    <>
      {trigger}
      {open ? (
        <Modal
          title={`تصمیم سبد برای ${symbol}`}
          onClose={() => {
            if (!busy) setOpen(false);
          }}
        >
          <div className="flex flex-col gap-3">
            <p className="text-xs text-text-secondary">
              وضعیت فعلی: {isError ? 'بدون داده (خطای اتصال)' : currentLabel}
              {decision?.updated_at ? ` · آخرین ثبت: ${decision.updated_at}` : ''}
            </p>
            {isError ? (
              <p className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-2 py-1 text-[11px] leading-5 text-accent-red">
                خواندن وضعیت فعلی ناموفق بود؛ اگر بک‌اند در دسترس است می‌توانی تصمیم جدید ثبت کنی.
              </p>
            ) : null}

            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1 text-[11px] font-bold text-text-secondary">وضعیت تصمیم</legend>
              {STATUS_OPTIONS.map(([value, label]) => (
                <label
                  key={value}
                  className="flex cursor-pointer items-center gap-2 text-xs text-text-primary"
                >
                  <input
                    type="radio"
                    name={`basket-status-${symbol}`}
                    value={value}
                    checked={status === value}
                    onChange={() => setStatus(value)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>

            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-[11px] font-bold text-text-secondary">
                وزن (درصد)
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  aria-label="وزن درصدی نماد"
                  placeholder="اختیاری"
                  dir="ltr"
                  className="num rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-left text-xs text-text-primary outline-none focus:border-border-accent"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-bold text-text-secondary">
                حد ضرر
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={stop}
                  onChange={(e) => setStop(e.target.value)}
                  aria-label="حد ضرر نماد"
                  placeholder="اختیاری"
                  dir="ltr"
                  className="num rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-left text-xs text-text-primary outline-none focus:border-border-accent"
                />
              </label>
            </div>

            <label className="flex flex-col gap-1 text-[11px] font-bold text-text-secondary">
              یادداشت
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                aria-label="یادداشت تصمیم"
                maxLength={500}
                className="rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-xs text-text-primary outline-none focus:border-border-accent"
              />
            </label>

            {errText ? (
              <p role="alert" className="text-[11px] font-bold text-accent-red">
                {errText}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--hairline)] pt-3">
              {state === 'none' ? (
                <span className="text-[10px] text-text-muted">نماد هنوز تصمیمی ثبت نشده ندارد.</span>
              ) : (
                <button
                  type="button"
                  onClick={doRemove}
                  disabled={busy}
                  className="rounded-full border border-accent-red/40 bg-accent-red/10 px-3 py-1.5 text-[11px] font-bold text-accent-red hover:bg-accent-red/20 disabled:opacity-60"
                >
                  {remove.isPending ? 'در حال حذف...' : 'حذف کامل از فهرست'}
                </button>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  disabled={busy}
                  className="rounded-full border border-border-c px-3 py-1.5 text-[11px] font-bold text-text-secondary hover:text-text-primary disabled:opacity-60"
                >
                  بستن
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy}
                  className="rounded-full border border-accent-green/40 bg-accent-green/15 px-4 py-1.5 text-[11px] font-bold text-accent-green hover:bg-accent-green/25 disabled:opacity-60"
                >
                  {save.isPending ? 'در حال ثبت...' : 'ثبت تصمیم'}
                </button>
              </div>
            </div>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
