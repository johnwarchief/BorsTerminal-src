// features/fundamental/lib/auditEvidence.ts -- ساخت «شاهد ممیزی» برای AuditBadge
// پوشش ۱۰۰٪ تمام احتمالات وضعیت شاخص‌ها با یک جمله خلاصه و ساده
import type { AuditEvidence } from '../components/AuditBadge';
import type { FtsCard } from '../api/useFtsCard';
import type { FtsScreenRow } from '../api/useFtsScreen';
import type { GapAxis } from './gapReason';
import { epsFailReason, epsRealYears } from './epsHistory';
import { isFinancialOrHolding, isPhysicalGrowthApplicable } from './assetScope';
import { toFaDigits } from '@shared/lib/fmt';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() !== '' ? v : null);

/** ۱-الف: رشد فروش ریالی (درآمد) */
function build1aEvidence(
  actual: number | null,
  target: number | null,
  pass: boolean | null | undefined,
  backendReason?: string | null,
): AuditEvidence {
  const thresh = target ?? 60;
  let reason = str(backendReason);
  if (!reason) {
    if (actual != null) {
      if (pass === true || actual >= thresh) {
        reason = `رشد درآمد ریالی سهم (${actual >= 0 ? '+' : ''}${toFaDigits(actual.toFixed(1))}٪) بالاتر از کف تورم مبنا (${toFaDigits(thresh)}٪) است و توانایی شرکت در افزایش درآمد و حفظ قدرت فروش را تایید می‌کند.`;
      } else if (actual < 0) {
        reason = `درآمد ریالی شرکت نسبت به دوره مشابه سال قبل افت کرده است (${toFaDigits(actual.toFixed(1))}٪) که نشان‌دهنده انقباض فروش است.`;
      } else {
        reason = `رشد درآمد ریالی (${toFaDigits(actual.toFixed(1))}٪) کمتر از کف تورم مبنا (${toFaDigits(thresh)}٪) است؛ افزایش درآمد شرکت از تورم عقب مانده و رشد واقعی منفی تلقی می‌شود.`;
      }
    } else {
      reason = 'گزارش فعالیت ماهانه دوره مشابه سال قبل در سامانه کدال ثبت نشده و امکان مقایسه و محاسبه نرخ رشد ریالی وجود ندارد.';
    }
  }

  return {
    actualValue: actual,
    targetThreshold: target,
    unit: '٪',
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۱الف (رشد ریالی ≥ تارگت)',
  };
}

/** ۱-ب: رشد تولیدی و مقداری (فیزیکی) */
function build1bEvidence(
  actual: number | null,
  pass: boolean | null | undefined,
  applicable: boolean,
  backendReason?: string | null,
): AuditEvidence {
  let reason = str(backendReason);
  if (!applicable) {
    reason = 'این شرکت ماهیت هلدینگ، سرمایه‌گذاری یا خدماتی دارد و فاقد محصول فیزیکی است؛ لذا از شرط رشد مقداری معاف است.';
  } else if (!reason) {
    if (actual != null) {
      if (pass === true || actual >= 0) {
        reason = `حجم تولید و فروش مقداری شرکت رشد مثبت داشته (${actual >= 0 ? '+' : ''}${toFaDigits(actual.toFixed(1))}٪) و نشان می‌دهد سود حاصل از جهش عملیاتی واقعی است نه صرفاً تورم قیمت‌ها.`;
      } else {
        reason = `حجم مقداری تولید و فروش سهم کاهش یافته است (${toFaDigits(actual.toFixed(1))}٪)؛ سود حاصل صرفاً از تورم قیمت‌ها ناشی شده و شرکت جهش مقداری نداشته است.`;
      }
    } else {
      reason = 'ارقام مقداری و فیزیکی در گزارش ماهانه کدال تفکیک نشده و فقط ارقام ریالی ثبت شده است.';
    }
  }

  return {
    actualValue: applicable ? actual : null,
    targetThreshold: applicable ? 0 : null,
    unit: applicable ? '٪' : null,
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۱ب (رشد مقداری / فیزیکی)',
  };
}

/** ۲: سابقه و روند سودآوری ۳ ساله EPS */
function build2Evidence(
  series: (number | null)[],
  slots: string[] | undefined,
  pass: boolean | null | undefined,
  rising: boolean | null | undefined,
  profitable: boolean | null | undefined,
  reqYears: number = 3,
  backendReason?: string | null,
): AuditEvidence {
  const realYears = epsRealYears(series);
  let reason = str(backendReason);
  if (!reason) {
    const fail = epsFailReason({ series, slots, strictlyRising: rising, allProfitable: profitable });
    if (fail) {
      reason = fail;
    } else if (pass === true || (rising && profitable && realYears >= reqYears)) {
      reason = 'سود خالص هر سهم (EPS) در ۳ سال مالی متوالی گذشته مثبت و اکیداً صعودی بوده و پایداری سودآوری شرکت را تضمین می‌کند.';
    } else if (realYears < reqYears && realYears >= 2) {
      reason = `سابقه صورت‌های مالی در کدال ناقص است (${toFaDigits(realYears)} سال موجود از ${toFaDigits(reqYears)} سال الزامی)؛ به دلیل عدم احراز شرط سه‌ساله مردود است.`;
    } else if (realYears < 2) {
      reason = 'صورت‌های مالی ۱۲ماهه حسابرسی‌شده شرکت در کدال ثبت نشده و سابقه سودآوری قابل بررسی نیست.';
    } else {
      reason = 'روند سود خالص هر سهم صعودی متوالی نبوده و شرط رشد مستمر ۳ ساله احراز نشد.';
    }
  }

  return {
    actualValue: realYears,
    targetThreshold: reqYears,
    unit: 'سال',
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۲ (۳ سال مالی متوالی صعودی)',
  };
}

/** ۳: حاشیه سود ناخالص */
function build3Evidence(
  actual: number | null,
  target: number | null,
  pass: boolean | null | undefined,
  isNa: boolean = false,
  backendReason?: string | null,
): AuditEvidence {
  const thresh = target ?? 20;
  let reason = str(backendReason);
  if (!reason) {
    if (isNa && actual == null) {
      reason = 'این نماد فاقد بهای تمام‌شده کالای فروش‌رفته است (خدماتی/بانکی/بیمه) و از شاخص حاشیه ناخالص معاف می‌باشد.';
    } else if (actual != null) {
      if (actual >= 30) {
        reason = `حاشیه سود ناخالص شرکت (${toFaDigits(actual.toFixed(1))}٪) بالای ۳۰٪ است که نشان‌دهنده قدرت انحصاری، بهره‌وری عالی و قیمت‌گذاری قوی است.`;
      } else if (pass === true || actual >= thresh) {
        reason = `حاشیه سود ناخالص (${toFaDigits(actual.toFixed(1))}٪) بالاتر از کف استاندارد ۲۰٪ قرار دارد و کارایی عملیاتی شرکت تایید می‌شود.`;
      } else if (actual < 0) {
        reason = `بهای تمام‌شده از درآمد فروش پیشی گرفته و شرکت با زیان ناخالص مواجه است (${toFaDigits(actual.toFixed(1))}٪).`;
      } else {
        reason = `حاشیه سود ناخالص (${toFaDigits(actual.toFixed(1))}٪) کمتر از حداقل نصاب ۲۰٪ است و شرکت حاشیه امن کافی در برابر هزینه‌ها ندارد.`;
      }
    } else {
      reason = 'صورت سود و زیان حسابرسی‌شده اخیر در سامانه کدال یافت نشد و حاشیه سود قابل محاسبه نیست.';
    }
  }

  return {
    actualValue: actual,
    targetThreshold: isNa && actual == null ? null : thresh,
    unit: '٪',
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۳ (حاشیهٔ ناخالص ≥ ۲۰٪ / مطلوب ≥ ۳۰٪)',
  };
}

/** ۴: نسبت فروش سالانه‌شده به ارزش بازار */
function build4Evidence(
  actual: number | null,
  target: number | null,
  pass: boolean | null | undefined,
  isHolding: boolean = false,
  backendReason?: string | null,
): AuditEvidence {
  const thresh = target ?? 0.33;
  let reason = str(backendReason);
  if (!reason) {
    if (actual != null) {
      if (pass === true || actual >= thresh) {
        reason = `فروش سالانه‌شده سهم بیش از ۳۳٪ ارزش بازار آن را پوشش می‌دهد (${toFaDigits(actual.toFixed(2))}× ارزش بازار) و ریسک حباب قیمت را رد می‌کند.`;
      } else {
        reason = `فروش سالانه‌شده شرکت نسبت به ارزش بازار آن اندک است (${toFaDigits(actual.toFixed(2))}× در برابر کف ${toFaDigits(thresh.toFixed(2))}×) و ارزش‌گذاری بازار فراتر از توان فروش فعلی است.`;
      }
    } else if (isHolding) {
      reason = 'شرکت‌های سرمایه‌گذاری و مالی طبق استراتژی FTS از نسبت فروش به ارزش بازار معاف هستند و با ارزش خالص دارایی‌ها (NAV) ارزیابی می‌شوند.';
    } else {
      reason = 'داده ارزش روز بازار یا درآمد سالانه‌شده در دسترس نیست و نسبت فروش به ارزش بازار قابل محاسبه نمی‌باشد.';
    }
  }

  return {
    actualValue: actual,
    targetThreshold: isHolding && actual == null ? null : thresh,
    unit: '×',
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۴ (فروش سالانه‌شده ÷ ارزش بازار)',
  };
}

/** ۵: رژیم قیمت‌گذاری صنعت */
function build5Evidence(
  mode: string | null | undefined,
  pass: boolean | null | undefined,
  backendReason?: string | null,
): AuditEvidence {
  let reason = str(backendReason);
  if (!reason) {
    if (mode === 'free' || pass === true) {
      reason = 'محصولات شرکت در بورس کالا یا بازار رقابتی و آزاد کشف نرخ می‌شوند و ریسک سرکوب قیمت و قیمت‌گذاری دستوری ندارند.';
    } else if (mode === 'mandatory' || pass === false) {
      reason = 'این صنعت مشمول قیمت‌گذاری دستوری دولتی است که حاشیه سود را سرکوب کرده و ریسک سودآوری عملیاتی بالایی ایجاد می‌کند.';
    } else if (mode === 'neutral') {
      reason = 'این صنعت ترکیبی از نرخ‌های توافقی و رقابتی دارد؛ حذف مستقیم نمی‌شود اما نیازمند دقت در رژیم نرخ‌گذاری قراردادهاست.';
    } else {
      reason = 'صنعت این نماد در طبقه‌بندی استاندارد رژیم نرخ‌گذاری بورس کالا ثبت نشده است.';
    }
  }

  return {
    actualValue: mode ? (mode === 'free' ? 'صنعت آزاد' : mode === 'mandatory' ? 'صنعت دستوری' : 'سایر صنایع') : null,
    targetThreshold: 'غیردستوری (آزاد / بورس کالا)',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۵ (رژیم قیمت‌گذاری صنعت)',
  };
}

/** شاهد ممیزی هر محور از کارت نماد (indicators + metrics) */
export function cardAuditEvidence(card: FtsCard): Partial<Record<GapAxis, AuditEvidence>> {
  const ind = card.indicators;
  const passes = card.passes ?? {};
  const i1 = ind?.['1'];
  const i2 = ind?.['2'];
  const i3 = ind?.['3'];
  const i4 = ind?.['4'];
  const i5 = ind?.['5'];
  const out: Partial<Record<GapAxis, AuditEvidence>> = {};

  const isHolding =
    card.profile?.kind === 'holding' ||
    isFinancialOrHolding({ name: card.symbol, sector_name: card.sector });

  const volApplicable = card.profile?.volume_applicable != null
    ? card.profile.volume_applicable
    : isPhysicalGrowthApplicable({ name: card.symbol, sector_name: card.sector });

  // ۱-الف: رشد ریالی
  out['1a_monetary_growth'] = build1aEvidence(
    num(i1?.monetary?.monetary_pct),
    num(i1?.monetary?.threshold),
    passes['1a_monetary_growth'],
    str(i1?.monetary?.reason)
  );

  // ۱-ب: رشد مقداری
  out['1b_volume_growth'] = build1bEvidence(
    num(i1?.volume?.real_pct) ?? num(i1?.volume?.volume_pct),
    passes['1b_volume_growth'],
    volApplicable,
    str(i1?.volume?.reason)
  );

  // ۲: سودآوری ۳ ساله
  out['2_eps_trend'] = build2Evidence(
    i2?.eps_series ?? card.metrics?.eps_series ?? [],
    i2?.period_slots ?? i2?.fiscal_years,
    passes['2_eps_trend'],
    i2?.strictly_rising,
    i2?.all_profitable,
    i2?.years_required ?? 3,
    str(i2?.reason)
  );

  // ۳: حاشیه سود ناخالص
  out['3_gross_margin'] = build3Evidence(
    num(i3?.margin_pct),
    num(i3?.threshold),
    passes['3_gross_margin'],
    Boolean(i3?.na),
    str(i3?.reason)
  );

  // ۴: ارزش بازار
  out['4_sales_to_mcap'] = build4Evidence(
    num(i4?.sales_to_mcap),
    num(i4?.sales_threshold),
    passes['4_sales_to_mcap'],
    isHolding,
    str(i4?.reason)
  );

  // ۵: رژیم صنعت
  out['5_industry'] = build5Evidence(
    card.pricing_mode,
    passes['5_industry'],
    str(i5?.outlook)
  );

  return out;
}

/** F-10: مقدار غایب در ردیف غربالگری ولی حکمِ موتور موجود */
const MISSING = 'مقدار این شاخص در پاسخ غربالگری نیامده، ولی حکمِ موتور FTS برای همان شاخص اعمال شده است (برای عدد دقیق به کارت نماد نگاه کنید).';

/** شاهد ممیزی هر ستون شاخص در جدول غربالگری (ردیف + تارگت‌های کانفیگ FTS) */
export function screenAuditEvidence(
  axis: GapAxis,
  row: FtsScreenRow,
  thresholds?: Record<string, unknown> | null,
): AuditEvidence {
  const cfg = thresholds ?? {};
  const isHolding = isFinancialOrHolding({ name: row.name, sector_name: row.sector_name });
  const volApplicable = isPhysicalGrowthApplicable({ name: row.name, sector_name: row.sector_name });

  switch (axis) {
    case '1a_monetary_growth': {
      const actual = num(row.rev_growth);
      const ev = build1aEvidence(actual, num(cfg.growth_min), row.i1_pass);
      if (actual == null) {
        ev.reason = MISSING;
      }
      return ev;
    }

    case '1b_volume_growth':
      return build1bEvidence(
        null,
        row.i1_pass,
        volApplicable
      );

    case '2_eps_trend': {
      const realYears = epsRealYears(row.eps_series);
      return {
        actualValue: realYears,
        targetThreshold: num(cfg.v10_eps_years) ?? 3,
        unit: 'سال',
        direction: 'higher',
        reason: realYears < 2 ? 'سابقهٔ EPS کمتر از ۲ سال در کدال ثبت شده است.' : null,
        ruleRef: 'جزوهٔ FTS — ۳ سال مالی متوالی صعودی',
      };
    }

    case '3_gross_margin': {
      const actual = num(row.gross_margin);
      const ev = build3Evidence(actual, num(cfg.margin_min), row.i3_pass, isHolding);
      if (actual == null && !isHolding) {
        ev.reason = MISSING;
      }
      return ev;
    }

    case '4_sales_to_mcap': {
      const actual = num(row.sales_to_mcap);
      const ev = build4Evidence(actual, num(cfg.v10_sales_to_mcap_min), row.i4_pass, isHolding);
      if (actual == null && !isHolding) {
        ev.reason = MISSING;
      }
      return ev;
    }

    default: {
      const mode = row.pricing_mode;
      const ev = build5Evidence(mode, row.i5_pass);
      if (mode == null) {
        ev.reason = MISSING;
      }
      return ev;
    }
  }
}
