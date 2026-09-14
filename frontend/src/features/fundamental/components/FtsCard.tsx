// features/fundamental/components/FtsCard.tsx -- شش سلول خلاصه پنج لایه
// هر سلول قابل کلیک است: پنل Drill-Down همان شاخص باز می‌شود.
// لایهٔ ۱ب (رشد فیزیکی) برای هلدینگ/خدماتی/مالی به‌جای «مردود/شکاف»
// برچسب N/A می‌گیرد — چون اصلاً قابل اعمال نیست.
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { ConfidenceDial } from '@shared/components/ConfidenceDial';
import type { DrillDownKey } from './FtsDrillDown';

const LAYERS: { key: string; drill: DrillDownKey | null; label: string; hint: string }[] = [
  { key: '1a_monetary_growth', drill: '1', label: '1 الف رشد ریالی', hint: 'رشد درآمد ریالی — کلیک: نمودار و فرمول' },
  { key: '1b_volume_growth', drill: '1', label: '1 ب رشد فیزیکی', hint: 'رشد حجم فروش — N/A برای غیرتولیدی' },
  { key: '2_eps_trend', drill: '2', label: '2 سودسازی', hint: 'روند سه ساله EPS — کلیک: نمودار پله‌ای' },
  { key: '3_gross_margin', drill: '3', label: '3 حاشیه', hint: 'حاشیه ناخالص — کلیک: روند ۶ فصل و آستانه‌ها' },
  { key: '4_sales_to_mcap', drill: '4', label: '4 ارزش', hint: 'فروش به ارزش بازار — کلیک: سالانه‌سازی پویا' },
  { key: '5_industry', drill: '5', label: '5 صنعت', hint: 'رژیم قیمت گذاری صنعت — کلیک: ماتریس چشم‌انداز' },
];

function cellTone(v: boolean | undefined, na: boolean): 'green' | 'red' | 'gray' {
  if (na) return 'gray';
  if (v == null) return 'gray';
  return v ? 'green' : 'red';
}

export function FtsCard({
  score,
  passes,
  verdict,
  physicalApplicable = true,
  activeDrill = null,
  onDrill,
}: {
  score: number | null;
  passes: Record<string, boolean>;
  verdict: string | null;
  /** رشد فیزیکی صرفاً برای تولیدی معنا دارد — هلدینگ/خدماتی N/A */
  physicalApplicable?: boolean;
  activeDrill?: DrillDownKey | null;
  onDrill?: (k: DrillDownKey) => void;
}) {
  return (
    <div className="glass-panel panel-in p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">کارت FTS</h3>
        <span className="flex items-center gap-2">
          {score != null ? (
            <Badge tone={score >= 4 ? 'green' : score >= 3 ? 'yellow' : 'red'}>
              امتیاز {toFaDigits(score)} از ۵
            </Badge>
          ) : (
            <Badge tone="gray">بدون امتیاز</Badge>
          )}
          {verdict ? <Badge tone="blue">{verdict}</Badge> : null}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {LAYERS.map((l) => {
          const v = passes[l.key];
          const na = l.key === '1b_volume_growth' && !physicalApplicable;
          const isActive = l.drill != null && l.drill === activeDrill;
          return (
            <button
              key={l.key}
              type="button"
              disabled={!l.drill || !onDrill}
              onClick={() => l.drill && onDrill?.(l.drill)}
              aria-pressed={isActive}
              data-testid={`fts-card-cell-${l.key}`}
              title={l.hint}
              className={`rounded-xl border p-3 text-center transition-all ${
                isActive
                  ? 'border-accent-blue/60 bg-accent-blue/10'
                  : 'border-border-c bg-bg-primary hover:border-border-accent disabled:cursor-default'
              }`}
            >
              <div className="mb-1 text-xs font-bold text-text-secondary">{l.label}</div>
              <Badge tone={cellTone(v, na)}>{na ? 'N/A' : v == null ? 'بدون داده' : v ? 'قبول' : 'مردود'}</Badge>
            </button>
          );
        })}
      </div>
      <div className="mt-3">
        <ConfidenceDial value={score == null ? 'nodata' : score >= 4 ? 'high' : score >= 3 ? 'medium' : 'low'} />
      </div>
    </div>
  );
}
