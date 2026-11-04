import { memo } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useFundamentalPrefs } from '../stores/prefs';
import {
  AXES,
  epsYearsRequired,
  formatAxisValue,
  formatEpsTrend,
  potentialPath,
  potentialStatusOf,
  reasonOf,
  statusFa,
  statusOf,
  thresholdOf,
  trendFa,
  trendOf,
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
  return `≥ ${toFaDigits(threshold)}٪`;
}

function epsThresholdLabel(years: number | null): string {
  return years == null ? '—' : `≥ ${toFaDigits(years)} سال`;
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
  // R98: محور ۲ روندِ EPS است، نه «N/N»؛ فلش در حالتِ فشرده هم می‌ماند.
  const epsYears = axis === 'eps' ? epsYearsRequired(row, thresholds) : null;
  const value = axis === 'eps'
    ? formatEpsTrend(row.eps_series)
    : formatAxisValue(valueOf(row, axis), axis);
  const threshold = thresholdOf(thresholds, axis);
  const reason = reasonOf(row, axis);
  // R-P0-1: زیرگیتِ پتانسیل و مسیرِ OR فقط برای محور ۴؛ وضعیتِ سلول همچنان ترکیبی است.
  const potential = axis === 'sales' ? potentialStatusOf(row, thresholds) : null;
  const path = axis === 'sales' ? potentialPath(row, thresholds) : null;
  const salesRatio = axis === 'sales'
    ? (row.sales_to_mcap == null ? '—' : toFaDigits(row.sales_to_mcap.toFixed(2)).replace('.', '٫'))
    : null;
  const subtitle = axis === 'eps'
    ? epsThresholdLabel(epsYears)
    : axis === 'industry'
      ? row.sector_name ?? '—'
      : axis === 'sales'
        ? (threshold == null
            ? '—'
            : `≥ ${toFaDigits(threshold)}٪ · ${path === 'sales' ? 'مسیر فروش/ارزش' : 'فروش/ارزش'} ${salesRatio}`)
        : thresholdLabel(thresholds, axis);
  const epsTrend = axis === 'eps' ? trendFa(trendOf(row.eps_series)) : null;

  return (
    <div
      role="cell"
      data-testid={`fundamental-cell-${row.symbol}-${axis}`}
      data-state={status}
      data-path={axis === 'sales' ? path ?? 'none' : undefined}
      className={`fd-axis-cell flex min-w-0 flex-col justify-center px-1.5 ${density === 'comfortable' ? 'gap-1 py-1' : 'gap-0 py-0.5'}`}
    >
      <div className="flex items-baseline gap-1.5">
        <b
          className="fd-axis-value text-[12px] font-medium tabular-nums text-[var(--fd-text)]"
          title={epsTrend ? `روند ${epsTrend}` : undefined}
        >
          {value}
        </b>
        <span
          className={`fd-status fd-status--${status} inline-flex items-center gap-0.5 text-[10px]`}
          title={reason ?? STATUS_TITLE[status]}
        >
          <span aria-hidden>{STATUS_ICON[status]}</span> {statusFa(status)}
        </span>
        {axis === 'sales' ? (
          <span
            className="rounded border border-[var(--fd-line-strong)] px-1 text-[8.5px] text-[var(--fd-text-3)]"
            title={path === 'potential' ? 'قبول از مسیر پتانسیل سود' : path === 'sales' ? 'قبول از مسیر فروش/ارزش' : 'مسیر قبولی مشخص نیست'}
          >
            {path === 'potential' ? '۴ب' : path === 'sales' ? '۴الف' : '—'}
          </span>
        ) : null}
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
            <Bullet
              value={row.profit_potential_pct ?? null}
              max={100}
              threshold={threshold}
              status={potential ?? 'unknown'}
              label={`پتانسیل سود ${value}`}
            />
          ) : null}
          {axis === 'industry' ? <RegimeGlyph regime={row.pricing_mode ?? null} status={status} /> : null}
        </div>
      ) : null}
      {/* R92: در حالت فشرده فقط مقدار و وضعیت می‌ماند تا محتوا بریده نشود؛
          خط آستانه در سرستون و راهنمای جدول هم‌چنان دیده می‌شود. */}
      {density === 'comfortable' ? (
        <span className="fd-axis-threshold truncate text-[9.5px] text-[var(--fd-text-3)]">{subtitle}</span>
      ) : null}
    </div>
  );
}

// R84: در طول اسکرول، row/axis/thresholds ارجاعاً پایدار می‌مانند؛ memo از رندر
// دوبارهٔ سلول و چهار نمودار SVG آن در هر به‌روزرسانی مجازی‌ساز جلوگیری می‌کند.
// مقایسهٔ سطحی پیش‌فرض کافی است — مقایسهٔ سفارشی نگذارید.
export const FundamentalAxisCell = memo(AxisCell);
