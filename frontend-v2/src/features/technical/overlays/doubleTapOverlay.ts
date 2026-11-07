/**
 * frontend-v2/src/features/technical/overlays/doubleTapOverlay.ts
 *
 * رسمِ تمیزِ الگوی دوقلو W/M روی canvas:
 * - هندسهٔ ثابت و کم‌سر‌و‌صدا برای الگوهای تاریخی
 * - تارگت/حد ضرر فقط برای آخرین الگو
 * - هیچ نئون، هیچ پالس و هیچ برچسب درصدیِ گمراه‌کننده
 *
 * تشخیص و احتمال از `model/doubleTapEngine` می‌آید؛ این فایل فقط رسم می‌کند.
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
} from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import { getMarketCohort } from '../model/doubletapCohort';
import {
  calculateAtr,
  detectDoubleTapPatterns,
  estimateFormation,
  selectLastFormingPattern,
  DEFAULT_PRECISION_PARAMS,
  DEFAULT_SOURCE_PARAMS,
} from '../model/doubleTapEngine';
import type { DoubleTapPattern } from '../model/types';

const INK = {
  top: '#b45a6a',
  bottom: '#4f8f72',
  neck: '#8a8580',
  target: '#c9a45c',
  loss: '#a05a4a',
  text: '#e8e3da',
  chipBg: 'rgba(24, 27, 34, 0.92)',
  chipBorder: 'rgba(232, 227, 218, 0.14)',
} as const;

function px(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  index: number,
  price: number
): { x: number; y: number } {
  const raw = params.chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}


function chipStyle(bg: string, color: string, size = 10) {
  return {
    color,
    backgroundColor: bg,
    size,
    weight: 'bold' as const,
    family: 'Vazirmatn, sans-serif',
    paddingLeft: 6,
    paddingRight: 6,
    paddingTop: 3,
    paddingBottom: 3,
    borderRadius: 3,
  };
}

function drawPattern(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  pattern: DoubleTapPattern,
  isLast: boolean
): OverlayFigure[] {
  const isTop = pattern.type === 'DOUBLE_TOP';
  const color = isTop ? INK.top : INK.bottom;
  const origin = pattern.origin ?? pattern.peak1;
  const p0 = px(params, origin.index, origin.price);
  const p1 = px(params, pattern.peak1.index, pattern.peak1.price);
  const neck = px(params, pattern.neckline.index, pattern.neckline.price);
  const p2 = px(params, pattern.peak2.index, pattern.peak2.price);
  const retest = pattern.retest ?? pattern.peak2;
  const p3 = px(params, retest.index, retest.price);

  const figures: OverlayFigure[] = [];

  figures.push({
    type: 'line',
    attrs: { coordinates: [p0, p1, neck, p2, p3] },
    styles: { color, size: isLast ? 2 : 1.25, style: 'solid' },
  });

  const neckStartX = Math.min(p0.x, p1.x);
  const neckEndX = Math.max(p2.x + 80, p3.x + 40, neck.x + 120);
  figures.push({
    type: 'line',
    attrs: { coordinates: [{ x: neckStartX, y: neck.y }, { x: neckEndX, y: neck.y }] },
    styles: {
      color: INK.neck,
      size: isLast ? 1.5 : 1,
      style: 'dashed',
      dashedValue: [4, 3],
      // klinecharts line styles do not support opacity directly; muted via color for history.
      ...(isLast ? {} : { color: 'rgba(138, 133, 128, 0.45)' }),
    },
  });

  if (!isLast) return figures;

  // تارگت‌ها و حد ضرر فقط برای آخرین الگو.
  const yTp1 = px(params, pattern.peak2.index, pattern.target1).y;
  const yTp2 = px(params, pattern.peak2.index, pattern.target2).y;
  const ySl = px(params, pattern.peak2.index, pattern.stopLoss).y;
  const xEnd = neckEndX;
  const targets: Array<{ y: number; label: string; color: string; style: 'solid' | 'dashed' | 'dotted' }> = [
    { y: yTp1, label: `TP1 ${toFaDigits(Math.round(pattern.target1))}`, color: INK.target, style: 'solid' },
    { y: yTp2, label: `TP2 ${toFaDigits(Math.round(pattern.target2))}`, color: INK.target, style: 'dashed' },
    { y: ySl, label: `SL ${toFaDigits(Math.round(pattern.stopLoss))}`, color: INK.loss, style: 'dotted' },
  ];

  targets.forEach((target, index) => {
    figures.push({
      type: 'line',
      attrs: {
        coordinates: [
          { x: p2.x, y: target.y },
          { x: xEnd - index * 62, y: target.y },
        ],
      },
      styles: { color: target.color, size: 1.25, style: target.style, dashedValue: [5, 3] },
    });
    figures.push({
      type: 'text',
      attrs: { x: xEnd - index * 62, y: target.y - 6, text: target.label, align: 'right', baseline: 'bottom' },
      styles: chipStyle(INK.chipBg, target.color, 9),
    });
  });

  return figures;
}

export function registerDoubleTapStoryOverlay(): void {
  const template: OverlayTemplate = {
    name: 'DoubleTap3D',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      if (dataList.length < 20) return [];

      const state = useTechnicalStore.getState();
      const stored = state.indicatorParams.DoubleTap3D ?? {};
      const base = state.doubleTapProfile === 'source' ? DEFAULT_SOURCE_PARAMS : DEFAULT_PRECISION_PARAMS;
      const engineParams = { ...base, ...stored };
      const patterns = detectDoubleTapPatterns(dataList, engineParams);

      const lastForming = selectLastFormingPattern(patterns);
      if (lastForming) {
        const atr = calculateAtr(dataList, engineParams.atrPeriod);
        const horizon = Number(stored.formationHorizon ?? 10);
        const estimate = estimateFormation(
          patterns,
          dataList,
          atr[lastForming.peak2.index] ?? atr[atr.length - 1] ?? 1,
          lastForming.id,
          horizon,
          getMarketCohort(state.timeframe, lastForming.quality) ?? undefined
        );
        if (estimate) lastForming.formation = estimate;
      }

      const prev = state.detectedDoubleTapPatterns;
      const changed =
        prev.length !== patterns.length ||
        prev.some(
          (p, i) =>
            p.id !== patterns[i]?.id ||
            p.status !== patterns[i]?.status ||
            p.quality !== patterns[i]?.quality ||
            p.formation?.probability !== patterns[i]?.formation?.probability ||
            p.formation?.resolved !== patterns[i]?.formation?.resolved
        );
      if (changed) useTechnicalStore.getState().setDetectedDoubleTapPatterns(patterns);

      const cap = Math.max(1, state.maxDrawnPatterns);
      const drawn = patterns.slice(-cap);
      const lastId = drawn[drawn.length - 1]?.id;
      const figures: OverlayFigure[] = [];
      for (const pattern of drawn) {
        figures.push(...drawPattern(params, pattern, pattern.id === lastId));
      }
      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // Idempotent
  }
}
