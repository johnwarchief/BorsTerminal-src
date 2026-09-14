// features/fundamental/components/SectorPePanel.tsx -- مقایسه P/E با میانه صنعت
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';

export function SectorPePanel({
  pe,
  median,
  sector,
}: {
  pe: number | null;
  median: number | null;
  sector: string;
}) {
  if (pe == null || median == null) {
    return (
      <div className="rounded-2xl border border-dashed border-border-c bg-bg-secondary p-4 text-center text-xs text-text-muted">
        P/E قابل اتکا برای مقایسه صنعتی نیست
      </div>
    );
  }
  const ratio = pe / median;
  const cheap = ratio < 1;
  const width = Math.max(4, Math.min(100, (pe / Math.max(pe, median)) * 100));
  const widthMed = Math.max(4, Math.min(100, (median / Math.max(pe, median)) * 100));
  return (
    <div className="glass-panel panel-in p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">P/E در برابر صنعت {sector}</h3>
        <Badge tone={cheap ? 'green' : ratio > 1.5 ? 'red' : 'yellow'}>
          {cheap ? `${toFaDigits(((1 - ratio) * 100).toFixed(0))} درصد ارزان تر` : `${toFaDigits(((ratio - 1) * 100).toFixed(0))} درصد گران تر`}
        </Badge>
      </div>
      <div className="flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-16 text-text-secondary">سهم</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-card">
            <div className="h-full rounded-full bg-accent-blue" style={{ width: `${width}%` }} />
          </div>
          <span className="w-14 text-left font-bold text-text-primary">{toFaDigits(pe.toFixed(2))}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-text-secondary">میانه صنعت</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-card">
            <div className="h-full rounded-full bg-accent-green" style={{ width: `${widthMed}%` }} />
          </div>
          <span className="w-14 text-left font-bold text-text-primary">{toFaDigits(median.toFixed(2))}</span>
        </div>
      </div>
    </div>
  );
}
