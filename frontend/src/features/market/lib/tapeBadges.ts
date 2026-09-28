// features/market/lib/tapeBadges.ts -- بج‌های ستونِ «الگو»
//
// چرا این‌جا نشسته و درِ TapeTable نیست: عددِ چیپِ هر فیلتر و بجِ همان فیلتر درِ
// جدول باید از **یک** داوری بیایند. تا ویرایشِ ۱٫۰٫۵۰ بج «فرمول **یا** پرچمِ
// بک‌اند **یا** ساعتِ قوی/طلایی» بود و چیپ فقط فرمول — سنجشِ زندۀ ۱۴۰۵-۰۷-۰۷:
// چیپِ «الگوی ساعت (۶)» در برابرِ ۸ بجِ «ساعت» درِ همان نما (`آريان`، `سدشت`).
// کاربر آن را «فیلترِ ما با سایت نمی‌خواند» دید، با این‌که هر پنج فرمول عینِ
// خودِ سایت بودند. حالا جدول این تابع را می‌خواند و چیپ همان `tapeFilterVerdict`.
import type { MarketRow } from '@shared/types/marketRow';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';
import {
  GOLDEN_HOUR_HINT,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_HINT,
  detectGoldenHour,
  detectStrongHour,
  lastCloseDiff,
} from './tapePatterns';
import { tapeFilterVerdict, type TapeFilterConfig } from './tapeAlgorithms';
import { LIMIT_PCT } from '../stores/tapeStore';

export type TapeBadgeTone = 'violet' | 'amber' | 'cyan' | 'emerald' | 'green' | 'red';

export type TapeBadge = {
  key: string;
  pattern: string;
  tone: TapeBadgeTone;
  label: string;
  title: string;
  /** بجِ یکی از پنج فیلترِ فایل — همان چیزی که چیپِ بالایِ جدول می‌شمارد. */
  filter: boolean;
};

/** فیلترِ فایلِ هر بج، برایِ ادعایِ «چیپ == آنچه می‌بینی». */
export const BADGE_FILTER_KEY: Record<string, string> = {
  clock: 'f_clock',
  susp: 'f_susp',
  jet: 'f_jet',
  sweep: 'f_roobi',
  noqteh: 'f_noqteh',
};

export function patternBadges(row: MarketRow, cfg: TapeFilterConfig): TapeBadge[] {
  const diff = lastCloseDiff(row);
  const strongHour = detectStrongHour(row);
  const goldenHour = !strongHour && detectGoldenHour(row);
  const pct = row.percent_change;
  const out: TapeBadge[] = [];

  // یکی از خانوادۀ «ساعت»، با اولویتِ فیلترِ فایل. «ساعت قوی» و «طلایی» الگوهایِ
  // خودِ جزوه‌اند و می‌مانند، ولی نامشان جدا است تا بجِ «ساعت» فقط فیلترنویس را
  // بگوید.
  if (tapeFilterVerdict(row, 'f_clock', cfg)) {
    out.push({
      key: 'clock',
      pattern: 'clock',
      tone: goldenHour ? 'amber' : 'violet',
      label: 'ساعت',
      title:
        `الگوی ساعت: پایانی بالاتر از آخرین${diff != null ? ` · اختلاف آخرین و پایانی: ${fmtPct(diff * 100)}` : ''}`
        + (strongHour ? ` · ${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}` : ''),
      filter: true,
    });
  } else if (strongHour) {
    out.push({
      key: 'strong-hour',
      pattern: 'strong-hour',
      tone: 'violet',
      label: 'ساعت قوی',
      title:
        `${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}`
        + (diff != null ? ` · دلتا: ${fmtPct(diff * 100)}` : ''),
      filter: false,
    });
  } else if (goldenHour) {
    out.push({
      key: 'golden-hour',
      pattern: 'golden-hour',
      tone: 'amber',
      label: 'طلایی',
      title: GOLDEN_HOUR_HINT,
      filter: false,
    });
  }

  const volMult = row.vol_ratio != null ? `${toFaDigits(row.vol_ratio.toFixed(1))}× میانگین ماه` : '—';
  if (tapeFilterVerdict(row, 'f_susp', cfg)) {
    out.push({ key: 'susp', pattern: 'susp', tone: 'amber', label: 'مشکوک', title: `حجم مشکوک: ${volMult}`, filter: true });
  }
  if (tapeFilterVerdict(row, 'f_jet', cfg)) {
    out.push({
      key: 'jet',
      pattern: 'jet',
      tone: 'cyan',
      label: 'جت',
      title: `جت: شکست مقاومت با سرانه خرید ${row.buyer_power != null ? toFaDigits(row.buyer_power.toFixed(2)) : '—'}×`,
      filter: true,
    });
  }
  if (tapeFilterVerdict(row, 'f_roobi', cfg)) {
    out.push({ key: 'sweep', pattern: 'sweep', tone: 'emerald', label: 'کف‌روب', title: `کف‌روب: ${SWEEP_HINT}`, filter: true });
  }
  if (tapeFilterVerdict(row, 'f_noqteh', cfg)) {
    out.push({ key: 'noqteh', pattern: 'noqteh', tone: 'amber', label: 'نقطه', title: 'نقطه‌زنی: فاصله نزدیک از کف ۳۰ روزه', filter: true });
  }
  if (pct != null && pct >= LIMIT_PCT) {
    out.push({ key: 'lu', pattern: 'limit-up', tone: 'green', label: 'صف+', title: 'صف خرید (تغییر ≥ ۴.۹٪)', filter: false });
  }
  if (pct != null && pct <= -LIMIT_PCT) {
    out.push({ key: 'ld', pattern: 'limit-down', tone: 'red', label: 'صف−', title: 'صف فروش (تغییر ≤ −۴.۹٪)', filter: false });
  }
  return out;
}
