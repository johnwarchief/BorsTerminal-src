import { fmtPct, toFaDigits } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { tapeFilterVerdict, type TapeFilterConfig } from './tapeAlgorithms';
import {
  GOLDEN_HOUR_HINT,
  STRONG_CLOCK_HINT,
  STRONG_HOUR_LABEL,
  SWEEP_HINT,
  detectGoldenHour,
  detectStrongHour,
  lastCloseDiff,
} from './tapePatterns';

export const LIMIT_PCT = 4.9;

export type TapeBadgeTone = 'violet' | 'amber' | 'cyan' | 'emerald' | 'green' | 'red';

export type TapeBadge = {
  key: string;
  pattern: string;
  tone: TapeBadgeTone;
  label: string;
  title: string;
  filter: boolean;
};

export const BADGE_FILTER_KEY: Record<string, string> = {
  clock: 'f_clock',
  susp: 'f_susp',
  jet: 'f_jet',
  sweep: 'f_roobi',
  noqteh: 'f_noqteh',
  smart: 'f_smart',
  legal: 'f_legal',
};

export function patternBadges(row: MarketRow, cfg: TapeFilterConfig): TapeBadge[] {
  const diff = lastCloseDiff(row);
  const strongHour = detectStrongHour(row);
  const goldenHour = !strongHour && detectGoldenHour(row);
  const pct = row.percent_change;
  const out: TapeBadge[] = [];

  if (tapeFilterVerdict(row, 'f_clock', cfg)) {
    out.push({
      key: 'clock',
      pattern: 'clock',
      tone: goldenHour ? 'amber' : 'violet',
      label: 'ساعت',
      title: `الگوی ساعت: آخرین معامله بالاتر از قیمت پایانی${diff != null ? ` · اختلاف آخرین و پایانی: ${fmtPct(diff * 100)}` : ''}${strongHour ? ` · ${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}` : ''}`,
      filter: true,
    });
  } else if (strongHour) {
    out.push({
      key: 'strong-hour',
      pattern: 'strong-hour',
      tone: 'violet',
      label: 'ساعت قوی',
      title: `${STRONG_HOUR_LABEL} — ${STRONG_CLOCK_HINT}${diff != null ? ` · دلتا (اختلاف قیمت آخرین معامله و پایانی): ${fmtPct(diff * 100)}` : ''}`,
      filter: false,
    });
  } else if (goldenHour) {
    out.push({ key: 'golden-hour', pattern: 'golden-hour', tone: 'amber', label: 'طلایی', title: GOLDEN_HOUR_HINT, filter: false });
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
    out.push({ key: 'noqteh', pattern: 'noqteh', tone: 'amber', label: 'نقطه', title: 'نقطه‌زنی: قیمت به کف ۳۰ روز اخیر نزدیک است', filter: true });
  }
  if (tapeFilterVerdict(row, 'f_smart', cfg)) {
    out.push({
      key: 'smart',
      pattern: 'smart',
      tone: 'cyan',
      label: 'پول هوشمند',
      title: `ورود پول هوشمند: حجم ${row.vol_ratio_file != null ? toFaDigits(row.vol_ratio_file.toFixed(2)) : '—'}× مبنای ۳۰ روز معاملاتی، سرانۀ خریدِ حقوقی ≥ فروشِ حقوقی، آخرین ≥ پایانی و درصدِ آخرین مثبت`,
      filter: true,
    });
  }
  if (tapeFilterVerdict(row, 'f_legal', cfg)) {
    out.push({
      key: 'legal',
      pattern: 'legal',
      tone: 'violet',
      label: 'کد به کد',
      title: 'کدبه‌کد حقوقی به حقیقی: شرط پول هوشمند برقرار است و خرید حقوقی و فروش حقیقی، هرکدام بیش از نیمی از حجم معاملات امروز هستند',
      filter: true,
    });
  }
  if (pct != null && pct >= LIMIT_PCT) {
    out.push({ key: 'lu', pattern: 'limit-up', tone: 'green', label: 'صف+', title: 'صف خرید (تغییر ≥ ۴.۹٪)', filter: false });
  }
  if (pct != null && pct <= -LIMIT_PCT) {
    out.push({ key: 'ld', pattern: 'limit-down', tone: 'red', label: 'صف−', title: 'صف فروش (تغییر ≤ −۴.۹٪)', filter: false });
  }
  if (row.stop_state) {
    const why = (row.stop_reasons || '').split('\n')[0].trim();
    out.push({
      key: 'stopped',
      pattern: 'stopped',
      tone: 'red',
      label: 'متوقف',
      title: `${row.stop_state}${row.stop_since ? ` — از ${toFaDigits(row.stop_since)}` : ''}${why ? `\n${why}` : ''}`,
      filter: false,
    });
  } else if (row.sup_flag) {
    out.push({
      key: 'supervised',
      pattern: 'supervised',
      tone: 'amber',
      label: 'نظارت',
      title: `زیرِ نظرِ سازمان${row.sup_reason_count ? ` (${toFaDigits(row.sup_reason_count)} دلیل)` : ''} — جزئیات درِ Inspector`,
      filter: false,
    });
  }
  return out;
}
