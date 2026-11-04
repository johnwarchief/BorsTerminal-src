import { memo } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useFundamentalPrefs } from '../stores/prefs';
import {
  AXES,
  formatAxisValue,
  reasonOf,
  statusFa,
  statusOf,
  thresholdOf,
  valueOf,
  type AxisKey,
  type AxisStatus,
  type AxisThresholds,
} from '../lib/axisMeta';
import { Bullet } from './mini/Bullet';
import { EpsBars } from './mini/EpsBars';
import { RegimeGlyph } from './mini/RegimeGlyph';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export const STATUS_ICON: Record<AxisStatus, string> = { pass: '✓', fail: '✕', na: '−', unknown: '?' };

const STATUS_TITLE: Record<AxisStatus, string> = {
  pass: 'قبول — این محور آستانه را پاس کرده است',
  fail: 'رد — این محور آستانه را پاس نکرده است',
  na: 'بی‌نظر (N/A) — حکمِ این محور سنجیده نمی‌شود',
  unknown: 'وضعیتِ این محور در پاسخ نیست',
};

function thresholdLabel(thresholds: AxisThresholds | null | undefined, axis: AxisKey): string {
  const threshold = thresholdOf(thresholds, axis);
  if (threshold == null) return '—';
  if (axis === 'sales') return `≥ ${toFaDigits(threshold.toFixed(2)).replace('.', '٫')}`;
  return `≥ ${toFaDigits(threshold)}٪`;
}

interface Props {
  row: ScreenerCoreRow;
  axis: AxisKey;
  thresholds?: AxisThresholds | null;
}

function AxisCell({ row, axis, thresholds }: Props) {
  const density = useFundamentalPrefs((state) => state.density);
  const meta = AXES.find((item) => item.key === axis)!;
  const status = statusOf(row, axis);
  const value = axis === 'eps'
    ? `${toFaDigits(row.eps_years_available ?? 0)}/۳`
    : formatAxisValue(valueOf(row, axis), axis);
  const threshold = thresholdOf(thresholds, axis);
  const reason = reasonOf(row, axis);
  const subtitle = axis === 'eps'
    ? '۳ سال'
    : axis === 'industry'
      ? row.sector_name ?? '—'
      : thresholdLabel(thresholds, axis);

  return (
    <div
      role="gridcell"
      data-testid={`fundamental-cell-${row.symbol}-${axis}`}
      data-state={status}
      className={`fd-axis-cell flex min-w-0 flex-col justify-center px-1.5 ${density === 'comfortable' ? 'gap-1 py-1' : 'gap-0 py-0.5'}`}
    >
      <div className="flex items-baseline gap-1.5">
        <b className="fd-axis-value text-[12px] font-medium tabular-nums text-[var(--fd-text)]">{value}</b>
        <span
          className={`fd-status fd-status--${status} inline-flex items-center gap-0.5 text-[10px]`}
          title={reason ?? STATUS_TITLE[status]}
        >
          <span aria-hidden>{STATUS_ICON[status]}</span> {statusFa(status)}
        </span>
      </div>
      {density === 'comfortable' ? (
        <div className="fd-axis-chart h-[24px]">
          {axis === 'growth' ? (
            <Bullet value={row.rev_growth ?? null} max={200} threshold={threshold} status={status} label={`${meta.label} ${value}`} />
          ) : null}
          {axis === 'eps' ? (
            <EpsBars series={row.eps_series} status={status} label="سری EPS" />
          ) : null}
          {axis === 'margin' ? (
            <Bullet value={row.gross_margin ?? null} max={60} threshold={threshold} status={status} label={`${meta.label} ${value}`} />
          ) : null}
          {axis === 'sales' ? (
            <Bullet value={row.sales_to_mcap ?? null} max={2} threshold={threshold} status={status} label={`${meta.label} ${value}`} />
          ) : null}
          {axis === 'industry' ? <RegimeGlyph regime={row.pricing_mode ?? null} status={status} /> : null}
        </div>
      ) : null}
      <span className="fd-axis-threshold truncate text-[9.5px] text-[var(--fd-text-3)]">{subtitle}</span>
    </div>
  );
}

export const FundamentalAxisCell = memo(AxisCell);
