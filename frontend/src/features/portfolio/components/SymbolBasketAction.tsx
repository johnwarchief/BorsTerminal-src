// features/portfolio/components/SymbolBasketAction.tsx -- دکمهٔ خودکفا «تصمیم سبد»
// وضعیت فعلی نماد را از /api/selection/portfolio می‌خواند (خودش با react-query؛
// در هر تب قابل نصب) و با کلیک، دیالوگ ثبت/ویرایش/حذف تصمیم باز می‌کند:
// نماد (جستجو در #106) · وضعیت · تعداد و قیمت → وزن خودکار · حد ضرر · یادداشت.
// اصل Circuit Breaker: خطا ⇒ «بدون داده» صادقانه؛ هرگز عدد ساختگی برای پوشاندن باگ بک‌اند.
import { useEffect, useState } from 'react';
import { Modal } from '@shared/components/Modal';
import { fmtInt, parseNum, toFaDigits } from '@shared/lib/fmt';
import {
  useRemoveBasketDecision,
  useSaveBasketDecision,
  useSymbolBasket,
  type BasketState,
  type BasketStatus,
} from '../api/useSymbolBasket';
import { SYMBOL_SEARCH_MIN, useSymbolSearch, type SymbolHit } from '../api/useSymbolSearch';

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

const STATE_DOT: Record<BasketState, string> = {
  accept: 'bg-accent-green',
  monitor: 'bg-accent-yellow',
  reject: 'bg-accent-red',
  none: 'bg-text-muted',
};

/** برچسب کوتاه حالت برای دکمهٔ فشرده (استاندارد و مینیمال) */
const STATE_MARK: Record<BasketState, string> = {
  accept: 'در سبد ✓',
  monitor: 'زیر نظر 👁',
  reject: 'حذف‌شده ✕',
  none: 'افزودن به سبد',
};

/** برچسب دکمهٔ کامل — فعل تصمیم، بدون چسباندن متن وضعیت */
const ACTION_LABEL: Record<BasketState, string> = {
  accept: 'ویرایش تصمیم سبد',
  monitor: 'ویرایش تصمیم سبد',
  reject: 'ویرایش تصمیم سبد',
  none: 'افزودن به سبد',
};

/** گزینه‌های وضعیت تصمیم — pending یعنی انصراف و پاک شدن رکورد در بک‌اند */
const STATUS_OPTIONS: [BasketStatus, string][] = [
  ['accept', 'خرید / نگهداری (در سبد)'],
  ['monitor', 'زیر نظر (بدون وزن)'],
  ['reject', 'حذف / رد شده'],
  ['pending', 'انصراف — بازگشت به بررسی‌نشده'],
];

const INPUT_CLS =
  'num rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-start text-xs text-text-primary outline-none focus:border-border-accent';

/** برچسب فارسیِ منشأِ وزن — «از چه چیزی» حساب شده باشد */
export function weightSourceLabel(src: string | null | undefined): string | null {
  if (src === 'value') return 'از قیمت × تعداد';
  if (src === 'manual') return 'وزنِ دستی';
  if (src === 'equal') return 'پیشنهادِ وزنِ مساوی';
  return null;
}

/**
 * وزنِ برآوردیِ یک ردیفِ تازه پیش از ذخیره.
 * فقط وقتی معلوم است که *همهٔ* ردیف‌های دیگرِ سبد ارزشِ ریالی داشته باشند؛ با یک
 * ردیفِ بی‌تعداد، مخرج ناقص است و درصدِ ساخته‌شده بزرگ‌نماییِ بقیه — پس null.
 */
export function previewWeightPct(
  others: { status?: string | null; value_toman?: number | null }[],
  value: number,
): number | null {
  if (!(value > 0)) return null;
  const accepted = (others ?? []).filter((d) => (d.status ?? '').toLowerCase() === 'accept');
  if (accepted.some((d) => !(typeof d.value_toman === 'number' && d.value_toman > 0))) return null;
  const sumOthers = accepted.reduce((s, d) => s + (d.value_toman as number), 0);
  return Math.round((value / (value + sumOthers)) * 1000) / 10;
}

function SymbolPicker({
  picked,
  onPick,
}: {
  picked: string;
  onPick: (hit: SymbolHit) => void;
}) {
  const [term, setTerm] = useState('');
  const search = useSymbolSearch(term);
  const q = term.trim();
  const hits = search.data?.data ?? [];

  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
        جستجوی نماد
        <input
          type="text"
          inputMode="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          aria-label="جستجوی نام یا نماد دارایی"
          placeholder="مثلاً عیار، فولاد، صندوق طلا"
          dir="rtl"
          className={INPUT_CLS}
        />
      </label>
      {q.length < SYMBOL_SEARCH_MIN ? (
        <p className="text-2xs text-text-muted">
          {toFaDigits(SYMBOL_SEARCH_MIN)} نویسه بنویس تا نمادها از تابلو بیایند.
        </p>
      ) : null}
      {search.isError ? (
        <p className="text-2xs font-bold text-accent-red">
          جستجو ناموفق بود — بک‌اند را بررسی کن؛ نام و قیمت را دستی وارد کن.
        </p>
      ) : null}
      {q.length >= SYMBOL_SEARCH_MIN && !search.isError ? (
        hits.length === 0 ? (
          <p className="text-2xs text-text-muted">
            {search.isLoading ? 'در حال جستجو…' : 'نمادی با این نام پیدا نشد (فقط سهام و صندوق).'}
          </p>
        ) : (
          <ul className="max-h-40 overflow-y-auto rounded-lg border border-[var(--hairline)] bg-bg-secondary/40">
            {hits.map((h) => (
              <li key={h.symbol}>
                <button
                  type="button"
                  onClick={() => onPick(h)}
                  aria-pressed={picked === h.symbol}
                  className={`flex w-full items-center gap-2 px-2 py-1.5 text-start text-2xs hover:bg-bg-card ${
                    picked === h.symbol ? 'bg-accent-blue/15' : ''
                  }`}
                >
                  <span className="shrink-0 font-black text-text-primary">{h.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-text-secondary" title={h.name}>
                    {h.name || '—'}
                  </span>
                  <span className="num shrink-0 text-text-secondary">
                    {h.price == null ? 'بدون قیمت' : fmtInt(h.price)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}

export function SymbolBasketAction({
  symbol,
  compact = false,
  addMode = false,
}: {
  /** نماد هدف؛ در حالت «افزودن» می‌تواند خالی باشد و از جستجو بیاید */
  symbol: string;
  compact?: boolean;
  /** دکمهٔ «افزودن دارایی» — دیالوگ با جستجوی نماد شروع می‌شود */
  addMode?: boolean;
}) {
  const [picked, setPicked] = useState<SymbolHit | null>(null);
  const sym = addMode ? (picked?.symbol ?? '') : symbol;
  const { state, decision, decisions, isLoading, isError } = useSymbolBasket(sym);
  const save = useSaveBasketDecision();
  const remove = useRemoveBasketDecision();

  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<BasketStatus>('accept');
  const [weight, setWeight] = useState('');
  const [qty, setQty] = useState('');
  const [price, setPrice] = useState('');
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
    // وزنِ دستیِ خالص؛ weight_eff_pct دیگر وزن نیست (از ارزش می‌آید) و پیش‌پر
    // کردنش با آن یعنی یک وزنِ دستیِ جعلی ذخیره شود.
    const w = decision?.weight_pct;
    setWeight(w != null && Number.isFinite(w) && w > 0 ? String(w) : '');
    const qv = decision?.qty;
    setQty(qv != null && Number.isFinite(qv) && qv > 0 ? String(qv) : '');
    const pr = decision?.price ?? picked?.price ?? null;
    setPrice(pr != null && Number.isFinite(pr) && pr > 0 ? String(pr) : '');
    const sl = decision?.stop_loss;
    setStop(sl != null && String(sl).trim() !== '' ? String(sl) : '');
    setNote(decision?.note ?? '');
  }, [open, state, decision, picked]);

  if (!addMode && !symbol) return null;

  const busy = save.isPending || remove.isPending;
  const currentLabel = !sym
    ? 'بدون نماد'
    : isLoading
      ? '...'
      : isError
        ? 'بدون داده'
        : BASKET_STATE_LABEL[state];

  // ارزش و وزنِ برآوردی از همین فرم — پیش از ذخیره، تا کاربر نتیجه را ببیند
  const qtyNum = parseNum(qty);
  const priceNum = parseNum(price);
  const value = qtyNum != null && priceNum != null ? Math.round(qtyNum * priceNum) : null;
  const others = decisions.filter((d) => d.symbol !== sym);
  const previewPct = value == null ? null : previewWeightPct(others, value);

  const mutationErr = (e: unknown, fallback: string): string =>
    e instanceof Error && e.message ? e.message : fallback;
  const errText =
    formErr ??
    (save.error ? mutationErr(save.error, 'ثبت تصمیم ناموفق بود.') : null) ??
    (remove.error ? mutationErr(remove.error, 'حذف تصمیم ناموفق بود.') : null);

  const submit = async () => {
    if (!sym) {
      setFormErr('اول نماد را از جستجو انتخاب کن.');
      return;
    }
    const qn = parseNum(qty);
    if (qty.trim() !== '' && (qn == null || qn <= 0)) {
      setFormErr('تعداد باید عددی مثبت باشد.');
      return;
    }
    const pn = parseNum(price);
    if (price.trim() !== '' && (pn == null || pn <= 0)) {
      setFormErr('قیمت باید عددی مثبت باشد.');
      return;
    }
    if (qn != null && pn == null) {
      setFormErr('برای وزنِ خودکار، قیمت هم لازم است (یا تعداد را خالی بگذار).');
      return;
    }
    const wTrim = weight.trim();
    let wNum: number | null = null;
    if (wTrim !== '') {
      wNum = parseNum(wTrim);
      if (wNum == null || wNum < 0 || wNum > 100) {
        setFormErr('وزن باید عددی بین ۰ تا ۱۰۰ باشد.');
        return;
      }
    }
    const sTrim = stop.trim();
    let sNum: number | string | null = null;
    if (sTrim !== '') {
      const sn = parseNum(sTrim);
      if (sn == null || sn <= 0) {
        setFormErr('حد ضرر باید عددی مثبت باشد.');
        return;
      }
      sNum = sn;
    }
    setFormErr(null);
    try {
      await save.mutateAsync({
        symbol: sym,
        status,
        weightPct: wNum,
        stopLoss: sNum,
        note,
        qty: qn,
        price: pn,
        // نام/صنعت از جستجوی سرور (یا رکوردِ قبلی) — بک‌اند کلیدِ غایب را حفظ می‌کند
        ...(picked ? { name: picked.name, sector: picked.sector_name } : {}),
      });
      setOpen(false);
      if (addMode) {
        // دکمهٔ «افزودن» باید برایِ داراییِ بعدی آماده بماند، نه به
        // «ویرایشِ همین ردیف» تبدیل شود.
        setPicked(null);
        setQty('');
        setPrice('');
        setWeight('');
        setStop('');
        setNote('');
      }
    } catch {
      // خطای mutation در errText نمایش داده می‌شود
    }
  };

  const doRemove = async () => {
    setFormErr(null);
    try {
      await remove.mutateAsync(sym);
      setOpen(false);
    } catch {
      // خطای mutation در errText نمایش داده می‌شود
    }
  };

  const trigger = compact ? (
    <button
      type="button"
      onClick={() => setOpen(true)}
      data-testid={`basket-action-${sym || 'add'}`}
      title={`تصمیم سبد — ${currentLabel}`}
      className={`shrink-0 rounded-full border border-border-c bg-bg-card/60 px-2.5 py-1 text-2xs font-bold transition-opacity duration-200 hover:opacity-85 ${
        isError ? 'text-text-muted' : STATE_TONE[state]
      }`}
    >
      {isLoading ? '…' : isError ? 'بدون داده' : STATE_MARK[state]}
    </button>
  ) : (
    <button
      type="button"
      onClick={() => setOpen(true)}
      data-testid={`basket-action-${sym || 'add'}`}
      title={addMode ? 'افزودن دارایی با جستجوی نماد' : `تصمیم سبد — وضعیت فعلی: ${currentLabel}`}
      className="shrink-0 rounded-full border border-border-c bg-bg-card px-3 py-1.5 text-xs font-bold text-text-secondary transition-colors duration-200 hover:border-border-accent hover:text-text-primary"
    >
      <span className="inline-flex items-center gap-1.5">
        <span
          aria-hidden
          className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${isError ? 'bg-text-muted' : isLoading ? 'animate-pulse bg-text-muted' : STATE_DOT[state]}`}
        />
        {addMode
          ? 'افزودن دارایی'
          : isLoading
            ? 'در حال بارگذاری'
            : isError
              ? 'بدون داده'
              : ACTION_LABEL[state]}
      </span>
    </button>
  );

  return (
    <>
      {trigger}
      {open ? (
        <Modal
          title={addMode && !sym ? 'افزودن دارایی به سبد' : `تصمیم سبد برای ${sym}`}
          onClose={() => {
            if (!busy) setOpen(false);
          }}
        >
          <div className="flex flex-col gap-3">
            {addMode ? (
              <SymbolPicker
                picked={sym}
                onPick={(h) => {
                  setPicked(h);
                  setFormErr(null);
                }}
              />
            ) : null}

            <p className="text-xs text-text-secondary">
              وضعیت فعلی: {!sym ? 'نمادی انتخاب نشده' : isError ? 'بدون داده (خطای اتصال)' : currentLabel}
              {decision?.updated_at ? (
                <>
                  {' '}
                  · آخرین ثبت: <span className="num">{decision.updated_at}</span>
                </>
              ) : (
                ''
              )}
            </p>
            {sym && isError ? (
              <p className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-2 py-1 text-2xs leading-5 text-accent-red">
                خواندن وضعیت فعلی ناموفق بود؛ اگر بک‌اند در دسترس است می‌توانی تصمیم جدید ثبت کنی.
              </p>
            ) : null}

            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1 text-2xs font-bold text-text-secondary">وضعیت تصمیم</legend>
              {STATUS_OPTIONS.map(([value2, label]) => (
                <label
                  key={value2}
                  className="flex cursor-pointer items-center gap-2 text-xs text-text-primary"
                >
                  <input
                    type="radio"
                    name={`basket-status-${sym || 'add'}`}
                    value={value2}
                    checked={status === value2}
                    onChange={() => setStatus(value2)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>

            {/* تعداد و قیمت → وزنِ خودکار (#106). وزنِ دستی فقط وقتی معنا دارد
                که تعداد نداشته باشیم؛ بک‌اند ارزش را بر وزنِ دستی مقدم می‌داند. */}
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
                تعداد
                <input
                  type="text"
                  inputMode="decimal"
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  aria-label="تعداد دارایی"
                  placeholder="مثلاً ۱۰۰۰"
                  dir="ltr"
                  className={INPUT_CLS}
                />
              </label>
              <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
                قیمت هر واحد (تومان)
                <input
                  type="text"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  aria-label="قیمت هر واحد به تومان"
                  placeholder={picked?.price != null ? String(picked.price) : 'از تابلو'}
                  dir="ltr"
                  className={INPUT_CLS}
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-[var(--hairline)] bg-bg-secondary/40 px-2.5 py-2 text-2xs">
              <span className="text-text-secondary" data-testid="basket-row-value">
                ارزش ردیف:{' '}
                {value == null ? (
                  <span className="text-text-muted">تعداد و قیمت لازم است</span>
                ) : (
                  <span className="num font-black text-text-primary">
                    {fmtInt(value)} <span className="font-normal text-text-muted">تومان</span>
                  </span>
                )}
              </span>
              <span className="text-text-secondary" data-testid="basket-row-weight">
                وزن در سبد:{' '}
                {value == null ? (
                  <span className="text-text-muted">خودکار حساب نمی‌شود</span>
                ) : previewPct == null ? (
                  <span className="text-text-muted">
                    بقیهٔ ردیف‌ها تعداد ندارند؛ پس از ذخیره با وزنِ دستی نشان داده می‌شود
                  </span>
                ) : (
                  <span className="num font-black text-accent-blue">{toFaDigits(previewPct)}٪</span>
                )}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
                وزن دستی (درصد)
                <input
                  type="text"
                  inputMode="decimal"
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                  aria-label="وزن درصدی نماد"
                  placeholder={value != null ? 'بی‌نیاز (از ارزش)' : 'اختیاری'}
                  dir="ltr"
                  className={INPUT_CLS}
                />
              </label>
              <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
                حد ضرر
                <input
                  type="text"
                  inputMode="decimal"
                  value={stop}
                  onChange={(e) => setStop(e.target.value)}
                  aria-label="حد ضرر نماد"
                  placeholder="اختیاری"
                  dir="ltr"
                  className={INPUT_CLS}
                />
              </label>
            </div>

            <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
              یادداشت
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                aria-label="یادداشت تصمیم"
                maxLength={500}
                className={INPUT_CLS}
              />
            </label>

            {errText ? (
              <p role="alert" className="text-2xs font-bold text-accent-red">
                {errText}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--hairline)] pt-3">
              {!sym || state === 'none' ? (
                <span className="text-2xs text-text-muted">
                  {sym ? 'نماد هنوز تصمیمی ثبت‌شده ندارد.' : 'نماد را از بالا انتخاب کن.'}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={doRemove}
                  disabled={busy}
                  className="rounded-full border border-accent-red/40 bg-accent-red/10 px-3 py-1.5 text-2xs font-bold text-accent-red hover:bg-accent-red/20 disabled:opacity-60"
                >
                  {remove.isPending ? 'در حال حذف...' : 'حذف کامل از فهرست'}
                </button>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  disabled={busy}
                  className="rounded-full border border-border-c px-3 py-1.5 text-2xs font-bold text-text-secondary hover:text-text-primary disabled:opacity-60"
                >
                  بستن
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy || !sym}
                  className="rounded-full border border-accent-green/40 bg-accent-green/15 px-4 py-1.5 text-2xs font-bold text-accent-green hover:bg-accent-green/25 disabled:opacity-60"
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
