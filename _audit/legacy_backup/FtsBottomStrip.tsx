// features/technical/components/FtsBottomStrip.tsx -- نوار باریک چندبخشی پایین چارت (HUD)
// جایگزین دو کارت مرده «چهار مووینگ FTS» و «ستاپ‌ها و سطوح»؛ اعداد سطوح حمایتی/مقاومتی همانجا.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { FTS_MA_COLORS } from './KLineChartWrapper';

export type BottomStripData = {
  /** آخرین مقدار هر مووینگ؛ دوره‌های غایب حذف می‌شوند */
  mas: Record<number, number | null>;
  stackLabel: string;
  stackTone: 'green' | 'red' | 'gray';
  /** ستاپ‌های فعال (فارسی) */
  setups: string[];
  /** خط آبی (مقاومت) و حمایت */
  resistance: number | null;
  support: number | null;
  /** حد ضرر MA-14 */
  stopLoss: number | null;
};

const STACK_TONE: Record<string, BottomStripData['stackTone']> = { bull: 'green', bear: 'red', mixed: 'gray', unknown: 'gray' };

export function FtsBottomStrip({ data }: { data: BottomStripData }) {
  const periods = Object.keys(data.mas)
    .map(Number)
    .sort((a, b) => a - b);
  return (
    <div
      className="glass-panel flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-1.5 text-[11px]"
      data-testid="fts-bottom-strip"
      dir="ltr"
    >
      {periods.map((p) => (
        <span key={p} className="num font-bold" style={{ color: FTS_MA_COLORS[p] ?? '#64748b' }} data-testid={`strip-ma-${p}`}>
          MA{p}: {data.mas[p] == null ? '-' : toFaDigits(data.mas[p].toFixed(0))}
        </span>
      ))}
      <span dir="rtl">
        <Badge tone={data.stackTone ?? STACK_TONE.unknown}>{data.stackLabel}</Badge>
      </span>
      {data.setups.length > 0 ? (
        <span className="flex flex-wrap items-center gap-1" dir="rtl" data-testid="strip-setups">
          {data.setups.map((s) => (
            <Badge key={s} tone="blue">{s}</Badge>
          ))}
        </span>
      ) : null}
      {data.resistance != null ? (
        <span className="num text-text-secondary" dir="rtl">
          مقاومت <span className="font-bold text-neon-cyan">{toFaDigits(data.resistance.toFixed(0))}</span>
        </span>
      ) : null}
      {data.support != null ? (
        <span className="num text-text-secondary" dir="rtl">
          حمایت <span className="font-bold text-accent-green">{toFaDigits(data.support.toFixed(0))}</span>
        </span>
      ) : null}
      {data.stopLoss != null ? (
        <span className="num text-text-secondary" dir="rtl">
          حد ضرر <span className="font-bold text-accent-red">{toFaDigits(data.stopLoss.toFixed(0))}</span>
        </span>
      ) : null}
    </div>
  );
}

export { STACK_TONE };
