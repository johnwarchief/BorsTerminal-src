// features/fundamental/lib/rejectReasons.ts -- علتِ دقیقِ رد برای بنرِ تصمیم (#205)
// رأیِ مالک: «به دلیل ضعف در سودسازی، حاشیه سود پایین یا قیمت‌گذاری دستوری» به
// درد نمی‌خورد — باید همان شاخص(ها)ی ردشده با عدد و آستانۀ خودش نام برده شوند.
// اینجا هیچ داوریِ تازه‌ای ساخته نمی‌شود: فهرست فقط از پرچم‌های false/na خودِ
// موتور و از همان اعدادی می‌آید که موتور برای آن محور فرستاده است.
import { FTS_LABEL } from '@shared/lib/ftsLabels';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsCardIndicators } from '../api/useFtsCard';

export type RejectLine = { label: string; detail: string; missing: boolean };

const fa = (v: number, digits = 1) => toFaDigits(v.toFixed(digits)).replace('.', '٫');
/** درصدِsigned — همان علامتی که کارت برای رشد به کار می‌برد */
const pct = (v: number) => `${v >= 0 ? '+' : '−'}${fa(Math.abs(v))}٪`;

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

  const push = (key: string, bad: boolean | null | undefined, detail: string, naDetail: string) => {
    // undefined یعنی این پرچم اصلاً از موتور نرسیده — چیزی برای نام بردن نیست
    const text = bad === false ? detail : bad === null ? naDetail : null;
    if (text == null) return;
    const label = FTS_LABEL[key] ?? key;
    let b = buckets.get(label);
    if (!b) {
      b = { details: [], hardFail: false };
      buckets.set(label, b);
      order.push(label);
    }
    b.details.push(text);
    if (bad === false) b.hardFail = true;
  };

  push(
    '1_growth',
    passes['1a_monetary_growth'],
    mon?.monetary_pct != null && mon?.threshold != null
      ? `رشد ریالی ${pct(mon.monetary_pct)} — کف ${fa(mon.threshold)}٪`
      : 'رشد ریالی به کفِ جزوه نرسید',
    'رشد ریالی اندازه‌گیری نشد',
  );
  const volPct = vol?.real_pct ?? vol?.volume_pct;
  push(
    '1_growth',
    passes['1b_volume_growth'],
    volPct != null && vol?.threshold != null
      ? `رشد تولیدی ${pct(volPct)} — کف ${fa(vol.threshold)}٪` +
        (vol?.price_benchmark_pct != null ? ` (مبنای تورم ${fa(vol.price_benchmark_pct)}٪)` : '')
      : 'رشد تولیدی به کف نرسید',
    'رشد تولیدی سنجیده نشد',
  );
  push(
    '2_eps_trend',
    passes['2_eps_trend'],
    // «۵ از ۳ سال» بی‌معناست — موتور سالِ درِ دسترس را تا لازم سقف می‌کند
    i2?.years_available != null && i2?.years_required != null
      ? `رشد متوالی سود هر سهم در ${fa(Math.min(i2.years_available, i2.years_required), 0)} از ${fa(i2.years_required, 0)} سال`
      : 'روند سه‌سالۀ EPS صعودیِ متوالی نیست',
    'سابقۀ EPS کامل نیست',
  );
  push(
    '3_gross_margin',
    passes['3_gross_margin'],
    i3?.margin_pct != null && i3?.threshold != null
      ? `حاشیۀ ناخالص ${fa(i3.margin_pct)}٪ — کف ${fa(i3.threshold)}٪`
      : 'حاشیۀ سود ناخالص زیرِ کف است',
    'حاشیۀ ناخالص محاسبه نشد',
  );
  push(
    '4_sales_to_mcap',
    passes['4a_sales_to_mcap'],
    i4?.sales_to_mcap != null && i4?.sales_threshold != null
      ? `نسبت فروش به ارزش بازار ${fa(i4.sales_to_mcap, 2)}× — کف ${fa(i4.sales_threshold, 2)}×`
      : 'نسبت فروش به ارزش بازار زیرِ کف است',
    'نسبت فروش سنجیده نشد',
  );
  push(
    '4_sales_to_mcap',
    passes['4b_profit_potential'],
    i4?.potential_pct != null && i4?.potential_threshold != null
      ? `پتانسیل سود ${fa(i4.potential_pct)}٪ — کف ${fa(i4.potential_threshold)}٪`
      : 'پتانسیل سود به کف نرسید',
    'پتانسیل سود محاسبه نشد',
  );
  push(
    '5_industry',
    passes['5_industry'],
    'رژیم قیمت‌گذاری صنعت دستوری است (بورس کالا/نرخ آزاد نیست)',
    'رژیم قیمت‌گذاری صنعت نامعلوم است',
  );
  // دو زیرِشرطِ یک شاخص (۱الف/۱ب و ۴الف/۴ب) در یک سطر می‌نشینند تا نامِ آن
  // شاخص دو بار تکرار نشود؛ «مردود» اگر یکی از دو زیرِشرط سرِ واقعی بخورد.
  return order.map((label) => {
    const b = buckets.get(label) as { details: string[]; hardFail: boolean };
    return { label, detail: b.details.join('؛ '), missing: !b.hardFail };
  });
}

/** یک سطرِ کامل: «۳. حاشیه سود ناخالص — حاشیۀ ناخالص ۱۲٫۴٪ — کف ۲۰٪» */
export function rejectLineText(l: RejectLine): string {
  return `${l.label} — ${l.detail}`;
}
