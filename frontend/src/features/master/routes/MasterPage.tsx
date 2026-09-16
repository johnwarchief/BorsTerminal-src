// features/master/routes/MasterPage.tsx -- داشبورد ایجنت ارشد (بازطراحی M-03)
// v3: لایوت full-bleed (گیج + خلاصهٔ تحلیلی مدیریتی آفلاین) + استپر چهار گیتی سخت‌گیرانه
// + ماشین وتو (بدون میانگین خطی) + ماشین‌حساب برنامهٔ معاملاتی/DCA + خروج ۵۰٪ + اکشن‌های سبد/واچ‌لیست.
import { useMemo } from 'react';
import { useParams } from 'react-router';
import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { AGENT_WEIGHTS } from '@contracts/signal';
import { usePortfolio, useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { SECTOR_BANDS, matchSectorBand, normalizeSector } from '@features/portfolio/model/sectorAllocation';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import {
  aggregateSignals,
  runGatingPipeline,
  synthesizeVerdict,
} from '../lib/masterMath';
import { buildTradePlan, riskLevel } from '../lib/tradePlanMath';
import { buildTradeBlueprint } from '../lib/dcaCalc';
import { DEFAULT_ASSUMED_CAPITAL, fa0 } from '../lib/fmtNum';
import {
  DEFAULT_INDUSTRY_CAP_PCT,
  definiteDecision,
  hasDirectEntrySetup,
  hourglassSwitch,
  isSuperFundamental,
  runStrictGates,
  weeklyTrendFromSignal,
  warRegimeCap,
} from '../lib/strictGates';
import { buildManagementSummary, halfExitPlan } from '../lib/managementSummary';
import { useCapitalStore } from '../stores/capitalStore';
import { useFtsPlan } from '../api/useFtsPlan';
import { MasterVerdictCard } from '../ui/MasterVerdictCard';
import { AgentMatrix } from '../ui/AgentMatrix';
import { ConflictBanner } from '../ui/ConflictBanner';
import { TradePlanCard } from '../ui/TradePlanCard';
import { TradeBlueprint } from '../ui/TradeBlueprint';
import { GatePipeline } from '../ui/GatePipeline';
import { SynthesisBox } from '../ui/SynthesisBox';
import { DecisionBadge } from '../ui/DecisionBadge';
import { ManagementSummary } from '../ui/ManagementSummary';

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
  const gates3 = useMemo(() => runGatingPipeline(inputs), [inputs]);

  const planFeed = useFtsPlan(symbol);
  const plan = useMemo(() => {
    const gateFails = gates3.filter((g) => g.status === 'fail').length;
    const gateWaits = gates3.filter((g) => g.status === 'wait').length;
    return buildTradePlan({
      fib: planFeed.data?.fts?.fib ?? null,
      jet: planFeed.data?.fts?.jet ?? null,
      exit: planFeed.data?.fts?.exit_engine ?? null,
      risk: riskLevel({ hasConflict: verdict?.hasConflict ?? false, gateFails, gateWaits }),
    });
  }, [planFeed.data, gates3, verdict]);

  const synthesis = useMemo(
    () => (symbol && verdict ? synthesizeVerdict(symbol, inputs, verdict, gates3) : ''),
    [symbol, verdict, inputs, gates3],
  );

  // ─── دادهٔ سبد/صنعت و رژیم ریسک ───────────────────────────────────
  const portfolio = usePortfolio();
  const closes = useMarketCloses();
  const warRegime = useCapitalStore((s) => s.warRegime);
  const totalToman = useCapitalStore((s) => s.totalToman);
  const setWarRegime = useCapitalStore((s) => s.setWarRegime);

  const regime = useMemo(() => {
    const decisions = portfolio.data?.decisions ?? [];
    const mine = decisions.find((d) => d.symbol === symbol) ?? null;
    const status = (mine?.status ?? '').toLowerCase();
    const inBasket = mine ? status === 'accept' : null;
    const sector = mine?.sector ?? null;
    const band = SECTOR_BANDS.find((b) => b.id === matchSectorBand(sector)) ?? null;
    const industryCapPct = band?.max ?? DEFAULT_INDUSTRY_CAP_PCT;
    const industryUsedPct =
      sector != null
        ? Math.round(
            decisions
              .filter(
                (d) =>
                  (d.status ?? '').toLowerCase() === 'accept' &&
                  d.symbol !== symbol &&
                  normalizeSector(d.sector ?? '') === normalizeSector(sector),
              )
              .reduce((s, d) => s + (typeof d.weight_eff_pct === 'number' ? d.weight_eff_pct : 0), 0) * 10,
          ) / 10
        : null;
    const symbolWeightPct = typeof mine?.weight_eff_pct === 'number' ? mine.weight_eff_pct : null;
    return { inBasket, industryCapPct, industryUsedPct, symbolWeightPct, bandLabel: band?.label ?? null };
  }, [portfolio.data, symbol]);

  const weekly = useMemo(() => weeklyTrendFromSignal(inputs.technical), [inputs.technical]);

  const strict = useMemo(
    () =>
      runStrictGates(
        inputs,
        {
          inBasket: regime.inBasket,
          industryUsedPct: regime.industryUsedPct,
          industryCapPct: regime.industryCapPct,
          warRegime,
          symbolWeightPct: regime.symbolWeightPct,
        },
        weekly,
      ),
    [inputs, regime, weekly, warRegime],
  );

  const decision = useMemo(() => definiteDecision(strict), [strict]);
  /** وتوی سخت‌گیرانه: نمرهٔ تجمیعی نباید اعتبار پیدا کند */
  const gateVetoActive = decision.action === 'veto_gate1' || decision.action === 'veto_gate2';
  const superFundamental = useMemo(() => isSuperFundamental(inputs.fundamental), [inputs.fundamental]);
  const warCap = warRegimeCap(warRegime);

  const currentPrice = (symbol ? closes.data?.get(symbol) : null) ?? null;
  const resistance = planFeed.data?.fts?.jet?.resistance ?? null;

  const blueprint = useMemo(() => {
    const userCapital = totalToman > 0 ? totalToman : null;
    return buildTradeBlueprint({
      // سرمایهٔ کاربر اگر ثبت شده باشد، وگرنه سرمایهٔ فرضی پیش‌فرض (قابل ویرایش آنی در همان اینپوت)
      capitalToman: userCapital ?? DEFAULT_ASSUMED_CAPITAL,
      assumedCapital: userCapital == null,
      baseStepWeightPct: plan.weight.pct,
      industryCapPct: regime.industryCapPct,
      industryUsedPct: regime.industryUsedPct,
      step1: plan.step1,
      step2: plan.step2,
      breakout: plan.breakout,
      priceActionStop: plan.stop.price,
      resistance,
      currentPrice,
      warCapPct: warCap?.max ?? null,
    });
  }, [totalToman, plan, regime, resistance, currentPrice, warCap]);

  const hourglass = useMemo(
    () =>
      hourglassSwitch({
        superFundamental,
        weekly,
        fundScore: typeof inputs.fundamental?.score === 'number' ? inputs.fundamental.score : null,
      }),
    [superFundamental, weekly, inputs.fundamental],
  );

  const halfExit = useMemo(
    () =>
      halfExitPlan({
        resistance,
        setupActive: hasDirectEntrySetup(inputs.technical),
        fundamentalOk: strict.gates.find((g) => g.id === 'fundamental')?.state === 'passed',
        currentPrice,
      }),
    [resistance, inputs.technical, strict.gates, currentPrice],
  );

  const summaryLines = useMemo(
    () =>
      symbol && verdict
        ? buildManagementSummary({
            symbol,
            verdict,
            input: inputs,
            strict,
            decision,
            warRegime,
            superFundamental,
            industryCapPct: regime.industryCapPct,
          })
        : [],
    [symbol, verdict, inputs, strict, decision, warRegime, superFundamental, regime.industryCapPct],
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
    <div className="relative flex w-full max-w-none flex-col gap-4 overflow-clip">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-black text-text-primary">برآیند مستر برای {symbol}</h2>
        <div className="flex flex-wrap items-center gap-2">
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

          {/* Full-bleed: گیج + حکم قطعی در یک ستون، خلاصهٔ تحلیلی مدیریتی فضای خالی کنار گیج */}
          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <div className="flex flex-col gap-3">
              <MasterVerdictCard verdict={verdict} inputs={inputs} />
              {gateVetoActive ? (
                <div role="alert" className="rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-2xs leading-5 text-accent-red">
                  حکم قطعی مستر: نمرهٔ تجمیعی و بازتوزیع وزن‌ها در این وضعیت <b>معتبر نیست</b> — ورود تا رفع گیت متوقف است.
                </div>
              ) : null}
              <div className="glass-panel relative overflow-hidden p-4">
                <DecisionBadge decision={decision} />
              </div>
            </div>
            <ManagementSummary lines={summaryLines} />
          </div>

          <TradePlanCard symbol={symbol} action={verdict.finalAction} plan={plan} />

          <TradeBlueprint
            symbol={symbol}
            plan={blueprint}
            hourglass={hourglass}
            halfExit={halfExit}
            superFundamental={superFundamental}
            warRegime={warRegime}
            assumedCapital={totalToman <= 0}
            onToggleWarRegime={setWarRegime}
          />

          <GatePipeline gates={strict.gates} />
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
            return (
              <span
                key={a}
                className={`rounded-full border px-3 py-1 text-2xs font-bold ${
                  active ? 'border-neon-cyan/40 bg-neon-cyan/10 text-neon-cyan' : 'border-border-c bg-bg-card text-text-muted'
                }`}
                title={active ? `وزن خام مصوب ${fa0(AGENT_WEIGHTS[a])}` : 'رأی فعال ندارد'}
              >
                {AGENT_FA[a]}: {active ? <><span className="num">وزن {fa0(AGENT_WEIGHTS[a])}</span> فعال</> : 'غیرفعال'}
              </span>
            );
          })}
        </div>
        <p className="mt-2 text-2xs leading-5 text-text-muted">
          علت نهایی: {empty ? 'هیچ رأی فعالی موجود نیست.' : activeCount < 4 ? `فقط ${fa0(activeCount)} رأی فعال — وزن‌ها بازتوزیع نمی‌شوند؛ رأی‌های غایب وزن صفر دارند.` : 'هر چهار ایجنت رای داده‌اند؛ وزن‌های مصوب کامل اعمال شد.'}
          {verdict.hasConflict ? ' تضاد افق زمانی باعث تنزیل اطمینان شد.' : ''}
          {gates3.some((g) => g.status === 'fail') ? ' رد گیت بنیادی/تکنیکال حکم نهایی را محدود کرد.' : ''}
        </p>
      </div>
    </div>
  );
}
