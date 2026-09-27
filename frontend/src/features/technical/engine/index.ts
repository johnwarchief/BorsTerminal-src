// features/technical/engine/index.ts -- ویترینِ لایه. مصرف‌کننده فقط این را
// import می‌کند و به همین دلیلِ ساده نمی‌تواند ناخواسته به موتور وصل شود.
export type {
  BarRequest,
  CandleStyleMode,
  ChartCapabilities,
  ChartEngineId,
  ChartIndicatorSpec,
  ChartOverlayKind,
  ChartOverlaySpec,
  ChartPalette,
  EngineBar,
  EngineError,
  EngineHealth,
} from './types';
export type { ChartEngine, CrosshairInfo, DrawnShape, EngineMountOptions } from './ChartEngine';
export { ENGINE_REGISTRY, DEFAULT_ENGINE, createDefaultEngine, engineEntry } from './registry';
export type { EngineEntry } from './registry';
export { KLineChartsEngine } from './klinecharts/KLineChartsEngine';

/** پالتِ نهایات‌نگر → نیتِ رنگیِ مشترک؛ یک‌جا تا دو موتور یک رنگ ببینند */
export function paletteFromTheme(dark: boolean): import('./types').ChartPalette {
  return dark
    ? {
        background: '#1e222d',
        grid: '#2a2e39',
        axisText: '#b2b5be',
        up: '#26a69a',
        down: '#ef5350',
        lastLine: '#f59e0b',
        crosshair: '#758696',
        dark: true,
      }
    : {
        background: '#ffffff',
        grid: '#eceff1',
        axisText: '#546e7a',
        up: '#089981',
        down: '#f23645',
        lastLine: '#ff9600',
        crosshair: '#9598a1',
        dark: false,
      };
}
