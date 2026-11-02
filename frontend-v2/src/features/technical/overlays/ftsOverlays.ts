/**
 * frontend-v2/src/features/technical/overlays/ftsOverlays.ts
 *
 * اورلی‌های اختصاصی سیستم معاملاتی FTS با هویت بصری برنجی (Brass Aesthetics):
 * ۱. سطوح حمایت و مقاومت کلیدی FTS (ftSupportResistance): خطوط تراز با بج‌های طلایی
 * ۲. کانال‌های روند FTS (ftsTrendChannel) و کانال رگرسیون بر پایه هندسه تحلیلی
 * ۳. خطوط پیوت کلیدی FTS (ftsKeyPivot): ترازهای محوری برگشتی
 * به همراه ثبت ابزارهای مکمل کاتالوگ ترسیم (چنگال اندروز، باکس گن، فیبو گسترشی و زون‌ها).
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
} from 'klinecharts';

// ----------------------------------------------------------------------------
// توابع کمکی تبدیل مختصات چارت به پیکسل‌های کانواس
// ----------------------------------------------------------------------------

function getY(
  params: OverlayCreateFiguresCallbackParams<any>,
  price: number
): number {
  if (params.yAxis && typeof params.yAxis.convertToPixel === 'function') {
    return params.yAxis.convertToPixel(price);
  }
  const pt = params.chart.convertToPixel({ value: price });
  if (Array.isArray(pt)) {
    return pt[0]?.y ?? 0;
  }
  return (pt as { y?: number })?.y ?? 0;
}

// ----------------------------------------------------------------------------
// ۱. سطوح حمایت و مقاومت FTS با استایل برنجی (FTS Support & Resistance)
// ----------------------------------------------------------------------------

export interface FTSLevelItem {
  price: number;
  type: 'support' | 'resistance';
  labelFa?: string;
  strength?: number; // ۱ تا ۳
}

export interface FTSSupportResistanceExtendData {
  levels?: FTSLevelItem[];
}

export function registerFTSSupportResistanceOverlay(): void {
  const template: OverlayTemplate<FTSSupportResistanceExtendData> = {
    name: 'ftsSupportResistance',
    totalStep: 2,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: true,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<FTSSupportResistanceExtendData>): OverlayFigure[] => {
      const { coordinates, bounding, overlay } = params;
      const figures: OverlayFigure[] = [];
      const extendData = overlay.extendData;

      // اگر لیست سطوح داده شده بود، تمام سطوح را رسم کن
      if (extendData?.levels && extendData.levels.length > 0) {
        for (const lvl of extendData.levels) {
          const y = getY(params, lvl.price);
          const isSupport = lvl.type === 'support';
          const lineColor = isSupport ? 'rgba(34, 197, 94, 0.85)' : 'rgba(218, 165, 32, 0.9)';
          const labelText = lvl.labelFa || (isSupport ? 'حمایت کلیدی FTS' : 'مقاومت کلیدی FTS');

          figures.push({
            type: 'line',
            attrs: {
              coordinates: [
                { x: 0, y },
                { x: bounding.width, y },
              ],
            },
            styles: {
              color: lineColor,
              size: lvl.strength === 3 ? 2 : 1.2,
              style: lvl.strength === 3 ? 'solid' : 'dashed',
              dashedValue: [6, 4],
            },
          });

          // بج متنی تراز سمت راست
          figures.push({
            type: 'text',
            attrs: {
              x: bounding.width - 12,
              y: y - 8,
              text: labelText,
              align: 'right',
              baseline: 'bottom',
            },
            styles: {
              color: lineColor,
              size: 10,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
            },
          });
        }
        return figures;
      }

      // در غیر این صورت بر مبنای نقاط رسم شده توسط کاربر (حداقل یک نقطه)
      if (coordinates.length > 0) {
        const y = coordinates[0].y;
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: 0, y },
              { x: bounding.width, y },
            ],
          },
          styles: {
            color: '#eab308',
            size: 1.5,
            style: 'dashed',
            dashedValue: [6, 4],
          },
        });

        figures.push({
          type: 'text',
          attrs: {
            x: bounding.width - 12,
            y: y - 8,
            text: 'تراز FTS',
            align: 'right',
            baseline: 'bottom',
          },
          styles: {
            color: '#eab308',
            size: 10,
            family: 'Vazirmatn, sans-serif',
            weight: 'bold',
          },
        });
      }

      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ۲. کانال روند FTS با سایه‌روشن برنجی (FTS Trend Channel)
// ----------------------------------------------------------------------------

export function registerFTSTrendChannelOverlay(): void {
  const template: OverlayTemplate = {
    name: 'ftsTrendChannel',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const figures: OverlayFigure[] = [];
      if (coordinates.length < 2) return figures;

      const p0 = coordinates[0];
      const p1 = coordinates[1];

      // خط مبنا
      figures.push({
        type: 'line',
        attrs: {
          coordinates: [p0, p1],
        },
        styles: {
          color: '#eab308',
          size: 1.5,
          style: 'solid',
        },
      });

      if (coordinates.length >= 3) {
        const p2 = coordinates[2];
        const dy = p2.y - p0.y;
        const p0Upper = { x: p0.x, y: p0.y + dy };
        const p1Upper = { x: p1.x, y: p1.y + dy };

        // خط موازی فوقانی/تحتانی
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [p0Upper, p1Upper],
          },
          styles: {
            color: '#c59b27',
            size: 1.5,
            style: 'solid',
          },
        });

        // خط میانه کانال
        const p0Mid = { x: p0.x, y: p0.y + dy / 2 };
        const p1Mid = { x: p1.x, y: p1.y + dy / 2 };
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [p0Mid, p1Mid],
          },
          styles: {
            color: '#d4af37',
            size: 1,
            style: 'dashed',
            dashedValue: [4, 4],
          },
        });

        // سایه فضای داخل کانال با استایل برنجی ملایم
        figures.push({
          type: 'polygon',
          attrs: {
            coordinates: [p0, p1, p1Upper, p0Upper],
          },
          styles: {
            style: 'fill',
            color: 'rgba(218, 165, 32, 0.08)',
          },
        });
      }

      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ۳. خطوط پیوت کلیدی FTS با استایل برنجی (Key Pivot Lines)
// ----------------------------------------------------------------------------

export function registerFTSKeyPivotOverlay(): void {
  const template: OverlayTemplate = {
    name: 'ftsKeyPivot',
    totalStep: 2,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: true,
    createPointFigures: ({ coordinates, bounding }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const figures: OverlayFigure[] = [];
      if (coordinates.length === 0) return figures;

      const y = coordinates[0].y;
      figures.push({
        type: 'line',
        attrs: {
          coordinates: [
            { x: 0, y },
            { x: bounding.width, y },
          ],
        },
        styles: {
          color: '#eab308',
          size: 1.5,
          style: 'dashed',
          dashedValue: [3, 3],
        },
      });

      figures.push({
        type: 'text',
        attrs: {
          x: bounding.width - 12,
          y: y - 8,
          text: 'پیوت کلیدی FTS',
          align: 'right',
          baseline: 'bottom',
        },
        styles: {
          color: '#facc15',
          size: 10,
          family: 'Vazirmatn, sans-serif',
          weight: 'bold',
        },
      });

      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ۴. رجیستری ابزارهای کاتالوگ ترسیم (Drawing Catalog Fillers)
// ----------------------------------------------------------------------------

export function registerRectZoneOverlay(): void {
  const template: OverlayTemplate = {
    name: 'rect',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 2) return [];
      const [p0, p1] = coordinates;
      const x = Math.min(p0.x, p1.x);
      const y = Math.min(p0.y, p1.y);
      const width = Math.abs(p1.x - p0.x);
      const height = Math.abs(p1.y - p0.y);

      return [
        {
          type: 'rect',
          attrs: { x, y, width, height },
          styles: {
            style: 'fill_stroke',
            color: 'rgba(218, 165, 32, 0.12)',
            borderColor: '#eab308',
            borderSize: 1,
            borderRadius: 2,
          },
        },
      ];
    },
  };
  registerOverlay(template);
}

export function registerRegressionChannelOverlay(): void {
  const template: OverlayTemplate = {
    name: 'regressionChannel',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 2) return [];
      const [p0, p1] = coordinates;
      const channelOffset = coordinates.length >= 3 ? Math.abs(coordinates[2].y - p0.y) : 25;

      const p0Upper = { x: p0.x, y: p0.y - channelOffset };
      const p1Upper = { x: p1.x, y: p1.y - channelOffset };
      const p0Lower = { x: p0.x, y: p0.y + channelOffset };
      const p1Lower = { x: p1.x, y: p1.y + channelOffset };

      return [
        {
          type: 'polygon',
          attrs: { coordinates: [p0Upper, p1Upper, p1Lower, p0Lower] },
          styles: { style: 'fill', color: 'rgba(218, 165, 32, 0.08)' },
        },
        {
          type: 'line',
          attrs: { coordinates: [p0, p1] },
          styles: { color: '#eab308', size: 1.5, style: 'dashed', dashedValue: [5, 4] },
        },
        {
          type: 'line',
          attrs: { coordinates: [p0Upper, p1Upper] },
          styles: { color: '#c59b27', size: 1.2 },
        },
        {
          type: 'line',
          attrs: { coordinates: [p0Lower, p1Lower] },
          styles: { color: '#c59b27', size: 1.2 },
        },
      ];
    },
  };
  registerOverlay(template);
}

export function registerAndrewsPitchforkOverlay(): void {
  const template: OverlayTemplate = {
    name: 'andrewsPitchfork',
    totalStep: 4,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 3) return [];
      const [p0, p1, p2] = coordinates;
      const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const ext = 1.6;
      const medianEnd = { x: p0.x + (mid.x - p0.x) * ext, y: p0.y + (mid.y - p0.y) * ext };

      const vUpper = { x: p1.x - mid.x, y: p1.y - mid.y };
      const vLower = { x: p2.x - mid.x, y: p2.y - mid.y };

      return [
        {
          type: 'line',
          attrs: { coordinates: [p1, p2] },
          styles: { color: '#c59b27', size: 1, style: 'dashed' },
        },
        {
          type: 'line',
          attrs: { coordinates: [p0, medianEnd] },
          styles: { color: '#eab308', size: 1.5 },
        },
        {
          type: 'line',
          attrs: {
            coordinates: [
              p1,
              { x: medianEnd.x + vUpper.x, y: medianEnd.y + vUpper.y },
            ],
          },
          styles: { color: '#c59b27', size: 1.2 },
        },
        {
          type: 'line',
          attrs: {
            coordinates: [
              p2,
              { x: medianEnd.x + vLower.x, y: medianEnd.y + vLower.y },
            ],
          },
          styles: { color: '#c59b27', size: 1.2 },
        },
      ];
    },
  };
  registerOverlay(template);
}

export function registerGannBoxOverlay(): void {
  const template: OverlayTemplate = {
    name: 'gannBox',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 2) return [];
      const [p0, p1] = coordinates;
      const x = Math.min(p0.x, p1.x);
      const y = Math.min(p0.y, p1.y);
      const w = Math.abs(p1.x - p0.x);
      const h = Math.abs(p1.y - p0.y);

      return [
        {
          type: 'rect',
          attrs: { x, y, width: w, height: h },
          styles: {
            style: 'stroke',
            borderColor: '#eab308',
            borderSize: 1.5,
          },
        },
        // خطوط تقاطع قطری باکس گن
        {
          type: 'line',
          attrs: { coordinates: [{ x, y }, { x: x + w, y: y + h }] },
          styles: { color: '#c59b27', size: 1, style: 'dashed' },
        },
        {
          type: 'line',
          attrs: { coordinates: [{ x, y: y + h }, { x: x + w, y }] },
          styles: { color: '#c59b27', size: 1, style: 'dashed' },
        },
        // خط افقی ۵۰٪
        {
          type: 'line',
          attrs: { coordinates: [{ x, y: y + h / 2 }, { x: x + w, y: y + h / 2 }] },
          styles: { color: 'rgba(218, 165, 32, 0.6)', size: 1, style: 'dashed' },
        },
      ];
    },
  };
  registerOverlay(template);
}

export function registerFibonacciExtensionOverlay(): void {
  const template: OverlayTemplate = {
    name: 'fibonacciExtension',
    totalStep: 4,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates, bounding }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 3) return [];
      const [p0, p1, p2] = coordinates;
      const impulse = p1.y - p0.y;
      const ratios = [0.618, 1.0, 1.272, 1.618];
      const figures: OverlayFigure[] = [];

      for (const r of ratios) {
        const y = p2.y + impulse * r;
        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: p2.x, y }, { x: bounding.width, y }] },
          styles: { color: '#eab308', size: 1, style: 'dashed', dashedValue: [4, 4] },
        });
        figures.push({
          type: 'text',
          attrs: {
            x: bounding.width - 8,
            y: y - 4,
            text: `Fib Ext ${r * 100}%`,
            align: 'right',
            baseline: 'bottom',
          },
          styles: { color: '#eab308', size: 9, family: 'Vazirmatn, sans-serif' },
        });
      }

      return figures;
    },
  };
  registerOverlay(template);
}

export function registerFibonacciFanOverlay(): void {
  const template: OverlayTemplate = {
    name: 'fibonacciFan',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 2) return [];
      const [p0, p1] = coordinates;
      const dy = p1.y - p0.y;
      const ratios = [0.382, 0.5, 0.618];
      const figures: OverlayFigure[] = [];

      for (const r of ratios) {
        const target = { x: p1.x + 200, y: p0.y + (dy * r * 2.5) };
        figures.push({
          type: 'line',
          attrs: { coordinates: [p0, target] },
          styles: { color: '#d4af37', size: 1, style: 'dashed' },
        });
      }

      return figures;
    },
  };
  registerOverlay(template);
}

export function registerPriceRangeOverlay(): void {
  const template: OverlayTemplate = {
    name: 'priceRange',
    totalStep: 3,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { coordinates } = params;
      if (coordinates.length < 2) return [];
      const [p0, p1] = coordinates;
      const x = Math.min(p0.x, p1.x);
      const y = Math.min(p0.y, p1.y);
      const w = Math.abs(p1.x - p0.x);
      const h = Math.abs(p1.y - p0.y);
      const isUp = p1.y < p0.y;

      return [
        {
          type: 'rect',
          attrs: { x, y, width: w, height: h },
          styles: {
            style: 'fill_stroke',
            color: isUp ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            borderColor: isUp ? '#22c55e' : '#ef4444',
            borderSize: 1,
          },
        },
        {
          type: 'text',
          attrs: {
            x: x + w / 2,
            y: y + h / 2,
            text: 'محدوده قیمت',
            align: 'center',
            baseline: 'middle',
          },
          styles: {
            color: isUp ? '#22c55e' : '#ef4444',
            size: 10,
            family: 'Vazirmatn, sans-serif',
            weight: 'bold',
          },
        },
      ];
    },
  };
  registerOverlay(template);
}

export function registerRiskRewardOverlay(): void {
  const template: OverlayTemplate = {
    name: 'riskReward',
    totalStep: 4,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: ({ coordinates }: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      if (coordinates.length < 3) return [];
      const [entry, tp, sl] = coordinates;
      const width = 120;
      const x = entry.x;

      return [
        // زون حد سود (TP)
        {
          type: 'rect',
          attrs: {
            x,
            y: Math.min(entry.y, tp.y),
            width,
            height: Math.abs(tp.y - entry.y),
          },
          styles: {
            style: 'fill_stroke',
            color: 'rgba(34, 197, 94, 0.18)',
            borderColor: '#22c55e',
            borderSize: 1,
          },
        },
        // زون حد ضرر (SL)
        {
          type: 'rect',
          attrs: {
            x,
            y: Math.min(entry.y, sl.y),
            width,
            height: Math.abs(sl.y - entry.y),
          },
          styles: {
            style: 'fill_stroke',
            color: 'rgba(239, 68, 68, 0.18)',
            borderColor: '#ef4444',
            borderSize: 1,
          },
        },
        // خط ورود
        {
          type: 'line',
          attrs: { coordinates: [{ x, y: entry.y }, { x: x + width, y: entry.y }] },
          styles: { color: '#eab308', size: 1.5, style: 'solid' },
        },
      ];
    },
  };
  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ثبت کلیه اورلی‌های سیستم FTS و کاتالوگ ترسیم
// ----------------------------------------------------------------------------

export function registerFTSOverlays(): void {
  registerFTSSupportResistanceOverlay();
  registerFTSTrendChannelOverlay();
  registerFTSKeyPivotOverlay();
  registerRectZoneOverlay();
  registerRegressionChannelOverlay();
  registerAndrewsPitchforkOverlay();
  registerGannBoxOverlay();
  registerFibonacciExtensionOverlay();
  registerFibonacciFanOverlay();
  registerPriceRangeOverlay();
  registerRiskRewardOverlay();
}
