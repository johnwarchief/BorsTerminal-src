// features/master/routes/MasterPage.tsx -- داشبورد ایجنت ارشد (بازطراحی M-03)
// v3: لایوت full-bleed (گیج + خلاصهٔ تحلیلی مدیریتی آفلاین) + استپر چهار گیتی سخت‌گیرانه
// + ماشین وتو (بدون میانگین خطی) + ماشین‌حساب برنامهٔ معاملاتی/DCA + خروج ۵۰٪ + اکشن‌های سبد/واچ‌لیست.
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { AGENT_WEIGHTS } from '@contracts/signal';
import { ftsScoreOf } from '@contracts/fundamental';
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
import { evaluateFtsPipeline, recommendHorizon } from '../lib/ftsPipelineEvaluator';
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
import { ExplainableAuditBox } from '../ui/ExplainableAuditBox';
import { StrategyHorizonSelector } from '../ui/StrategyHorizonSelector';
import { StrategyTreeDrawer } from '../ui/StrategyTreeDrawer';
import { FtsFunnelStages } from '../ui/FtsFunnelStages';
import { EliteFunnelHub } from '../ui/EliteFunnelHub';
import { FtsAnalystModal } from '@widgets/FtsAnalystModal';

const AGENT_FA: Record<string, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'پرتفوی',
};

export default function MasterPage() {
  const params = useParams();
  const navigate = useNavigate();
  const stored = useSymbolStore((s) => s.symbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const symbol = params.symbol ?? stored;

  const horizon = useStrategyStore((s) => s.horizon);
  const setHorizon = useStrategyStore((s) => s.setHorizon);
  const [analystModalOpen, setAnalystModalOpen] = useState(false);
  const [treeModalOpen, setTreeModalOpen] = useState(false);

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
  const fundScore = ftsScoreOf(inputs.fundamental);
  const superFundamental = useMemo(() => isSuperFundamental(inputs.fundamental), [inputs.fundamental]);
  const hasSetup = useMemo(() => hasDirectEntrySetup(inputs.technical), [inputs.technical]);
  const recommendedHorizon = useMemo(
    () => recommendHorizon(fundScore, superFundamental, hasSetup),
    [fundScore, superFundamental, hasSetup],
  );
  const warCap = warRegimeCap(warRegime);

  const currentPrice = (symbol ? closes.data?.get(symbol) : null) ?? null;
  const resistance = planFeed.data?.fts?.jet?.resistance ?? null;

  const blueprint = useMemo(() => {
    const userCapital = totalToman > 0 ? totalToman : null;
    const effectiveStop =
      horizon === 'swing' && currentPrice != null
        ? Math.round(currentPrice * 0.95)
        : plan.stop.price;
    return buildTradeBlueprint({
      // سرمایهٔ کاربر اگر ثبت شده باشد، وگرنه سرمایهٔ فرضی پیش‌فرض (قابل ویرایش آنی در همان اینپوت)
      capitalToman: userCapital ?? DEFAULT_ASSUMED_CAPITAL,
      assumedCapital: userCapital == null,
      baseStepWeightPct: horizon === 'hourglass' ? Math.min(plan.weight.pct * 1.5, 10) : plan.weight.pct,
      industryCapPct: regime.industryCapPct,
      industryUsedPct: regime.industryUsedPct,
      step1: plan.step1,
      step2: plan.step2,
      breakout: plan.breakout,
      priceActionStop: effectiveStop,
      resistance,
      currentPrice,
      warCapPct: warCap?.max ?? null,
    });
  }, [totalToman, plan, regime, resistance, currentPrice, warCap, horizon]);

  const hourglass = useMemo(
    () =>
      hourglassSwitch({
        superFundamental,
        weekly,
        fundScore,
      }),
    [superFundamental, weekly, fundScore],
  );

  const halfExit = useMemo(
    () =>
      horizon === 'swing'
        ? {
            active: true,
            text: 'استراتژی نوسانی: خروج کامل در اولین سقف بدون نگهداری میان‌مدت.',
            resistance,
          }
        : horizon === 'hourglass'
          ? {
              active: false,
              text: 'استراتژی ساعت شنی: نگهداری بلندمدت؛ بدون خروج ۵۰٪ در مقاومت‌های نوسانی.',
              resistance: null,
            }
          : halfExitPlan({
              resistance,
              setupActive: hasDirectEntrySetup(inputs.technical),
              fundamentalOk: strict.gates.find((g) => g.id === 'fundamental')?.state === 'passed',
              currentPrice,
            }),
    [resistance, inputs.technical, strict.gates, currentPrice, horizon],
  );

  const evaluation = useMemo(
    () =>
      evaluateFtsPipeline({
        symbol: symbol || '',
        horizon,
        inputs,
        strict,
        decision,
        currentPrice,
        resistancePrice: resistance,
        supportPrice: plan.stop.price,
        fundScore,
      }),
    [symbol, horizon, inputs, strict, decision, currentPrice, resistance, plan.stop.price, fundScore],
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
            currentPrice,
            resistancePrice: resistance,
          })
        : [],
    [symbol, verdict, inputs, strict, decision, warRegime, superFundamental, regime.industryCapPct, currentPrice, resistance],
  );

  if (!symbol) {
    return (
      <div className="flex w-full max-w-none flex-col gap-4">
        {/* پیش‌تر این تب بی‌نماد تنها یک پیامِ «نمادی انتخاب نشده» بود و قیفِ
            غربالگری درِ تبِ «درخت استراتژی» نشسته بود. جایِ درستِ قیف همین‌جاست:
            همان‌جا که کاربر هنوز چیزی انتخاب نکرده و می‌خواهد بداند از کجا شروع
            کند. کلیکِ هر سطرِ قیف نماد را برمی‌دارد و همین صفحه داوری را باز می‌کند. */}
        <FtsFunnelStages preset={horizon} />
        <EliteFunnelHub />
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
          {/* راهِ بازگشت به قیف: با پاک‌شدنِ نماد، همین تب دوباره غربالگری را
              نشان می‌دهد (قیف فقط در حالتِ بی‌نماد زنده است تا رایگانِ CPU باشد). */}
          <button
            type="button"
            data-testid="master-open-funnel"
            onClick={() => {
              clearSymbol();
              navigate('/master');
            }}
            className="rounded-lg border border-border-c bg-bg-card px-2 py-1 text-2xs font-bold text-text-secondary hover:border-accent-blue/60 hover:text-accent-blue"
          >
            قیفِ غربالگری
          </button>
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
              <MasterVerdictCard verdict={verdict} inputs={inputs} decision={decision} />
              {gateVetoActive ? (
                <div role="alert" className="rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-2xs leading-5 text-accent-red">
                  حکم قطعی مستر: نمرهٔ تجمیعی و بازتوزیع وزن‌ها در این وضعیت <b>معتبر نیست</b> — ورود تا رفع موانع فیلترها متوقف است.
                </div>
              ) : null}
              <div className="glass-panel relative overflow-hidden p-4">
                <DecisionBadge decision={decision} />
              </div>
            </div>
            <ManagementSummary lines={summaryLines} />
          </div>

          {/* باکس ممیزی شروط و دلایل توقف (Explainable Decision Audit) */}
          <ExplainableAuditBox
            symbol={symbol}
            isVeto={gateVetoActive}
            decision={decision}
            strict={strict}
            currentPrice={currentPrice}
            resistancePrice={resistance}
            supportPrice={plan.stop.price}
            fundScore={fundScore}
          />

          <StrategyHorizonSelector
            horizon={horizon}
            recommendedHorizon={recommendedHorizon}
            onSelectHorizon={setHorizon}
            onOpenAnalystModal={() => setAnalystModalOpen(true)}
            onOpenTreeModal={() => setTreeModalOpen(true)}
          />

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
            horizon={horizon}
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
          {gates3.some((g) => g.status === 'fail') ? ' رد فیلتر بنیادی/تکنیکال حکم نهایی را محدود کرد.' : ''}
        </p>
      </div>

      <FtsAnalystModal
        open={analystModalOpen}
        onClose={() => setAnalystModalOpen(false)}
        evaluation={evaluation}
        onHorizonChange={setHorizon}
      />

      <StrategyTreeDrawer
        open={treeModalOpen}
        onClose={() => setTreeModalOpen(false)}
      />
    </div>
  );
}
