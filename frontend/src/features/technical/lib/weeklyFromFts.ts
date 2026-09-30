// features/technical/lib/weeklyFromFts.ts -- نگاشتِ رأیِ هفتگیِ موتورِ FTSِ سرور
// به بلوکی که گیتِ وتوی هفتگیِ تبِ مستر و سایدبارِ چپ می‌خوانند.
//
// چرا اینجا: پیش‌تر هیچ تولیدکننده‌ای `weekly_uptrend` / `belowMa52` / `rsi`
// هفتگی را منتشر نمی‌کرد، پس `weeklyTrendFromSignal` همیشه null می‌داد و گیتِ
// وتوی هفتگی برای هر نمادی «در انتظار» می‌ماند — سیم‌کشیِ مرده.
import type { WeeklyTrend } from '@contracts/technical';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';

/**
 * «na» یعنی ساختارِ کافی برای قضاوت نیست (کمتر از دو پیوتِ کامل) ⇒ null، نه false.
 * فرقش حیاتی است: false وتوی قطعی می‌گیرد، null صادقانه «در انتظار» می‌ماند.
 * «range» هم false است — طبق رأیِ ۱۲ مالک، هفتگیِ خنثی هم ورود نمی‌گیرد.
 */
export function weeklyFromFts(fts: FtsAnalysisData | null | undefined): WeeklyTrend | null {
  if (!fts) return null;
  const w = fts.trend?.W?.trend ?? null;
  const hg = fts.hourglass;
  return {
    uptrend: w === 'up' ? true : w === 'down' || w === 'range' ? false : null,
    belowMa52: hg?.weekly_close != null && hg?.ma52 != null ? hg.weekly_close < hg.ma52 : null,
    rsi: hg?.weekly_rsi5 ?? null,
    basis: fts.trend?.W?.basis ?? null,
    reason: fts.trend?.matrix?.basis?.weekly ?? null,
    matrixDecision: fts.trend?.matrix?.decision ?? null,
  };
}
