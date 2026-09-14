// features/technical/lib/chartPalette.ts -- پالت‌های تم چارت (هم‌راستا با TradingView)
// فقط رنگ‌های ظاهری (پس‌زمینه/گرید/متن/محور) به سمت TV می‌روند؛ رنگ‌های سبز/قرمز
// (معنایی صعود/نزول) بدون تغییر می‌مانند.
import type { ChartPalette } from '../components/KLineChartWrapper';

/** تم تاریک — پس‌زمینه/گرید/متن هم‌خوان TradingView dark */
export const DARK_PALETTE: ChartPalette = {
  up: '#10b981',
  down: '#f43f5e',
  grid: 'rgba(42, 46, 57, 0.85)',
  text: '#d1d4dc',
  background: '#131722',
  axis: '#2a2e39',
};

/** تم روشن — سطح‌بندی ملایم و hairline */
export const LIGHT_PALETTE: ChartPalette = {
  up: '#089981',
  down: '#f23645',
  grid: 'rgba(229, 232, 240, 0.9)',
  text: '#131722',
  background: '#ffffff',
  axis: '#d6dbe8',
};

export function paletteFor(theme: string): ChartPalette {
  return theme === 'dark' ? DARK_PALETTE : LIGHT_PALETTE;
}
