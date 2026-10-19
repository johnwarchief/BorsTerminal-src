// features/portfolio/components/sarkhati/SarkhatiBudgetCard.tsx — «چقدر می‌شود خرید؟»
//
// این کارت فقط پاسخِ `GET /api/execution/budget` را می‌نویسد. سه چیزی که عمداً
// *نمی‌کند*:
//  • عددی نمی‌سازد: بی‌قدرتِ خریدِ واقعی `plan.quantity` تهی است و همان «—» باِ
//    علتش نوشته می‌شود — نه صفر، نه تخمینِ سرمایه (قفلِ «هیچ مقدارِ بدلِ کم‌نمونه
//    منتشر نمی‌کنیم» درِ همین تب).
//  • سفارش نیست: `is_order` و `from_broker` ازِ پاسخ خوانده می‌شوند و تا
//    `from_broker` روشن نشده، برچسبِ «ازِ خودِ کارگزاری نرسیده» رویِ کارت می‌ماند.
//  • مجوز نمی‌دهد: هیچ کنشی درِ این فایل ارسال را باز نمی‌کند؛ دروازۀ نوشتن همان
//    `BORS_EXECUTION_LIVE` و تأییدِ صریحِ خودِ فرم است.
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { useExecutionBudget, type BudgetView } from '../../lib/orderClient';
import { Chip, Field, Note } from './parts';

const BASIS_LABEL: Record<string, string> = {
  explicit: 'قیمتِ خودتان',
  allowed_max: 'سقفِ مجازِ همین نماد',
  allowed_min: 'کفِّ مجازِ همین نماد',
};

/** «۱۱٬۰۱۰ تا ۱۰۳۷۰» — بی‌یکی ازِ دو، همان یکی نوشته می‌شود و «—» جایِ دیگری. */
function bandText(min?: number | null, max?: number | null): string {
  if (min == null && max == null) return '—';
  if (min == null) return `حداکثر ${fmtInt(max)}`;
  if (max == null) return `حداقل ${fmtInt(min)}`;
  return `${fmtInt(max)} تا ${fmtInt(min)}`;
}

function money(v?: number | null): string {
  return v == null || !Number.isFinite(v) ? '—' : `${fmtInt(v)} ریال`;
}

export function SarkhatiBudgetCard({ symbol, side = 'buy', price = '',
  adapter = '' }: { symbol: string; side?: 'buy' | 'sell'; price?: string;
  adapter?: string }) {
  const q = useExecutionBudget(symbol, side, price, !!symbol.trim());
  const b: BudgetView | undefined = q.data;
  const band = b?.band ?? null;
  const plan = b?.plan ?? null;
  const blockers = Array.isArray(b?.blockers) ? b.blockers : [];
  const fromBroker = b?.from_broker === true;
  const qty = plan?.quantity;
  const unknown = plan?.status === 'UNKNOWN' || qty == null;

  return (
    <div className="mt-1.5 rounded-lg border border-border-c/50 bg-bg-primary/40 px-2 py-1.5"
      data-testid="sarkhati-budget-card" data-from-broker={fromBroker ? 'true' : 'false'}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-2xs font-black text-text-primary">پیش‌نمایشِ بودجه</span>
        <Chip tone={fromBroker ? 'ok' : 'idle'} testId="sarkhati-budget-source"
          title={fromBroker ? 'قدرتِ خرید ازِ پاسخِ کارگزاری آمده'
            : 'این عدد ازِ کارگزاری نیامده؛ محاسبۀِ خودِ برنامه ازِ بازۀِ قیمت و قدرتِ خریدِ داده‌شده'}>
          {fromBroker ? 'ازِ کارگزاری' : 'محاسبۀِ خودِ برنامه'}
        </Chip>
        <span className="text-3xs text-text-muted" data-testid="sarkhati-budget-not-order">
          پیش‌نمایش است، نه سفارش
        </span>
      </div>

      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <Field label="کارگزاری" value={(
          <span className="text-2xs text-text-secondary" data-testid="sarkhati-budget-broker">
            {adapter === 'easytrader' ? 'مفید — EasyTrader'
              : adapter ? `بدل (${adapter})` : '—'}
          </span>)} />
        <Field label="نماد" value={(
          <span className="text-2xs" data-testid="sarkhati-budget-symbol">
            <b className="font-black text-text-primary">{symbol || '—'}</b>
            {b?.instrument?.resolved
              ? <span className="num ms-1 text-3xs text-text-muted" dir="ltr"
                      title="شناسۀِ رسمی ازِ دادهٔ تابلو">
                  {String(b.instrument.isin ?? b.instrument.ins_code ?? '')}
                </span>
              : <span className="ms-1 text-3xs text-accent-red"
                      data-testid="sarkhati-budget-unresolved">بی‌شناسۀِ رسمی</span>}
          </span>)} />
        <Field label="جهت" value={(
          <span className="text-2xs" data-testid="sarkhati-budget-side">
            {side === 'buy' ? 'خرید' : 'فروش'}
          </span>)} />
        <Field label="قیمت" value={(
          <span className="num text-2xs font-black text-text-primary" dir="ltr"
                data-testid="sarkhati-budget-price">
            {b?.price != null ? fmtInt(b.price) : '—'}
            {b?.price_basis ? (
              <span className="ms-1 text-3xs font-normal text-text-muted" dir="rtl">
                {BASIS_LABEL[String(b.price_basis)] ?? String(b.price_basis)}
              </span>
            ) : null}
          </span>)} />
        <Field label="بازۀِ مجازِ امروز" value={(
          <span className="num text-2xs text-text-secondary" dir="ltr"
                data-testid="sarkhati-budget-band"
                title={band?.as_of ? `منبع: ${band.source ?? '—'} · ${band.as_of}`
                  : 'بازۀِ مجاز ازِ دادهٔ تابلویِ امروز'}>
            {bandText(band?.allowed_min, band?.allowed_max)}
          </span>)} />
        <Field label="قدرتِ خریدِ قابل‌استفاده" value={(
          <span className="num text-2xs" data-testid="sarkhati-budget-power"
                title={b?.buying_power_source ?? ''}>
            {b?.buying_power_rial != null
              ? <b className="font-black text-text-primary">
                  {money(b.buying_power_rial)}
                </b>
              : <span className="text-accent-yellow">نرسیده</span>}
          </span>)} />
        <Field label="حداکثرِ تعداد" value={(
          <span className="num text-2xs" data-testid="sarkhati-budget-qty">
            {unknown
              ? <span className="text-accent-yellow">محاسبه نشد</span>
              : <b className="font-black text-text-primary">{toFaDigits(String(qty))} واحد</b>}
          </span>)} />
        <Field label="مبلغِ تقریبی" value={(
          <span className="num text-2xs" data-testid="sarkhati-budget-total">
            {unknown ? '—' : money(plan?.total_rial)}
          </span>)} />
        {!unknown ? (
          <Field label="باقی‌ماندۀِ قدرتِ خرید" value={(
            <span className="num text-2xs text-text-secondary" dir="rtl"
                  data-testid="sarkhati-budget-remaining">
              {money(plan?.remaining_rial)}
            </span>)} />
        ) : null}
      </div>

      {plan?.caps_verified === false && !unknown ? (
        <p className="mt-0.5 text-3xs text-accent-yellow" data-testid="sarkhati-budget-caps">
          سقفِ تعداد ازِ کارگزاری نرسیده — تعداد حساب شده ولی مجازبودنش تأیید نشده
        </p>
      ) : null}

      {blockers.length > 0 ? (
        <ul className="mt-1 flex flex-col gap-0.5" data-testid="sarkhati-budget-blockers">
          {blockers.map((t, i) => (
            <li key={i} className="text-3xs leading-4 text-accent-yellow">· {t}</li>
          ))}
        </ul>
      ) : null}

      {q.isError ? (
        <p className="mt-0.5 text-3xs text-accent-red" data-testid="sarkhati-budget-error">
          پیش‌نمایشِ بودجه پاسخ نداد — هیچ تعدادی ازِ خودِ رابط ساخته نمی‌شود
        </p>
      ) : null}

      <Note label="این عدد ازِ کجا می‌آید" testId="sarkhati-budget-how">
        <ul className="flex flex-col gap-0.5">
          <li>قیمت ازِ بازۀِ مجازِ *همین نماد درِ تابلویِ امروز* برداشته می‌شود
              (سقفِ مجاز برایِ خرید)، نه ازِ حدسِ قیمتِ سرخطی؛ بی‌ردیف درِ تابلو،
              قیمت ساخته نمی‌شود.</li>
          <li>تعداد فقط ازِ قدرتِ خریدی می‌آید که *کارگزاری* گفته باشد. بی‌آن،
              «محاسبه نشد» نوشته می‌شود — صفر یا تخمینِ سرمایه جایِ آن نمی‌آید.</li>
          <li>کمیسیون و سقفِ تعداد درِ محاسبه لحاظ می‌شود؛ اگر سقفِ تعداد ازِ
              کارگزاری نرسیده باشد، همان رویِ کارت نوشته می‌شود، نه ادعایِ مجازبودن.</li>
        </ul>
      </Note>
    </div>
  );
}
