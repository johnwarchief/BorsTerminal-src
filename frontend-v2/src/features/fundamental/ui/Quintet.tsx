import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import type { FtsCard } from '../api/useFtsCard';
import { AXES, formatAxisValue, statusFa, type AxisKey, type AxisStatus } from '../lib/axisMeta';
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

function yearsLabel(years: number | null | undefined): string {
  // رأی R50: نبودِ سابقه «—/۳» است، نه «۰/۳».
  return years == null ? '—/۳' : `${toFaDigits(years)}/۳`;
}

function thresholdLabel(value: number | null | undefined, suffix = '٪'): string {
  return value == null ? '—' : `${toFaDigits(String(value)).replace('.', '٫')}${suffix}`;
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

  const items: QuintetItem[] = [
    {
      axis: 'growth',
      // R91: رشد مثل ستون جدول علامتِ +/− دارد («+۴۵٫۹٪»).
      value: formatAxisValue(monetary?.monetary_pct ?? null, 'growth'),
      threshold: `کف ${thresholdLabel(monetary?.threshold)}`,
      status: cardStatus(card, 'growth'),
      chart: <Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={monetary?.threshold ?? null} status={cardStatus(card, 'growth')} label="رشد" />,
    },
    {
      axis: 'eps',
      value: yearsLabel(eps?.years_available),
      threshold: 'سال',
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
      value: sales?.sales_to_mcap == null ? '—' : toFaDigits(sales.sales_to_mcap.toFixed(2)).replace('.', '٫').replace(/^-/, '−'),
      threshold: `کف ${thresholdLabel(sales?.sales_threshold, '')}`,
      status: cardStatus(card, 'sales'),
      chart: <Bullet value={sales?.sales_to_mcap ?? null} max={2} threshold={sales?.sales_threshold ?? null} status={cardStatus(card, 'sales')} label="فروش/ارزش" />,
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
            <span className="flex items-center gap-1 text-[10.5px] text-[var(--fd-text-2)]">
              <span className="grid h-4 w-4 flex-none place-items-center rounded border border-[var(--fd-line-strong)] text-[9px]">{meta.num}</span>
              {meta.label}
            </span>
            <span className="flex items-baseline gap-1">
              <b className="text-[16px] font-medium tabular-nums text-[var(--fd-text)]">{item.value}</b>
              <span className="text-[9px] text-[var(--fd-text-3)]">{item.threshold}</span>
            </span>
            <span className="h-[18px]">{item.chart}</span>
            <span className={`text-[9px] fd-status--${item.status}`}>{statusFa(item.status)}</span>
          </button>
        );
      })}
    </div>
  );
}
