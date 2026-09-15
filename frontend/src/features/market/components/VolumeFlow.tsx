// features/market/components/VolumeFlow.tsx -- جریان حجم نماد انتخابی
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { EmptyState } from '@shared/components/EmptyState';
import { useHistory } from '../api/useHistory';

const LAST_N = 60;

export function VolumeFlow({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useHistory(symbol);
  const volumes = useMemo(() => (data?.volumes ?? []).slice(-LAST_N), [data]);

  if (!symbol) return <EmptyState title="نمادی انتخاب نشده" hint="یک ردیف از جدول را انتخاب کن" />;

  const max = Math.max(1, ...volumes.map((v) => v.value));
  const avg = volumes.length > 0 ? volumes.reduce((a, v) => a + v.value, 0) / volumes.length : 0;
  const peakIdx = volumes.reduce((best, v, i) => (v.value > volumes[best].value ? i : best), 0);
  const avgH = Math.min(100, (avg / max) * 100);

  return (
    <div className="glass-panel panel-in p-4">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">جریان حجم {symbol}</h3>
        <span className="text-2xs text-text-muted">میانگین: {fmtInt(avg)}</span>
      </div>
      {isLoading && <div className="py-8 text-center text-xs text-text-secondary">در حال بارگذاری...</div>}
      {isError && <div className="py-8 text-center text-xs text-accent-red">خطا در دریافت تاریخچه</div>}
      {!isLoading && !isError && volumes.length === 0 && (
        <div className="py-8 text-center text-xs text-text-muted">تاریخچه ای نیست</div>
      )}
      {volumes.length > 0 && (
        <div className="relative flex h-28 items-end gap-[2px]" dir="ltr">
          <div
            className="pointer-events-none absolute right-0 w-full border-t border-dashed border-accent-yellow/50"
            style={{ bottom: `${Math.max(3, avgH)}%` }}
            title={`میانگین: ${fmtInt(avg)}`}
          />
          {volumes.map((v, i) => (
            <div
              key={v.time}
              title={`${v.time}: ${fmtInt(v.value)}`}
              className={`flex-1 rounded-sm ${i === peakIdx ? 'bg-accent-yellow/80' : v.color ?? 'bg-accent-blue/60'}`}
              style={{ height: `${Math.max(3, (v.value / max) * 100)}%` }}
            />
          ))}
        </div>
      )}
      <div className="mt-1 flex items-center justify-between text-2xs text-text-muted">
        <span>{toFaDigits(volumes.length)} جلسه آخر</span>
        {volumes.length > 0 && (
          <span>
            اوج: <span className="num">{fmtInt(volumes[peakIdx].value)}</span>
          </span>
        )}
      </div>
    </div>
  );
}
