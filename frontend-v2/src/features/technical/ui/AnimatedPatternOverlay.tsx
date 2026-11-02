/**
 * frontend-v2/src/features/technical/ui/AnimatedPatternOverlay.tsx
 *
 * لایه رندر انیمیشن‌های پیشرفته وب بر پایه استاندارد /web-animation-design برای الگوهای کلاسیک:
 * - انیمیشن خط‌گردن نئونی درخشان (Pulsing Glowing Neckline)
 * - حلقه‌های پالس هاله‌ای در سقف‌ها و کف‌ها (Pulsing Halo Rings)
 * - استروک روان و پویا برای پایه‌های W و M (Stroke Dash Flow)
 * - شناوری ملایم بج امتیاز الگو با شتاب‌دهی سخت‌افزاری GPU و احترام به prefers-reduced-motion
 */

import React, { useMemo, useState, useEffect } from 'react';
import type { Chart } from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import type { DoubleTapPattern } from '../model/types';

import { useUiStore } from '@shared/stores/uiStore';

export interface AnimatedPatternOverlayProps {
  chart: Chart | null;
  patterns: DoubleTapPattern[];
  active?: boolean;
  isLight?: boolean;
}

export const AnimatedPatternOverlay: React.FC<AnimatedPatternOverlayProps> = ({
  chart,
  patterns,
  active = true,
  isLight,
}) => {
  const currentTheme = useUiStore((s) => s.theme);
  const effectiveIsLight = isLight ?? (currentTheme === 'warm' || currentTheme === 'cool');
  const [viewportTick, setViewportTick] = useState(0);

  // اشتراک رویدادهای زوم، اسکرول، تغییر بازه و درگ پنل چارت KLineCharts
  useEffect(() => {
    if (!chart) return;
    const handleUpdate = () => {
      setViewportTick((t) => (t + 1) % 1_000_000);
    };

    try {
      chart.subscribeAction('onZoom', handleUpdate);
      chart.subscribeAction('onScroll', handleUpdate);
      chart.subscribeAction('onVisibleRangeChange', handleUpdate);
      chart.subscribeAction('onPaneDrag', handleUpdate);
    } catch {
      // ایمنی در زمان تست
    }

    return () => {
      try {
        chart.unsubscribeAction('onZoom', handleUpdate);
        chart.unsubscribeAction('onScroll', handleUpdate);
        chart.unsubscribeAction('onVisibleRangeChange', handleUpdate);
        chart.unsubscribeAction('onPaneDrag', handleUpdate);
      } catch {
        // ایمنی
      }
    };
  }, [chart]);

  // استخراج مختصات ۵ نقطه‌ای الگوهای فعال (P0 -> P1 -> Neckline -> P2 -> P3)
  const renderedItems = useMemo(() => {
    if (!active || !chart || patterns.length === 0) return [];

    return patterns.slice(-3).map((pat) => {
      try {
        const pt1 = chart.convertToPixel({ dataIndex: pat.peak1.index, value: pat.peak1.price });
        const ptNeck = chart.convertToPixel({ dataIndex: pat.neckline.index, value: pat.neckline.price });
        const pt2 = chart.convertToPixel({ dataIndex: pat.peak2.index, value: pat.peak2.price });

        const p1Coord = Array.isArray(pt1) ? pt1[0] : pt1;
        const neckCoord = Array.isArray(ptNeck) ? ptNeck[0] : ptNeck;
        const p2Coord = Array.isArray(pt2) ? pt2[0] : pt2;

        if (!p1Coord || !neckCoord || !p2Coord) return null;

        const isDoubleTop = pat.type === 'DOUBLE_TOP';
        const color = effectiveIsLight
          ? (isDoubleTop ? '#be123c' : '#0284c7')
          : (isDoubleTop ? '#ff2079' : '#00f0ff');
        const necklineColor = effectiveIsLight ? '#7c3aed' : '#bc13fe';
        const label = isDoubleTop ? 'الگوی M (سقف دوقلو)' : 'الگوی W (کف دوقلو)';

        // محاسبه مختصات نقطه آغاز حرکت (P0 یا T0)
        let p0Coord: { x: number; y: number } = { x: (p1Coord.x ?? 0) - 35, y: neckCoord.y ?? 0 };
        if (pat.origin) {
          try {
            const raw0 = chart.convertToPixel({ dataIndex: pat.origin.index, value: pat.origin.price });
            const c0 = Array.isArray(raw0) ? raw0[0] : raw0;
            if (c0 && typeof c0.x === 'number') {
              p0Coord = { x: c0.x, y: c0.y ?? 0 };
            }
          } catch {
            // استفاده از پیش‌فرض
          }
        }

        // محاسبه مختصات نقطه بازآزمایی و شکست (P3 یا T3)
        let p3Coord: { x: number; y: number } = { x: (p2Coord.x ?? 0) + 35, y: neckCoord.y ?? 0 };
        if (pat.retest) {
          try {
            const raw3 = chart.convertToPixel({ dataIndex: pat.retest.index, value: pat.retest.price });
            const c3 = Array.isArray(raw3) ? raw3[0] : raw3;
            if (c3 && typeof c3.x === 'number') {
              p3Coord = { x: c3.x, y: c3.y ?? 0 };
            }
          } catch {
            // استفاده از پیش‌فرض
          }
        }

        return {
          id: pat.id,
          score: pat.score,
          color,
          necklineColor,
          isDoubleTop,
          label,
          p0: p0Coord,
          p1: { x: p1Coord.x ?? 0, y: p1Coord.y ?? 0 },
          neck: { x: neckCoord.x ?? 0, y: neckCoord.y ?? 0 },
          p2: { x: p2Coord.x ?? 0, y: p2Coord.y ?? 0 },
          p3: p3Coord,
        };
      } catch {
        return null;
      }
    }).filter(Boolean);
  }, [chart, patterns, active, viewportTick, effectiveIsLight]);

  if (!active || !chart || patterns.length === 0 || renderedItems.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="animated-pattern-overlay"
      className="absolute inset-0 pointer-events-none overflow-hidden z-15"
      style={{ transform: 'translateZ(0)', willChange: 'transform' }}
    >
      <svg className="w-full h-full" style={{ overflow: 'visible' }}>
        <defs>
          <filter id="neon-glow-magenta" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="neon-glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {renderedItems.map((item) => {
          if (!item) return null;
          const { id, color, necklineColor, isDoubleTop, label, score, p0, p1, neck, p2, p3 } = item;
          const neckStartX = Math.min(p0.x, p1.x);
          const neckEndX = Math.max(p2.x + 80, p3.x + 40, neck.x + 120);

          return (
            <g key={id} data-testid={`animated-pattern-${id}`}>
              {/* ۱. خط‌گردن پالس‌زن با افکت متناسب تم در سرتاسر الگوی W/M */}
              <line
                x1={neckStartX}
                y1={neck.y}
                x2={neckEndX}
                y2={neck.y}
                stroke={necklineColor}
                strokeWidth="2.5"
                strokeDasharray="6 3"
                className="double-tap-neckline-animated"
                style={{ willChange: 'filter, stroke-opacity' }}
              />

              {/* ۲. حلقه‌های هاله‌ای پالس در ۵ نقطه ساختاری الگو */}
              {[p0, p1, neck, p2, p3].map((pt, idx) => (
                <circle
                  key={idx}
                  cx={pt.x}
                  cy={pt.y}
                  r="5"
                  fill="none"
                  stroke={idx === 2 ? necklineColor : color}
                  strokeWidth="2"
                  className="double-tap-halo-animated"
                />
              ))}

              {/* ۳. ساقه‌های حرکتی ۵ نقطه‌ای کامل W و M با شارش خط‌چین */}
              <polyline
                points={`${p0.x},${p0.y} ${p1.x},${p1.y} ${neck.x},${neck.y} ${p2.x},${p2.y} ${p3.x},${p3.y}`}
                fill="none"
                stroke={color}
                strokeWidth="2.5"
                className="double-tap-leg-animated"
                style={{ opacity: 0.9 }}
              />

              {/* ۴. برچسب شناور نشان‌دهنده نام الگو و درصد اطمینان با کنتراست ارگونومیک */}
              <g
                transform={`translate(${p2.x}, ${p2.y - 18})`}
                className="double-tap-badge-animated"
              >
                <rect
                  x="-65"
                  y="-12"
                  width="130"
                  height="22"
                  rx="4"
                  fill={effectiveIsLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(24, 27, 34, 0.92)'}
                  stroke={effectiveIsLight ? (isDoubleTop ? '#fda4af' : '#7dd3fc') : color}
                  strokeWidth="1"
                />
                <text
                  x="0"
                  y="2"
                  fill={effectiveIsLight ? '#1e293b' : color}
                  fontSize="9.5"
                  fontWeight="bold"
                  fontFamily="Vazirmatn, sans-serif"
                  textAnchor="middle"
                  alignmentBaseline="middle"
                >
                  {label} · {toFaDigits(score)}٪
                </text>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
