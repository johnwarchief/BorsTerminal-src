/**
 * frontend-v2/src/features/technical/overlays/patternOverlay.ts
 *
 * رسمِ کم‌سر‌و‌صدای الگوهای کلاسیک روی چارت:
 * - حداکثر شش شکلِ منتخب (selectFeaturedPatterns) و یک برچسب برای هر الگو
 * - برچسب فارسی با ارقام فارسی؛ درصدِ تشکیل فقط وقتی احتمال واقعاً موجود است
 * - بدون انیمیشن، پالس یا افکت اضافه
 *
 * تشخیص و آمار از `model/patterns/registry` می‌آید؛ این فایل فقط رسم می‌کند.
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayCreateFiguresCallbackParams,
  OverlayFigure,
  OverlayTemplate,
} from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import { selectFeaturedPatterns } from '../model/patterns/registry';
import type { ChartPattern } from '../model/patterns/types';

const KIND_FA: Record<string, string> = {
  FLAG_BULL: 'پرچم صعودی', FLAG_BEAR: 'پرچم نزولی', PENNANT: 'پنانت',
  TRIANGLE_ASC: 'مثلث صعودی', TRIANGLE_DESC: 'مثلث نزولی', TRIANGLE_SYM: 'مثلث متقارن',
  RECTANGLE: 'مستطیل', WEDGE_RISING: 'گُوهٔ صعودی', WEDGE_FALLING: 'گُوهٔ نزولی',
  HEAD_SHOULDERS: 'سر و شانه', INVERSE_HEAD_SHOULDERS: 'سر و شانهٔ معکوس',
  TRIPLE_TOP: 'سه‌قلوی سقف', TRIPLE_BOTTOM: 'سه‌قلوی کف',
  DOUBLE_TOP: 'سقف دوقلو', DOUBLE_BOTTOM: 'کف دوقلو',
};

const KIND_COLOR: Record<string, string> = {
  bullish: '#4f8f72', bearish: '#b45a6a', neutral: '#a89a6a',
};

function px(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  index: number,
  price: number,
): { x: number; y: number } {
  const raw = params.chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}

export function patternFigures(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  patterns: readonly ChartPattern[],
): OverlayFigure[] {
  const figures: OverlayFigure[] = [];
  const featured = selectFeaturedPatterns(patterns, 6);
  for (const pattern of featured) {
    const color = KIND_COLOR[pattern.direction] ?? KIND_COLOR.neutral;
    const forming = pattern.status === 'forming';
    figures.push({
      type: 'line',
      attrs: {
        coordinates: [
          px(params, pattern.upper.from.index, pattern.upper.from.price),
          px(params, pattern.upper.to.index, pattern.upper.to.price),
        ],
      },
      styles: { color, size: forming ? 1.75 : 1.1, style: 'solid' },
    });
    figures.push({
      type: 'line',
      attrs: {
        coordinates: [
          px(params, pattern.lower.from.index, pattern.lower.from.price),
          px(params, pattern.lower.to.index, pattern.lower.to.price),
        ],
      },
      styles: { color, size: forming ? 1.75 : 1.1, style: 'solid' },
    });
    if (pattern.neckline) {
      figures.push({
        type: 'line',
        attrs: {
          coordinates: [
            px(params, pattern.neckline.from.index, pattern.neckline.from.price),
            px(params, pattern.neckline.to.index, pattern.neckline.to.price),
          ],
        },
        styles: { color: '#8a8580', size: 1.1, style: 'dashed', dashedValue: [4, 3] },
      });
    }
    const label = KIND_FA[pattern.kind] ?? pattern.kind;
    // R-PAT-3: درصد فقط وقتی احتمالِ تشکیل واقعاً موجود است.
    const pct = pattern.formation?.probability;
    const text = forming
      ? pct == null ? `${label} — در حال تشکیل` : `${label} — تشکیل ${toFaDigits(Math.round(pct))}٪`
      : label;
    const anchor = px(params, pattern.anchor.index, pattern.anchor.price);
    figures.push({
      type: 'text',
      attrs: { x: anchor.x + 6, y: anchor.y - 8, text, align: 'left', baseline: 'bottom' },
      styles: { color, size: 10, family: 'inherit' },
    });
  }
  return figures;
}

export function registerPatternOverlay(): void {
  const template: OverlayTemplate = {
    name: 'ClassicPatterns',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params): OverlayFigure[] =>
      patternFigures(params, useTechnicalStore.getState().detectedPatterns),
  };
  try {
    registerOverlay(template);
  } catch {
    // idempotent
  }
}
