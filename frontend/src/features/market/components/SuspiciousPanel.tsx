// features/market/components/SuspiciousPanel.tsx -- نامزدهای الگوی ساعت، حجم مشکوک و روباهی
import { useMemo } from 'react';
import { FlashNum } from '@shared/components/FlashNum';
import type { MarketRow } from '@shared/types/marketRow';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { buyerPowerRatio, detectClockPattern, detectSuspiciousVolume } from '../lib/tapeMath';
import { STRONG_HOUR_LABEL, detectStrongHour } from '../lib/tapePatterns';

const MAX_ITEMS = 15;

/** بخش‌های پذیرفته پنل -- برای رندر انتخابی در دیده‌بان‌ها */
export type SuspSection = 'clock' | 'susp' | 'roobi';
export const ALL_SUSP_SECTIONS: SuspSection[] = ['clock', 'susp', 'roobi'];

/** برچسب کف‌روبی: صف فروشِ قفل + خریدار درشتِ در حال جمع‌آوری (آینهٔ f_roobi در api/market.py) */
export const ROOBI_LABEL = 'در صف فروش قفل + خریدار درشت در حال جمع‌آوری';

type Item = {
  symbol: string;
  name: string;
  metric: number;
  power: number | null;
  extra: string;
  strong: boolean;
  title?: string;
};

export function SuspiciousPanel({
  rows,
  onSelect,
  sections = ALL_SUSP_SECTIONS,
}: {
  rows: MarketRow[];
  onSelect: (s: string) => void;
  /** زیرمجموعه بخش‌های قابل نمایش؛ پیش‌فرض هر سه (ساعت/حجم مشکوک/کف‌روبی) */
  sections?: SuspSection[];
}) {
  const clocks = useMemo<Item[]>(() => {
    const out: Item[] = [];
    for (const r of rows) {
      if (!r.symbol) continue;
      const c = detectClockPattern(r);
      if (c.hit && c.gap != null) {
        out.push({
          symbol: r.symbol,
          name: r.name ?? '',
          metric: c.gap,
          power: buyerPowerRatio(r.buy_i_vol, r.buy_count_i, r.sell_i_vol, r.sell_count_i),
          extra: fmtPct(c.gap * 100),
          strong: detectStrongHour(r),
        });
      }
    }
    return out.sort((a, b) => b.metric - a.metric).slice(0, MAX_ITEMS);
  }, [rows]);

  const susps = useMemo<Item[]>(() => {
    const out: Item[] = [];
    for (const r of rows) {
      if (!r.symbol) continue;
      const s = detectSuspiciousVolume(r);
      if (s.hit && s.multiple != null) {
        out.push({
          symbol: r.symbol,
          name: r.name ?? '',
          metric: s.multiple,
          power: buyerPowerRatio(r.buy_i_vol, r.buy_count_i, r.sell_i_vol, r.sell_count_i),
          extra: toFaDigits(s.multiple.toFixed(1)) + ' برابر',
          strong: detectStrongHour(r),
        });
      }
    }
    return out.sort((a, b) => b.metric - a.metric).slice(0, MAX_ITEMS);
  }, [rows]);

  /** کف‌روبی: ردیف‌های f_roobi از همان فید تابلو (فیلتر بک‌اند، نه محاسبهٔ مجدد) */
  const roobis = useMemo<Item[]>(() => {
    const out: Item[] = [];
    for (const r of rows) {
      if (!r.symbol || !r.f_roobi) continue;
      out.push({
        symbol: r.symbol,
        name: r.name ?? '',
        metric: r.percent_change ?? 0,
        power: buyerPowerRatio(r.buy_i_vol, r.buy_count_i, r.sell_i_vol, r.sell_count_i),
        extra: r.percent_change != null ? fmtPct(r.percent_change) : '-',
        strong: false,
        title: ROOBI_LABEL,
      });
    }
    return out.sort((a, b) => a.metric - b.metric).slice(0, MAX_ITEMS);
  }, [rows]);

  const section = (
    title: string,
    items: Item[],
    badge: React.ReactNode,
    hint?: string,
  ) => (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">{title}</h3>
        {badge}
      </div>
      {hint ? <p className="mb-1 text-2xs leading-5 text-text-muted">{hint}</p> : null}
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-c p-2 text-center text-xs text-text-muted">
          موردی نیست
        </div>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {items.map((it) => (
            <li key={it.symbol}>
              <button
                type="button"
                onClick={() => onSelect(it.symbol)}
                title={it.title}
                className="flex w-full items-center justify-between gap-2 rounded-lg border border-transparent px-2 py-1 text-sm hover:border-border-c hover:bg-bg-card"
              >
                <span className="font-bold text-text-primary">
                  {it.symbol} <span className="font-normal text-text-muted">{it.name}</span>
                  {it.title ? (
                    <span className="mt-0.5 block text-2xs font-normal leading-4 text-text-muted">{it.title}</span>
                  ) : null}
                </span>
                <span className="flex items-center gap-2">
                  {it.strong ? (
                    <span title={STRONG_HOUR_LABEL}>
                      <Badge tone="green">ساعت قوی</Badge>
                    </span>
                  ) : null}
                  <FlashNum
                    value={it.metric}
                    render={() => it.extra}
                    className="text-text-secondary"
                  />
                  {it.power != null && it.power >= 1.5 ? (
                    <Badge tone="green">{toFaDigits(it.power.toFixed(1))}</Badge>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div className="glass-panel panel-in flex w-full max-w-none flex-col gap-3 p-2">
      {sections.includes('clock')
        ? section(`الگوی ساعت (${toFaDigits(clocks.length)})`, clocks, <Badge tone="blue">پایانی بالاتر</Badge>)
        : null}
      {sections.includes('susp')
        ? section(`حجم مشکوک (${toFaDigits(susps.length)})`, susps, <Badge tone="orange">حجم بالا</Badge>)
        : null}
      {sections.includes('roobi')
        ? section(
            `کف‌روبی (${toFaDigits(roobis.length)})`,
            roobis,
            <Badge tone="gray">روباهی</Badge>,
            ROOBI_LABEL,
          )
        : null}
    </div>
  );
}
