/**
 * ui/PatternSpotlightLayer.tsx
 *
 * لایهٔ اسپات‌لایت ۳D الگوی اصلی (spec §3.2/§3.3):
 * - یک الگوی اصلی؛ گرامر p12: اسلب خط گردن/تریگر با وجه جلو/بالا/کنار، پاهای سایه‌دار،
 *   برچسب اصلی (نوع · وضعیت + گرید/امتیاز)، تگ BREAK و LONG/SHORT، ریل TP1/TP2/SL
 * - «۳D» فقط با آفست/اکستروژن SVG است؛ بدون WebGL و بدون glow/pulse
 * - انیمیشن یک‌باره در هر identity؛ prefers-reduced-motion → static
 *
 * داده از `SpotlightModel` می‌آید؛ این فایل هیچ تشخیصی انجام نمی‌دهد.
 */
import React, { useEffect, useMemo, useState } from 'react';
import type { Chart } from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import type { SpotlightModel, SpotlightStatus } from '../model/spotlight/types';
import './patternSpotlight.css';

export interface PatternSpotlightLayerProps {
  chart: Chart | null;
  primary: SpotlightModel | null;
  isLight?: boolean;
}

const COLORS = {
  top: '#FF2079',
  bottom: '#00F0FF',
  win: '#39FF14',
  loss: '#FF5F1F',
  tp: '#FFF01F',
  neck: '#BC13FE',
} as const;

const DEPTH_BARS = 4;
const DEPTH_ATR = 0.6;
const SHADOW_ATR = 0.18;

const STATUS_EN: Record<SpotlightStatus, string> = {
  forming: 'FORMING',
  confirmed: 'CONFIRMED',
  active: 'ACTIVE',
  tp1_hit: 'TP1 HIT',
  tp2_hit: 'TP2 HIT',
  invalidated: 'INVALIDATED',
  failed: 'FAILED',
  timed_out: 'TIMED OUT',
};

const STATUS_FA: Record<SpotlightStatus, string> = {
  forming: 'در حال تشکیل',
  confirmed: 'تأییدشده',
  active: 'فعال',
  tp1_hit: 'TP1',
  tp2_hit: 'TP2',
  invalidated: 'باطل',
  failed: 'ناموفق',
  timed_out: 'منقضی',
};

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    try {
      return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    try {
      const query = window.matchMedia('(prefers-reduced-motion: reduce)');
      const update = () => setReduced(query.matches);
      update();
      query.addEventListener?.('change', update);
      return () => query.removeEventListener?.('change', update);
    } catch {
      return undefined;
    }
  }, []);
  return reduced;
}

interface ScreenPoint { x: number; y: number }

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function poly(points: ScreenPoint[]): string {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
}

function accentOf(model: SpotlightModel): string {
  if (model.status === 'tp2_hit') return COLORS.win;
  if (model.status === 'failed' || model.status === 'timed_out') return COLORS.loss;
  return model.direction === 'bullish' ? COLORS.bottom : COLORS.top;
}

export const PatternSpotlightLayer: React.FC<PatternSpotlightLayerProps> = ({
  chart,
  primary,
  isLight = false,
}) => {
  const reduced = usePrefersReducedMotion();
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

  const geometry = useMemo(() => {
    if (!chart || !primary) return null;
    try {
      const toPixel = (index: number, price: number): ScreenPoint => {
        const raw = chart.convertToPixel({ dataIndex: index, value: price });
        const first = Array.isArray(raw) ? raw[0] : raw;
        return { x: first?.x ?? Number.NaN, y: first?.y ?? Number.NaN };
      };
      const dataLength = chart.getDataList?.().length ?? 0;
      const lastIndex = Math.max(
        dataLength - 1,
        primary.anchorIndex,
        primary.breakoutIndex ?? 0,
        primary.points[primary.points.length - 1]?.index ?? 0,
      );
      const startIndex = primary.source === 'doubleTap'
        ? (primary.points[0]?.index ?? primary.anchorIndex)
        : (primary.points[0]?.index ?? Math.max(0, primary.anchorIndex - 10));
      const endIndex = Math.max(lastIndex, primary.anchorIndex);
      const size = chart.getSize?.() ?? { width: 800, height: 600 };

      const pStart = toPixel(startIndex, primary.lower);
      const pEnd = toPixel(endIndex, primary.lower);
      const upperEnd = toPixel(endIndex, primary.upper);
      if (![pStart.x, pStart.y, pEnd.x, pEnd.y, upperEnd.y].every((v) => Number.isFinite(v))) {
        return null;
      }
      const yTop = Math.min(upperEnd.y, pEnd.y);
      const yBot = Math.max(upperEnd.y, pEnd.y);
      const atr = primary.atr
        ?? Math.max(0.001, Math.abs(primary.upper - primary.lower) || Math.abs(primary.target - primary.stop) / 3);
      const depthRef = toPixel(Math.min(endIndex + DEPTH_BARS, endIndex + DEPTH_BARS), primary.upper);
      const dx = clamp((depthRef.x - pEnd.x) || 6, 2, 20);
      const dy = clamp(toPixel(endIndex, primary.upper + DEPTH_ATR * atr).y - upperEnd.y, -26, -3);
      const shadowPx = clamp(
        toPixel(endIndex, primary.lower - SHADOW_ATR * atr).y - pEnd.y,
        -8,
        14,
      );

      const legSource = primary.legs && primary.legs.length >= 2 ? primary.legs : primary.points;
      const legs = legSource.map((p) => toPixel(p.index, p.price));
      const legsFinite = legs.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y));

      const neckY = primary.neckline != null ? toPixel(primary.anchorIndex, primary.neckline).y : null;
      const rails: Array<{ id: string; text: string; y: number; color: string; dash: string; testId: string }> = [];
      const railX = primary.breakoutIndex != null
        ? toPixel(primary.breakoutIndex, primary.lower).x
        : toPixel(primary.anchorIndex, primary.lower).x;
      if (primary.tp1 != null) {
        const y = toPixel(primary.anchorIndex, primary.tp1).y;
        if (Number.isFinite(y)) rails.push({ id: 'tp1', text: `TP1 ${toFaDigits(Math.round(primary.tp1))}`, y, color: COLORS.tp, dash: '6 3', testId: 'spotlight-tp1' });
      }
      if (primary.tp2 != null) {
        const y = toPixel(primary.anchorIndex, primary.tp2).y;
        if (Number.isFinite(y)) rails.push({ id: 'tp2', text: `TP2 ${toFaDigits(Math.round(primary.tp2))}`, y, color: COLORS.tp, dash: '3 3', testId: 'spotlight-tp2' });
      }
      if (primary.stop != null) {
        const y = toPixel(primary.anchorIndex, primary.stop).y;
        if (Number.isFinite(y)) rails.push({ id: 'sl', text: `SL ${toFaDigits(Math.round(primary.stop))}`, y, color: COLORS.loss, dash: '2 3', testId: 'spotlight-sl' });
      }

      const breakPoint = primary.breakoutIndex != null
        ? toPixel(primary.breakoutIndex, primary.neckline ?? primary.upper)
        : null;
      const isBearish = primary.direction === 'bearish';
      const labelX = clamp((pStart.x + pEnd.x) / 2, 96, Math.max(96, size.width - 96));

      return {
        width: size.width,
        height: size.height,
        x1: pStart.x,
        x2: pEnd.x,
        yTop,
        yBot,
        dx,
        dy,
        shadowPx,
        legs: legsFinite ? legs : [],
        neckY,
        rails,
        railX,
        breakPoint,
        labelX,
        labelY: isBearish ? Math.max(8, yTop - 44) : Math.min(size.height - 48, yBot + 18),
        atr,
      };
    } catch {
      return null;
    }
  }, [chart, primary, viewportTick]);

  if (!chart || !primary || !geometry) return null;

  const accent = accentOf(primary);
  const chipFill = isLight ? 'rgba(255,255,255,0.95)' : 'rgba(16, 18, 24, 0.94)';
  const chipStroke = isLight ? 'rgba(20, 24, 30, 0.18)' : 'rgba(232, 227, 218, 0.18)';
  const mainText = isLight ? '#1e293b' : '#f3f4f6';
  const subText = isLight ? '#5b6472' : '#a9a396';
  const kicker = primary.source === 'doubleTap'
    ? `${primary.kindLabel} · ${STATUS_EN[primary.status]}`
    : `${primary.kindLabel} · ${STATUS_FA[primary.status]}`;
  const detail = primary.source === 'doubleTap'
    ? `Grade ${primary.grade ?? '—'} · ${toFaDigits(Math.round(primary.score ?? primary.quality))}/۱۰۰`
    : `کیفیت ${toFaDigits(Math.round(primary.quality))}`;
  const signal = primary.source === 'doubleTap' && (primary.score ?? 0) >= 50
    ? primary.direction === 'bullish' ? 'LONG' : 'SHORT'
    : null;
  const signalY = geometry.breakPoint
    ? clamp(geometry.breakPoint.y + (primary.direction === 'bearish' ? -30 : 30), 12, geometry.height - 12)
    : 0;

  return (
    <div
      data-testid="spotlight-overlay"
      className={`absolute inset-0 pointer-events-none overflow-hidden z-15 ${reduced ? 'spotlight-reduced' : ''}`}
      style={{ transform: 'translateZ(0)' }}
      aria-hidden="true"
    >
      {/* key = identity الگو: همان الگو انیمیشن را از نو اجرا نمی‌کند، الگوی تازه می‌کند. */}
      <svg key={primary.id} className="w-full h-full" style={{ overflow: 'visible' }} direction="rtl">
        {geometry.legs.length >= 2 && (
          <>
            <polyline
              data-testid="spotlight-leg-shadow"
              points={poly(geometry.legs.map((p) => ({ x: p.x + 1, y: p.y + geometry.shadowPx })))}
              fill="none"
              stroke={accent}
              strokeOpacity="0.28"
              strokeWidth="3"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            <polyline
              data-testid="spotlight-legs"
              className="spotlight-path"
              pathLength={1}
              points={poly(geometry.legs)}
              fill="none"
              stroke={accent}
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </>
        )}

        {geometry.neckY != null && (
          <line
            data-testid="spotlight-neckline"
            x1={geometry.x1}
            y1={geometry.neckY}
            x2={geometry.x2}
            y2={geometry.neckY}
            stroke={COLORS.neck}
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        )}

        <polygon
          data-testid="spotlight-slab-front"
          className="spotlight-slab"
          points={poly([
            { x: geometry.x1, y: geometry.yTop },
            { x: geometry.x2, y: geometry.yTop },
            { x: geometry.x2, y: geometry.yBot },
            { x: geometry.x1, y: geometry.yBot },
          ])}
          fill={accent}
          fillOpacity="0.22"
          stroke={accent}
          strokeWidth="1.5"
        />
        <polygon
          data-testid="spotlight-slab-top"
          className="spotlight-slab spotlight-slab-top"
          points={poly([
            { x: geometry.x1, y: geometry.yTop },
            { x: geometry.x1 + geometry.dx, y: geometry.yTop + geometry.dy },
            { x: geometry.x2 + geometry.dx, y: geometry.yTop + geometry.dy },
            { x: geometry.x2, y: geometry.yTop },
          ])}
          fill={accent}
          fillOpacity="0.34"
          stroke={accent}
          strokeWidth="1"
        />
        <polygon
          data-testid="spotlight-slab-side"
          className="spotlight-slab spotlight-slab-side"
          points={poly([
            { x: geometry.x2, y: geometry.yTop },
            { x: geometry.x2 + geometry.dx, y: geometry.yTop + geometry.dy },
            { x: geometry.x2 + geometry.dx, y: geometry.yBot + geometry.dy },
            { x: geometry.x2, y: geometry.yBot },
          ])}
          fill={accent}
          fillOpacity="0.16"
          stroke={accent}
          strokeWidth="1"
        />

        {geometry.rails.map((rail) => (
          <g key={rail.id} data-testid={rail.testId} className="spotlight-rail">
            <line
              x1={geometry.railX}
              y1={rail.y}
              x2={geometry.x2 + geometry.dx}
              y2={rail.y}
              stroke={rail.color}
              strokeWidth="1.5"
              strokeDasharray={rail.dash}
            />
            <text
              x={geometry.x2 + geometry.dx - 4}
              y={rail.y - 5}
              textAnchor="end"
              fill={rail.color}
              fontSize="12"
              fontFamily="Vazirmatn, sans-serif"
              direction="rtl"
            >
              {rail.text}
            </text>
          </g>
        ))}

        {primary.breakoutIndex != null && geometry.breakPoint && (
          <g data-testid="spotlight-break-tag" className="spotlight-tag">
            <rect
              x={geometry.breakPoint.x - 30}
              y={geometry.breakPoint.y + (primary.direction === 'bearish' ? -46 : 16)}
              width="60"
              height="20"
              rx="3"
              fill={accent}
              fillOpacity="0.92"
            />
            <text
              x={geometry.breakPoint.x}
              y={geometry.breakPoint.y + (primary.direction === 'bearish' ? -32 : 30)}
              textAnchor="middle"
              fill="#0b0d10"
              fontSize="12"
              fontWeight="700"
              fontFamily="Vazirmatn, sans-serif"
            >
              BREAK
            </text>
          </g>
        )}

        {signal && geometry.breakPoint && (
          <g data-testid="spotlight-signal-tag" className="spotlight-tag spotlight-tag-2">
            <rect
              x={geometry.breakPoint.x - 34}
              y={signalY - 10}
              width="68"
              height="20"
              rx="3"
              fill={primary.direction === 'bullish' ? COLORS.win : COLORS.loss}
              fillOpacity="0.9"
            />
            <text
              x={geometry.breakPoint.x}
              y={signalY + 4}
              textAnchor="middle"
              fill="#0b0d10"
              fontSize="12"
              fontWeight="700"
              fontFamily="Vazirmatn, sans-serif"
            >
              {signal}
            </text>
          </g>
        )}

        <g data-testid="spotlight-label" className="spotlight-label">
          <rect
            x={geometry.labelX - 96}
            y={geometry.labelY}
            width="192"
            height="38"
            rx="4"
            fill={chipFill}
            stroke={chipStroke}
            strokeWidth="1"
          />
          <text
            x={geometry.labelX}
            y={geometry.labelY + 16}
            textAnchor="middle"
            fill={mainText}
            fontSize="12"
            fontWeight="600"
            fontFamily="Vazirmatn, sans-serif"
            direction="rtl"
          >
            {kicker}
          </text>
          <text
            x={geometry.labelX}
            y={geometry.labelY + 31}
            textAnchor="middle"
            fill={subText}
            fontSize="12"
            fontFamily="Vazirmatn, sans-serif"
            direction="rtl"
          >
            {detail}
          </text>
        </g>
      </svg>
    </div>
  );
};
