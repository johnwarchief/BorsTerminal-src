// features/technical/lib/chartPalette.ts -- پالت‌های تم چارت (تک‌منبع برای چارت نماد و «کل بورس»)
import type { ChartPalette } from '../components/KLineChartWrapper';

export const DARK_PALETTE: ChartPalette = {
  up: '#10b981',
  down: '#f43f5e',
  grid: 'rgba(148, 163, 184, 0.07)',
  text: '#93a3ba',
  background: '#0a0e17',
};

export const LIGHT_PALETTE: ChartPalette = {
  up: '#089981',
  down: '#f23645',
  grid: '#e0e3eb',
  text: '#4a4b52',
  background: '#ffffff',
};

export function paletteFor(theme: string): ChartPalette {
  return theme === 'dark' ? DARK_PALETTE : LIGHT_PALETTE;
}
