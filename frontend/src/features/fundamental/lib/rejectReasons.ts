// features/fundamental/lib/rejectReasons.ts -- علتِ دقیقِ رد برای بنرِ تصمیم (#205، #217)
// رأیِ مالک: «به دلیل ضعف در سودسازی، حاشیه سود پایین یا قیمت‌گذاری دستوری» به
// درد نمی‌خورد — باید همان شاخص(ها)ی ردشده با عدد و آستانۀ خودش نام برده شوند.
// رأیِ دومِ مالک (#217): همان خط باید کوتاه و لپِ کلام هم باشد. قاعدهٔ انتخابِ متن:
//  ۱. عددِ موتور و کفِ هر دو هست ⇒ «عدد — کفِ عدد» (کوتاه‌ترین شکلِ دقیق).
//  ۲. عدد نیست ⇒ علتی که خودِ موتور فرستاده. اینجا هرگز «زیرِ کف است» نوشته
//     نمی‌شود، چون چیزی سنجیده نشده؛ سنجیده‌نشدن با مردود یکی نیست. نمونۀ
//     واقعیِ خبهمن: فرانت می‌گفت «رشد متوالی سود هر سهم در ۳ از ۳ سال» در حالی
//     که علتِ موتور این بود که سابقه فقط از صورت‌های مالیِ تلفیقی است.
//  ۳. نه عدد هست نه علت ⇒ فقط همین که آن محور سنجیده نشد، بدون رقمِ ساختگی.
// اینجا هیچ داوریِ تازه‌ای ساخته نمی‌شود: فهرست فقط از پرچم‌های false/na خودِ
// موتور و از همان اعدادی می‌آید که موتور برای آن محور فرستاده است.
import { FTS_LABEL } from '@shared/lib/ftsLabels';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsCardIndicators } from '../api/useFtsCard';

export type RejectLine = { label: string; detail: string; missing: boolean };

const fa = (v: number, digits = 1) => toFaDigits(v.toFixed(digits)).replace('.', '٫');
/** درصدِ signed — همان علامتی که کارت برای رشد به کار می‌برد */
const pct = (v: number) => `${v >= 0 ? '+' : '−'}${fa(Math.abs(v))}٪`;
/** علتِ موتور یا null. ارقامِ لاتینِ درج‌شده در متنِ بک‌اند (سال، درصد) با
 *  همان تبدیلِ همیشگیِ رابط فارسی می‌شوند. */
const why = (s: string | null | undefined) => {
  const t = (s ?? '').trim();
  return t ? toFaDigits(t) : null;
};

/**
 * علت‌های رد، به همان ترتیبِ پنج شاخص. `passes` آرایهٔ سه‌حالۀ موتور است:
 * false = مردود، null = «نظر نمی‌دهد» (بی‌داده/معاف) — که آن هم جلویِ نمره را
 * می‌گیرد و مالک باید بداند کدام محور بوده.
 */
export function rejectReasons(
  passes: Record<string, boolean | null | undefined>,
  indicators: FtsCardIndicators | null | undefined,
): RejectLine[] {
  const order: string[] = [];
  const buckets = new Map<string, { details: string[]; hardFail: boolean }>();
  const mon = indicators?.['1']?.monetary;
  const vol = indicators?.['1']?.volume;
  const i2 = indicators?.['2'];
  const i3 = indicators?.['3'];
  const i4 = indicators?.['4'];
  const i5 = indicators?.['5'];

  const push = (
    key: string,
    bad: boolean | null | undefined,
    detail: string,
    naDetail: string | null,
  ) => {
    // undefined یعنی این پرچم اصلاً از موتور نرسیده — چیزی برای نام بردن نیست
    if (bad === undefined) return;
    // قبول هیچ علتی برای نوشتن ندارد؛ فهرست فقط مردودها و سنجیده‌نشده‌هاست
    if (bad === true) return;
    // null = «نظر نمی‌دهد» ⇒ عددِ مردود نوشته نمی‌شود، فقط علتِ سنجیده‌نشدن
    const text = bad === false ? detail : naDetail;
    const label = FTS_LABEL[key] ?? key;
    let b = buckets.get(label);
    if (!b) {
      b = { details: [], hardFail: false };
      buckets.set(label, b);
      order.push(label);
    }
    // دو زیرِشرطِ یک شاخص اغلب یک علتِ مشترک دارند ⇒ یک‌بار نوشته می‌شود
    if (text != null && !b.details.includes(text)) b.details.push(text);
    if (bad === false) b.hardFail = true;
  };

  push(
    '1_growth',
    passes['1a_monetary_growth'],
    mon?.monetary_pct != null && mon?.threshold != null
      ? `رشد ریالی ${pct(mon.monetary_pct)} — کف ${fa(mon.threshold)}٪`
      : why(mon?.reason) ?? 'رشد ریالی به کفِ جزوه نرسید',
    why(mon?.reason) ?? 'رشد ریالی سنجیده نشد',
  );
  const volPct = vol?.real_pct ?? vol?.volume_pct;
  push(
    '1_growth',
    passes['1b_volume_growth'],
    volPct != null && vol?.threshold != null
      ? `رشد تولیدی ${pct(volPct)} — کف ${fa(vol.threshold)}٪` +
        (vol?.price_benchmark_pct != null ? ` (مبنای تورم ${fa(vol.price_benchmark_pct)}٪)` : '')
      : why(vol?.reason) ?? 'رشد تولیدی به کف نرسید',
    why(vol?.reason) ?? 'رشد تولیدی سنجیده نشد',
  );
  // «۳ از ۳ سال» علتِ رد نیست — فقط می‌گوید چند سال در دسترس بوده؛ تنها وقتی
  // معنا دارد که کمبودِ سال، خودِ علتِ مردود باشد.
  const i2Short =
    i2?.years_available != null && i2?.years_required != null &&
    i2.years_available < i2.years_required
      ? `سابقۀ EPS کامل نیست — ${fa(Math.min(i2.years_available, i2.years_required), 0)} از ${fa(i2.years_required, 0)} سال`
      : null;
  push(
    '2_eps_trend',
    passes['2_eps_trend'],
    i2Short ?? why(i2?.reason) ?? 'روند سه‌سالۀ EPS صعودیِ متوالی نیست',
    i2Short ?? why(i2?.reason) ?? 'سابقۀ EPS کامل نیست',
  );
  push(
    '3_gross_margin',
    passes['3_gross_margin'],
    i3?.margin_pct != null && i3?.threshold != null
      ? `حاشیۀ ناخالص ${fa(i3.margin_pct)}٪ — کف ${fa(i3.threshold)}٪`
      : why(i3?.reason) ?? 'حاشیۀ سود ناخالص زیرِ کف است',
    why(i3?.reason) ?? 'حاشیۀ ناخالص سنجیده نشد',
  );
  push(
    '4_sales_to_mcap',
    passes['4a_sales_to_mcap'],
    i4?.sales_to_mcap != null && i4?.sales_threshold != null
      ? `نسبت فروش به ارزش بازار ${fa(i4.sales_to_mcap, 2)}× — کف ${fa(i4.sales_threshold, 2)}×`
      : why(i4?.reason) ?? 'نسبت فروش به ارزش بازار زیرِ کف است',
    why(i4?.reason) ?? 'نسبت فروش سنجیده نشد',
  );
  push(
    '4_sales_to_mcap',
    passes['4b_profit_potential'],
    i4?.potential_pct != null && i4?.potential_threshold != null
      ? `پتانسیل سود ${fa(i4.potential_pct)}٪ — کف ${fa(i4.potential_threshold)}٪`
      : why(i4?.reason) ?? 'پتانسیل سود به کف نرسید',
    why(i4?.reason) ?? 'پتانسیل سود سنجیده نشد',
  );
  push(
    '5_industry',
    passes['5_industry'],
    // موتور برای این محور عددی ندارد؛ آنچه می‌فرستد خودِ برچسبِ رژیم است
    // («قیمت‌گذاری دستوری» / «خنثی — نیازمند بررسی موردی»). همان نوشته می‌شود.
    why(i5?.label) ?? 'رژیم قیمت‌گذاری صنعت دستوری است',
    why(i5?.label) ?? 'رژیم قیمت‌گذاری صنعت نامعلوم است',
  );
  return order.map((label) => {
    const b = buckets.get(label) as { details: string[]; hardFail: boolean };
    return { label, detail: b.details.join('؛ '), missing: !b.hardFail };
  });
}

/** یک سطرِ کامل: «۳. حاشیه سود ناخالص — حاشیۀ ناخالص ۱۲٫۴٪ — کف ۲۰٪» */
export function rejectLineText(l: RejectLine): string {
  return `${l.label} — ${l.detail}`;
}
