// features/technical/lib/levels.ts -- ترازها و حد ضرر نوسان‌گیر FTS (سایدبار تب ۳)
// خالص و مستقل از DOM. حد ضرر نوسان‌گیر = ۵٪ زیر آخرین کف روند صعودی
// (FTS_SPEC بخش اول، بند ۵). آخرین کف از پیوتِ فرکتالی؛ در نبود پیوت، آخرین کف سری.
import { swingLows } from './indicators';

export type TradeLevels = {
  /** آخرین کف سوینگ (پیوت فرکتالی) یا آخرین کف موجود */
  swingLow: number | null;
  /** حد ضرر نوسان‌گیر = ۰٫۹۵ × کف سوینگ */
  stop5pct: number | null;
};

/** آخرین کف سوینگ — پیوتِ فرکتالیِ order کندل دو طرف */
export function lastSwingLow(lows: (number | null)[], order = 3): number | null {
  const swings = swingLows(lows, order);
  if (swings.length > 0) return swings[swings.length - 1].price;
  for (let i = lows.length - 1; i >= 0; i--) {
    const v = lows[i];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return null;
}

export function computeTradeLevels(lows: (number | null)[], order = 3): TradeLevels {
  const swingLow = lastSwingLow(lows, order);
  return { swingLow, stop5pct: swingLow != null ? swingLow * 0.95 : null };
}

export const SETUP_FA: Record<string, string> = {
  breakout: 'جت (شکست سقف)',
  pullback: 'پولبک',
  fibonacci: 'فیبوناچی',
  choch: 'CHoCH',
  bearish_div: 'واگرایی منفی',
  range: 'رنج',
  trend: 'روند',
};
