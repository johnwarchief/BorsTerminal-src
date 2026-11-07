/**
 * frontend-v2/src/features/technical/overlays/patternOverlay.ts
 *
 * رسمِ کم‌سر‌و‌صدای الگوهای کلاسیک روی چارت:
 * - حداکثر شش شکلِ منتخب (selectFeaturedPatterns) و یک برچسب برای هر الگو
 * - برچسب فارسی با ارقام فارسی؛ درصدِ تشکیل فقط وقتی احتمال واقعاً موجود است
 * - بدون انیمیشن، پالس یا افکت اضافه
 * - خطِ صفرطول رسم نمی‌شود؛ خط گردنی که با مرزِ بالا/پایین یکسان است دوباره کشیده نمی‌شود
 * - رنگِ برچسب تابعِ تم است تا روی پنلِ روشن و تیره کنتراستِ ≥ ۴٫۵:۱ داشته باشد
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
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import { PATTERN_CONFIG } from '../model/patterns/config';
import { KIND_FA, showPercent } from '../model/patterns/labels';
import { selectFeaturedPatterns } from '../model/patterns/registry';
import type { BoundaryLine, ChartPattern } from '../model/patterns/types';

const KIND_COLOR: Record<string, string> = {
  bullish: '#4f8f72', bearish: '#b45a6a', neutral: '#a89a6a',
};

/**
 * پالتِ برچسب جدا از پالتِ خط است: متن باید کنتراستِ ≥ ۴٫۵:۱ با پس‌زمینهٔ پنل
 * داشته باشد. رنگ‌های KIND_COLOR روی پنلِ روشن فقط ۲٫۶۶–۳٫۷۱:۱ می‌دهند،
 * بنابراین نسخهٔ تیره‌تر (تمِ روشن) و روشن‌تر (تمِ تیره) اینجا آمده است.
 */
const LABEL_COLOR_DARK: Record<string, string> = {
  bullish: '#7fc4a0', bearish: '#e79aa7', neutral: '#d8c98d',
};
const LABEL_COLOR_LIGHT: Record<string, string> = {
  bullish: '#2f6b52', bearish: '#8f3f4f', neutral: '#6f6132',
};

/** همان روشِ smcOverlays: تمِ روشن یعنی warm/cool؛ پیش‌فرضِ امن = تیره. */
function isLightTheme(): boolean {
  try {
    const theme = useUiStore.getState().theme;
    return theme === 'warm' || theme === 'cool';
  } catch {
    return false;
  }
}

function samePoint(a: { index: number; price: number }, b: { index: number; price: number }): boolean {
  return a.index === b.index && a.price === b.price;
}

function sameLine(a: BoundaryLine, b: BoundaryLine): boolean {
  return samePoint(a.from, b.from) && samePoint(a.to, b.to);
}

function px(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  index: number,
  price: number,
): { x: number; y: number } {
  const raw = params.chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}

/**
 * جای برچسب: اگر لنگر به لبهٔ راستِ پنل نزدیک باشد، متن به سمت چپ باز می‌شود
 * تا برش نخورد. عرض تقریبی هر کاراکتر در ۱۱px حدود ۷px است؛ حاشیهٔ امن ۸px.
 */
function labelPlacement(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  anchor: { x: number; y: number },
  text: string,
): { x: number; y: number; align: 'left' | 'right' } {
  const width = params.bounding?.width ?? 0;
  const approxWidth = text.length * 7 + 8;
  const flip = width > 0 && anchor.x + approxWidth > width;
  return flip
    ? { x: anchor.x - 6, y: anchor.y - 8, align: 'right' }
    : { x: anchor.x + 6, y: anchor.y - 8, align: 'left' };
}

export function patternFigures(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  patterns: readonly ChartPattern[],
): OverlayFigure[] {
  const figures: OverlayFigure[] = [];
  // مالکیت واحد W/M: رسم/برچسب DOUBLE_TOP و DOUBLE_BOTTOM فقط از موتور دوقلو
  // (`DoubleTap3D`/`PatternSpotlightLayer`) می‌آید؛ این اورلی کلاسیک هرگز آن‌ها را دوباره نمی‌کشد.
  const classicOnly = patterns.filter(
    (pattern) => pattern.kind !== 'DOUBLE_TOP' && pattern.kind !== 'DOUBLE_BOTTOM',
  );
  const featured = selectFeaturedPatterns(classicOnly, 6);
  const labelPalette = isLightTheme() ? LABEL_COLOR_LIGHT : LABEL_COLOR_DARK;
  const pushBoundary = (line: BoundaryLine, styles: Record<string, unknown>) => {
    // خطِ صفرطول (from === to در اندیس و قیمت) هیچ چیزِ مفیدی رسم نمی‌کند:
    // سقفِ سر و شانه و هر دو مرزِ الگوهای دوقلویی چنین‌اند.
    if (samePoint(line.from, line.to)) return;
    figures.push({
      type: 'line',
      attrs: {
        coordinates: [
          px(params, line.from.index, line.from.price),
          px(params, line.to.index, line.to.price),
        ],
      },
      styles,
    });
  };
  for (const pattern of featured) {
    const color = KIND_COLOR[pattern.direction] ?? KIND_COLOR.neutral;
    const labelColor = labelPalette[pattern.direction] ?? labelPalette.neutral;
    const forming = pattern.status === 'forming';
    const boundaryStyle = { color, size: forming ? 1.75 : 1.1, style: 'solid' };
    pushBoundary(pattern.upper, boundaryStyle);
    pushBoundary(pattern.lower, boundaryStyle);
    if (
      pattern.neckline
      && !sameLine(pattern.neckline, pattern.upper)
      && !sameLine(pattern.neckline, pattern.lower)
    ) {
      pushBoundary(pattern.neckline, {
        color: '#8a8580', size: 1.1, style: 'dashed', dashedValue: [4, 3],
      });
    }
    const label = KIND_FA[pattern.kind] ?? pattern.kind;
    // R-PB-9: شکلِ الگو مثل W/M دوقلو با یک خطِ پیوسته از پیوت‌ها کشیده می‌شود،
    // نه فقط دو مرزِ موازی. نقاطِ تکراری حذف و به ترتیبِ زمان مرتب می‌شوند؛
    // لنگر اگر در فهرست نباشد به انتها اضافه می‌شود.
    const pathPoints = [...pattern.points]
      .sort((a, b) => a.index - b.index)
      .filter((p, i, all) => i === 0 || p.index !== all[i - 1]!.index || p.price !== all[i - 1]!.price);
    const lastPoint = pattern.points[pattern.points.length - 1];
    if (lastPoint && !pathPoints.some((p) => p.index === lastPoint.index && p.price === lastPoint.price)) {
      pathPoints.push(lastPoint);
    }
    if (pathPoints.length >= 2) {
      figures.push({
        type: 'line',
        attrs: { coordinates: pathPoints.map((p) => px(params, p.index, p.price)) },
        styles: { color, size: forming ? 2.5 : 1.8, style: 'solid' },
      });
      // نقطه‌های پیوت شکل را می‌خوانند (مثلِ W/M دوقلو): بدونِ نشانگر، خطِ نازک
      // روی کندل‌ها گم می‌شود.
      for (const point of pathPoints) {
        const screen = px(params, point.index, point.price);
        figures.push({
          type: 'circle',
          attrs: { x: screen.x, y: screen.y, r: forming ? 3 : 2.5 },
          styles: { style: 'fill', color, borderColor: color, borderSize: 0 },
        });
      }
    }
    // R-PAT-3: درصد فقط وقتی احتمالِ تشکیل واقعاً موجود است.
    // R-PAT-24: احتمال نسبت ۰..۱ است؛ نمایش درصدی یعنی ×۱۰۰.
    const pct = showPercent(pattern.formation, PATTERN_CONFIG.formationMinResolved);
    const text = forming
      ? pct == null ? `${label} — در حال تشکیل` : `${label} — تشکیل ${toFaDigits(Math.round(pct * 100))}٪`
      : label;
    const anchor = px(params, pattern.anchor.index, pattern.anchor.price);
    const placement = labelPlacement(params, anchor, text);
    figures.push({
      type: 'text',
      attrs: {
        x: placement.x, y: placement.y, text, align: placement.align, baseline: 'bottom',
      },
      styles: { color: labelColor, size: 11, family: 'Vazirmatn, sans-serif' },
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
    createPointFigures: (params): OverlayFigure[] => {
      const state = useTechnicalStore.getState();
      const visible = state.showTier2Patterns
        ? state.detectedPatterns
        : state.detectedPatterns.filter((pattern) => pattern.tier !== 2);
      return patternFigures(params, visible);
    },
  };
  try {
    registerOverlay(template);
  } catch {
    // idempotent
  }
}
