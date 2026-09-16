// features/fundamental/lib/auditEvidence.ts -- ساخت «شاهد ممیزی» برای AuditBadge
// فیلدهای ممیزی بک‌اند (reason / actual_value / target_threshold / rule_ref) در حال
// آماده‌سازی‌اند؛ تا آن زمان شاهد را از همان پاسخ فعلی می‌سازیم: مقدار واقعی هر
// شاخص از indicators/ردیف جدول و تارگت از threshold همان شاخص. اگر چیزی نبود،
// خالی می‌ماند تا AuditBadge فقط متن موجود را نشان دهد (هیچ عدد ساختگی).
import type { AuditEvidence } from '../components/AuditBadge';
import type { FtsCard } from '../api/useFtsCard';
import type { FtsScreenRow } from '../api/useFtsScreen';
import type { GapAxis } from './gapReason';
import { epsFailReason, epsRealYears } from './epsHistory';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() !== '' ? v : null);

/** شاهد ممیزی هر محور از کارت نماد (indicators + metrics) */
export function cardAuditEvidence(card: FtsCard): Partial<Record<GapAxis, AuditEvidence>> {
  const ind = card.indicators;
  const i1 = ind?.['1'];
  const i2 = ind?.['2'];
  const i3 = ind?.['3'];
  const i4 = ind?.['4'];
  const i5 = ind?.['5'];
  const out: Partial<Record<GapAxis, AuditEvidence>> = {};

  if (i1?.monetary) {
    out['1a_monetary_growth'] = {
      actualValue: num(i1.monetary.monetary_pct),
      targetThreshold: num(i1.monetary.threshold),
      unit: '٪',
      direction: 'higher',
      reason: str(i1.monetary.reason) ?? str(i1.monetary.denominator_basis),
      ruleRef: 'جزوهٔ FTS — شاخص ۱الف (رشد ریالی ≥ تارگت)',
    };
  }
  if (i1?.volume) {
    out['1b_volume_growth'] = {
      actualValue: num(i1.volume.real_pct),
      targetThreshold: null,
      unit: '٪',
      direction: 'higher',
      reason: str(i1.volume.reason) ?? str(i1.volume.note),
      ruleRef: 'جزوهٔ FTS — شاخص ۱ب (رشد مقداری/تناژ)',
    };
  }
  if (i2) {
    const realYears = epsRealYears(i2.eps_series);
    out['2_eps_trend'] = {
      actualValue: i2.years_available ?? realYears,
      targetThreshold: i2.years_required ?? 3,
      unit: 'سال',
      direction: 'higher',
      reason:
        epsFailReason({
          series: i2.eps_series,
          slots: i2.period_slots ?? i2.fiscal_years,
          strictlyRising: i2.strictly_rising,
          allProfitable: i2.all_profitable,
        }) ??
        str(i2.reason) ??
        (realYears < 2 ? 'سابقهٔ EPS کافی در کدال ثبت نشده است.' : null),
      ruleRef: 'جزوهٔ FTS — شاخص ۲ (۳ سال مالی متوالی صعودی)',
    };
  }
  if (i3) {
    out['3_gross_margin'] = {
      actualValue: num(i3.margin_pct),
      targetThreshold: num(i3.threshold),
      unit: '٪',
      direction: 'higher',
      reason: str(i3.reason) ?? str(i3.basis),
      ruleRef: 'جزوهٔ FTS — شاخص ۳ (حاشیهٔ ناخالص ≥ ۲۰٪ / مطلوب ≥ ۳۰٪)',
    };
  }
  if (i4) {
    out['4_sales_to_mcap'] = {
      actualValue: num(i4.sales_to_mcap),
      targetThreshold: num(i4.sales_threshold),
      unit: '×',
      direction: 'higher',
      reason: str(i4.annualize_basis),
      ruleRef: 'جزوهٔ FTS — شاخص ۴ (فروش سالانه‌شده ÷ ارزش بازار)',
    };
  }
  if (i5) {
    out['5_industry'] = {
      actualValue: str(i5.regime_label) ?? str(i5.verdict),
      targetThreshold: 'غیردستوری (آزاد / بورس کالا)',
      reason: str(i5.outlook),
      ruleRef: 'جزوهٔ FTS — شاخص ۵ (رژیم قیمت‌گذاری صنعت)',
    };
  }
  return out;
}

/** شاهد ممیزی هر ستون شاخص در جدول غربالگری (ردیف + تارگت‌های کانفیگ FTS) */
export function screenAuditEvidence(
  axis: GapAxis,
  row: FtsScreenRow,
  thresholds?: Record<string, unknown> | null,
): AuditEvidence {
  const cfg = thresholds ?? {};
  switch (axis) {
    case '1a_monetary_growth':
      return {
        actualValue: num(row.rev_growth),
        targetThreshold: num(cfg.growth_min),
        unit: '٪',
        direction: 'higher',
        reason: num(row.rev_growth) == null ? 'گزارش فروش دورهٔ مشابه سال قبل در کدال موجود نیست.' : null,
        ruleRef: 'رشد فروش تجمعی ÷ همان دورهٔ سال قبل',
      };
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
    case '3_gross_margin':
      return {
        actualValue: num(row.gross_margin),
        targetThreshold: num(cfg.margin_min),
        unit: '٪',
        direction: 'higher',
        reason: num(row.gross_margin) == null ? 'سود ناخالصِ ثبت‌شده برای این نماد موجود نیست.' : null,
        ruleRef: 'حاشیهٔ ناخالص = سود ناخالص ÷ درآمد عملیاتی',
      };
    case '4_sales_to_mcap':
      return {
        actualValue: num(row.sales_to_mcap),
        targetThreshold: num(cfg.v10_sales_to_mcap_min),
        unit: '×',
        direction: 'higher',
        reason: num(row.sales_to_mcap) == null ? 'گزارش‌های ماهانهٔ کدال برای سالانه‌سازی فروش کافی نیست.' : null,
        ruleRef: 'فروش سالانه‌شده ÷ ارزش بازار',
      };
    default:
      return {
        actualValue: str(row.pricing_mode),
        targetThreshold: 'غیردستوری (آزاد / بورس کالا)',
        reason: row.pricing_mode == null ? 'رژیم قیمت‌گذاری این صنعت در کدال مشخص نیست.' : null,
        ruleRef: 'رژیم قیمت‌گذاری صنعت',
      };
  }
}
