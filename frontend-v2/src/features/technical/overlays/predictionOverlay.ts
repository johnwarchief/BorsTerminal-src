/**
 * frontend-v2/src/features/technical/overlays/predictionOverlay.ts
 *
 * اورلی کان پیش‌بینی احتمالاتی هوش مصنوعی (AI Prediction Cone):
 * - ترسیم باند سایه‌روشن بین کران‌های صدک ۱۰ و ۹۰ با شفافیت کم (rgba(218, 165, 32, 0.15))
 * - ترسیم مسیر میانه پیش‌بینی (P50) با خط چین طلایی (#eab308)
 * - بج‌های احتمال صعودی (Upside Probability) و ضریب بزرگ‌نمایی نوسان (Volatility Amplification)
 *   در نزدیکی نقطه پایانی افق زمانی با ارقام فارسی
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
  Coordinate,
} from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import type { PredictionData } from '../model/types';

function getX(
  params: OverlayCreateFiguresCallbackParams<any>,
  dataIndex: number,
  timestamp?: number
): number {
  if (params.xAxis) {
    if (typeof (params.xAxis as { convertToPixel?: (v: number) => number }).convertToPixel === 'function') {
      return (params.xAxis as { convertToPixel: (v: number) => number }).convertToPixel(dataIndex);
    }
    if (timestamp && typeof params.xAxis.convertTimestampToPixel === 'function') {
      return params.xAxis.convertTimestampToPixel(timestamp);
    }
  }
  const pt = params.chart.convertToPixel({ dataIndex });
  if (Array.isArray(pt)) {
    return pt[0]?.x ?? 0;
  }
  return (pt as { x?: number })?.x ?? 0;
}

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

export function registerPredictionOverlay(): void {
  const template: OverlayTemplate<PredictionData> = {
    name: 'predictionCone',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<PredictionData>): OverlayFigure[] => {
      const { overlay, chart, bounding } = params;

      // دریافت داده پیش‌بینی یا از extendData یا از استور مرکزی
      const data: PredictionData | null =
        (overlay.extendData as PredictionData | null) ??
        useTechnicalStore.getState().predictionData;

      if (!data || !data.forecastSteps || data.forecastSteps.length === 0) {
        return [];
      }

      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n === 0) return [];

      const lastCandle = dataList[n - 1];
      const lastIndex = n - 1;
      const lastX = getX(params, lastIndex, lastCandle.timestamp);
      const lastY = getY(params, lastCandle.close);

      // محاسبه فاصله بین کندل‌ها جهت پیش‌روی در آینده
      let barSpace = 12;
      if (n >= 2) {
        const prevX = getX(params, n - 2, dataList[n - 2].timestamp);
        barSpace = Math.max(lastX - prevX, 6);
      }

      // ساخت نقاط منحنی‌های P10، P50 و P90
      const p10Points: Coordinate[] = [];
      const p50Points: Coordinate[] = [];
      const p90Points: Coordinate[] = [];

      data.forecastSteps.forEach((step, idx) => {
        let x = -1;
        if (params.xAxis && typeof params.xAxis.convertTimestampToPixel === 'function') {
          x = params.xAxis.convertTimestampToPixel(step.timestamp);
        }
        if (x == null || isNaN(x) || x <= 0) {
          x = lastX + (idx + 1) * barSpace;
        }

        const yP10 = getY(params, step.p10);
        const yP50 = getY(params, step.p50);
        const yP90 = getY(params, step.p90);

        p10Points.push({ x, y: yP10 });
        p50Points.push({ x, y: yP50 });
        p90Points.push({ x, y: yP90 });
      });

      const figures: OverlayFigure[] = [];

      // ۱. چندضلعی بسته کان احتمالاتی بین P10 و P90 با شفافیت ملایم برنجی
      const conePolygon: Coordinate[] = [
        { x: lastX, y: lastY },
        ...p90Points,
        ...p10Points.slice().reverse(),
      ];

      figures.push({
        type: 'polygon',
        attrs: {
          coordinates: conePolygon,
        },
        styles: {
          style: 'fill',
          color: 'rgba(218, 165, 32, 0.15)',
          borderColor: 'rgba(218, 165, 32, 0.35)',
          borderSize: 1,
        },
      });

      // ۲. خط میانه پیش‌بینی (P50 Median Trajectory) با خط‌چین طلایی
      const p50Trajectory: Coordinate[] = [{ x: lastX, y: lastY }, ...p50Points];
      figures.push({
        type: 'line',
        attrs: {
          coordinates: p50Trajectory,
        },
        styles: {
          color: '#eab308',
          size: 2,
          style: 'dashed',
          dashedValue: [6, 4],
        },
      });

      // ۳. نقطه نشانگر پایانی افق زمانی
      const terminalStep = data.forecastSteps[data.forecastSteps.length - 1];
      const terminalPt = p50Points[p50Points.length - 1];

      figures.push({
        type: 'circle',
        attrs: {
          x: terminalPt.x,
          y: terminalPt.y,
          r: 4.5,
        },
        styles: {
          style: 'fill',
          color: '#eab308',
          borderColor: '#ffffff',
          borderSize: 1.5,
        },
      });

      // ۴. محاسبه و رندر بج‌های آماری (احتمال صعود و بزرگ‌نمایی نوسان)
      const baselinePrice = lastCandle.close;
      const spread = Math.abs(terminalStep.p90 - terminalStep.p10);
      const ratio = spread > 0 ? (terminalStep.p50 - terminalStep.p10) / spread : 0.5;
      const upsidePct = Math.round(Math.min(Math.max(ratio * 100, 5), 95));

      const volAmp = baselinePrice > 0 ? ((spread / baselinePrice) * 5 + 1).toFixed(1) : '1.2';

      const badgeX = Math.min(terminalPt.x + 14, bounding.width - 150);
      const badgeY1 = terminalPt.y - 28;
      const badgeY2 = terminalPt.y + 4;
      const badgeWidth = 138;
      const badgeHeight = 22;

      // بج احتمال صعود (Upside Probability)
      figures.push({
        type: 'rect',
        attrs: {
          x: badgeX,
          y: badgeY1,
          width: badgeWidth,
          height: badgeHeight,
        },
        styles: {
          style: 'fill_stroke',
          color: 'rgba(18, 20, 26, 0.92)',
          borderColor: upsidePct >= 50 ? '#22c55e' : '#ef4444',
          borderSize: 1,
          borderRadius: 4,
        },
      });

      figures.push({
        type: 'text',
        attrs: {
          x: badgeX + badgeWidth / 2,
          y: badgeY1 + badgeHeight / 2,
          text: `احتمال صعود: ${toFaDigits(upsidePct)}٪`,
          align: 'center',
          baseline: 'middle',
        },
        styles: {
          color: upsidePct >= 50 ? '#22c55e' : '#ef4444',
          size: 10,
          family: 'Vazirmatn, sans-serif',
          weight: 'bold',
        },
      });

      // بج بزرگ‌نمایی نوسان (Volatility Amplification)
      figures.push({
        type: 'rect',
        attrs: {
          x: badgeX,
          y: badgeY2,
          width: badgeWidth,
          height: badgeHeight,
        },
        styles: {
          style: 'fill_stroke',
          color: 'rgba(18, 20, 26, 0.92)',
          borderColor: 'rgba(218, 165, 32, 0.65)',
          borderSize: 1,
          borderRadius: 4,
        },
      });

      figures.push({
        type: 'text',
        attrs: {
          x: badgeX + badgeWidth / 2,
          y: badgeY2 + badgeHeight / 2,
          text: `بزرگ‌نمایی نوسان: ${toFaDigits(volAmp)}x`,
          align: 'center',
          baseline: 'middle',
        },
        styles: {
          color: '#eab308',
          size: 10,
          family: 'Vazirmatn, sans-serif',
          weight: 'bold',
        },
      });

      // پیام اخطار برای نمادهای با نقدشوندگی پایین
      if (data.isLiquid === false) {
        figures.push({
          type: 'text',
          attrs: {
            x: badgeX + badgeWidth / 2,
            y: badgeY2 + badgeHeight + 14,
            text: 'هشدار نقدشوندگی: ارزش روزانه زیر ۵ همت',
            align: 'center',
            baseline: 'middle',
          },
          styles: {
            color: '#ef4444',
            size: 9,
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
