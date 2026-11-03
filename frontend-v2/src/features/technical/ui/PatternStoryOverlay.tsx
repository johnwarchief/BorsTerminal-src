/**
 * frontend-v2/src/features/technical/ui/PatternStoryOverlay.tsx
 *
 * لایهٔ توضیحی الگوی دوقلو W/M:
 * - فقط آخرین الگو را نشان می‌دهد (تاریخی‌ها روی canvas کم‌رنگ‌اند)
 * - یک‌بار مسیر تشکیل را می‌کشد، بعد خط گردن/تارگت و در پایان چیپ احتمال
 * - بدون نئون، بدون پالس بی‌پایان، با احترام به prefers-reduced-motion
 */

import React, { useEffect, useMemo, useState } from 'react';
import type { Chart } from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import type { DoubleTapPattern, FormationConfidence } from '../model/types';
import { useUiStore } from '@shared/stores/uiStore';

export interface PatternStoryOverlayProps {
  chart: Chart | null;
  patterns: DoubleTapPattern[];
  active?: boolean;
  isLight?: boolean;
}

const COLORS = {
  top: '#b45a6a',
  bottom: '#4f8f72',
  neck: '#8a8580',
  target: '#c9a45c',
  loss: '#a05a4a',
  chipBg: 'rgba(21, 24, 28, 0.94)',
  chipBorder: 'rgba(232, 227, 218, 0.16)',
};

function confidenceFa(confidence: FormationConfidence | undefined): string {
  if (confidence === 'low') return 'اطمینان کم';
  if (confidence === 'medium') return 'اطمینان متوسط';
  if (confidence === 'high') return 'اطمینان بالا';
  return 'نمونهٔ کافی نیست';
}

function toPixel(
  chart: Chart,
  index: number,
  price: number
): { x: number; y: number } {
  const raw = chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}

export const PatternStoryOverlay: React.FC<PatternStoryOverlayProps> = ({
  chart,
  patterns,
  active = true,
  isLight,
}) => {
  const theme = useUiStore((s) => s.theme);
  const effectiveIsLight = isLight ?? (theme === 'warm' || theme === 'cool');
  const [viewportTick, setViewportTick] = useState(0);

  useEffect(() => {
    if (!chart) return;
    const bump = () => setViewportTick((t) => (t + 1) % 1_000_000);
    try {
      chart.subscribeAction('onZoom', bump);
      chart.subscribeAction('onScroll', bump);
      chart.subscribeAction('onVisibleRangeChange', bump);
      chart.subscribeAction('onPaneDrag', bump);
    } catch {
      // محیط آزمون
    }
    return () => {
      try {
        chart.unsubscribeAction('onZoom', bump);
        chart.unsubscribeAction('onScroll', bump);
        chart.unsubscribeAction('onVisibleRangeChange', bump);
        chart.unsubscribeAction('onPaneDrag', bump);
      } catch {
        // محیط آزمون
      }
    };
  }, [chart]);

  const last = useMemo(() => {
    if (!active || !chart || patterns.length === 0) return null;
    const sorted = [...patterns].sort((a, b) => a.peak2.index - b.peak2.index);
    const pattern = sorted[sorted.length - 1];
    try {
      const origin = pattern.origin ?? pattern.peak1;
      const p0 = toPixel(chart, origin.index, origin.price);
      const p1 = toPixel(chart, pattern.peak1.index, pattern.peak1.price);
      const neck = toPixel(chart, pattern.neckline.index, pattern.neckline.price);
      const p2 = toPixel(chart, pattern.peak2.index, pattern.peak2.price);
      const retest = pattern.retest ?? pattern.peak2;
      const p3 = toPixel(chart, retest.index, retest.price);
      if (![p0, p1, neck, p2, p3].every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))) return null;
      return { pattern, p0, p1, neck, p2, p3 };
    } catch {
      return null;
    }
  }, [chart, patterns, active, viewportTick, effectiveIsLight]);

  if (!active || !chart || !last) return null;

  const { pattern, p0, p1, neck, p2, p3 } = last;
  const isTop = pattern.type === 'DOUBLE_TOP';
  const color = isTop ? COLORS.top : COLORS.bottom;
  const formation = pattern.formation;
  const probability =
    formation?.probability != null ? Math.round(formation.probability * 100) : null;
  const statusLabel =
    pattern.status === 'forming'
      ? probability != null
        ? `در حال تشکیل · احتمال ${toFaDigits(probability)}٪`
        : 'در حال تشکیل · نمونهٔ کافی نیست'
      : pattern.status === 'invalidated'
        ? 'الگو باطل شد'
        : 'الگو تأیید شد';
  const sampleLabel =
    formation && formation.resolved > 0
      ? `${
          formation.method === 'market-cohort' ? 'هم‌گروه بازار' : 'همان نماد'
        } · ${toFaDigits(formation.resolved)} نمونه · ${confidenceFa(formation.confidence)}`
      : 'نمونهٔ تاریخی کافی نیست';
  const size = chart.getSize?.() ?? { width: 800, height: 600 };
  const xs = [p0.x, p1.x, neck.x, p2.x, p3.x];
  const ys = [p0.y, p1.y, neck.y, p2.y, p3.y];
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const chipWidth = 224;
  const chipHeight = 66;
  const chipX = Math.max(8, Math.min(minX, size.width - chipWidth - 8));
  const above = minY - chipHeight - 12;
  const chipY = above >= 8 ? above : Math.min(size.height - chipHeight - 8, maxY + 12);
  const targetLabel = `هدف TP1 ${toFaDigits(Math.round(pattern.target1))} · TP2 ${toFaDigits(Math.round(pattern.target2))}`;

  return (
    <div
      data-testid="pattern-story-overlay"
      className="absolute inset-0 pointer-events-none overflow-hidden z-15"
      style={{ transform: 'translateZ(0)', willChange: 'transform' }}
    >
      <style>{`
        @keyframes dt-story-draw {
          from { stroke-dashoffset: 1; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes dt-story-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes dt-story-chip {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .dt-story-path {
          stroke-dasharray: 1;
          stroke-dashoffset: 1;
          animation: dt-story-draw 700ms cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        .dt-story-neck {
          animation: dt-story-fade 250ms cubic-bezier(0.22, 1, 0.36, 1) 700ms both;
        }
        .dt-story-target {
          animation: dt-story-fade 250ms cubic-bezier(0.22, 1, 0.36, 1) 780ms both;
        }
        .dt-story-chip {
          animation: dt-story-chip 150ms cubic-bezier(0.22, 1, 0.36, 1) 950ms both;
          transform-box: fill-box;
        }
        @media (prefers-reduced-motion: reduce) {
          .dt-story-path, .dt-story-neck, .dt-story-target, .dt-story-chip {
            animation: none !important;
            stroke-dashoffset: 0 !important;
            opacity: 1 !important;
          }
        }
      `}</style>
      <svg className="w-full h-full" style={{ overflow: 'visible' }} direction="rtl">
        <polyline
          className="dt-story-path"
          pathLength={1}
          points={`${p0.x},${p0.y} ${p1.x},${p1.y} ${neck.x},${neck.y} ${p2.x},${p2.y} ${p3.x},${p3.y}`}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <line
          className="dt-story-neck"
          x1={Math.min(p0.x, p1.x)}
          y1={neck.y}
          x2={Math.max(p2.x + 60, neck.x + 100)}
          y2={neck.y}
          stroke={COLORS.neck}
          strokeWidth="1.25"
          strokeDasharray="4 3"
        />
        <g className="dt-story-target">
          <circle cx={p2.x} cy={p2.y} r="3.5" fill={color} />
          <circle cx={p1.x} cy={p1.y} r="3" fill={color} />
        </g>
        <g className="dt-story-chip">
          <rect
            x={chipX}
            y={chipY}
            width={chipWidth}
            height={chipHeight}
            rx="6"
            fill={effectiveIsLight ? 'rgba(255,255,255,0.96)' : COLORS.chipBg}
            stroke={effectiveIsLight ? 'rgba(20,24,30,0.18)' : COLORS.chipBorder}
            strokeWidth="1"
          />
          <text
            x={chipX + chipWidth / 2}
            y={chipY + 18}
            textAnchor="middle"
            fill={effectiveIsLight ? '#1e293b' : color}
            fontSize="11"
            fontWeight="600"
            fontFamily="Vazirmatn, sans-serif"
            direction="rtl"
          >
            {statusLabel}
          </text>
          <text
            x={chipX + chipWidth / 2}
            y={chipY + 35}
            textAnchor="middle"
            fill={effectiveIsLight ? '#5b6472' : '#a9a396'}
            fontSize="10"
            fontFamily="Vazirmatn, sans-serif"
            direction="rtl"
          >
            {sampleLabel}
          </text>
          <text
            x={chipX + chipWidth / 2}
            y={chipY + 52}
            textAnchor="middle"
            fill={effectiveIsLight ? '#76551f' : COLORS.target}
            fontSize="10"
            fontFamily="Vazirmatn, sans-serif"
            direction="rtl"
          >
            {targetLabel}
          </text>
        </g>
      </svg>
    </div>
  );
};
