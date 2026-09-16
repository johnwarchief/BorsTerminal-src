// features/master/routes/MasterPage.tsx -- داشبورد ایجنت ارشد (بازطراحی)
// v2: گیج تجمیعی با آرا/وزن‌های واقعی + کارت برنامه معاملاتی + گیتینگ سه‌گانه
// + باکس synthesis قانون‌محور. تمام‌عرض داخل صفحه خودش.
import { useMemo } from 'react';
import { useParams } from 'react-router';
import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { AGENT_WEIGHTS } from '@contracts/signal';
import {
  aggregateSignals,
  effectiveWeights,
  runGatingPipeline,
  synthesizeVerdict,
} from '../lib/masterMath';
import { buildTradePlan, riskLevel } from '../lib/tradePlanMath';
import { useFtsPlan } from '../api/useFtsPlan';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { MasterVerdictCard } from '../ui/MasterVerdictCard';
import { AgentMatrix } from '../ui/AgentMatrix';
import { ConflictBanner } from '../ui/ConflictBanner';
import { TradePlanCard } from '../ui/TradePlanCard';
import { GatePipeline } from '../ui/GatePipeline';
import { SynthesisBox } from '../ui/SynthesisBox';

const AGENT_FA: Record<string, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'پرتفوی',
};

export default function MasterPage() {
  const params = useParams();
  const stored = useSymbolStore((s) => s.symbol);
  const symbol = params.symbol ?? stored;

  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const inputs = useMemo(() => (symbol ? getActiveSignals(symbol) : {}), [symbol, entry]);
  const verdict = useMemo(() => (symbol ? aggregateSignals(symbol, inputs) : null), [symbol, inputs]);
  const gates = useMemo(() => runGatingPipeline(inputs), [inputs]);
  const weights = useMemo(() => effectiveWeights(inputs), [inputs]);

  const planFeed = useFtsPlan(symbol);
  const plan = useMemo(() => {
    const gateFails = gates.filter((g) => g.status === 'fail').length;
    const gateWaits = gates.filter((g) => g.status === 'wait').length;
    return buildTradePlan({
      fib: planFeed.data?.fts?.fib ?? null,
      jet: planFeed.data?.fts?.jet ?? null,
      exit: planFeed.data?.fts?.exit_engine ?? null,
      risk: riskLevel({ hasConflict: verdict?.hasConflict ?? false, gateFails, gateWaits }),
    });
  }, [planFeed.data, gates, verdict]);

  const synthesis = useMemo(
    () => (symbol && verdict ? synthesizeVerdict(symbol, inputs, verdict, gates) : ''),
    [symbol, verdict, inputs, gates],
  );

  if (!symbol) {
    return (
      <div className="w-full max-w-none">
        <EmptyState title="نمادی انتخاب نشده" hint="از تابلو یک نماد انتخاب کن تا برآیند چهار ایجنت دیده شود" />
      </div>
    );
  }
  if (!verdict) return <EmptyState title="در حال محاسبه..." />;

  const empty = verdict.usedSignalIds.length === 0 && verdict.discardedSignalIds.length === 0;
  const activeCount = verdict.usedSignalIds.length;

  return (
    <div className="flex w-full max-w-none flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-black text-text-primary">برآیند مستر برای {symbol}</h2>
        <div className="flex items-center gap-2">
          {/* اقدام سریع سبد: افزودن/ویرایش/حذف تصمیم این نماد */}
          <SymbolBasketAction symbol={symbol} />
          <span className="text-2xs uppercase tracking-widest text-text-muted">
            {activeCount > 0 ? `${toFaDigits(activeCount)} سیگنال فعال در رای گیری` : 'بدون سیگنال فعال'}
          </span>
        </div>
      </div>

      {empty ? (
        <EmptyState
          title="هنوز سیگنالی در باس نیست"
          hint="تب های تابلو و بنیادی و تکنیکال و پرتفوی را باز کن تا هر ایجنت سیگنالش را منتشر کند"
        />
      ) : (
        <>
          <ConflictBanner verdict={verdict} />
          <MasterVerdictCard verdict={verdict} inputs={inputs} />
          <TradePlanCard symbol={symbol} action={verdict.finalAction} plan={plan} />
          <GatePipeline gates={gates} />
          <SynthesisBox text={synthesis} />
        </>
      )}
      <AgentMatrix symbol={symbol} inputs={inputs} verdict={verdict} />

      {/* گیج تجمیعی: تعداد دقیق آرا، وزن‌های واقعی، علت نهایی اجماع */}
      <div className="glass-panel p-4">
        <h3 className="mb-2 text-sm font-black text-text-primary">آمار رای‌گیری</h3>
        <div className="flex flex-wrap gap-2">
          {(['fundamental', 'technical', 'tape', 'portfolio'] as const).map((a) => {
            const c = verdict.contributions.find((x) => x.agentId === a);
            const active = c != null && c.signalCount > 0;
            const w = weights[a];
            return (
              <span
                key={a}
                className={`rounded-full border px-3 py-1 text-2xs font-bold ${
                  active ? 'border-neon-cyan/40 bg-neon-cyan/10 text-neon-cyan' : 'border-border-c bg-bg-card text-text-muted'
                }`}
                title={active ? `وزن خام ${toFaDigits(AGENT_WEIGHTS[a])} از ${toFaDigits(AGENT_WEIGHTS[a])}` : 'رأی فعال ندارد'}
              >
                {AGENT_FA[a]}: {active ? <><span className="num">{toFaDigits(Math.round(w * 1000) / 10)}٪</span> موثر</> : 'غیرفعال'}
              </span>
            );
          })}
        </div>
        <p className="mt-2 text-2xs leading-5 text-text-muted">
          علت نهایی: {empty ? 'هیچ رأی فعالی موجود نیست.' : activeCount < 4 ? `فقط ${toFaDigits(activeCount)} رأی فعال — وزن‌ها بین آرای فعال بازتوزیع شده‌اند.` : 'هر چهار ایجنت رای داده‌اند؛ وزن‌ها کامل اعمال شد.'}
          {verdict.hasConflict ? ' تضاد افق زمانی باعث تنزیل اطمینان شد.' : ''}
          {gates.some((g) => g.status === 'fail') ? ' رد گیت بنیادی/تکنیکال حکم نهایی را محدود کرد.' : ''}
        </p>
      </div>
    </div>
  );
}
