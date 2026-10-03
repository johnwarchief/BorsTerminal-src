// features/fundamental/lib/auditEvidence.ts -- ساخت «شاهد ممیزی» برای AuditBadge
// پوشش ۱۰۰٪ تمام احتمالات وضعیت شاخص‌ها با یک جمله خلاصه و ساده
import type { AuditEvidence } from '../components/AuditBadge';
import type { FtsCard } from '../api/useFtsCard';
import type { FtsScreenRow } from '../api/useFtsScreen';
import type { GapAxis } from './gapReason';
import { epsFailReason, epsRealYears } from './epsHistory';
import { toFaDigits } from '@shared/lib/fmt';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
// متنِ موتور ارقام لاتین دارد («افت سود در 1404»)؛ تبدیلِ رقم لایهٔ نمایش است و
// یک‌جا همین‌جا انجام می‌شود تا در بازِ همهٔ شاخص‌ها فارسی بماند.
const str = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? toFaDigits(v.trim()) : null;

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
      if (pass === true || (pass == null && actual >= thresh)) {
        reason = `رشد درآمد ریالی ${toFaDigits(actual.toFixed(1))}٪ — از کف ${toFaDigits(thresh)}٪ بالاتر.`;
      } else if (actual < 0) {
        reason = `درآمد ریالی ${toFaDigits(actual.toFixed(1))}٪ افت کرده است (کف: رشد ≥ ${toFaDigits(thresh)}٪).`;
      } else {
        reason = `رشد درآمد ریالی ${toFaDigits(actual.toFixed(1))}٪ — کمتر از کف ${toFaDigits(thresh)}٪.`;
      }
    } else {
      reason = 'گزارش فعالیت ماهانهٔ دورهٔ مشابه سال قبل در کدال نیست؛ رشد ریالی محاسبه نشد.';
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

/** ۱-ب: رشد تولیدی (تناژ) */
function build1bEvidence(
  actual: number | null,
  pass: boolean | null | undefined,
  applicable: boolean,
  backendReason?: string | null,
): AuditEvidence {
  let reason = str(backendReason);
  if (!applicable) {
    reason = 'این نماد محصول فیزیکی ندارد؛ شرط رشد تولیدی بر آن اعمال نمی‌شود.';
  } else if (!reason) {
    if (actual != null) {
      if (pass === true || (pass == null && actual >= 0)) {
        reason = `تولید و فروش ${toFaDigits(actual.toFixed(1))}٪ — مثبت.`;
      } else {
        reason = `تولید و فروش ${toFaDigits(actual.toFixed(1))}٪ — منفی.`;
      }
    } else {
      reason = 'ارقام تولیدی در گزارش ماهانهٔ کدال تفکیک نشده است.';
    }
  }

  return {
    actualValue: applicable ? actual : null,
    targetThreshold: applicable ? 0 : null,
    unit: applicable ? '٪' : null,
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۱ب (رشد تولیدی / تناژ)',
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
    } else if (pass === true || (pass == null && rising && profitable && realYears >= reqYears)) {
      reason = `سود هر سهم در ${toFaDigits(reqYears)} سال مالی متوالی مثبت و روبه‌بالا بوده است.`;
    } else if (realYears < reqYears && realYears >= 2) {
      reason = `سابقهٔ EPS ${toFaDigits(realYears)} سال از ${toFaDigits(reqYears)} سال لازم.`;
    } else if (realYears < 2) {
      reason = 'صورت مالی سالانهٔ ۱۲ماهه در کدال نیست؛ سابقهٔ سودآوری بررسی نشد.';
    } else {
      reason = 'سود هر سهم در سه سال متوالی بالتر نرفته است.';
    }
  }

  return {
    actualValue: realYears,
    targetThreshold: reqYears,
    unit: 'سال',
    direction: 'higher',
    reason,
    ruleRef: 'جزوهٔ FTS — شاخص ۲ (۳ سال مالی با رشد متوالی سود)',
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
      reason = 'بهای تمام‌شدهٔ کالای فروش‌رفته ندارد (خدماتی/بانکی/بیمه)؛ این شاخص کاربرد ندارد.';
    } else if (actual != null) {
      if (pass !== false && actual >= 30) {
        reason = `حاشیهٔ سود ناخالص ${toFaDigits(actual.toFixed(1))}٪ — از کف ${toFaDigits(thresh)}٪ و از آستانهٔ ۳۰٪ بالاتر.`;
      } else if (pass === true || (pass == null && actual >= thresh)) {
        reason = `حاشیهٔ سود ناخالص ${toFaDigits(actual.toFixed(1))}٪ — از کف ${toFaDigits(thresh)}٪ بالاتر.`;
      } else if (actual < 0) {
        reason = `سود ناخالص منفی است (${toFaDigits(actual.toFixed(1))}٪) — بهای تمام‌شده از درآمد بیشتر.`;
      } else {
        reason = `حاشیهٔ سود ناخالص ${toFaDigits(actual.toFixed(1))}٪ — کمتر از کف ${toFaDigits(thresh)}٪.`;
      }
    } else {
      reason = 'صورت سود و زیانِ اخیر در کدال نیست؛ حاشیهٔ سود محاسبه نشد.';
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
      if (pass === true || (pass == null && actual >= thresh)) {
        reason = `فروش سالانه‌شده ${toFaDigits(actual.toFixed(2))}× ارزش بازار — از کف ${toFaDigits(thresh.toFixed(2))}× بالاتر.`;
      } else {
        reason = `فروش سالانه‌شده ${toFaDigits(actual.toFixed(2))}× ارزش بازار — کمتر از کف ${toFaDigits(thresh.toFixed(2))}×.`;
      }
    } else if (isHolding) {
      reason = 'این نماد از شرط فروش‌به‌ارزش‌بازار معاف است (هلدینگ/مالی).';
    } else {
      reason = 'ارزش بازار یا فروش سالانه‌شده موجود نیست؛ نسبت محاسبه نشد.';
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
      reason = 'رژیم قیمت‌گذاری: آزاد / بورس کالا.';
    } else if (mode === 'mandatory' || pass === false) {
      reason = 'رژیم قیمت‌گذاری: دستوری.';
    } else if (mode === 'neutral') {
      reason = 'رژیم قیمت‌گذاری: ترکیبی (توافقی و رقابتی).';
    } else {
      reason = 'رژیم قیمت‌گذاری این صنعت در فهرست FTS ثبت نشده.';
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
  const out: Partial<Record<GapAxis, AuditEvidence>> = {};

  // «معاف است؟» و «قابل اعمال است؟» را خودِ کارت می‌گوید. دو خطِ پیشین برایِ
  // همین دو، regexِ نام/صنعت را رویِ **نمادِ شش‌حرفی** اجرا می‌کردند
  // (`card.symbol`) — یعنی نه نامِ شرکت دیده می‌شد نه صنعتِ کامل، و جوابِ
  // شاهدِ ممیزی با جوابِ کارت می‌جنگید.
  const isHolding = Boolean(i4?.na) || Boolean(i4?.exempt)
    || card.profile?.kind === 'holding';

  const volApplicable = i1?.volume?.applicable != null
    ? Boolean(i1.volume.applicable)
    : card.profile?.volume_applicable != null
      ? card.profile.volume_applicable
      : true;

  // ۱-الف: رشد ریالی
  out['1a_monetary_growth'] = build1aEvidence(
    num(i1?.monetary?.monetary_pct),
    num(i1?.monetary?.threshold),
    passes['1a_monetary_growth'],
    str(i1?.monetary?.reason)
  );

  // ۱-ب: رشد تولیدی
  out['1b_volume_growth'] = build1bEvidence(
    num(i1?.volume?.real_pct) ?? num(i1?.volume?.volume_pct),
    passes['1b_volume_growth'],
    volApplicable,
    str(i1?.volume?.reason)
  );

  // ۲: سودآوری ۳ ساله
  out['2_eps_trend'] = build2Evidence(
    i2?.eps_series ?? card.metrics?.eps_series ?? [],
    i2?.period_slots ?? i2?.fiscal_years ?? undefined,
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
  // «outlook» بک‌اند یک پاراگراف تفسیر است (۲۵ کلمه) — در جای‌گاهِ «علت» نمایش
  // داده می‌شد و خواننده آن را دلیلِ رأی می‌خواند. علتِ کوتاهِ همین فایل جای آن
  // را می‌گیرد؛ خودِ outlook در دریل‌دانِ منبع باقی می‌ماند.
  out['5_industry'] = build5Evidence(card.pricing_mode, passes['5_industry']);

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
  // علتِ «چرا حکمی نیست» از پرچم‌هایِ خودِ بک‌اند خوانده می‌شود
  // (`i1b_applicable`, `i3_na`, `i4_na`)؛ نسخهٔ پیشین هر سه را از regexِ
  // نام/صنعت حدس می‌زد و شاهدِ ممیزی را با همان حدس پر می‌کرد.
  const volApplicable = row.i1b_applicable !== false;

  switch (axis) {
    case '1a_monetary_growth': {
      const actual = num(row.rev_growth);
      const ev = build1aEvidence(actual, num(cfg.growth_min), row.i1a_pass);
      if (actual == null) {
        ev.reason = MISSING;
      }
      return ev;
    }

    case '1b_volume_growth':
      return build1bEvidence(
        null,
        row.i1b_pass,
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
        ruleRef: 'جزوهٔ FTS — ۳ سال مالی با رشد متوالی سود',
      };
    }

    case '3_gross_margin': {
      const actual = num(row.gross_margin);
      const ev = build3Evidence(actual, num(cfg.margin_min), row.i3_pass, row.i3_na === true);
      if (actual == null && row.i3_na !== true) {
        ev.reason = MISSING;
      }
      return ev;
    }

    case '4_sales_to_mcap': {
      const actual = num(row.sales_to_mcap);
      const ev = build4Evidence(actual, num(cfg.v10_sales_to_mcap_min), row.i4_pass, row.i4_na === true);
      if (actual == null && row.i4_na !== true) {
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
