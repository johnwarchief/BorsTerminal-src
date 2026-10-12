// shared/components/ClientSharePct.tsx — نمایشِ درصدِ حقیقی/حقوقیِ یک نماد.
//
// هیچ عددی این‌جا حساب نمی‌شود. هرچه می‌بینید ستون‌هایِ خودِ تابلو است که درِ
// `client_split.py` (بند ۲ مأموریت، رأیِ مالک 1405-07-20) از **ارزشِ** مبدأ
// ساخته شده‌اند — نه از حجم، و نه از ضربِ حجم در قیمت. رابط حقِ ساختنِ کسرِ
// دوم را ندارد؛ فقط قالبِ نمایش و علتِ «نامشخص» این‌جا می‌ماند.
import { fmtPct } from '@shared/lib/fmt';
import { dEvenToJalali } from '@shared/lib/jalaali';

/** ستون‌هایی که بک‌اند برایِ یک سمت می‌فرستد (همه `.nullish()`). */
export interface ClientShareFields {
  retail_buy_pct?: number | null;
  legal_buy_pct?: number | null;
  retail_sell_pct?: number | null;
  legal_sell_pct?: number | null;
  pct_basis?: string | null;
  /** نشستِ خودِ ردیفِ `client_type_value` (۲۰۲۶۱۰۰۷) */
  ctv_d?: number | null;
  /** ۱ = همان نشستِ تابلو، ۰ = نشستِ پیشین، null = ردیفِ مبدأ نداریم */
  pct_is_current?: number | null;
}

const UNKNOWN = 'نامشخص';

function pctText(v: number | null | undefined): string | null {
  if (v == null || !Number.isFinite(v)) return null;
  // همان قالبِ درصدِ خودِ برنامه (`fmtPct`) — رابط علامتِ تازه اختراع نمی‌کند.
  return fmtPct(v);
}

/** علتِ «نامشخص» — سه حالتِ جدا، بی‌اشتباهِ «صفر» با «نداریم» */
function unknownReason(row: ClientShareFields): string {
  if (row.pct_basis == null && row.ctv_d == null) {
    return 'ارزشِ خرید و فروشِ حقیقی و حقوقی برایِ این نماد منتشر نشده است. '
      + 'TSETMC مبدأِ ارزش را پس از پایانِ روز معاملاتی می‌دهد و ما هرگز از ضربِ حجم در '
      + 'قیمت نمی‌سازیم؛ پس «نامشخص» خوانده می‌شود، نه صفر.';
  }
  return 'ارزشِ مبدأ برایِ این نماد کامل نیست (یک گروه عدد ندارد)، پس سهمِ آن '
    + 'سمت ساخته نمی‌شود.';
}

function sessionNote(row: ClientShareFields): string {
  const d = dEvenToJalali(row.ctv_d);
  if (!d) return '';
  if (row.pct_is_current === 1) return ` — از همان روزِ تابلو (${d})`;
  return ` — از ${d}؛ TSETMC ارزشِ گروه‌ها را برای روزِ جاری هنوز منتشر نکرده`;
}

function SideRow({
  testId, label, retail, legal, basis, session, dense,
}: {
  testId: string;
  label: string;
  retail: number | null | undefined;
  legal: number | null | undefined;
  basis: string;
  session: string;
  dense?: boolean;
}) {
  const r = pctText(retail);
  const l = pctText(legal);
  const known = r != null && l != null;
  const share = known ? Math.max(0, Math.min(100, retail ?? 0)) : null;
  return (
    <div className="flex items-center gap-1.5" data-testid={testId}
         data-state={known ? 'ok' : 'unknown'}
         title={`مبنایِ محاسبه: ${basis}${session}`}>
      <span className={`shrink-0 ${dense ? 'text-3xs' : 'text-[9px]'} text-text-muted`}>{label}</span>
      {known ? (
        <>
          <span className={`num ${dense ? 'text-3xs' : 'text-[10px]'} font-bold text-accent-green`}>
            حقیقی {r}
          </span>
          <span aria-hidden="true" className="h-1 flex-1 min-w-6 overflow-hidden rounded-full bg-accent-blue/25">
            <span className="block h-full rounded-full bg-accent-green" style={{ width: `${share}%` }} />
          </span>
          <span className={`num ${dense ? 'text-3xs' : 'text-[10px]'} font-bold text-accent-blue`}>
            {l} حقوقی
          </span>
        </>
      ) : (
        <span className={`text-3xs text-text-muted`} data-testid={`${testId}-unknown`}>{UNKNOWN}</span>
      )}
    </div>
  );
}

/**
 * دو سمتِ مستقل: «سهم از ارزش خرید» و «سهم از ارزش فروش». درصدِ خرید هرگز
 * جای درصدِ فروش نمی‌نشیند — دو کسرِ جدا با دو مخرجِ جدا (همان تعریفِ بک‌اند).
 */
export function ClientSharePct({
  row, dense = false, testId = 'client-share', className = '',
}: {
  row: ClientShareFields | null | undefined;
  dense?: boolean;
  testId?: string;
  className?: string;
}) {
  const r = row ?? {};
  const hasAny = r.pct_basis != null;
  const basis = 'ارزشِ خرید و فروش (نه حجم)';
  const session = sessionNote(r);
  const reason = unknownReason(r);
  return (
    <div className={`flex flex-col gap-0.5 ${className}`} data-testid={testId}
         data-basis="value" data-has-data={hasAny ? '1' : '0'}
         title={hasAny ? `مبنا: ${basis}${session}` : reason}>
      <SideRow testId={`${testId}-buy`} label="سهم از ارزش خرید"
               retail={r.retail_buy_pct} legal={r.legal_buy_pct}
               basis={basis} session={session} dense={dense} />
      <SideRow testId={`${testId}-sell`} label="سهم از ارزش فروش"
               retail={r.retail_sell_pct} legal={r.legal_sell_pct}
               basis={basis} session={session} dense={dense} />
    </div>
  );
}

/** تک‌خطِ فشرده برایِ ستونِ جدول و نوارِ زمینهٔ نماد: «ح ۸۷٫۸٪ / ح.ق ۱۲٫۲٪» */
export function ClientShareInline({
  row, side, testId,
}: {
  row: ClientShareFields | null | undefined;
  side: 'buy' | 'sell';
  testId?: string;
}) {
  const r = row ?? {};
  const retail = pctText(side === 'buy' ? r.retail_buy_pct : r.retail_sell_pct);
  const legal = pctText(side === 'buy' ? r.legal_buy_pct : r.legal_sell_pct);
  const label = side === 'buy' ? 'سهم از ارزش خرید' : 'سهم از ارزش فروش';
  if (retail == null || legal == null) {
    return (
      <span className="num text-3xs text-text-muted" data-testid={testId}
            data-state="unknown" title={unknownReason(r)}>{UNKNOWN}</span>
    );
  }
  return (
    <span className="num-text inline-flex items-baseline gap-1" data-testid={testId}
          data-state="ok"
          title={`${label} — مبنایِ ارزش (نه حجم)${sessionNote(r)}`}>
      <span className="num text-accent-green">{retail}</span>
      <span className="text-text-muted">/</span>
      <span className="num text-accent-blue">{legal}</span>
    </span>
  );
}
