import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../api/useFtsCard';
import { AXES, formatAxisValue, formatEpsValue, potentialStatusOf, statusFa, type AxisKey, type AxisStatus } from '../lib/axisMeta';
import { cardStatus } from '../lib/cardStatus';
import { Bullet } from './mini/Bullet';
import { EpsBars } from './mini/EpsBars';
import { RegimeGlyph } from './mini/RegimeGlyph';

interface QuintetItem {
  axis: AxisKey;
  value: string;
  threshold: string;
  status: AxisStatus;
  chart: ReactNode;
}

function pct(value: number | null | undefined): string {
  return value == null
    ? '—'
    : `${toFaDigits(value.toFixed(1)).replace('.', '٫').replace(/^-/, '−')}٪`;
}

function thresholdLabel(value: number | null | undefined, suffix = '٪'): string {
  return value == null ? '—' : `${toFaDigits(String(value)).replace('.', '٫')}${suffix}`;
}

/** R99: سال‌های گیتِ EPS از تنظیمِ ردیف، وگرنه ریشهٔ کارت؛ نبودِ تنظیم «—» است. */
function requiredYears(card: FtsCard): number | null {
  return card.indicators?.['2']?.years_required ?? card.thresholds?.v10_eps_years ?? null;
}

/**
 * نوارِ پنج‌گانهٔ بالای کاکپیت. وضعیت هر محور فقط از `cardStatus` می‌آید
 * و رنگ‌ها با توکن‌های fd (pass=up, fail=down, na=flat, unknown=warn).
 */
export function Quintet({ card, onFocus }: { card: FtsCard; onFocus?: (axis: AxisKey) => void }) {
  const monetary = card.indicators?.['1']?.monetary;
  const eps = card.indicators?.['2'];
  const margin = card.indicators?.['3'];
  const sales = card.indicators?.['4'];
  const industry = card.indicators?.['5'];
  // R-P1-1: کفِ نمودار/وضعیت threshold است؛ target_threshold فقط برچسبِ هدف است.
  const growthFloor = monetary?.threshold ?? null;
  const growthTarget = monetary?.target_threshold ?? null;
  const growthThresholdText = `کف ${thresholdLabel(growthFloor)}${growthTarget == null || growthTarget === growthFloor ? '' : ` · هدف ${thresholdLabel(growthTarget)}`}`;
  const epsRequired = requiredYears(card);
  // R-P0-1: وضعیتِ نمودار فقط زیرگیتِ پتانسیل است؛ وضعیتِ کاشی همچنان ترکیبی است.
  const salesPotentialStatus = potentialStatusOf(
    { profit_potential_pct: sales?.potential_pct ?? null },
    { profit_potential_min: sales?.potential_threshold ?? null },
  );

  const items: QuintetItem[] = [
    {
      axis: 'growth',
      // R91: رشد مثل ستون جدول علامتِ +/− دارد («+۴۵٫۹٪»).
      value: formatAxisValue(monetary?.monetary_pct ?? null, 'growth'),
      threshold: growthThresholdText,
      status: cardStatus(card, 'growth'),
      chart: <Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={growthFloor} status={cardStatus(card, 'growth')} label="رشد" />,
    },
    {
      axis: 'eps',
      // R98: مقدارِ محور ۲ آخرین EPS + فلشِ روند است، نه «سال‌های موجود/نیاز».
      value: formatEpsValue(eps?.eps_series),
      threshold: epsRequired == null ? '—' : `${toFaDigits(epsRequired)} سال`,
      status: cardStatus(card, 'eps'),
      chart: <EpsBars series={eps?.eps_series} status={cardStatus(card, 'eps')} label="EPS" />,
    },
    {
      axis: 'margin',
      value: pct(margin?.margin_pct),
      threshold: `کف ${thresholdLabel(margin?.threshold)}`,
      status: cardStatus(card, 'margin'),
      chart: <Bullet value={margin?.margin_pct ?? null} max={60} threshold={margin?.threshold ?? null} status={cardStatus(card, 'margin')} label="حاشیه" />,
    },
    {
      axis: 'sales',
      // R-P0-1: تیترِ محور ۴ درصدِ نهاییِ پتانسیل سود است؛ فروش/ارزش فقط مسیر/شاهد است.
      value: formatAxisValue(sales?.potential_pct ?? null, 'sales'),
      threshold: `کف ${thresholdLabel(sales?.potential_threshold, '٪')}`,
      status: cardStatus(card, 'sales'),
      chart: (
        <Bullet
          value={sales?.potential_pct ?? null}
          max={100}
          threshold={sales?.potential_threshold ?? null}
          status={salesPotentialStatus}
          label="پتانسیل سود"
        />
      ),
    },
    {
      axis: 'industry',
      value: industry?.label ?? industry?.regime_label ?? '—',
      threshold: 'رژیم',
      status: cardStatus(card, 'industry'),
      chart: <RegimeGlyph regime={industry?.verdict ?? null} status={cardStatus(card, 'industry')} />,
    },
  ];

  return (
    <div data-testid="fundamental-quintet" className="fd-in grid grid-cols-5 gap-2 max-[1050px]:grid-cols-2">
      {items.map((item) => {
        const meta = AXES.find((axis) => axis.key === item.axis)!;
        return (
          <button
            key={item.axis}
            type="button"
            data-axis={item.axis}
            onClick={() => onFocus?.(item.axis)}
            className="flex flex-col gap-1 rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2 text-start hover:border-[var(--fd-line-strong)]"
            aria-label={`${meta.label} — ${item.value} — ${statusFa(item.status)}`}
          >
            <span className="flex items-center gap-1 fd-meta text-[var(--fd-text-2)]">
              <span className="grid h-4 w-4 flex-none place-items-center rounded border border-[var(--fd-line-strong)] fd-meta">{meta.num}</span>
              {meta.label}
            </span>
            <span className="flex items-baseline gap-1">
              <b className="fd-heading  tabular-nums text-[var(--fd-text)]">{item.value}</b>
              <span className="fd-meta text-[var(--fd-text-3)]">{item.threshold}</span>
            </span>
            <span className="h-[20px]">{item.chart}</span>
            <span className={`fd-meta fd-status--${item.status}`}>{statusFa(item.status)}</span>
          </button>
        );
      })}
    </div>
  );
}
