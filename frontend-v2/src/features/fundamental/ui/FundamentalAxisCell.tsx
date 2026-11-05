import { memo } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { useFundamentalPrefs } from '../stores/prefs';
import {
  AXES,
  epsYearsRequired,
  formatAxisValue,
  formatEpsValue,
  growthSubStatuses,
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
import { faSectorName } from '../lib/faOrthography';
import { Bullet } from './mini/Bullet';
import { EpsBars } from './mini/EpsBars';
import { RegimeGlyph } from './mini/RegimeGlyph';
import { StatusMark, TrendMark } from './icons';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

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
  // R98: محور ۲ روندِ EPS است، نه «N/N»؛ R-UNSLOP-3: روند آیکنِ SVG است، نه کاراکتر.
  const epsYears = axis === 'eps' ? epsYearsRequired(row, thresholds) : null;
  const value = axis === 'eps'
    ? formatEpsValue(row.eps_series)
    : formatAxisValue(valueOf(row, axis), axis);
  const threshold = thresholdOf(thresholds, axis);
  const reason = reasonOf(row, axis);
  // R-P0-1: زیرگیتِ پتانسیل و مسیرِ OR فقط برای محور ۴؛ وضعیتِ سلول همچنان ترکیبی است.
  const potential = axis === 'sales' ? potentialStatusOf(row, thresholds) : null;
  const path = axis === 'sales' ? potentialPath(row, thresholds) : null;
  const salesRatio = axis === 'sales'
    ? (row.sales_to_mcap == null ? '—' : toFaDigits(row.sales_to_mcap.toFixed(2)).replace('.', '٫'))
    : null;
  // R-P0-4: نشانِ مسیر و صفتِ data-path فقط با قبولیِ ترکیبیِ محور معنا دارند.
  const pathBadge = axis === 'sales' && status === 'pass'
    ? path === 'potential' ? '۴ب' : path === 'sales' ? '۴الف' : '—'
    : null;
  const salesWord = status === 'pass' && path === 'sales' ? 'مسیر فروش/ارزش' : 'فروش/ارزش';
  // R-P1-2: ستونِ رشد در حالتِ راحت وضعیتِ جداگانهٔ ۱الف/۱ب را هم نشان می‌دهد.
  const subs = axis === 'growth' ? growthSubStatuses(row) : null;
  const growthSubtitle = subs
    ? `${thresholdLabel(thresholds, 'growth')} · ۱الف ${statusFa(subs.a)} · ۱ب ${statusFa(subs.b)}`
    : null;
  const subtitle = axis === 'eps'
    ? epsThresholdLabel(epsYears)
    : axis === 'industry'
      ? faSectorName(row.sector_name) || '—'
      : axis === 'sales'
        // شاهدِ فروش/ارزش حتی بدون آستانهٔ پتانسیل می‌ماند («≥ —٪ · فروش/ارزش ۱٫۱۵»).
        ? `≥ ${threshold == null ? '—' : toFaDigits(threshold)}٪ · ${salesWord} ${salesRatio}`
        : growthSubtitle ?? thresholdLabel(thresholds, axis);
  const epsTrend = axis === 'eps' ? trendOf(row.eps_series) : null;

  return (
    <div
      role="cell"
      data-testid={`fundamental-cell-${row.symbol}-${axis}`}
      data-state={status}
      data-path={axis === 'sales' ? (status === 'pass' && path ? path : 'none') : undefined}
      className={`fd-axis-cell flex min-w-0 flex-col justify-center px-2 ${density === 'comfortable' ? 'gap-1 py-1' : 'gap-0 py-1'}`}
    >
      <div className="flex items-baseline gap-2">
        <b
          className="fd-axis-value fd-cell-strong tabular-nums text-[var(--fd-text)]"
          title={epsTrend ? `روند ${trendFa(epsTrend)}` : undefined}
        >
          {value}
        </b>
        {axis === 'eps' ? <TrendMark trend={epsTrend} /> : null}
        <StatusMark
          status={status}
          word={statusFa(status)}
          title={reason ?? STATUS_TITLE[status]}
          className="fd-cell-meta"
        />
        {pathBadge ? (
          <span
            className="rounded border border-[var(--fd-line-strong)] px-1 fd-cell-meta text-[var(--fd-text-3)]"
            title={path === 'potential' ? 'قبول از مسیر پتانسیل سود' : path === 'sales' ? 'قبول از مسیر فروش/ارزش' : 'مسیر قبولی مشخص نیست'}
          >
            {pathBadge}
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
        // R-P1-2: زیرنویسِ رشد ممکن است در ستونِ باریک بریده شود؛ متنِ کامل در title می‌ماند.
        <span className="fd-axis-threshold truncate fd-cell-meta text-[var(--fd-text-3)]" title={subtitle}>{subtitle}</span>
      ) : null}
    </div>
  );
}

// R84: در طول اسکرول، row/axis/thresholds ارجاعاً پایدار می‌مانند؛ memo از رندر
// دوبارهٔ سلول و چهار نمودار SVG آن در هر به‌روزرسانی مجازی‌ساز جلوگیری می‌کند.
// مقایسهٔ سطحی پیش‌فرض کافی است — مقایسهٔ سفارشی نگذارید.
export const FundamentalAxisCell = memo(AxisCell);
