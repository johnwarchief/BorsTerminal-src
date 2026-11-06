import React from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../../model/technicalStore';
import type { ChartEvent } from '../../model/events/types';
import {
  EVENT_DIRECTION_FA,
  EVENT_FAMILY_FA,
  EVENT_STATUS_FA,
  eventKindFa,
} from '../../model/events/labels';

const DIRECTION_COLOR: Record<string, string> = {
  bullish: 'var(--color-profit, #4f8f72)',
  bearish: 'var(--color-loss, #b45a6a)',
  neutral: 'var(--color-text-3, #a89a6a)',
};

function metricText(event: ChartEvent): string {
  if (event.family === 'divergence') {
    return `RSI ${toFaDigits(event.metrics.rsi1 ?? '—')} → ${toFaDigits(event.metrics.rsi2 ?? '—')}`;
  }
  if (event.family === 'channel') {
    return `R² ${toFaDigits(event.metrics.r2 ?? '—')} · لمس ${toFaDigits(event.metrics.touchesUpper ?? '—')}/${toFaDigits(event.metrics.touchesLower ?? '—')}`;
  }
  if (event.family === 'pullback' || event.family === 'breakout') {
    return `سطح ${toFaDigits(event.metrics.level ?? event.metrics.ema ?? '—')}`;
  }
  return event.pattern ? `کیفیت هندسی ${toFaDigits(Math.round(event.quality))}` : '';
}

export interface UnifiedEventListProps {
  events: readonly ChartEvent[];
  limit?: number;
  className?: string;
  /** فقط رویدادهای برجسته (ریل)؛ پیش‌فرض همه. */
  primariesOnly?: boolean;
}

/**
 * فهرست رویدادهای واحد؛ خانواده/نوع/جهت/وضعیت/کیفیت را یک‌جا نشان می‌دهد.
 * کلیک روی رویداد الگو، همان focusPatternId موجود را فعال می‌کند.
 */
export const UnifiedEventList: React.FC<UnifiedEventListProps> = ({
  events,
  limit = 12,
  className = '',
  primariesOnly = false,
}) => {
  const scanResult = useTechnicalStore((s) => s.scanResult);
  const setFocusPatternId = useTechnicalStore((s) => s.setFocusPatternId);
  const primaryIds = new Set(Object.values(scanResult?.primary ?? {}).filter(Boolean) as string[]);
  const source = primariesOnly ? events.filter((event) => primaryIds.has(event.id)) : events;
  const shown = [...source]
    .sort((a, b) => b.anchor.index - a.anchor.index || b.quality - a.quality)
    .slice(0, limit);

  if (!shown.length) {
    return (
      <div data-testid="unified-event-list-empty" className={`px-3 py-2 text-xs text-text-3 ${className}`}>
        رویداد فعالی در این نماد پیدا نشد.
      </div>
    );
  }

  return (
    <div data-testid="unified-event-list" className={`flex flex-col ${className}`}>
      {shown.map((event) => {
        const canFocus = Boolean(event.pattern);
        return (
          <button
            key={event.id}
            type="button"
            data-testid={`unified-event-${event.id}`}
            disabled={!canFocus}
            onClick={() => {
              if (event.pattern) setFocusPatternId(event.pattern.id);
            }}
            className={`min-h-8 px-3 py-1 flex items-center gap-2 border-b border-line/60 text-right text-xs outline-none ${
              canFocus ? 'hover:bg-panel-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent' : 'cursor-default'
            }`}
          >
            <span className="shrink-0 text-text-3">{EVENT_FAMILY_FA[event.family]}</span>
            <span className="min-w-0 flex-1 truncate text-text">{eventKindFa(event)}</span>
            <span className="shrink-0" style={{ color: DIRECTION_COLOR[event.direction] }}>
              {EVENT_DIRECTION_FA[event.direction]}
            </span>
            <span className="shrink-0 text-text-3">{EVENT_STATUS_FA[event.status]}</span>
            <span className="shrink-0 text-text-3 tabular-nums">{toFaDigits(Math.round(event.quality))}</span>
            <span className="shrink-0 text-text-3 tabular-nums hidden lg:inline">{metricText(event)}</span>
          </button>
        );
      })}
      {source.length > shown.length && (
        <div className="px-3 py-1 text-xs text-text-3">
          {toFaDigits(source.length - shown.length)} رویداد دیگر در فید کامل
        </div>
      )}
    </div>
  );
};
