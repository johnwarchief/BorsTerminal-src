// features/master/ui/GatePipeline.tsx -- نمایش گیتینگ سه‌گانه FTS
// کدام گیت پاس شده / سهم پشت کدام گیت مانده.
import type { GateFinding, GateStatus } from '../lib/masterMath';

const GATE_FA: Record<string, string> = {
  fundamental: 'گیت ۱ · بنیادی',
  technical: 'گیت ۲ · تکنیکال',
  tape: 'گیت ۳ · تابلو',
};

const STATUS_FA: Record<GateStatus, { label: string; cls: string }> = {
  pass: { label: 'عبور', cls: 'border-accent-green/40 bg-accent-green/12 text-accent-green' },
  wait: { label: 'انتظار', cls: 'border-accent-yellow/40 bg-accent-yellow/12 text-accent-yellow' },
  fail: { label: 'رد', cls: 'border-accent-red/40 bg-accent-red/12 text-accent-red' },
  nodata: { label: 'بدون داده', cls: 'border-border-c bg-bg-card text-text-muted' },
  missing: { label: 'منتشرنشده', cls: 'border-border-c bg-bg-card text-text-muted' },
};

export function GatePipeline({ gates }: { gates: GateFinding[] }) {
  return (
    <div className="glass-panel panel-in p-4">
      <h3 className="mb-2 text-sm font-black text-text-primary">پایپ‌لاین گیتینگ FTS</h3>
      <p className="mb-3 text-2xs leading-5 text-text-muted">
        تقدم سلسله‌مراتبی: رد بنیادی ⇒ سهم حداکثر «فاقد بنیاد/حذف‌شده» و هرگز خرید نمی‌گیرد؛ ورود مستقیم فقط با ستاپ جت/پولبک؛ تأیید نهایی با نقدینگی تابلو.
      </p>
      <ol className="flex flex-col gap-2">
        {gates.map((g, i) => {
          const st = STATUS_FA[g.status];
          return (
            <li key={g.gate} className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
              <span className="num flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border-c text-2xs font-black text-text-secondary">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="text-xs font-bold text-text-primary">{GATE_FA[g.gate]}</span>
              <span className={`rounded-full border px-2 py-0.5 text-2xs font-bold ${st.cls}`}>{st.label}</span>
              <span className="min-w-0 flex-1 basis-full text-2xs leading-5 text-text-secondary sm:basis-auto">{g.note}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
