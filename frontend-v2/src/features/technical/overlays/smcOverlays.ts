/**
 * frontend-v2/src/features/technical/overlays/smcOverlays.ts
 *
 * اورلی‌های پرایس‌اکشن نهادی و مفاهیم پول هوشمند (Smart Money Concepts - SMC):
 * ۱. خلاء نقدینگی (Fair Value Gap - FVG):
 *    - صعودی: مستطیل سبز (rgba(34, 197, 94, 0.18)) با خط تعادل ۵۰٪ (Equilibrium) چین‌دار
 *    - نزولی: مستطیل قرمز (rgba(239, 68, 68, 0.18)) با خط تعادل ۵۰٪ چین‌دار
 * ۲. بلوک سفارشات نهادی (Order Block - OB):
 *    - صعودی و نزولی با ترازهای ورود و خط میانه
 * ۳. مدیریت خودکار مصرف‌شدگی (Automated Mitigation):
 *    - کاهش شفافیت زون‌های مصرف‌شده و هماهنگی با تنظیمات نمایش در technicalStore
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
  KLineData,
} from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import type { PriceZone } from '../model/types';

function getIsLight(): boolean {
  try {
    const t = useUiStore.getState().theme;
    return t === 'warm' || t === 'cool';
  } catch {
    return false;
  }
}

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

/**
 * تابع کمکی رندر زون واحد (FVG یا Order Block)
 */
function renderSingleZoneFigures(
  params: OverlayCreateFiguresCallbackParams<any>,
  zone: PriceZone,
  dataList: KLineData[],
  boundingWidth: number
): OverlayFigure[] {
  const figures: OverlayFigure[] = [];

  // محاسبه مختصات افقی X شروع و پایان
  let startX = -1;
  if (params.xAxis && zone.startTs && typeof params.xAxis.convertTimestampToPixel === 'function') {
    startX = params.xAxis.convertTimestampToPixel(zone.startTs);
  }
  if (startX == null || isNaN(startX) || startX <= 0) {
    if (zone.startIndex >= 0 && zone.startIndex < dataList.length) {
      startX = getX(params, zone.startIndex, dataList[zone.startIndex]?.timestamp);
    } else {
      startX = getX(params, 0);
    }
  }

  let endX = boundingWidth;
  if (zone.mitigated && zone.mitigatedTs && params.xAxis && typeof params.xAxis.convertTimestampToPixel === 'function') {
    const mitX = params.xAxis.convertTimestampToPixel(zone.mitigatedTs);
    if (mitX && !isNaN(mitX) && mitX > startX) {
      endX = mitX;
    }
  }

  // اطمینان از عرض مناسب زون
  if (endX <= startX) {
    endX = startX + 60;
  }

  const yTop = getY(params, zone.top);
  const yBottom = getY(params, zone.bottom);
  const yEq = getY(params, zone.equilibrium || (zone.top + zone.bottom) / 2);

  const rectY = Math.min(yTop, yBottom);
  const rectHeight = Math.max(Math.abs(yBottom - yTop), 2);
  const rectWidth = endX - startX;

  const isFvg = zone.type === 'FVG';

  // پالت رنگ بر مبنای صعودی/نزولی و وضعیت مصرف‌شدگی (Mitigation)
  const isLight = getIsLight();
  let fillColor = '';
  let borderColor = '';
  let eqLineColor = '';
  let badgeBg = '';
  let textColor = '';

  if (zone.isBullish) {
    if (zone.mitigated) {
      fillColor = isLight ? 'rgba(4, 120, 87, 0.03)' : 'rgba(34, 197, 94, 0.02)';
      borderColor = isLight ? 'rgba(4, 120, 87, 0.22)' : 'rgba(34, 197, 94, 0.18)';
      eqLineColor = isLight ? 'rgba(4, 120, 87, 0.28)' : 'rgba(34, 197, 94, 0.22)';
      badgeBg = isLight ? 'rgba(241, 245, 249, 0.92)' : 'rgba(18, 20, 24, 0.70)';
      textColor = isLight ? 'rgba(4, 120, 87, 0.75)' : 'rgba(34, 197, 94, 0.65)';
    } else {
      fillColor = isLight
        ? (isFvg ? 'rgba(4, 120, 87, 0.08)' : 'rgba(4, 120, 87, 0.10)')
        : (isFvg ? 'rgba(34, 197, 94, 0.07)' : 'rgba(34, 197, 94, 0.09)');
      borderColor = isLight
        ? (isFvg ? 'rgba(4, 120, 87, 0.50)' : 'rgba(5, 150, 105, 0.60)')
        : (isFvg ? 'rgba(34, 197, 94, 0.40)' : 'rgba(22, 163, 74, 0.50)');
      eqLineColor = isLight ? '#047857' : '#22c55e';
      badgeBg = isLight ? 'rgba(240, 253, 244, 0.95)' : 'rgba(16, 28, 20, 0.90)';
      textColor = isLight ? '#047857' : '#22c55e';
    }
  } else {
    if (zone.mitigated) {
      fillColor = isLight ? 'rgba(185, 28, 28, 0.03)' : 'rgba(239, 68, 68, 0.02)';
      borderColor = isLight ? 'rgba(185, 28, 28, 0.22)' : 'rgba(239, 68, 68, 0.18)';
      eqLineColor = isLight ? 'rgba(185, 28, 28, 0.28)' : 'rgba(239, 68, 68, 0.22)';
      badgeBg = isLight ? 'rgba(241, 245, 249, 0.92)' : 'rgba(18, 20, 24, 0.70)';
      textColor = isLight ? 'rgba(185, 28, 28, 0.75)' : 'rgba(239, 68, 68, 0.65)';
    } else {
      fillColor = isLight
        ? (isFvg ? 'rgba(185, 28, 28, 0.08)' : 'rgba(185, 28, 28, 0.10)')
        : (isFvg ? 'rgba(239, 68, 68, 0.07)' : 'rgba(239, 68, 68, 0.09)');
      borderColor = isLight
        ? (isFvg ? 'rgba(185, 28, 28, 0.50)' : 'rgba(220, 38, 38, 0.60)')
        : (isFvg ? 'rgba(239, 68, 68, 0.40)' : 'rgba(220, 38, 38, 0.50)');
      eqLineColor = isLight ? '#b91c1c' : '#ef4444';
      badgeBg = isLight ? 'rgba(254, 242, 242, 0.95)' : 'rgba(28, 16, 18, 0.90)';
      textColor = isLight ? '#b91c1c' : '#ef4444';
    }
  }

  // ۱. کادر مستطیلی زون با حاشیه ظریف و گرادیان آرام
  figures.push({
    type: 'rect',
    attrs: {
      x: startX,
      y: rectY,
      width: rectWidth,
      height: rectHeight,
    },
    styles: {
      style: 'fill_stroke',
      color: fillColor,
      borderColor: borderColor,
      borderSize: zone.mitigated ? 0.75 : 1,
      borderStyle: zone.mitigated ? 'dashed' : 'solid',
      borderRadius: 1,
    },
  });

  // ۲. بج مشخصات زون (پیل ظریف در گوشه بالا، در ارتفاع کم به بیرون منتقل می‌شود)
  const labelPrefix = isFvg ? 'FVG' : 'OB';
  const dirLabel = zone.isBullish ? 'تقاضا' : 'عرضه';
  const mitLabel = zone.mitigated ? ' [مصرف‌شده]' : '';
  const zoneLabel = `${labelPrefix} · ${dirLabel}${mitLabel}`;
  const badgeWidth = zone.mitigated ? 94 : 68;
  const badgeHeight = 16;
  const badgeY = rectHeight < 18
    ? (rectY - badgeHeight - 2 >= 0 ? rectY - badgeHeight - 2 : rectY + rectHeight + 2)
    : rectY + 2;

  figures.push({
    type: 'rect',
    attrs: {
      x: startX + 4,
      y: badgeY,
      width: badgeWidth,
      height: badgeHeight,
    },
    styles: {
      style: 'fill_stroke',
      color: badgeBg,
      borderColor: borderColor,
      borderSize: 0.8,
      borderRadius: 2,
    },
  });

  figures.push({
    type: 'text',
    attrs: {
      x: startX + 4 + badgeWidth / 2,
      y: badgeY + badgeHeight / 2,
      text: zoneLabel,
      align: 'center',
      baseline: 'middle',
    },
    styles: {
      color: textColor,
      size: 9,
      family: 'Vazirmatn, sans-serif',
      weight: 'bold',
    },
  });

  // ۳. خط تراز تعادل ۵۰٪ (Equilibrium Line) به صورت خط‌چین ظریف فقط در ارتفاع کافی
  if (rectHeight >= 8) {
    figures.push({
      type: 'line',
      attrs: {
        coordinates: [
          { x: startX, y: yEq },
          { x: endX, y: yEq },
        ],
      },
      styles: {
        color: eqLineColor,
        size: 1,
        style: 'dashed',
        dashedValue: [3, 3],
      },
    });

    // برچسب ۵۰٪ تعادل به سبک پیل مینیمال
    if (rectWidth > 75) {
      const eqBadgeW = 28;
      const eqBadgeH = 13;
      const eqBadgeX = endX - eqBadgeW - 4;
      const eqBadgeY = yEq - eqBadgeH / 2;

      figures.push({
        type: 'rect',
        attrs: {
          x: eqBadgeX,
          y: eqBadgeY,
          width: eqBadgeW,
          height: eqBadgeH,
        },
        styles: {
          style: 'fill',
          color: badgeBg,
          borderRadius: 2,
        },
      });

      figures.push({
        type: 'text',
        attrs: {
          x: eqBadgeX + eqBadgeW / 2,
          y: yEq,
          text: '۵۰٪',
          align: 'center',
          baseline: 'middle',
        },
        styles: {
          color: eqLineColor,
          size: 8,
          family: 'Vazirmatn, sans-serif',
          weight: 'bold',
        },
      });
    }
  }

  // ۴. نمایش حدود قیمت در صورت داشتن ارتفاع کافی (>۲۴px)
  if (rectHeight >= 24 && rectWidth > 120) {
    const topStr = toFaDigits(Math.round(zone.top).toLocaleString('en-US'));
    const bottomStr = toFaDigits(Math.round(zone.bottom).toLocaleString('en-US'));
    figures.push({
      type: 'text',
      attrs: {
        x: endX - 6,
        y: rectY + 3,
        text: topStr,
        align: 'right',
        baseline: 'top',
      },
      styles: {
        color: textColor,
        size: 8,
        family: 'monospace, sans-serif',
      },
    });
    figures.push({
      type: 'text',
      attrs: {
        x: endX - 6,
        y: rectY + rectHeight - 3,
        text: bottomStr,
        align: 'right',
        baseline: 'bottom',
      },
      styles: {
        color: textColor,
        size: 8,
        family: 'monospace, sans-serif',
      },
    });
  }

  return figures;
}

// ----------------------------------------------------------------------------
// ۱. اورلی زون FVG (Fair Value Gap)
// ----------------------------------------------------------------------------

export interface FVGExtendData {
  zone?: PriceZone;
  zones?: PriceZone[];
}

export function registerFVGOverlay(): void {
  const template: OverlayTemplate<FVGExtendData> = {
    name: 'fvgZone',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<FVGExtendData>): OverlayFigure[] => {
      const showZones = useTechnicalStore.getState().showSMCZones;
      if (!showZones) return [];

      const { overlay, chart, bounding } = params;
      const dataList = chart.getDataList();
      const extendData = overlay.extendData;

      const figures: OverlayFigure[] = [];

      if (extendData?.zone) {
        figures.push(...renderSingleZoneFigures(params, extendData.zone, dataList, bounding.width));
      } else if (extendData?.zones && extendData.zones.length > 0) {
        for (const z of extendData.zones) {
          if (z.type === 'FVG') {
            figures.push(...renderSingleZoneFigures(params, z, dataList, bounding.width));
          }
        }
      } else {
        // دریافت از استور مرکزی
        const activeZones = useTechnicalStore.getState().candleEdgeData?.activeZones;
        if (activeZones) {
          for (const z of activeZones) {
            if (z.type === 'FVG') {
              figures.push(...renderSingleZoneFigures(params, z, dataList, bounding.width));
            }
          }
        }
      }

      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ۲. اورلی اردر بلاک (Order Block Zone)
// ----------------------------------------------------------------------------

export interface OrderBlockExtendData {
  zone?: PriceZone;
  zones?: PriceZone[];
}

export function registerOrderBlockOverlay(): void {
  const template: OverlayTemplate<OrderBlockExtendData> = {
    name: 'orderBlockZone',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<OrderBlockExtendData>): OverlayFigure[] => {
      const showZones = useTechnicalStore.getState().showSMCZones;
      if (!showZones) return [];

      const { overlay, chart, bounding } = params;
      const dataList = chart.getDataList();
      const extendData = overlay.extendData;

      const figures: OverlayFigure[] = [];

      if (extendData?.zone) {
        figures.push(...renderSingleZoneFigures(params, extendData.zone, dataList, bounding.width));
      } else if (extendData?.zones && extendData.zones.length > 0) {
        for (const z of extendData.zones) {
          if (z.type === 'ORDER_BLOCK') {
            figures.push(...renderSingleZoneFigures(params, z, dataList, bounding.width));
          }
        }
      } else {
        // دریافت از استور مرکزی
        const activeZones = useTechnicalStore.getState().candleEdgeData?.activeZones;
        if (activeZones) {
          for (const z of activeZones) {
            if (z.type === 'ORDER_BLOCK') {
              figures.push(...renderSingleZoneFigures(params, z, dataList, bounding.width));
            }
          }
        }
      }

      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ۳. اورلی تجمیعی زون‌های SMC (SMC Zones Composite)
// ----------------------------------------------------------------------------

export interface SMCZonesExtendData {
  zones?: PriceZone[];
}

export function registerAllSMCZonesOverlay(): void {
  const template: OverlayTemplate<SMCZonesExtendData> = {
    name: 'smcZones',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<SMCZonesExtendData>): OverlayFigure[] => {
      const showZones = useTechnicalStore.getState().showSMCZones;
      if (!showZones) return [];

      const { overlay, chart, bounding } = params;
      const dataList = chart.getDataList();
      const zonesToRender =
        overlay.extendData?.zones ??
        useTechnicalStore.getState().candleEdgeData?.activeZones ??
        [];

      const figures: OverlayFigure[] = [];
      for (const zone of zonesToRender) {
        figures.push(...renderSingleZoneFigures(params, zone, dataList, bounding.width));
      }
      return figures;
    },
  };

  registerOverlay(template);
}

// ----------------------------------------------------------------------------
// ثبت کلیه اورلی‌های SMC
// ----------------------------------------------------------------------------

export function registerSMCOverlays(): void {
  registerFVGOverlay();
  registerOrderBlockOverlay();
  registerAllSMCZonesOverlay();
}
